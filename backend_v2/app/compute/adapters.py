from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Protocol

from ..artifacts.storage import MAX_PRESIGN_SECONDS, ObjectStorage
from ..core.config import get_settings
from .scripts import ScriptContext, parameter_environment, render_script
from .ssh_transport import KeySSHTransport, PasswordSSHTransport, SSHTransport, read_secret

# Collected outputs are buffered in memory up to this size and spill to disk beyond it,
# so a large structure set cannot exhaust the worker.
SPOOL_TO_DISK_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class RuntimeJob:
    id: uuid.UUID
    attempt_number: int
    model_plugin: str
    runtime_spec: dict

    @property
    def deterministic_name(self) -> str:
        return f"bda-{self.id.hex}-a{self.attempt_number}"


@dataclass(frozen=True)
class AdapterStatus:
    """A backend's view of one job.

    ``status`` is one of ``queued``, ``running``, ``succeeded``, ``failed`` or
    ``unknown``. Only ``succeeded`` and ``failed`` are terminal; ``unknown`` says the
    backend cannot answer right now, which leaves the job polling under its own deadline
    instead of inventing an outcome for it.
    """

    status: str
    error: str | None = None


class ComputeAdapter(Protocol):
    def ensure_submitted(self, job: RuntimeJob) -> str: ...

    # ``status`` takes the job for the same reason ``collect`` does: a scheduler that has
    # already discarded a finished job can only be judged by what the job left behind,
    # and locating that needs the job's identity, not just the scheduler's id.
    def status(self, job: RuntimeJob, external_id: str) -> AdapterStatus: ...

    def cancel(self, external_id: str) -> bool: ...

    def collect(self, job: RuntimeJob, external_id: str) -> list[dict]: ...


class DemoAdapter:
    def ensure_submitted(self, job: RuntimeJob) -> str:
        return f"demo-{job.deterministic_name}"

    def status(self, job: RuntimeJob, external_id: str) -> AdapterStatus:
        return AdapterStatus("succeeded")

    def cancel(self, external_id: str) -> bool:
        return True

    def collect(self, job: RuntimeJob, external_id: str) -> list[dict]:
        # Demo jobs do not execute a workload, so no process exists to upload an
        # output manifest. Treat the simulated successful run as having no outputs.
        return []


class DockerAdapter:
    def __init__(self) -> None:
        import docker
        from docker.tls import TLSConfig  # type: ignore[import-not-found]

        settings = get_settings()
        if settings.docker_host.startswith("unix:"):
            if settings.is_production:
                raise RuntimeError("docker_socket_forbidden_in_production")
            self.client = docker.from_env()  # type: ignore[attr-defined]
        else:
            client_cert: tuple[str, str] | None = None
            if settings.docker_tls_cert and settings.docker_tls_key:
                client_cert = (settings.docker_tls_cert, settings.docker_tls_key)
            elif settings.docker_tls_cert or settings.docker_tls_key:
                raise RuntimeError("docker_tls_cert_and_key_must_be_configured_together")
            tls = TLSConfig(
                client_cert=client_cert,
                ca_cert=settings.docker_tls_ca,
                verify=settings.docker_tls_verify,
            )
            self.client = docker.DockerClient(base_url=settings.docker_host, tls=tls)  # type: ignore[attr-defined]

    def ensure_submitted(self, job: RuntimeJob) -> str:
        import docker

        try:
            existing = self.client.containers.get(job.deterministic_name)
            return str(existing.id)
        except docker.errors.NotFound:  # type: ignore[attr-defined]
            pass
        image = str(job.runtime_spec.get("image") or job.model_plugin)
        command = job.runtime_spec.get("command")
        container = self.client.containers.run(
            image=image,
            command=command,
            name=job.deterministic_name,
            detach=True,
            remove=False,
            labels={"bda.job_id": str(job.id), "bda.attempt": str(job.attempt_number)},
            environment={**_manifest_environment(job), **_parameter_environment(job)},
        )
        return str(container.id)

    def status(self, job: RuntimeJob, external_id: str) -> AdapterStatus:
        container = self.client.containers.get(external_id)
        container.reload()
        state = container.attrs.get("State", {})
        if container.status in {"created", "restarting"}:
            return AdapterStatus("queued")
        if container.status == "running":
            return AdapterStatus("running")
        if container.status == "exited":
            return AdapterStatus("succeeded" if state.get("ExitCode") == 0 else "failed", state.get("Error"))
        return AdapterStatus("failed", f"unsupported_container_status:{container.status}")

    def cancel(self, external_id: str) -> bool:
        container = self.client.containers.get(external_id)
        container.stop(timeout=10)
        return True

    def collect(self, job: RuntimeJob, external_id: str) -> list[dict]:
        return _collect_manifest(job)


class _TargetSettings:
    """Global settings with a per-target override layer.

    Keeps adapters reading a single object while letting a specific compute target
    supply its own host, queue, credentials or staging mode.
    """

    def __init__(self, settings, target: dict) -> None:
        self._settings = settings
        self._target = target

    def __getattr__(self, name: str):
        # Guard the two own attributes: without this, an instance whose __init__ has not
        # run (copy, pickle) recurses until the stack is exhausted.
        if name in {"_settings", "_target"}:
            raise AttributeError(name)
        if name in self._target:
            return self._target[name]
        return getattr(self._settings, name)


def _build_transport(settings) -> SSHTransport:
    """Pick an SSH transport from configuration.

    Password auth exists because some clusters disable publickey entirely; key auth
    stays the default and the preferred option.
    """
    if settings.lsf_ssh_password_ref:
        return PasswordSSHTransport(
            settings.lsf_ssh_host,
            username=settings.lsf_ssh_user or "",
            password=read_secret(settings.lsf_ssh_password_ref),
            port=settings.lsf_ssh_port,
            connect_timeout=settings.lsf_connect_timeout_seconds,
        )
    return KeySSHTransport(
        settings.lsf_ssh_host,
        key_path=settings.lsf_ssh_key_path,
        connect_timeout=settings.lsf_connect_timeout_seconds,
        port=settings.lsf_ssh_port if settings.lsf_ssh_port != 22 else None,
    )


class LSFAdapter:
    _job_id = re.compile(r"Job <(\d+)>")
    # How LSF answers a query about a job it has already cleaned out of bjobs. It arrives
    # on stdout through a PTY session and on stderr otherwise, and it is not a job state:
    # read as one it silently turns every finished job into a failure.
    _forgotten = re.compile(r"is not found|no unfinished job found|no job found", re.IGNORECASE)

    def __init__(self, target: dict | None = None) -> None:
        """Configure against global settings, overridden per key by ``target``.

        ``target`` is what a registered compute node would supply, so pointing a job at
        a second cluster is data rather than a code change.
        """
        settings = _TargetSettings(get_settings(), target or {})
        self.host = settings.lsf_ssh_host
        self.root = settings.lsf_remote_root.rstrip("/")
        self.timeout = settings.lsf_connect_timeout_seconds
        self.ssh_key = settings.lsf_ssh_key_path
        self.default_queue = settings.lsf_queue
        self.upload_wrapper = settings.lsf_upload_wrapper
        self.staging_mode = settings.lsf_staging_mode
        self.transport = _build_transport(settings)

    def _ssh(
        self, command: str, *, input_text: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run a remote command. Kept returning CompletedProcess for call-site stability."""
        if input_text is not None:
            # The only stdin use is writing a submit script; transports have a direct
            # path for that which survives PTY-based sessions.
            target = command.split(">", 1)[1].strip() if ">" in command else ""
            self.transport.put_file(target.strip("'\""), input_text)
            return subprocess.CompletedProcess([], 0, "", "")
        result = self.transport.run(command, check=check, timeout=60)
        return subprocess.CompletedProcess([], result.returncode, result.stdout, result.stderr)

    def remote_dir(self, job: RuntimeJob) -> str:
        return f"{self.root}/jobs/{job.id.hex}/attempt-{job.attempt_number}"

    def script_context(self, job: RuntimeJob, env: dict[str, str]) -> ScriptContext:
        """The exact inputs used to render the submitted script.

        Exposed so the preview endpoint can render byte-identical output instead of
        maintaining its own approximation.
        """
        snapshot = job.runtime_spec.get("plugin_snapshot")
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        return ScriptContext(
            job_name=job.deterministic_name,
            remote_dir=self.remote_dir(job),
            command=str(job.runtime_spec.get("command") or "true"),
            queue=str(job.runtime_spec.get("queue") or self.default_queue),
            backend="lsf",
            runtime_mode=str(snapshot.get("runtime_mode") or "container"),
            container_image=job.runtime_spec.get("image") or snapshot.get("image"),
            input_manifest_url=env.get("BDA_INPUT_MANIFEST_URL", ""),
            output_manifest_url=env.get("BDA_OUTPUT_MANIFEST_URL", ""),
            upload_wrapper=self.upload_wrapper,
            staging_mode=self.staging_mode,
            runtime_setup=raw_setup if isinstance(raw_setup := snapshot.get("runtime_setup"), list) else [],
            parameters=raw_params if isinstance(raw_params := job.runtime_spec.get("parameters"), dict) else {},
            resources=raw_resources if isinstance(raw_resources := snapshot.get("resources"), dict) else {},
        )

    def ensure_submitted(self, job: RuntimeJob) -> str:
        name = job.deterministic_name
        existing = self._ssh(f"bjobs -a -J {shlex.quote(name)} -noheader -o jobid", check=False)
        known_ids = [item for item in existing.stdout.split() if item.isdigit()]
        if known_ids:
            return known_ids[0]
        remote_dir = self.remote_dir(job)
        env = {} if self.staging_mode == "ssh" else _manifest_environment(job)
        script = render_script(self.script_context(job, env))
        self._ssh(f"umask 077 && mkdir -p {shlex.quote(remote_dir)}")
        if self.staging_mode == "ssh":
            self._stage_inputs(job, remote_dir)
        self._ssh(f"cat > {shlex.quote(remote_dir)}/submit.lsf", input_text=script)
        submitted = self._ssh(f"cd {shlex.quote(remote_dir)} && bsub < submit.lsf")
        match = self._job_id.search(submitted.stdout)
        if not match:
            raise RuntimeError(f"lsf_submit_unrecognized:{submitted.stdout.strip()}")
        return match.group(1)

    def status(self, job: RuntimeJob, external_id: str) -> AdapterStatus:
        result = self._ssh(f"bjobs -a -noheader -o stat {shlex.quote(external_id)}", check=False)
        raw = result.stdout.strip().split()
        state = raw[0] if raw else ""
        mapping = {
            "PEND": "queued",
            "WAIT": "queued",
            "RUN": "running",
            "DONE": "succeeded",
            "EXIT": "failed",
            "ZOMBI": "failed",
        }
        if state in mapping:
            return AdapterStatus(mapping[state])
        if self._forgotten.search(f"{result.stdout}\n{result.stderr}"):
            return self._status_without_bjobs(job, external_id)
        # No state and no explanation. A busy or briefly unreachable mbatchd looks like
        # this, so the job stays pollable rather than being failed for the cluster's mood.
        return AdapterStatus("queued") if not state else AdapterStatus("failed", state)

    def _status_without_bjobs(self, job: RuntimeJob, external_id: str) -> AdapterStatus:
        """Decide the outcome of a job LSF no longer remembers.

        Sites configure how long a finished job stays queryable, and on some it is under
        an hour - well inside the window in which a job can still be waiting to be
        collected. ``bhist`` is not a fallback: the unbounded form scans every history
        file and outlives the SSH timeout, and the bounded forms find nothing once the
        history files have rotated.

        What does survive is the job's own completion marker. The submitted script runs
        under ``set -Eeuo pipefail`` and writes its output manifest as the last thing it
        does, so the manifest exists only if the command succeeded. A working directory
        with no manifest is therefore a real failure; neither one means there is nothing
        to judge, and the answer stays non-terminal so the job's own deadline governs.
        """
        if self._manifest_present(job):
            return AdapterStatus("succeeded")
        if self._remote_exists("-d", self.remote_dir(job)):
            return AdapterStatus("failed", f"lsf_job_gone_without_manifest:{external_id}")
        return AdapterStatus("unknown", f"lsf_job_gone_without_remote_dir:{external_id}")

    def _manifest_present(self, job: RuntimeJob) -> bool:
        """Whether the job wrote the output manifest that marks a successful run.

        Where that manifest lands depends on staging: on the cluster filesystem when the
        API collects over SSH, in object storage when the job uploads it itself.
        """
        if self.staging_mode == "ssh":
            return self._remote_exists("-f", f"{self.remote_dir(job)}/output-manifest.json")
        key = str(job.runtime_spec.get("output_manifest_key") or "")
        return bool(key) and ObjectStorage().exists(key)

    def _remote_exists(self, flag: str, path: str) -> bool:
        """``test`` on the cluster, read from the exit code rather than from any output.

        An unreachable cluster reads as absent, which keeps it out of the terminal
        branches of :meth:`_status_without_bjobs` instead of failing a live job.
        """
        return self._ssh(f"test {flag} {shlex.quote(path)}", check=False).returncode == 0

    def cancel(self, external_id: str) -> bool:
        return self._ssh(f"bkill {shlex.quote(external_id)}", check=False).returncode == 0

    def collect(self, job: RuntimeJob, external_id: str) -> list[dict]:
        if self.staging_mode != "ssh":
            return _collect_manifest(job)
        return self._collect_over_ssh(job)

    def _stage_inputs(self, job: RuntimeJob, remote_dir: str) -> None:
        """Copy the job's inputs from object storage onto the cluster filesystem.

        Compute nodes routinely have no route to the object store, so the API moves the
        bytes over the SSH channel it already holds rather than handing the job a
        presigned URL it cannot reach.
        """
        manifest = job.runtime_spec.get("input_manifest") or {}
        raw_inputs = manifest.get("inputs")
        inputs: list = raw_inputs if isinstance(raw_inputs, list) else []
        storage = ObjectStorage()
        self._ssh(f"mkdir -p {shlex.quote(remote_dir)}/inputs {shlex.quote(remote_dir)}/outputs")
        staged = []
        for item in inputs:
            if not isinstance(item, dict) or not item.get("object_key"):
                continue
            filename = PurePosixPath(str(item.get("filename") or "input")).name
            relative = f"inputs/{item.get('port') or 'input'}/{filename}"
            remote_path = f"{remote_dir}/{relative}"
            self._ssh(f"mkdir -p {shlex.quote(str(PurePosixPath(remote_path).parent))}")
            self.transport.put_stream(remote_path, storage.stream(str(item["object_key"])))
            staged.append({**item, "path": remote_path, "relative_path": relative})
        # The job reads local paths, so the staged manifest replaces URLs with them.
        self.transport.put_file(
            f"{remote_dir}/input-manifest.json",
            json.dumps({**manifest, "inputs": staged, "staging": "ssh"}, separators=(",", ":")),
        )

    def _collect_over_ssh(self, job: RuntimeJob) -> list[dict]:
        """Pull the job's outputs off the cluster and into object storage."""
        remote_dir = self.remote_dir(job)
        raw = self.transport.get_bytes(f"{remote_dir}/output-manifest.json")
        manifest = json.loads(raw.decode("utf-8"))
        if manifest.get("schema_version") != "1" or not isinstance(manifest.get("outputs"), list):
            raise ValueError("output_manifest_schema_invalid")
        storage = ObjectStorage()
        prefix = f"jobs/{job.id}/attempt-{job.attempt_number}/outputs"
        declared = {
            str(port.get("name")): port
            for port in (job.runtime_spec.get("plugin_snapshot") or {}).get("output_ports", [])
            if isinstance(port, dict)
        }
        collected: list[dict] = []
        for entry in manifest["outputs"]:
            relative = PurePosixPath(str(entry.get("relative_path") or entry.get("filename") or ""))
            if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("output_manifest_path_invalid")
            content_type = str(entry.get("content_type") or "application/octet-stream")
            object_key = f"{prefix}/{relative}"
            with tempfile.SpooledTemporaryFile(max_size=SPOOL_TO_DISK_BYTES) as buffer:
                digest = hashlib.sha256()
                size = 0
                for chunk in self.transport.stream(f"{remote_dir}/outputs/{relative}"):
                    digest.update(chunk)
                    size += len(chunk)
                    buffer.write(chunk)
                checksum = digest.hexdigest()
                if str(entry.get("checksum_sha256", "")).lower() != checksum:
                    raise ValueError("collect_output_checksum_mismatch")
                buffer.seek(0)
                storage.put_stream(object_key, buffer, size, content_type)
            # A file under outputs/<port>/ declares its port by location. Models that
            # write to their own directory layout, or straight into the root, are typed
            # by matching the declared filename globs instead.
            port_name = relative.parts[0] if len(relative.parts) > 1 and relative.parts[0] in declared else None
            if port_name is None:
                port_name = next(
                    (
                        name
                        for name, port in declared.items()
                        if fnmatch(relative.name, str(port.get("filename_glob") or "*"))
                        and str(port.get("filename_glob") or "*") != "*"
                    ),
                    None,
                )
            collected.append(
                {
                    "object_key": object_key,
                    "checksum_sha256": checksum,
                    "size_bytes": size,
                    "filename": relative.name,
                    "content_type": content_type,
                    "artifact_type": str(
                        entry.get("artifact_type")
                        or (declared.get(port_name, {}).get("artifact_type") if port_name else None)
                        or "compute_output"
                    ),
                    "port": port_name,
                    "metadata": entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {},
                }
            )
        return collected


def _parameter_environment(job: RuntimeJob) -> dict[str, str]:
    """Node parameters as container environment, mirroring the exports a script gets.

    A container gets no shell to run the export lines, so the same values are handed to
    the runtime directly; a plugin command reads "$mode" the same way on either backend.
    """
    parameters = job.runtime_spec.get("parameters")
    return parameter_environment(parameters if isinstance(parameters, dict) else {})


def _manifest_environment(job: RuntimeJob) -> dict[str, str]:
    """Manifest URLs handed to the runner.

    The lifetime must cover the whole queue wait, not just dispatch: a job that pends
    for hours on a shared cluster would otherwise wake up holding expired URLs.
    """
    storage = ObjectStorage()
    input_key = str(job.runtime_spec["input_manifest_key"])
    output_key = str(job.runtime_spec["output_manifest_key"])
    ttl = int(job.runtime_spec.get("manifest_ttl_seconds") or MAX_PRESIGN_SECONDS)
    return {
        "BDA_INPUT_MANIFEST_URL": storage.download_url(input_key, ttl_seconds=ttl),
        "BDA_OUTPUT_MANIFEST_URL": storage.upload_url(output_key, ttl_seconds=ttl),
        "BDA_JOB_ID": str(job.id),
        "BDA_ATTEMPT": str(job.attempt_number),
    }


def _collect_manifest(job: RuntimeJob) -> list[dict]:
    key = str(job.runtime_spec.get("output_manifest_key") or "")
    expected_prefix = f"jobs/{job.id}/attempt-{job.attempt_number}/outputs/"
    manifest = ObjectStorage().read_json(key)
    if manifest.get("schema_version") != "1" or not isinstance(manifest.get("outputs"), list):
        raise ValueError("output_manifest_schema_invalid")
    outputs: list[dict] = []
    for raw in manifest["outputs"]:
        if not isinstance(raw, dict):
            raise ValueError("output_manifest_entry_invalid")
        object_key = str(raw.get("object_key") or "")
        path = PurePosixPath(object_key)
        if path.is_absolute() or ".." in path.parts or not object_key.startswith(expected_prefix):
            raise ValueError("output_manifest_path_invalid")
        checksum = str(raw.get("checksum_sha256") or "").lower()
        if len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
            raise ValueError("output_manifest_checksum_invalid")
        size = raw.get("size_bytes")
        if not isinstance(size, int) or size < 0:
            raise ValueError("output_manifest_size_invalid")
        filename = str(raw.get("filename") or path.name)
        filename_path = PurePosixPath(filename)
        if filename_path.is_absolute() or len(filename_path.parts) != 1 or filename in {".", ".."}:
            raise ValueError("output_manifest_filename_invalid")
        outputs.append(
            {
                "object_key": object_key,
                "checksum_sha256": checksum,
                "size_bytes": size,
                "filename": filename,
                "content_type": str(raw.get("content_type") or "application/octet-stream"),
                "artifact_type": str(raw.get("artifact_type") or "compute_output"),
                # Which declared output port this file belongs to. Optional: when the
                # runner omits it, collection falls back to an artifact_type/filename
                # reverse lookup so plugins written before ports still wire up.
                "port": str(raw["port"]) if raw.get("port") else None,
                "metadata": raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
            }
        )
    return outputs


def _demo_factory(target: dict | None = None) -> ComputeAdapter:
    if get_settings().is_production:
        raise RuntimeError("unsupported_compute_backend:demo")
    return DemoAdapter()


# Backend name -> factory. A registry rather than an if-chain so a site can add Slurm,
# PBS, Kubernetes or a cloud batch service without editing this module.
#
# Factories take an optional ``target`` config so a deployment is not limited to the one
# cluster described by global settings: a second cluster or a cloud queue is a different
# target dict, not different code.
AdapterFactory = Callable[..., ComputeAdapter]

ADAPTER_REGISTRY: dict[str, AdapterFactory] = {
    "docker": DockerAdapter,
    "lsf": LSFAdapter,
    "demo": _demo_factory,
}


def register_adapter(name: str, factory: AdapterFactory) -> None:
    """Register a compute backend. Intended for site plugins loaded at startup."""
    ADAPTER_REGISTRY[name] = factory


def available_backends() -> list[str]:
    """Backend names that can be selected right now, honouring the demo restriction."""
    names = set(ADAPTER_REGISTRY)
    if get_settings().is_production:
        names.discard("demo")
    return sorted(names)


def adapter_for(name: str, target: dict | None = None) -> ComputeAdapter:
    """Build the adapter for a backend, optionally against a specific target.

    ``target`` overrides the global settings for that one call, which is what lets a
    future job be routed to a registered compute node instead of the single cluster the
    process was configured with.
    """
    factory = ADAPTER_REGISTRY.get(name)
    if factory is None:
        raise RuntimeError(f"unsupported_compute_backend:{name}")
    if target is None:
        return factory()
    try:
        return factory(target)
    except TypeError:
        # A factory that predates target support still works for the default target.
        return factory()
