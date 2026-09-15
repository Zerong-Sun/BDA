"""What a plugin declares it needs, against what the cluster will actually give it.

`auditor`'s resource review is the review stance applied to resource declarations, and its charter
names four things that must agree: the slot count, the per-host span, the thread
count the tool will really start, and the GPU declaration. None of those were
readable through any copilot tool - `get_compute_status` returns a draft's
free-form specification, while the numbers that reach LSF come from the plugin
registry row and from the queue chosen on the `bsub` command line. A charter
instructing a comparison its operator cannot make is the same defect the roster
already fixed once, in `archivist` (now part of `analyst`).

So this module reads the declaration the way the cluster does. It is deliberately
the same knowledge `backend_v2/scripts/check_plugin_cpu_declarations.py` and
`check_cluster_claims.py` encode for CI, applied to one plugin on demand, and it
reports rather than repairs - a reviewer that edits the draft is a producer.

The rule that catches the most here is the queue's own GPU request. `#BSUB`
carrying no `-gpu` does not mean no GPU: `2v100-32-e5` merges
`num=1:mode=exclusive_process` into everything it runs, and three jackhmmer
stages once held a V100 for about seven GPU-hours while their comments said they
had asked for none. That is a violation in this project, not a notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .diagnosis import GPU_FORCING_QUEUES
from .scripts import _resource_directives, declared_cpus

#: Above this, a slot count needs evidence naming the measurement or the thread
#: flag behind it. One slot needs none: it is the floor, not a claim.
EVIDENCE_REQUIRED_ABOVE = 1


@dataclass(frozen=True)
class Finding:
    """One disagreement, stated as the two things that disagree.

    `severity` separates "the cluster will treat this as a violation" from "this
    is worth a sentence in the review". A reviewer that reports both at the same
    weight is one whose findings get skimmed.
    """

    id: str
    severity: str  # "violation" | "warning" | "note"
    title: str
    detail: str
    declared: Any
    effective: Any


def _evidence(resources: dict) -> str:
    value = resources.get("cpus_evidence")
    return str(value).strip() if isinstance(value, str) else ""


def _gpu_requested(resources: dict) -> bool:
    return bool(resources.get("gpu"))


def review(
    *,
    plugin_key: str,
    plugin_version: str,
    resources: dict,
    backend: str,
    queue: str | None,
) -> dict[str, Any]:
    """The declaration, what the cluster would make of it, and the disagreements.

    Returns the rendered directives as well as the findings: a reviewer quoting
    `-n 8` should be quoting the line that will actually be submitted, not a
    number it recomputed and hopes matches.
    """
    resources = dict(resources or {})
    cpus = declared_cpus(resources)
    evidence = _evidence(resources)
    gpu = _gpu_requested(resources)
    queue_name = (queue or "").strip()
    # Only LSF schedules by queue. On any other backend the name is inert, so a
    # queue that would force a GPU there forces nothing here - reporting it as a
    # violation would be an accusation about a machine the job never reaches.
    queue_forces_gpu = backend == "lsf" and queue_name in GPU_FORCING_QUEUES

    findings: list[Finding] = []

    if cpus > EVIDENCE_REQUIRED_ABOVE and not evidence:
        findings.append(
            Finding(
                id="cpus_without_evidence",
                severity="violation",
                title="More than one slot is requested with nothing supporting the number",
                detail=(
                    "A job holding cores it cannot use draws low-utilisation "
                    "inspection mail, which this project treats as a violation. "
                    "The number needs a measurement or an upstream thread flag "
                    "named beside it in `resources.cpus_evidence`."
                ),
                declared=cpus,
                effective=cpus,
            )
        )

    if queue_forces_gpu and not gpu:
        findings.append(
            Finding(
                id="queue_forces_unrequested_gpu",
                severity="violation",
                title="The queue attaches a GPU this plugin says it does not need",
                detail=(
                    f"Queue {queue_name!r} merges its own GPU request into every "
                    "job it runs, so directives carrying no `-gpu` still hold one "
                    "exclusively. Either move the stage to a CPU queue or declare "
                    "the GPU and justify it."
                ),
                declared=False,
                effective=True,
            )
        )

    if gpu and queue_name and backend == "lsf" and not queue_forces_gpu:
        findings.append(
            Finding(
                id="gpu_requested_on_unconfirmed_queue",
                severity="warning",
                title="A GPU is declared on a queue not known to provide one",
                detail=(
                    f"Queue {queue_name!r} is not in the set this platform knows "
                    "to attach a GPU. The request may simply not be satisfied, "
                    "which surfaces as a job that runs on CPU and looks slow "
                    "rather than as a failure."
                ),
                declared=True,
                effective="unknown",
            )
        )

    gpu_count = resources.get("gpu_count") or (1 if gpu else 0)
    if gpu and isinstance(gpu_count, int) and gpu_count > 1 and not evidence:
        findings.append(
            Finding(
                id="multiple_gpus_without_evidence",
                severity="violation",
                title="More than one GPU is requested with nothing supporting the number",
                detail=(
                    "Each GPU is held in exclusive_process mode, so an unused "
                    "second device is idle for the whole run and visible to the "
                    "cluster as such."
                ),
                declared=gpu_count,
                effective=gpu_count,
            )
        )

    if backend != "lsf" and queue_name:
        findings.append(
            Finding(
                id="queue_on_non_lsf_backend",
                severity="note",
                title="A queue is named for a backend that does not schedule by queue",
                detail=(
                    f"Backend {backend!r} ignores the queue, so the name records "
                    "an intention the run will not honour."
                ),
                declared=queue_name,
                effective=None,
            )
        )

    return {
        "plugin": f"{plugin_key}@{plugin_version}",
        "backend": backend,
        "queue": queue_name or None,
        "declared": {
            "cpus": cpus,
            "cpus_evidence": evidence or None,
            "gpu": gpu,
            "gpu_count": gpu_count,
            "memory_gb": resources.get("memory_gb"),
            "walltime_minutes": resources.get("walltime_minutes"),
        },
        "effective": {
            # `-n` and `span[ptile]` come from one number by construction, so the
            # reviewer states that rather than discovering it; the directives are
            # returned so the statement quotes the lines that will be submitted.
            "slots": cpus,
            "slots_per_host": cpus,
            "thread_budget_env": "BDA_CPUS",
            "gpu_attached": bool(gpu or queue_forces_gpu),
            "gpu_forced_by_queue": queue_forces_gpu,
        },
        "directives": _resource_directives(resources) if backend == "lsf" else [],
        "findings": [
            {
                "id": item.id,
                "severity": item.severity,
                "title": item.title,
                "detail": item.detail,
                "declared": item.declared,
                "effective": item.effective,
            }
            for item in findings
        ],
        # Said explicitly rather than left as an empty list. A review that never
        # approves is one that stops being read, and `auditor`'s resource-review charter requires
        # it to say so when the declaration is sound.
        "verdict": (
            "violation"
            if any(item.severity == "violation" for item in findings)
            else "sound"
            if not findings
            else "review"
        ),
    }
