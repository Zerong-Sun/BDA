"""Preflight for the host compute worker.

Checks every dependency the worker needs before it starts consuming jobs, so a
misconfiguration shows up here rather than as jobs failing one at a time.

    backend_v2/scripts/run-host-worker.sh --check
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str = "") -> None:
    results.append((status, name, detail))


def _reachable(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False



def _resolved_endpoint(host: str, port: int) -> tuple[str, int]:
    """The address ssh would actually dial for ``host``.

    `lsf_ssh_host` is whatever the deployment configured, and for the system ssh client
    that may legitimately be an ssh_config alias. A TCP probe has to resolve it the same
    way ssh does, or it reports an unreachable cluster for a name only ssh understands.
    """
    try:
        out = subprocess.run(
            ["ssh", "-G", host], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return host, port
    resolved_host, resolved_port = host, port
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        if key == "hostname" and value:
            resolved_host = value
        elif key == "port" and value.isdigit():
            resolved_port = int(value)
    # An explicitly configured non-default port wins over ssh_config's.
    return resolved_host, port if port != 22 else resolved_port


def main() -> int:
    from backend_v2.app.core.config import get_settings

    settings = get_settings()

    database = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql"))
    check(
        "PostgreSQL reachable",
        PASS if _reachable(database.hostname or "localhost", database.port or 5432) else FAIL,
        f"{database.hostname}:{database.port}",
    )

    broker = urlparse(settings.celery_broker_url)
    check(
        "Redis broker reachable",
        PASS if _reachable(broker.hostname or "localhost", broker.port or 6379) else FAIL,
        f"{broker.hostname}:{broker.port}",
    )

    minio_host, _, minio_port = settings.minio_endpoint.partition(":")
    check(
        "MinIO reachable",
        PASS if _reachable(minio_host, int(minio_port or 9000)) else FAIL,
        settings.minio_endpoint,
    )

    backend = settings.compute_backend
    check("Compute backend", PASS, backend)

    if backend == "lsf":
        if settings.lsf_ssh_password_ref:
            reference = settings.lsf_ssh_password_ref
            path = Path(reference.removeprefix("file:")) if reference.startswith("file:") else None
            if path is None:
                check("LSF credentials configured", FAIL, f"{reference} is not a file: reference")
            elif not path.is_file():
                # The one step the account owner has to take themselves.
                check("LSF credentials configured", FAIL, f"{path} does not exist")
            elif path.stat().st_size == 0:
                check("LSF credentials configured", FAIL, f"{path} is empty")
            elif path.stat().st_mode & 0o077:
                check("LSF credentials configured", FAIL, f"{path} is readable by others; chmod 600 it")
            else:
                check("LSF credentials configured", PASS, f"password reference {path}")
        elif settings.lsf_ssh_key_path:
            check("LSF credentials configured", PASS, f"key {settings.lsf_ssh_key_path}")
        else:
            # Not a failure. With neither set the adapter uses the system ssh client
            # under BatchMode, which is how a cluster that only authenticates an
            # interactive session is meant to be driven - the session is the credential.
            check(
                "LSF credentials configured",
                WARN,
                "none configured; the adapter will reuse an interactive ssh session, "
                "so dispatch fails whenever that session is gone",
            )
        # Resolve through ssh_config before connecting: `lsf_ssh_host` may be an alias,
        # and a raw socket to the alias name asks DNS for a host that does not exist.
        # That reported FAIL on a cluster that was reachable the whole time.
        host, port = _resolved_endpoint(settings.lsf_ssh_host, settings.lsf_ssh_port)
        detail = f"{host}:{port}"
        if (host, port) != (settings.lsf_ssh_host, settings.lsf_ssh_port):
            detail += f" (via ssh_config for {settings.lsf_ssh_host})"
        check("Cluster reachable", PASS if _reachable(host, port, timeout=10) else FAIL, detail)
        # A remembered queue is the failure this project has already paid for: jobs
        # 4167123/4167124 were killed in PEND for inheriting an unrelated job's
        # resources, and the hand-written preparers refuse to render a script whose
        # queue was defaulted rather than read from `bqueues` at submit time. The
        # worker's global queue is a fallback for nodes that name none, so say plainly
        # which one it would use rather than letting it be discovered from a job.
        check(
            "Fallback queue",
            WARN,
            f"{settings.lsf_queue} - used only when a node names no queue of its own; "
            "confirm it against bqueues before relying on it",
        )
        check(
            "Staging mode",
            PASS if settings.lsf_staging_mode == "ssh" else WARN,
            f"{settings.lsf_staging_mode}"
            + ("" if settings.lsf_staging_mode == "ssh" else " (nodes must reach the object store)"),
        )
        try:
            from backend_v2.app.compute.adapters import LSFAdapter

            probe = LSFAdapter().transport.run("bjobs -V 2>&1 | head -1", check=False)
            ok = "LSF" in probe.stdout or probe.returncode == 0
            check("LSF commands available", PASS if ok else FAIL, probe.stdout.strip()[:70])
        except Exception as exc:  # noqa: BLE001 - report any failure mode to the operator
            check("LSF commands available", FAIL, f"{type(exc).__name__}: {exc}"[:120])

    width = max(len(name) for _, name, _ in results)
    for status, name, detail in results:
        print(f"[{status}] {name.ljust(width)}  {detail}")
    failures = sum(1 for status, _, _ in results if status == FAIL)
    print(f"\n{len(results) - failures}/{len(results)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
