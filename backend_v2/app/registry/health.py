"""Read-only runtime probes. A registered declaration is not a connection test."""
from __future__ import annotations

import shlex

from ..core.config import get_settings


def probe_compute_node(*, backend: str, queue: str | None, server_id, labels: dict) -> tuple[str, str | None]:
    # Legacy HTTP worker registrations are not Docker/SSH runtime endpoints. Do not
    # accidentally probe this process's local engine and certify a different server.
    if server_id is not None:
        return "unverified", "This target references a server without a configured runtime probe. Configure its Docker or SSH runtime endpoint."
    if backend == "lsf":
        if not get_settings().lsf_ssh_host:
            return "unhealthy", "LSF SSH access is not configured."
        if not queue:
            return "unhealthy", "Select an LSF queue before checking this target."
        from ..compute.adapters import LSFAdapter

        try:
            result = LSFAdapter().transport.run(
                f"LC_ALL=C bqueues {shlex.quote(queue)}", check=False, timeout=20
            )
            if result.returncode:
                return "unhealthy", "LSF queue query failed. Check SSH access, LSF environment and queue name."
            fields = next((line.split() for line in result.stdout.splitlines() if line.split()[:1] == [queue]), [])
            if len(fields) < 3:
                return "unhealthy", "The requested queue was not returned by LSF."
            if fields[2].lower() != "open:active":
                return "unhealthy", f"LSF queue is {fields[2][:80]}; it is not open and active."
            return "healthy", None
        except Exception:
            # Transport errors can include sensitive command/configuration details.
            return "unhealthy", "LSF connection failed or timed out. Check SSH access and the cluster environment."
    if backend == "docker":
        from ..compute.adapters import DockerAdapter

        client = None
        try:
            client = DockerAdapter().client
            client.api.timeout = 20
            if not client.ping():
                return "unhealthy", "Docker engine did not respond."
            if labels.get("gpu_count", 0):
                return "unverified", "Docker engine responded, but GPU execution has not been verified. No container was started."
            return "healthy", None
        except Exception:
            return "unhealthy", "Docker engine is unavailable. Check the configured runtime endpoint and credentials."
        finally:
            if client is not None:
                client.close()
    return "unhealthy", "Unsupported compute backend."
