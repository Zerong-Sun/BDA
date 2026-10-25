"""Real descriptor reads reject post-manifest symlink swaps and bound collection."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from backend_v2.app.compute import adapters
from backend_v2.app.compute.checked_reader import checked_reader_command
from backend_v2.app.compute.ssh_transport import KeySSHTransport, PasswordSSHTransport
from backend_v2.app.core.config import Settings
from backend_v2.tests.test_lsf_staging import _adapter, _collect_fixture, _FakeStorage, _job


class _LocalPTY:
    """Use a real local process behind the same Paramiko streaming interface."""
    def exec_command(self, command, *, timeout, get_pty):
        assert get_pty is True
        process = subprocess.Popen(["bash", "-c", command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        class Output:
            channel = SimpleNamespace(close=lambda: process.wait(timeout=10))

            def readline(self, limit):
                return process.stdout.readline(limit).replace(b"\n", b"\r\n")

            def close(self):
                process.stdout.close()

        return process.stdin, Output(), SimpleNamespace(close=lambda: None)


@pytest.fixture(params=["key", "password"])
def checked_transport(request, monkeypatch):
    if request.param == "key":
        transport = KeySSHTransport("fixture", key_path=None, connect_timeout=5)
        # SSH executes the last argv string remotely. Execute that exact string
        # locally for a real filesystem test, without any network or cluster.
        monkeypatch.setattr(transport, "_argv", lambda: [sys.executable, "-c",
            "import subprocess,sys;sys.exit(subprocess.call(sys.argv[-1], shell=True))"])
        return transport
    transport = PasswordSSHTransport("fixture", username="fixture", password="unused")
    monkeypatch.setattr(transport, "_connect", lambda: _LocalPTY())
    return transport


@pytest.mark.parametrize("swap", ["file", "parent", "root"])
def test_checked_transports_reject_symlinks_even_after_manifest_creation(tmp_path, checked_transport, swap):
    root = tmp_path.resolve() / "job"
    outputs = root / "outputs"
    outputs.mkdir(parents=True)
    (outputs / "score.csv").write_bytes(b"safe")
    foreign = tmp_path.resolve() / "foreign"
    foreign.mkdir()
    (foreign / "score.csv").write_bytes(b"private research")
    if swap == "file":
        (outputs / "score.csv").unlink()
        (outputs / "score.csv").symlink_to(foreign / "score.csv")
    elif swap == "parent":
        outputs.rename(root / "old-outputs")
        outputs.symlink_to(foreign, target_is_directory=True)
    else:
        root.rename(root.with_name("old-job"))
        root.symlink_to(foreign, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError)):
        list(checked_transport.stream_checked(str(root), "outputs/score.csv", max_bytes=100))


def test_checked_transports_keep_open_inode_when_path_is_replaced(tmp_path, checked_transport):
    root = tmp_path.resolve()
    payload = b"sequence\r\n\x00\xff" * 100_000
    original = root / "output.bin"
    original.write_bytes(payload)
    private = root / "private.bin"
    private.write_bytes(b"secret")
    stream = checked_transport.stream_checked(str(root), original.name, max_bytes=len(payload))
    first = next(stream)
    original.unlink()
    original.symlink_to(private)
    assert first + b"".join(stream) == payload


@pytest.mark.parametrize("payload", [b"", b"exact bytes\r\n\x00\xff"])
def test_checked_transports_accept_exact_size_and_empty_files(tmp_path, checked_transport, payload):
    root = tmp_path.resolve()
    (root / "output.bin").write_bytes(payload)
    assert b"".join(checked_transport.stream_checked(str(root), "output.bin", max_bytes=len(payload))) == payload


def test_checked_transports_stop_a_file_that_grows_after_open(tmp_path, checked_transport):
    root = tmp_path.resolve()
    path = root / "output.bin"
    payload = b"A" * (2 * 1024 * 1024)
    path.write_bytes(payload)
    stream = checked_transport.stream_checked(str(root), path.name, max_bytes=len(payload))
    assert next(stream)
    with path.open("ab") as handle:
        handle.write(b"over quota")
    with pytest.raises((ValueError, RuntimeError)):
        list(stream)


@pytest.mark.parametrize("kind", ["oversize", "fifo", "hardlink"])
def test_checked_transports_reject_unsafe_files_without_reading_them(tmp_path, checked_transport, kind):
    import os
    root = tmp_path.resolve()
    path = root / "output"
    if kind == "fifo":
        os.mkfifo(path)
    else:
        path.write_bytes(b"too large")
        if kind == "hardlink":
            os.link(path, root / "private-copy")
    with pytest.raises((ValueError, RuntimeError)):
        list(checked_transport.stream_checked(str(root), path.name, max_bytes=1 if kind == "oversize" else 100))


def test_collector_caps_declared_total_and_does_not_upload_short_reads(monkeypatch):
    payload = b"safe output"
    job_id, transport = _collect_fixture(payload)
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    monkeypatch.setattr(adapters, "get_settings", lambda: Settings(compute_max_collection_bytes=1, _env_file=None))
    with pytest.raises(ValueError, match="output_manifest_size_invalid"):
        _adapter(transport)._collect_over_ssh(_job(job_id, []))
    assert not storage.objects
    monkeypatch.setattr(adapters, "get_settings", lambda: Settings(_env_file=None))
    path = f"/work/bda/jobs/{job_id.hex}/attempt-1/outputs/designs/design_0.pdb"
    transport.files[path] = b"short"
    with pytest.raises(ValueError, match="collect_output_size_mismatch"):
        _adapter(transport)._collect_over_ssh(_job(job_id, []))
    assert not storage.objects


def test_collector_caps_manifest_and_file_count(monkeypatch):
    job_id, transport = _collect_fixture(b"safe")
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    remote_manifest = f"/work/bda/jobs/{job_id.hex}/attempt-1/output-manifest.json"
    monkeypatch.setattr(adapters, "MAX_OUTPUT_MANIFEST_BYTES", 1)
    with pytest.raises(ValueError, match="size_exceeded"):
        _adapter(transport)._collect_over_ssh(_job(job_id, []))
    monkeypatch.setattr(adapters, "MAX_OUTPUT_MANIFEST_BYTES", 8 * 1024 * 1024)
    monkeypatch.setattr(adapters, "get_settings", lambda: Settings(compute_max_collection_files=1, _env_file=None))
    manifest = json.loads(transport.files[remote_manifest])
    manifest["outputs"] *= 2
    transport.files[remote_manifest] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match="too_many_files"):
        _adapter(transport)._collect_over_ssh(_job(job_id, []))


def test_collector_rejects_a_real_symlink_replacement_before_upload(tmp_path, monkeypatch, checked_transport):
    import uuid
    root = tmp_path.resolve()
    job = _job(uuid.uuid4(), [])
    output_dir = root / "jobs" / job.id.hex / "attempt-1" / "outputs"
    output_dir.mkdir(parents=True)
    secret = root / "foreign.txt"
    secret.write_bytes(b"secret")
    (output_dir / "leak.txt").symlink_to(secret)
    (output_dir.parent / "output-manifest.json").write_text(json.dumps({"schema_version": "1", "outputs": [{
        "relative_path": "leak.txt", "size_bytes": 6, "checksum_sha256": hashlib.sha256(b"secret").hexdigest()}]}))
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    adapter = _adapter(checked_transport)
    adapter.root = str(root)
    with pytest.raises((ValueError, RuntimeError)):
        adapter._collect_over_ssh(job)
    assert not storage.objects


@pytest.mark.parametrize("relative", ["../private", "/etc/passwd", ".", "a/../../secret"])
def test_checked_reader_rejects_escape_before_launch(relative):
    with pytest.raises(ValueError):
        checked_reader_command("/shared/job", relative, 100)


@pytest.mark.parametrize("sizes", [[True], [-1], [1.0], [11], [6, 5]])
def test_presigned_collector_rejects_invalid_sizes_and_total_over_quota(monkeypatch, sizes):
    import uuid
    job = _job(uuid.uuid4(), [])
    key = f"jobs/{job.id}/attempt-1/outputs/result.bin"
    captured = []

    def read_json(_key, *, max_bytes):
        captured.append(max_bytes)
        return {"schema_version": "1", "outputs": [{"object_key": key, "size_bytes": size, "checksum_sha256": "a" * 64} for size in sizes]}

    monkeypatch.setattr(adapters, "get_settings", lambda: Settings(compute_max_collection_bytes=10, _env_file=None))
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: SimpleNamespace(read_json=read_json))
    with pytest.raises(ValueError, match="output_manifest_size_invalid"):
        adapters._collect_manifest(job)
    assert captured == [adapters.MAX_OUTPUT_MANIFEST_BYTES]


def test_presigned_collector_rejects_too_many_files(monkeypatch):
    import uuid
    job = _job(uuid.uuid4(), [])
    monkeypatch.setattr(adapters, "get_settings", lambda: Settings(compute_max_collection_files=1, _env_file=None))
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: SimpleNamespace(read_json=lambda _, **kwargs: {
        "schema_version": "1", "outputs": [{}, {}]}))
    with pytest.raises(ValueError, match="too_many_files"):
        adapters._collect_manifest(job)


def test_object_store_manifest_read_is_bounded_and_closes_response(monkeypatch):
    from backend_v2.app.artifacts.storage import ObjectStorage

    class Response:
        closed = False
        released = False
        sizes = []

        def read(self, size):
            self.sizes.append(size)
            return b" " * size

        def close(self):
            self.closed = True

        def release_conn(self):
            self.released = True

    response = Response()
    storage = ObjectStorage.__new__(ObjectStorage)
    storage.bucket = "fixture"
    storage.client = SimpleNamespace(get_object=lambda *_: response)
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    monkeypatch.setattr(adapters, "MAX_OUTPUT_MANIFEST_BYTES", 16)
    import uuid
    with pytest.raises(ValueError, match="object_too_large"):
        adapters._collect_manifest(_job(uuid.uuid4(), []))
    assert response.sizes == [17]
    assert response.closed and response.released
