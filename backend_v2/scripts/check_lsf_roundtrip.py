#!/usr/bin/env python3
"""Prove the LSF adapter against a real cluster: submit, poll, collect.

Everything else about the compute path is tested with fixtures, which is right for logic
and cannot answer the question this script exists for - does `LSFAdapter` work against the
scheduler as that scheduler is actually configured. The failures it catches are the ones
fixtures cannot have: an `ssh_config` alias that paramiko does not read, a queue that
merges in a GPU requirement, a `bjobs` output format that does not parse, a finished job
LSF has already forgotten.

What it submits is deliberately trivial - one slot, a few seconds, `hostname` and a marker
string. It is a mechanism test, not a workload:

* ``-n 1`` with ``span[ptile=1]`` and ``BDA_CPUS=1``, all from one number, because a job
  holding cores it does not use is what draws the cluster's low-utilisation mail, and this
  project treats that as a violation rather than a notice;
* no GPU, and the queue is checked for a merged ``GPU_REQ`` first - some queues here
  attach an exclusive GPU even to a job that never asked for one;
* the same job id twice, because the adapter's recovery discipline is "query external
  state before resubmitting" and a redelivery that creates a second job costs real time.

Not part of the default suite: it needs cluster credentials and it puts a job on a shared
queue. Run it deliberately, after the owner has a session:

    set -a; . .env; . backend_v2/scripts/host-worker.env; set +a
    PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/check_lsf_roundtrip.py

Exit status is 0 only if the job reached `succeeded` and `collect` parsed the manifest the
job itself wrote.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid

from backend_v2.app.compute.adapters import LSFAdapter, RuntimeJob

MARKER = "BDA_LSF_ROUNDTRIP_OK"

#: Fixed so a re-run reuses one staging directory instead of littering the jobs root, and
#: so `ensure_submitted`'s lookup is exercised across invocations rather than only within
#: one. Version 4 with a recognisable tail: it is not a real job and should not look like
#: one to anybody reading the cluster's directory listing.
PROBE_JOB_ID = uuid.UUID("00000000-0000-4000-8000-00000000e2e1")


def _probe_job(queue: str, attempt: int) -> RuntimeJob:
    return RuntimeJob(
        id=PROBE_JOB_ID,
        attempt_number=attempt,
        model_plugin="lsf-roundtrip-probe",
        runtime_spec={
            "command": f"hostname; echo {MARKER}; sleep 3",
            "queue": queue,
            "plugin_snapshot": {"runtime_mode": "shell", "resources": {"cpus": 1, "gpus": 0}},
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", default=None, help="Defaults to BDA_V2_LSF_QUEUE.")
    parser.add_argument("--attempt", type=int, default=1, help="Bump to force a fresh run.")
    parser.add_argument("--polls", type=int, default=20)
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Print the script that would be submitted and stop. Submits nothing.",
    )
    args = parser.parse_args()

    adapter = LSFAdapter()
    queue = args.queue or adapter.default_queue
    if not queue:
        print("no queue: pass --queue or set BDA_V2_LSF_QUEUE", file=sys.stderr)
        return 2
    job = _probe_job(queue, args.attempt)

    if args.render_only:
        from backend_v2.app.compute.scripts import render_script

        print(render_script(adapter.script_context(job, {})))
        return 0

    # A queue that merges in a GPU request would hand this one-slot job an exclusive GPU.
    # Cheaper to read the queue than to explain the utilisation report afterwards.
    described = adapter._ssh(f"bqueues -l {queue}", check=False)
    if "GPU_REQ" in described.stdout:
        print(f"refusing: queue {queue} declares GPU_REQ; a CPU probe there would hold a GPU")
        return 2

    external = adapter.ensure_submitted(job)
    print(f"submitted: {external}")
    again = adapter.ensure_submitted(job)
    if again != external:
        print(f"NOT IDEMPOTENT: a second call created {again}", file=sys.stderr)
        return 1
    print(f"re-called:  {again} (same job)")

    for index in range(args.polls):
        state = adapter.status(job, external)
        print(f"poll {index}: {state.status} {state.error or ''}".rstrip(), flush=True)
        if state.status == "succeeded":
            break
        if state.status == "failed":
            print("job failed on the cluster", file=sys.stderr)
            return 1
        time.sleep(args.interval)
    else:
        print("never reached a terminal state", file=sys.stderr)
        return 1

    # An empty list here is the correct answer for a job that produced no files - but only
    # if it came from parsing the manifest the job wrote. `collect` raising, or the file
    # being absent, is the failure this distinguishes.
    outputs = adapter.collect(job, external)
    print(f"collect: {len(outputs)} output(s) from the job's own manifest")
    print("LSF round trip OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
