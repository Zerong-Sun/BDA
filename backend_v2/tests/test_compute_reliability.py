from __future__ import annotations

import base64
import io
import shlex
import subprocess
import uuid
from types import SimpleNamespace

import docker
import pytest
from backend_v2.app.compute import adapters
from backend_v2.app.compute.adapters import AdapterStatus, DockerAdapter, LSFAdapter, RuntimeJob
from backend_v2.app.compute.ssh_transport import KeySSHTransport, PasswordSSHTransport, SSHResult


class FakeStorage:
    manifest: dict = {}
    issued_ttls: list[int | None] = []
    existing: set[str] = set()

    def download_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        type(self).issued_ttls.append(ttl_seconds)
        return f"https://get/{key}"

    def upload_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        type(self).issued_ttls.append(ttl_seconds)
        return f"https://put/{key}"

    def read_json(self, key: str) -> dict:
        return self.manifest

    def exists(self, key: str) -> bool:
        return key in self.existing


@pytest.fixture
def runtime() -> RuntimeJob:
    job_id = uuid.uuid4()
    return RuntimeJob(
        id=job_id,
        attempt_number=2,
        model_plugin="model:1",
        runtime_spec={
            "image": "image:1",
            "command": "run --safe",
            "queue": "gpu",
            "input_manifest_key": f"jobs/{job_id}/attempt-2/input-manifest.json",
            "output_manifest_key": f"jobs/{job_id}/attempt-2/output-manifest.json",
        },
    )


def test_runtime_name_environment_demo_and_factory(monkeypatch, runtime) -> None:
    monkeypatch.setattr(adapters, "ObjectStorage", FakeStorage)
    assert runtime.deterministic_name == f"bda-{runtime.id.hex}-a2"
    environment = adapters._manifest_environment(runtime)
    assert environment["BDA_JOB_ID"] == str(runtime.id)
    assert environment["BDA_INPUT_MANIFEST_URL"].startswith("https://get/")
    demo = adapters.DemoAdapter()
    assert demo.ensure_submitted(runtime).startswith("demo-bda-")
    assert demo.status(runtime, "x") == AdapterStatus("succeeded")
    assert demo.cancel("x") is True
    monkeypatch.setattr(FakeStorage, "manifest", {"schema_version": "1", "outputs": []})
    assert demo.collect(runtime, "x") == []
    assert isinstance(adapters.adapter_for("demo"), adapters.DemoAdapter)
    with pytest.raises(RuntimeError, match="unsupported_compute_backend"):
        adapters.adapter_for("bad")


def test_output_manifest_validation(monkeypatch, runtime) -> None:
    monkeypatch.setattr(adapters, "ObjectStorage", FakeStorage)
    key = f"jobs/{runtime.id}/attempt-2/outputs/result.pdb"
    FakeStorage.manifest = {
        "schema_version": "1",
        "outputs": [{"object_key": key, "size_bytes": 4, "checksum_sha256": "a" * 64}],
    }
    result = adapters._collect_manifest(runtime)
    assert result[0]["filename"] == "result.pdb"
    assert result[0]["artifact_type"] == "compute_output"

    invalid = [
        {},
        {"schema_version": "1", "outputs": ["bad"]},
        {"schema_version": "1", "outputs": [{"object_key": "../x", "size_bytes": 1, "checksum_sha256": "a" * 64}]},
        {"schema_version": "1", "outputs": [{"object_key": key, "size_bytes": 1, "checksum_sha256": "x"}]},
        {"schema_version": "1", "outputs": [{"object_key": key, "size_bytes": -1, "checksum_sha256": "a" * 64}]},
    ]
    for manifest in invalid:
        FakeStorage.manifest = manifest
        with pytest.raises(ValueError):
            adapters._collect_manifest(runtime)


class FakeContainer:
    def __init__(self, status: str = "running", exit_code: int = 0) -> None:
        self.id = "container-id"
        self.status = status
        self.attrs = {"State": {"ExitCode": exit_code, "Error": "boom"}}
        self.stopped = False

    def reload(self) -> None:
        pass

    def stop(self, timeout: int) -> None:
        self.stopped = timeout == 10


def test_docker_adapter_idempotency_status_and_cancel(monkeypatch, runtime) -> None:
    monkeypatch.setattr(adapters, "ObjectStorage", FakeStorage)
    existing = FakeContainer()
    containers = SimpleNamespace(get=lambda _key: existing)
    adapter = DockerAdapter.__new__(DockerAdapter)
    adapter.client = SimpleNamespace(containers=containers)
    assert adapter.ensure_submitted(runtime) == "container-id"
    assert adapter.status(runtime, "container-id").status == "running"
    assert adapter.cancel("container-id") is True and existing.stopped

    for state, code, expected in [
        ("created", 0, "queued"),
        ("restarting", 0, "queued"),
        ("exited", 0, "succeeded"),
        ("exited", 1, "failed"),
        ("dead", 1, "failed"),
    ]:
        container = FakeContainer(state, code)
        adapter.client = SimpleNamespace(containers=SimpleNamespace(get=lambda _key, c=container: c))
        assert adapter.status(runtime, "id").status == expected

    def missing(_key: str):
        raise docker.errors.NotFound("missing")

    created = FakeContainer()
    adapter.client = SimpleNamespace(
        containers=SimpleNamespace(get=missing, run=lambda **kwargs: created),
    )
    assert adapter.ensure_submitted(runtime) == created.id


def test_lsf_adapter_submit_status_cancel_and_ssh(monkeypatch, runtime) -> None:
    monkeypatch.setattr(adapters, "ObjectStorage", FakeStorage)
    adapter = LSFAdapter.__new__(LSFAdapter)
    adapter.host, adapter.root, adapter.timeout = "lsf", "/work", 5
    adapter.ssh_key, adapter.default_queue, adapter.upload_wrapper = "/key", "normal", "/upload"
    adapter.transport = KeySSHTransport("lsf", key_path="/key", connect_timeout=5)
    adapter.staging_mode = "presigned"
    calls: list[tuple[str, str | None]] = []

    def existing(command: str, *, input_text=None, check=True):
        return subprocess.CompletedProcess([], 0, stdout="123\n", stderr="")

    adapter._ssh = existing
    assert adapter.ensure_submitted(runtime) == "123"

    responses = iter(["", "", "", "Job <456> is submitted"])
    adapter._ssh = lambda command, **kwargs: (
        calls.append((command, kwargs.get("input_text")))
        or subprocess.CompletedProcess([], 0, stdout=next(responses), stderr="")
    )
    assert adapter.ensure_submitted(runtime) == "456"
    assert any("#BSUB -q gpu" in (body or "") for _, body in calls)

    for raw, expected in [
        ("PEND", "queued"),
        ("RUN", "running"),
        ("DONE", "succeeded"),
        ("EXIT", "failed"),
        ("", "queued"),
        ("ODD", "failed"),
    ]:
        adapter._ssh = lambda *args, value=raw, **kwargs: subprocess.CompletedProcess([], 0, stdout=value, stderr="")
        assert adapter.status(runtime, "1").status == expected
    adapter._ssh = lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout="", stderr="")
    assert adapter.cancel("1") is True

    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "ok", ""))
    assert LSFAdapter._ssh(adapter, "true", input_text="x").returncode == 0
    assert LSFAdapter._ssh(adapter, "true").returncode == 0


def test_lsf_unrecognized_submission(monkeypatch, runtime) -> None:
    monkeypatch.setattr(adapters, "ObjectStorage", FakeStorage)
    adapter = LSFAdapter.__new__(LSFAdapter)
    adapter.root, adapter.default_queue, adapter.upload_wrapper = "/work", "normal", "/upload"
    adapter.staging_mode = "presigned"
    responses = iter(["", "", "", "not a job"])
    adapter._ssh = lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout=next(responses), stderr="")
    with pytest.raises(RuntimeError, match="lsf_submit_unrecognized"):
        adapter.ensure_submitted(runtime)


class _ForgetfulLSFTransport:
    """A cluster whose ``bjobs`` has already discarded the job.

    ``present`` is the set of remote paths that still exist, which is what has to decide
    the outcome once the scheduler has stopped answering. ``on_stderr`` selects where the
    not-found message lands: stdout under the PTY-based password transport, stderr under
    the key transport.
    """

    def __init__(self, present: set[str], *, on_stderr: bool = False) -> None:
        self.present = present
        self.on_stderr = on_stderr
        self.commands: list[str] = []

    def run(self, command: str, *, check: bool = True, timeout: int = 60) -> SSHResult:
        self.commands.append(command)
        if command.startswith("bjobs"):
            # Verbatim from qm for LSF job 4039777 — a ProteinHunter run that succeeded.
            message = "Job <4039777> is not found\n"
            return SSHResult(255, "" if self.on_stderr else message, message if self.on_stderr else "")
        if command.startswith("test "):
            _, _flag, path = shlex.split(command)
            return SSHResult(0 if path in self.present else 1, "", "")
        raise AssertionError(f"unexpected remote command: {command}")


def _forgetful_adapter(transport: _ForgetfulLSFTransport, *, staging_mode: str = "ssh") -> LSFAdapter:
    adapter = LSFAdapter.__new__(LSFAdapter)
    adapter.host, adapter.root, adapter.timeout = "qm", "/work", 5
    adapter.ssh_key, adapter.default_queue, adapter.upload_wrapper = None, "normal", ""
    adapter.staging_mode = staging_mode
    adapter.transport = transport
    return adapter


def test_lsf_status_reads_the_completion_marker_once_bjobs_forgets_the_job(runtime) -> None:
    """'Job <id> is not found' is not a job state.

    Sites expire finished jobs from ``bjobs`` - on qm within about an hour, well before a
    job is necessarily collected. Parsed as a state, that message failed runs that had
    genuinely succeeded (LSF 4039777, 4040398, 4040425), and poll_job then never ran
    collection, so their outputs stayed on the cluster. ``bhist`` cannot stand in: the
    unbounded form outlives the SSH timeout and the bounded forms find nothing once the
    history files have rotated. The manifest the job itself wrote is what remains.
    """
    remote_dir = f"/work/jobs/{runtime.id.hex}/attempt-2"
    manifest = f"{remote_dir}/output-manifest.json"

    for on_stderr in (False, True):
        transport = _ForgetfulLSFTransport({remote_dir, manifest}, on_stderr=on_stderr)
        live = _forgetful_adapter(transport).status(runtime, "4039777")
        assert live.status == "succeeded", f"on_stderr={on_stderr}"
        assert any(command.startswith("bjobs") for command in transport.commands)


def test_lsf_status_still_fails_a_forgotten_job_that_left_no_manifest(runtime) -> None:
    """The script runs under ``set -Eeuo pipefail`` and writes the manifest last.

    A working directory without one therefore did not finish, and that is a real failure
    rather than an absence of evidence.
    """
    remote_dir = f"/work/jobs/{runtime.id.hex}/attempt-2"
    live = _forgetful_adapter(_ForgetfulLSFTransport({remote_dir})).status(runtime, "4039777")
    assert live.status == "failed"
    assert live.error == "lsf_job_gone_without_manifest:4039777"


def test_lsf_status_is_non_terminal_when_nothing_survives_to_judge(runtime) -> None:
    """With neither manifest nor working directory there is nothing to conclude.

    poll_job only resolves on 'succeeded'/'failed', so a non-terminal answer leaves the
    job polling under its own timeout_at instead of inventing an outcome. An unreachable
    cluster lands here too: every ``test`` fails, so nothing reads as present.
    """
    live = _forgetful_adapter(_ForgetfulLSFTransport(set())).status(runtime, "4039777")
    assert live.status == "unknown"


def test_lsf_status_of_a_forgotten_job_checks_object_storage_under_presigned_staging(monkeypatch, runtime) -> None:
    """Under presigned staging the job uploads its own manifest, so that is the marker."""
    monkeypatch.setattr(adapters, "ObjectStorage", FakeStorage)
    remote_dir = f"/work/jobs/{runtime.id.hex}/attempt-2"
    adapter = _forgetful_adapter(_ForgetfulLSFTransport({remote_dir}), staging_mode="presigned")

    monkeypatch.setattr(FakeStorage, "existing", set())
    assert adapter.status(runtime, "4039777").status == "failed"
    monkeypatch.setattr(FakeStorage, "existing", {runtime.runtime_spec["output_manifest_key"]})
    assert adapter.status(runtime, "4039777").status == "succeeded"


class _FakeChannelFile:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _FakeParamikoClient:
    """Emulates a PTY session: echoes the command, uses CRLF, prepends shell noise."""

    def __init__(self, body: str, code: int = 0) -> None:
        self.body = body
        self.code = code
        self.commands: list[str] = []

    def exec_command(self, command: str, timeout=None, get_pty=False):
        self.commands.append(command)
        token = command.split("__BDA_BEGIN_")[1].split("__")[0]
        noise = "(base) [user@host ~]$ " + command + "\r\n"
        payload = (
            f"{noise}__BDA_BEGIN_{token}__\r\n{self.body}\r\n__BDA_END_{token}_{self.code}__\r\n"
        )
        return None, _FakeChannelFile(payload.encode()), None


def _password_transport(client) -> PasswordSSHTransport:
    transport = PasswordSSHTransport("host", username="u", password="p")
    transport._connect = lambda: client  # type: ignore[method-assign]
    return transport


def test_password_transport_strips_pty_echo_and_shell_noise() -> None:
    """A PTY echoes the command and adds CRLF; bjobs output must survive that."""
    client = _FakeParamikoClient("DONE")
    result = _password_transport(client).run("bjobs -noheader -o stat 123")
    assert result.stdout.strip() == "DONE"
    assert result.returncode == 0
    # CR would survive into status parsing and break the state mapping.
    assert "\r" not in result.stdout
    # The echoed command and the shell prompt must not leak into the payload.
    assert "BDA_BEGIN" not in result.stdout and "base)" not in result.stdout


def test_password_transport_propagates_remote_exit_code() -> None:
    client = _FakeParamikoClient("no such job", code=255)
    transport = _password_transport(client)
    with pytest.raises(subprocess.CalledProcessError):
        transport.run("bjobs 999")
    assert transport.run("bjobs 999", check=False).returncode == 255


def test_password_transport_ships_scripts_base64_not_over_stdin() -> None:
    """A PTY would mangle a heredoc, so script bodies go over base64 instead."""
    client = _FakeParamikoClient("")
    _password_transport(client).put_file("/work/submit.lsf", "#!/bin/bash\n#BSUB -q gpu\n")
    sent = client.commands[0]
    assert "base64 -d > /work/submit.lsf" in sent
    encoded = sent.split("printf %s ")[1].split(" |")[0].strip("'")
    assert base64.b64decode(encoded).decode() == "#!/bin/bash\n#BSUB -q gpu\n"


def test_password_reference_must_be_a_file(tmp_path) -> None:
    """Passwords are never taken from env, which is visible in docker inspect."""
    from backend_v2.app.compute.ssh_transport import read_secret

    secret = tmp_path / "pw"
    secret.write_text("hunter2\n")
    assert read_secret(f"file:{secret}") == "hunter2"
    with pytest.raises(RuntimeError, match="must_be_file"):
        read_secret("env:QM_PASSWORD")


def test_password_transport_isolates_command_in_a_subshell() -> None:
    """A brace group would let a command containing `exit` kill the login shell.

    That loses the closing sentinel and with it the real exit code, so remote failures
    would silently read as a generic error.
    """
    client = _FakeParamikoClient("")
    _password_transport(client).run("bsub < submit.lsf")
    wrapped = client.commands[0]
    assert "( bsub < submit.lsf )" in wrapped
    assert "{ bsub" not in wrapped


class _FakeSFTPFile:
    def __init__(self, sink: dict, path: str, data: bytes = b"") -> None:
        self._sink, self._path = sink, path
        self._buffer = bytearray(data)
        self._offset = 0

    def write(self, chunk: bytes) -> None:
        self._buffer.extend(chunk)

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._buffer) - self._offset
        chunk = bytes(self._buffer[self._offset : self._offset + size])
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self._sink[self._path] = bytes(self._buffer)


class _FakeSFTP:
    def __init__(self, files: dict) -> None:
        self.files = files
        self.closed = False

    def open(self, path: str, mode: str):
        return _FakeSFTPFile(self.files, path, self.files.get(path, b"") if "r" in mode else b"")

    def close(self) -> None:
        self.closed = True


def test_password_transport_streams_uploads_and_downloads() -> None:
    """Whole-object reads are bounded by memory; scientific inputs are not."""
    files: dict[str, bytes] = {}
    transport = PasswordSSHTransport("host", username="u", password="p")
    sftps: list[_FakeSFTP] = []

    def make_sftp():
        sftp = _FakeSFTP(files)
        sftps.append(sftp)
        return sftp

    transport._sftp = make_sftp  # type: ignore[method-assign]

    payload = b"ATOM\n" * 5000
    transport.put_stream("/work/in.pdb", iter([payload[:2000], payload[2000:]]))
    assert files["/work/in.pdb"] == payload

    chunks = list(transport.stream("/work/in.pdb", chunk_size=1024))
    assert b"".join(chunks) == payload
    # Chunked, not one slurp — that is the whole point.
    assert len(chunks) > 1
    # Every session is closed, so a long staging run does not leak SFTP channels.
    assert all(sftp.closed for sftp in sftps)


def test_key_transport_streams_through_the_ssh_process(monkeypatch, tmp_path) -> None:
    """The key transport pipes through ssh rather than buffering the whole object."""
    from backend_v2.app.compute.ssh_transport import KeySSHTransport

    transport = KeySSHTransport("host", key_path=None, connect_timeout=5)
    written: dict[str, bytes] = {}

    class _CapturingPipe(io.BytesIO):
        """Production closes stdin before wait(), so capture on close."""

        def close(self) -> None:
            written["body"] = self.getvalue()
            super().close()

    class _Process:
        def __init__(self, mode: str, payload: bytes = b"") -> None:
            self.stdin = _CapturingPipe() if mode == "w" else None
            self.stdout = io.BytesIO(payload) if mode == "r" else None
            self.returncode = 0

        def wait(self, timeout=None) -> int:
            return self.returncode

    monkeypatch.setattr(
        "subprocess.Popen", lambda argv, **kwargs: _Process("w" if "cat >" in argv[-1] else "r", b"payload")
    )
    transport.put_stream("/work/x", iter([b"ab", b"cd"]))
    assert written["body"] == b"abcd"
    assert b"".join(transport.stream("/work/x", chunk_size=2)) == b"payload"


def test_streaming_surfaces_a_failed_remote_process(monkeypatch) -> None:
    """A silent partial transfer would corrupt an artifact; it must raise instead."""
    from backend_v2.app.compute.ssh_transport import KeySSHTransport

    transport = KeySSHTransport("host", key_path=None, connect_timeout=5)

    class _Failing:
        def __init__(self) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(b"")

        def wait(self, timeout=None) -> int:
            return 3  # a non-zero exit means the transfer did not complete

    monkeypatch.setattr("subprocess.Popen", lambda argv, **kwargs: _Failing())
    with pytest.raises(RuntimeError, match="ssh_put_stream_failed"):
        transport.put_stream("/work/x", iter([b"a"]))
    with pytest.raises(RuntimeError, match="ssh_stream_failed"):
        list(transport.stream("/work/x"))
