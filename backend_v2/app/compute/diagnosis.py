"""Why one job failed, from the evidence the platform already recorded.

`get_compute_status` reports that a job failed and what its error string was.
That is where every investigation here has started and it is never where one
ends, because the failures this cluster produces are rarely exceptions in the
platform. They are disagreements between what a job *declared* and what it was
actually given: a stage that says it needs no GPU submitted to a queue that
merges one in, `-n` disagreeing with the thread count the tool was told to use,
a registry row whose image or command makes the job exit in seconds with an
empty log, a staged-input loop that verified a manifest which never listed the
file that was missing.

So the shape here is: gather the recorded evidence for one job, run an explicit
rule set over it, and return findings that each name the evidence they rest on.

Three properties are deliberate.

**Rules are data.** Each is a `Rule` with a predicate, so one rule can be tested
against one piece of evidence, and adding the next lesson this cluster teaches
is adding a row rather than extending a branch.

**Confidence is stated, not implied.** `confirmed` means the evidence says it;
`possible` means the evidence is consistent with it and with other things. A
reader who cannot tell the two apart will act on the second as if it were the
first.

**No match is an answer.** A job whose evidence fits no rule yields no findings
and says so. An invented cause ends an investigation, which is strictly worse
than admitting the evidence does not determine one.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import Job, JobAttempt, JobEvent

#: Queues that merge their own GPU requirement into every job, whatever the
#: submitted directives say. A stage that declares no GPU and lands here holds
#: one exclusively for its whole run, and the low-utilisation mail that follows
#: is treated as a violation in this project, not as a notice.
GPU_FORCING_QUEUES = frozenset({"2v100-32-e5", "2v100-32", "gpu-v100"})

#: A dispatch that failed this fast did not run the model. Something rejected it
#: before the work began - a missing image, an entrypoint that is not there, a
#: command that exits immediately - and all of those live in the plugin
#: declaration rather than in the science.
IMMEDIATE_EXIT_SECONDS = 45

#: How many of a job's most recent events the bundle carries. Enough to see the
#: transition that ended it without turning the result into a log file.
EVENT_LIMIT = 20

_PATTERNS: dict[str, re.Pattern[str]] = {
    "oom": re.compile(
        r"TERM_MEMLIMIT|out of memory|OutOfMemory|CUDA out of memory|Killed\b|exit code 137",
        re.IGNORECASE,
    ),
    "timeout": re.compile(r"TERM_RUNLIMIT|run limit|walltime|timed? ?out|DeadlineExceeded", re.IGNORECASE),
    "image": re.compile(
        r"pull access denied|manifest unknown|no such image|ImagePullBackOff|"
        r"repository does not exist|not found: manifest",
        re.IGNORECASE,
    ),
    "missing_file": re.compile(
        r"No such file or directory|FileNotFoundError|cannot open .* for reading|"
        r"cannot stat|does not exist",
        re.IGNORECASE,
    ),
    "checksum": re.compile(
        r"sha256sum|checksum|FAILED open or read|computed checksum did not match",
        re.IGNORECASE,
    ),
    "permission": re.compile(r"Permission denied|Operation not permitted|EACCES", re.IGNORECASE),
}


@dataclass(frozen=True)
class Finding:
    id: str
    title: str
    confidence: str  # "confirmed" | "possible"
    detail: str
    remedy: str
    #: Which fields of the evidence bundle the rule read. Named so a reader can
    #: check the finding against the same evidence rather than trusting it.
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "confidence": self.confidence,
            "detail": self.detail,
            "remedy": self.remedy,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class Rule:
    id: str
    check: Callable[[dict[str, Any]], Finding | None]


def _errors(evidence: dict[str, Any]) -> str:
    """Every recorded error string for this job, joined for pattern matching.

    The job's own message, and each attempt's. A retry that failed differently
    is the interesting case, and matching only the latest would miss it.
    """
    parts = [str(evidence.get("error_message") or ""), str(evidence.get("error_code") or "")]
    parts.extend(str(attempt.get("error") or "") for attempt in evidence.get("attempts", []))
    return "\n".join(part for part in parts if part)


def _resources(evidence: dict[str, Any]) -> dict[str, Any]:
    snapshot = evidence.get("plugin_snapshot") or {}
    resources = snapshot.get("resources")
    return resources if isinstance(resources, dict) else {}


def _rule_pending_inputs(evidence: dict[str, Any]) -> Finding | None:
    pending = evidence.get("pending_inputs") or []
    if not pending:
        return None
    return Finding(
        id="pending_inputs_unresolved",
        title="The job was dispatched with unresolved input ports",
        confidence="confirmed",
        detail=(
            f"The input manifest still lists {len(pending)} unresolved port(s): "
            f"{', '.join(str(item) for item in pending[:6])}. The stage ran without "
            "the artifact it was supposed to read."
        ),
        remedy=(
            "Bind the upstream output port to this node's input port, or wait for the "
            "producing stage to succeed, before submitting again."
        ),
        evidence=("runtime_spec.input_manifest.pending_inputs",),
    )


def _rule_no_command(evidence: dict[str, Any]) -> Finding | None:
    if evidence.get("command"):
        return None
    return Finding(
        id="no_command_declared",
        title="Neither the plugin nor the node declared a command",
        confidence="confirmed",
        detail=(
            "The runtime spec carries no command, so the container had nothing to run. "
            "A job in this state exits immediately and produces an empty log."
        ),
        remedy=(
            "Set the command on the model plugin registry row (preferred, so every node "
            "using it inherits the fix) or on the workflow node."
        ),
        evidence=("runtime_spec.command", "runtime_spec.plugin_snapshot.command"),
    )


def _rule_gpu_queue(evidence: dict[str, Any]) -> Finding | None:
    queue = str(evidence.get("queue") or "")
    if queue not in GPU_FORCING_QUEUES:
        return None
    resources = _resources(evidence)
    if resources.get("gpu"):
        return None
    return Finding(
        id="gpu_forced_by_queue",
        title="A no-GPU stage was submitted to a queue that forces a GPU",
        confidence="confirmed",
        detail=(
            f"The plugin declares no GPU, but queue {queue!r} merges its own GPU "
            "requirement into every job it accepts. The stage held a GPU exclusively "
            "for its whole run without using it. This does not by itself fail a job, "
            "and it is a violation here regardless of whether the job succeeded."
        ),
        remedy=(
            "Submit CPU-only stages to a CPU queue, and have the stage exit when "
            "CUDA_VISIBLE_DEVICES is set so the mismatch cannot recur silently."
        ),
        evidence=("runtime_spec.queue", "runtime_spec.plugin_snapshot.resources.gpu"),
    )


def _rule_cpu_evidence(evidence: dict[str, Any]) -> Finding | None:
    resources = _resources(evidence)
    cpus = resources.get("cpus")
    if not isinstance(cpus, int) or cpus <= 1:
        return None
    if str(resources.get("cpus_evidence") or "").strip():
        return None
    return Finding(
        id="cpu_declaration_unsupported",
        title=f"The plugin asks for {cpus} slots with no evidence that it uses them",
        confidence="possible",
        detail=(
            f"`-n`, `span[ptile=]` and $BDA_CPUS all derive from this one number, so the "
            f"scheduler reserved {cpus} cores. The registry row names no measurement or "
            "upstream thread flag supporting that, and a job holding cores it cannot use "
            "draws low-utilisation inspection."
        ),
        remedy=(
            "Either record the measurement in `cpus_evidence` on the plugin row, or "
            "reduce `cpus` to what the tool actually saturates."
        ),
        evidence=("runtime_spec.plugin_snapshot.resources.cpus",),
    )


def _rule_immediate_exit(evidence: dict[str, Any]) -> Finding | None:
    attempts = evidence.get("attempts") or []
    quick = [
        attempt
        for attempt in attempts
        if attempt.get("duration_seconds") is not None
        and attempt["duration_seconds"] <= IMMEDIATE_EXIT_SECONDS
        and attempt.get("status") in {"failed", "error"}
    ]
    if not quick:
        return None
    return Finding(
        id="immediate_exit",
        title="The job died before the model could have started",
        confidence="possible",
        detail=(
            f"Attempt(s) {', '.join(str(a.get('attempt_number')) for a in quick)} failed "
            f"within {IMMEDIATE_EXIT_SECONDS}s. That is too fast for the model to have "
            "run, so the cause is almost always the plugin declaration - image, command, "
            "entrypoint or runtime setup - rather than the input or the science."
        ),
        remedy=(
            "Preview the rendered script for this node, then check the plugin's image, "
            "command and runtime_setup against what the container actually provides."
        ),
        evidence=("attempts[].started_at", "attempts[].finished_at", "attempts[].status"),
    )


def _pattern_rule(
    rule_id: str,
    pattern_key: str,
    title: str,
    detail: str,
    remedy: str,
) -> Callable[[dict[str, Any]], Finding | None]:
    def check(evidence: dict[str, Any]) -> Finding | None:
        match = _PATTERNS[pattern_key].search(_errors(evidence))
        if match is None:
            return None
        return Finding(
            id=rule_id,
            title=title,
            confidence="confirmed",
            detail=f"{detail} The recorded error matches {match.group(0)!r}.",
            remedy=remedy,
            evidence=("error_message", "attempts[].error"),
        )

    return check


def _rule_repeated_failure(evidence: dict[str, Any]) -> Finding | None:
    attempts = [attempt for attempt in evidence.get("attempts") or [] if attempt.get("error")]
    if len(attempts) < 2:
        return None
    messages = {str(attempt["error"]).strip() for attempt in attempts}
    if len(messages) > 1:
        return None
    return Finding(
        id="repeated_identical_failure",
        title="Every attempt failed the same way",
        confidence="confirmed",
        detail=(
            f"{len(attempts)} attempts recorded an identical error. The failure is "
            "deterministic, so resubmitting the same specification reproduces it."
        ),
        remedy="Change the specification before the next submission; a retry alone will not help.",
        evidence=("attempts[].error",),
    )


def _rule_never_reached_scheduler(evidence: dict[str, Any]) -> Finding | None:
    if evidence.get("external_id"):
        return None
    if evidence.get("status") not in {"failed", "cancelled"}:
        return None
    return Finding(
        id="never_reached_backend",
        title="The job never received an external id",
        confidence="possible",
        detail=(
            "The compute backend never returned an identifier for this job, so it "
            "probably failed on submission rather than during execution. The transport "
            "(SSH to the cluster, or the Docker endpoint) is the first place to look."
        ),
        remedy=(
            "Check backend connectivity and credentials, then resubmit; recovery queries "
            "external state before resubmitting, so a job that did start will not be "
            "duplicated."
        ),
        evidence=("external_id", "status"),
    )


RULES: tuple[Rule, ...] = (
    Rule("pending_inputs_unresolved", _rule_pending_inputs),
    Rule("no_command_declared", _rule_no_command),
    Rule(
        "out_of_memory",
        _pattern_rule(
            "out_of_memory",
            "oom",
            "The job was killed for exceeding its memory",
            "Memory limits are enforced by the scheduler and by the GPU driver separately.",
            "Raise `memory_gb` on the plugin row, or reduce the batch/crop size the stage uses.",
        ),
    ),
    Rule(
        "walltime_exceeded",
        _pattern_rule(
            "walltime_exceeded",
            "timeout",
            "The job hit its run-time limit",
            "The work was still running when the limit expired; it did not fail on its own.",
            "Raise the stage's time limit, or split the input so one job does less.",
        ),
    ),
    Rule(
        "image_unavailable",
        _pattern_rule(
            "image_unavailable",
            "image",
            "The container image could not be obtained",
            "The runtime could not pull or find the declared image.",
            "Correct the image reference on the plugin row, or make the image available "
            "on the execution host; compute nodes here have no internet.",
        ),
    ),
    Rule(
        "input_file_missing",
        _pattern_rule(
            "input_file_missing",
            "missing_file",
            "A file the job expected was not there",
            "A staged input was absent at run time. A manifest check cannot catch this on "
            "its own: `sha256sum -c` verifies the files its manifest lists and is silent "
            "about one it never listed, which is why staged-input loops must also compare "
            "a count.",
            "Confirm the staging step wrote every declared input, and have the job compare "
            "the number of staged files against the number expected.",
        ),
    ),
    Rule(
        "checksum_mismatch",
        _pattern_rule(
            "checksum_mismatch",
            "checksum",
            "A staged file failed its checksum",
            "The bytes on the execution host are not the bytes that were staged.",
            "Re-stage the input. On macOS-created archives, check for `._*` sidecar files: "
            "they pass `sha256sum -c` and then trip the job's own file-count guard.",
        ),
    ),
    Rule(
        "permission_denied",
        _pattern_rule(
            "permission_denied",
            "permission",
            "The job was denied access to a path or device",
            "The execution account could not read or write something the stage needs.",
            "Check the staging directory's ownership and the account the job runs under.",
        ),
    ),
    Rule("immediate_exit", _rule_immediate_exit),
    Rule("gpu_forced_by_queue", _rule_gpu_queue),
    Rule("cpu_declaration_unsupported", _rule_cpu_evidence),
    Rule("repeated_identical_failure", _rule_repeated_failure),
    Rule("never_reached_backend", _rule_never_reached_scheduler),
)


def _duration(started: datetime | None, finished: datetime | None) -> float | None:
    if started is None or finished is None:
        return None
    left = started if started.tzinfo else started.replace(tzinfo=UTC)
    right = finished if finished.tzinfo else finished.replace(tzinfo=UTC)
    return round((right - left).total_seconds(), 1)


def collect_evidence(session: Session, project_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, Any]:
    """The recorded facts about one job, and nothing derived from them.

    Separated from `diagnose` so the rules can be exercised against a literal
    bundle in a test without a database, which is the only way to prove that a
    rule stays silent on evidence it does not read.
    """
    job = session.scalar(select(Job).where(Job.id == job_id))
    if job is None or job.project_id != project_id:
        raise DomainError("job_not_found", "No such job in this project.", status_code=404)

    attempts = list(
        session.scalars(
            select(JobAttempt)
            .where(JobAttempt.job_id == job.id)
            .order_by(JobAttempt.attempt_number.asc())
        )
    )
    events = list(
        session.scalars(
            select(JobEvent)
            .where(JobEvent.job_id == job.id)
            .order_by(JobEvent.created_at.desc())
            .limit(EVENT_LIMIT)
        )
    )
    spec = job.runtime_spec or {}
    manifest = spec.get("input_manifest") or {}
    snapshot = spec.get("plugin_snapshot") or {}
    return {
        "job_id": str(job.id),
        "status": job.status,
        "compute_backend": job.compute_backend,
        "model_plugin": job.model_plugin,
        "attempt_number": job.attempt_number,
        "external_id": job.external_id,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "queue": spec.get("queue"),
        "image": spec.get("image") or snapshot.get("image"),
        "command": spec.get("command") or snapshot.get("command"),
        "plugin_snapshot": {
            "key": snapshot.get("key"),
            "version": snapshot.get("version"),
            "resources": snapshot.get("resources") or {},
            "runtime_mode": snapshot.get("runtime_mode"),
        },
        "resolved_input_count": len(manifest.get("inputs") or []),
        "pending_inputs": list(manifest.get("pending_inputs") or []),
        "attempts": [
            {
                "attempt_number": attempt.attempt_number,
                "status": attempt.status,
                "error": attempt.error,
                "external_id": attempt.external_id,
                "duration_seconds": _duration(attempt.started_at, attempt.finished_at),
            }
            for attempt in attempts
        ],
        "recent_events": [
            {"event_type": event.event_type, "at": event.created_at.isoformat()}
            for event in events
        ],
    }


def diagnose(session: Session, project_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, Any]:
    evidence = collect_evidence(session, project_id, job_id)
    return {"evidence": evidence, **findings_for(evidence)}


def findings_for(evidence: dict[str, Any]) -> dict[str, Any]:
    findings = [finding for rule in RULES if (finding := rule.check(evidence)) is not None]
    confirmed = [finding for finding in findings if finding.confidence == "confirmed"]
    return {
        "findings": [finding.as_dict() for finding in findings],
        "summary": (
            f"{len(confirmed)} confirmed and {len(findings) - len(confirmed)} possible "
            f"cause(s) identified from the recorded evidence."
            if findings
            else (
                "The recorded evidence matches none of the known failure patterns. "
                "Do not infer a cause from this result; the job's own log is the next "
                "place to look."
            )
        ),
    }
