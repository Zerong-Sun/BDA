"""Submit a real LSF job through LSFAdapter and collect its outputs.

Exercises the whole ssh-staged path against a live cluster: input staging over SFTP,
script rendering, ``bsub``, status polling, inline manifest generation on the compute
node, output retrieval, and checksum-verified upload into object storage.

Requires a route to the cluster and to MinIO, so it runs from an environment that has
both.

The password is read from a file you create yourself, never from the environment. The
project's cluster rules are explicit that a password must not enter "commands,
environment variables, scripts, Git, logs or reports" (docs/QM_CLUSTER_OPERATION_RULES.md
section 1), and an env var fails that on two counts: it is visible in ``ps`` and in
``docker inspect``, and a shell records the line that set it. The adapter has always
accepted only a ``file:`` reference for the same reason; this script used to be the one
place in the repository that demonstrated the opposite.

    umask 077 && printf %s 'THE_PASSWORD' > ~/.bda/lsf-password
    QM_PASSWORD_FILE=~/.bda/lsf-password python backend_v2/scripts/verify_lsf_e2e.py
"""

from __future__ import annotations

import os
import stat
import sys
import time
import uuid
from pathlib import Path

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"[{PASS if ok else FAIL}] {name}" + (f"  {detail}" if detail else ""))


def _credential_file() -> str:
    """The path of the password file, checked for existence and for private permissions.

    Nothing here reads the contents: the adapter opens the file itself, so the secret
    never enters this process, its argv, or anything it prints.
    """
    raw = os.environ.get("QM_PASSWORD_FILE")
    if not raw:
        print(
            "QM_PASSWORD_FILE is not set. Write the password to a private file first:\n"
            "    umask 077 && printf %s 'THE_PASSWORD' > ~/.bda/lsf-password\n"
            "Passwords must not be passed in the environment.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    path = Path(raw).expanduser()
    if not path.is_file():
        print(f"{path} does not exist", file=sys.stderr)
        raise SystemExit(2)
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        print(
            f"{path} is readable by group or others; run: chmod 600 {path}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return str(path)


def main() -> int:
    secret_path = _credential_file()
    os.environ.update(
        {
            "BDA_V2_COMPUTE_BACKEND": "lsf",
            "BDA_V2_LSF_SSH_HOST": os.environ.get("QM_HOST", "172.18.6.10"),
            "BDA_V2_LSF_SSH_PORT": os.environ.get("QM_PORT", "18188"),
            "BDA_V2_LSF_SSH_USER": os.environ.get("QM_USER", "bme-sunzr"),
            "BDA_V2_LSF_SSH_PASSWORD_REF": f"file:{secret_path}",
            "BDA_V2_LSF_REMOTE_ROOT": os.environ.get("QM_ROOT", "/work/bme-sunzr/bda-v2"),
            "BDA_V2_LSF_QUEUE": os.environ.get("QM_QUEUE", "v3-64"),
            "BDA_V2_LSF_STAGING_MODE": "ssh",
        }
    )

    from backend_v2.app.artifacts.storage import ObjectStorage
    from backend_v2.app.compute.adapters import LSFAdapter, RuntimeJob
    from backend_v2.app.core.config import get_settings

    get_settings.cache_clear()
    storage = ObjectStorage()
    storage.ensure_bucket()

    job_id = uuid.uuid4()
    # A real structure file, staged through object storage exactly as a bound input is.
    payload = b"ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00  0.00           N\nEND\n"
    input_key = f"e2e/{job_id}/input.pdb"
    storage.put_bytes(input_key, payload, "chemical/x-pdb")

    job = RuntimeJob(
        id=job_id,
        attempt_number=1,
        model_plugin="e2e-probe",
        runtime_spec={
            "queue": os.environ["BDA_V2_LSF_QUEUE"],
            # Copies the staged input into the declared output port directory. Stands in
            # for a model without needing one installed on the cluster.
            "command": (
                'mkdir -p "$BDA_OUTPUT_DIR/designs" && '
                'cp "$BDA_INPUT_DIR/backbone/input.pdb" "$BDA_OUTPUT_DIR/designs/design_0.pdb" && '
                'echo "bda e2e produced $(ls "$BDA_OUTPUT_DIR/designs" | wc -l) file(s)"'
            ),
            "input_manifest_key": f"jobs/{job_id}/attempt-1/input-manifest.json",
            "output_manifest_key": f"jobs/{job_id}/attempt-1/output-manifest.json",
            "input_manifest": {
                "schema_version": "1",
                "parameters": {},
                "inputs": [
                    {
                        "port": "backbone",
                        "artifact_id": str(uuid.uuid4()),
                        "filename": "input.pdb",
                        "object_key": input_key,
                        "content_type": "chemical/x-pdb",
                        "checksum_sha256": "0" * 64,
                        "size_bytes": len(payload),
                    }
                ],
            },
            "plugin_snapshot": {
                "runtime_mode": "container",
                "resources": {},
                "output_ports": [
                    {"name": "designs", "kind": "protein_structure", "artifact_type": "backbone_set"}
                ],
            },
        },
    )

    adapter = LSFAdapter()
    check("adapter uses ssh staging", adapter.staging_mode == "ssh")

    external_id = adapter.ensure_submitted(job)
    check("bsub accepted the job", external_id.isdigit(), f"LSF job id {external_id}")

    remote = adapter.remote_dir(job)
    listing = adapter._ssh(f"ls -R {remote} 2>&1 | head -20", check=False).stdout
    check("inputs staged onto the cluster", "input.pdb" in listing, listing.replace("\n", " ")[:120])

    deadline = time.time() + 600
    state = "unknown"
    while time.time() < deadline:
        state = adapter.status(job, external_id).status
        if state in {"succeeded", "failed"}:
            break
        time.sleep(10)
    check("job reached a terminal state", state == "succeeded", f"final status {state}")
    if state != "succeeded":
        stderr = adapter._ssh(f"cat {remote}/stderr.log 2>&1 | tail -20", check=False).stdout
        print("--- remote stderr ---\n" + stderr)

    if state == "succeeded":
        outputs = adapter.collect(job, external_id)
        check("outputs collected", len(outputs) == 1, f"{len(outputs)} output(s)")
        if outputs:
            entry = outputs[0]
            check("output landed in object storage", storage.exists(entry["object_key"]), entry["object_key"])
            size, checksum = storage.inspect_and_hash(entry["object_key"])
            check(
                "checksum verified end to end",
                checksum == entry["checksum_sha256"] and size == entry["size_bytes"],
                f"{checksum[:16]}… {size}B",
            )
            check(
                "output port inferred from directory layout",
                entry["port"] == "designs" and entry["artifact_type"] == "backbone_set",
                f"port={entry['port']} type={entry['artifact_type']}",
            )
            check("round-tripped bytes match the input", storage.read_bytes(entry["object_key"]) == payload)

    adapter._ssh(f"rm -rf {remote}", check=False)
    for key in [input_key, *[item["object_key"] for item in (outputs if state == "succeeded" else [])]]:
        try:
            storage.remove(key)
        except Exception:
            pass
    Path(secret_path).unlink(missing_ok=True)

    failures = sum(1 for status, _, _ in results if status == FAIL)
    print(f"\n{len(results) - failures}/{len(results)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
