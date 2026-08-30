"""The ssh-staged LSF data path.

This is the path a real job's data travels, and until now it was only exercised by the
live-cluster script — which needs a VPN and so never ran in CI.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.compute import adapters
from backend_v2.app.compute.adapters import LSFAdapter, RuntimeJob


class _FakeTransport:
    """Records what would be written to the cluster and serves what it would read back."""

    def __init__(self, remote_files: dict[str, bytes] | None = None) -> None:
        self.files: dict[str, bytes] = dict(remote_files or {})
        self.commands: list[str] = []

    def run(self, command, *, check=True, timeout=60):
        from backend_v2.app.compute.ssh_transport import SSHResult

        self.commands.append(command)
        return SSHResult(0, "", "")

    def put_file(self, remote_path: str, content: str) -> None:
        self.files[remote_path] = content.encode()

    def put_bytes(self, remote_path: str, data: bytes) -> None:
        self.files[remote_path] = data

    def put_stream(self, remote_path: str, body) -> None:
        self.files[remote_path] = b"".join(body)

    def get_bytes(self, remote_path: str) -> bytes:
        return self.files[remote_path]

    def stream(self, remote_path: str, *, chunk_size: int = 1024 * 1024):
        data = self.files[remote_path]
        for offset in range(0, len(data), chunk_size):
            yield data[offset : offset + chunk_size]


class _FakeStorage:
    """Object storage that records writes and streams reads, like the real one."""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})
        self.content_types: dict[str, str] = {}

    def stream(self, object_key: str, *, chunk_size: int = 1024 * 1024):
        data = self.objects[object_key]
        for offset in range(0, len(data), chunk_size):
            yield data[offset : offset + chunk_size]

    def put_stream(self, object_key: str, body, length: int, content_type: str) -> None:
        payload = body.read()
        assert len(payload) == length, "declared length must match the streamed bytes"
        self.objects[object_key] = payload
        self.content_types[object_key] = content_type

    def read_bytes(self, object_key: str, *, max_bytes=None) -> bytes:
        return self.objects[object_key]


def _adapter(transport: _FakeTransport) -> LSFAdapter:
    adapter = LSFAdapter.__new__(LSFAdapter)
    adapter.host, adapter.root, adapter.timeout = "qm", "/work/bda", 5
    adapter.ssh_key, adapter.default_queue, adapter.upload_wrapper = None, "normal", "/upload"
    adapter.staging_mode = "ssh"
    adapter.transport = transport
    return adapter


def _job(job_id: uuid.UUID, inputs: list[dict], output_ports: list[dict] | None = None) -> RuntimeJob:
    return RuntimeJob(
        id=job_id,
        attempt_number=1,
        model_plugin="ProteinMPNN",
        runtime_spec={
            "command": "run.sh",
            "queue": "v3-64",
            "input_manifest": {"schema_version": "1", "parameters": {}, "inputs": inputs},
            "plugin_snapshot": {"output_ports": output_ports or []},
        },
    )


def test_inputs_are_staged_per_port_with_a_local_manifest(monkeypatch) -> None:
    """The job reads local paths, so the staged manifest must replace object keys."""
    storage = _FakeStorage({"projects/p/sha256/abc": b"ATOM      1  N   MET A   1\n"})
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    transport = _FakeTransport()
    adapter = _adapter(transport)
    job_id = uuid.uuid4()
    job = _job(
        job_id,
        [{"port": "backbone", "filename": "target.pdb", "object_key": "projects/p/sha256/abc"}],
    )

    adapter._stage_inputs(job, adapter.remote_dir(job))

    staged_path = f"{adapter.remote_dir(job)}/inputs/backbone/target.pdb"
    assert transport.files[staged_path] == storage.objects["projects/p/sha256/abc"]
    manifest = json.loads(transport.files[f"{adapter.remote_dir(job)}/input-manifest.json"])
    assert manifest["staging"] == "ssh"
    assert manifest["inputs"][0]["path"] == staged_path
    assert manifest["inputs"][0]["relative_path"] == "inputs/backbone/target.pdb"


def test_staging_creates_the_port_directory_before_writing() -> None:
    """A per-port subdirectory has to exist before the transfer, not after."""
    storage = _FakeStorage({"k": b"x"})
    transport = _FakeTransport()
    adapter = _adapter(transport)
    job = _job(uuid.uuid4(), [{"port": "backbone", "filename": "t.pdb", "object_key": "k"}])
    import backend_v2.app.compute.adapters as module

    original = module.ObjectStorage
    module.ObjectStorage = lambda: storage
    try:
        adapter._stage_inputs(job, adapter.remote_dir(job))
    finally:
        module.ObjectStorage = original
    assert any("inputs/backbone" in command for command in transport.commands)


def test_staging_skips_entries_without_an_object_key(monkeypatch) -> None:
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    transport = _FakeTransport()
    adapter = _adapter(transport)
    job = _job(uuid.uuid4(), [{"port": "backbone", "filename": "x"}, "not-a-dict"])

    adapter._stage_inputs(job, adapter.remote_dir(job))

    manifest = json.loads(transport.files[f"{adapter.remote_dir(job)}/input-manifest.json"])
    assert manifest["inputs"] == []


def _collect_fixture(payload: bytes, relative: str = "designs/design_0.pdb") -> tuple:
    job_id = uuid.uuid4()
    remote = f"/work/bda/jobs/{job_id.hex}/attempt-1"
    transport = _FakeTransport(
        {
            f"{remote}/output-manifest.json": json.dumps(
                {
                    "schema_version": "1",
                    "outputs": [
                        {
                            "relative_path": relative,
                            "filename": relative.rsplit("/", 1)[-1],
                            "size_bytes": len(payload),
                            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
                        }
                    ],
                }
            ).encode(),
            f"{remote}/outputs/{relative}": payload,
        }
    )
    return job_id, transport


def test_outputs_are_retrieved_verified_and_typed_by_port(monkeypatch) -> None:
    payload = b"ATOM      1  N   MET A   1\n" * 100
    job_id, transport = _collect_fixture(payload)
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    adapter = _adapter(transport)
    job = _job(job_id, [], [{"name": "designs", "kind": "protein_structure", "artifact_type": "backbone_set"}])

    collected = adapter._collect_over_ssh(job)

    assert len(collected) == 1
    entry = collected[0]
    assert entry["port"] == "designs"
    # A file under outputs/<port>/ takes that port's declared artifact_type.
    assert entry["artifact_type"] == "backbone_set"
    assert entry["size_bytes"] == len(payload)
    assert entry["checksum_sha256"] == hashlib.sha256(payload).hexdigest()
    assert entry["object_key"] == f"jobs/{job_id}/attempt-1/outputs/designs/design_0.pdb"
    assert storage.objects[entry["object_key"]] == payload


def test_a_corrupted_transfer_is_rejected(monkeypatch) -> None:
    """Checksums are computed on the node; a mismatch after transfer must fail."""
    job_id, transport = _collect_fixture(b"original")
    remote = f"/work/bda/jobs/{job_id.hex}/attempt-1"
    transport.files[f"{remote}/outputs/designs/design_0.pdb"] = b"tampered"
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: _FakeStorage())
    adapter = _adapter(transport)

    with pytest.raises(ValueError, match="collect_output_checksum_mismatch"):
        adapter._collect_over_ssh(_job(job_id, []))


def test_path_traversal_in_the_manifest_is_rejected(monkeypatch) -> None:
    """The manifest is written on the cluster, so it is not trusted input."""
    job_id = uuid.uuid4()
    remote = f"/work/bda/jobs/{job_id.hex}/attempt-1"
    for relative in ("../../etc/passwd", "/etc/passwd"):
        transport = _FakeTransport(
            {
                f"{remote}/output-manifest.json": json.dumps(
                    {"schema_version": "1", "outputs": [{"relative_path": relative, "checksum_sha256": "a" * 64}]}
                ).encode()
            }
        )
        monkeypatch.setattr(adapters, "ObjectStorage", lambda: _FakeStorage())
        with pytest.raises(ValueError, match="output_manifest_path_invalid"):
            _adapter(transport)._collect_over_ssh(_job(job_id, []))


def test_a_malformed_output_manifest_is_rejected(monkeypatch) -> None:
    job_id = uuid.uuid4()
    remote = f"/work/bda/jobs/{job_id.hex}/attempt-1"
    for manifest in ({"schema_version": "2", "outputs": []}, {"schema_version": "1", "outputs": "nope"}):
        transport = _FakeTransport({f"{remote}/output-manifest.json": json.dumps(manifest).encode()})
        monkeypatch.setattr(adapters, "ObjectStorage", lambda: _FakeStorage())
        with pytest.raises(ValueError, match="output_manifest_schema_invalid"):
            _adapter(transport)._collect_over_ssh(_job(job_id, []))


def test_outputs_outside_a_declared_port_still_collect(monkeypatch) -> None:
    """A plugin that writes flat output must not be dropped on the floor."""
    payload = b"scores\n"
    job_id, transport = _collect_fixture(payload, relative="score.sc")
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: _FakeStorage())
    collected = _adapter(transport)._collect_over_ssh(_job(job_id, []))
    assert collected[0]["port"] is None
    assert collected[0]["artifact_type"] == "compute_output"


def test_large_outputs_do_not_buffer_entirely_in_memory(monkeypatch) -> None:
    """Spooling is what keeps a multi-gigabyte structure set from killing the worker."""
    monkeypatch.setattr(adapters, "SPOOL_TO_DISK_BYTES", 1024)
    payload = b"A" * (64 * 1024)
    job_id, transport = _collect_fixture(payload)
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)

    collected = _adapter(transport)._collect_over_ssh(_job(job_id, []))

    assert collected[0]["size_bytes"] == len(payload)
    assert storage.objects[collected[0]["object_key"]] == payload


def test_outputs_at_the_root_are_typed_by_filename_glob(monkeypatch) -> None:
    """Models write their own layout; the summary CSVs land beside the port directories.

    ProteinHunter writes high_iptm_pdb/ and high_iptm_yaml/ but drops summary_*.csv at the
    root, so directory-based typing alone would register them as untyped compute_output.
    """
    payload = b"run_id,cycle\n1,1\n"
    job_id, transport = _collect_fixture(payload, relative="summary_high_iptm.csv")
    storage = _FakeStorage()
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: storage)
    job = _job(
        job_id,
        [],
        [
            {"name": "high_iptm_pdb", "kind": "protein_structure", "artifact_type": "candidate_complex",
             "filename_glob": "*.pdb"},
            {"name": "summaries", "kind": "tabular", "artifact_type": "score_table",
             "filename_glob": "summary_*.csv"},
        ],
    )

    collected = _adapter(transport)._collect_over_ssh(job)

    assert collected[0]["port"] == "summaries"
    assert collected[0]["artifact_type"] == "score_table"


def test_a_port_directory_still_wins_over_a_glob(monkeypatch) -> None:
    payload = b"ATOM\n"
    job_id, transport = _collect_fixture(payload, relative="high_iptm_pdb/run4.pdb")
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: _FakeStorage())
    job = _job(
        job_id,
        [],
        [
            {"name": "high_iptm_pdb", "kind": "protein_structure", "artifact_type": "candidate_complex",
             "filename_glob": "*.pdb"},
        ],
    )
    collected = _adapter(transport)._collect_over_ssh(job)
    assert collected[0]["port"] == "high_iptm_pdb"
    assert collected[0]["artifact_type"] == "candidate_complex"


def test_a_catch_all_glob_does_not_capture_unrelated_outputs(monkeypatch) -> None:
    """A port declaring "*" must not silently claim every stray file."""
    job_id, transport = _collect_fixture(b"x", relative="stray.log")
    monkeypatch.setattr(adapters, "ObjectStorage", lambda: _FakeStorage())
    job = _job(job_id, [], [{"name": "anything", "kind": "opaque", "artifact_type": "blob", "filename_glob": "*"}])
    collected = _adapter(transport)._collect_over_ssh(job)
    assert collected[0]["port"] is None
    assert collected[0]["artifact_type"] == "compute_output"
