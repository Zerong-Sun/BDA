from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.config import get_settings
from ..core.problem import DomainError
from ..core.statuses import TERMINAL_JOB_STATUSES, JobStatus, WorkflowRunStatus
from ..identity.models import User
from ..projects.models import Project
from ..workflows.models import WorkflowNode, WorkflowRun
from ..workflows.repository import WorkflowRepository
from .binding import BindingError, resolve_artifact_bindings, resolve_pending_inputs
from .models import ComputeDraft, IdempotencyRecord, Job, JobSubmission
from .repository import ComputeRepository
from .schemas import ComputeDraftCreate, SubmissionCreate

TERMINAL_STATES = TERMINAL_JOB_STATUSES
ALLOWED_TRANSITIONS = {
    "pending": {"dispatching", "cancelled", "failed"},
    "dispatching": {"queued", "running", "failed", "cancelled"},
    "queued": {"running", "collecting", "failed", "cancelled"},
    "running": {"collecting", "failed", "cancelled"},
    "collecting": {"succeeded", "failed"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def create_compute_draft(session: Session, payload: ComputeDraftCreate, user: User) -> ComputeDraft:
    row = ComputeDraft(created_by=user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    return row


def confirm_draft(session: Session, row: ComputeDraft, project: Project, user: User) -> ComputeDraft:
    if row.status != "draft":
        return row
    row.status = "confirmed"
    row.version += 1
    from ..platform.operations import enqueue_operation

    enqueue_operation(
        session,
        topic="compute_draft.confirm",
        resource_type="compute_draft",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"draft_id": str(row.id)},
    )
    return row


def transition_job(session: Session, job: Job, next_status: JobStatus, *, payload: dict | None = None) -> Job:
    if next_status not in ALLOWED_TRANSITIONS.get(job.status, set()):
        raise DomainError(
            "invalid_job_transition",
            f"Job cannot transition from {job.status} to {next_status}",
            status_code=409,
        )
    job.status = next_status
    job.version += 1
    repo = ComputeRepository(session)
    repo.append_event(job, f"job.{next_status}", payload)
    if next_status in TERMINAL_STATES:
        # Every terminal state, not only success. Emitting on success alone left
        # every consumer to discover failure by polling: a campaign round whose
        # job died stayed "running" until another job in the same submission
        # happened to succeed, and an agent waiting on the job slept forever.
        repo.enqueue("job.settled", job.id, {"job_id": str(job.id), "status": next_status})
    _mirror_status_onto_node(session, job)
    return job


def _mirror_status_onto_node(session: Session, job: Job) -> None:
    """Copy a job's status onto the workflow node it ran for.

    The column existed but nothing ever wrote it, so every node read as 'draft' forever:
    the canvas showed no progress, and the Copilot's project context told the model that
    finished work had not started. Only the newest attempt may write, so a retry is not
    overwritten by the failed attempt it replaced.
    """
    node = session.get(WorkflowNode, job.workflow_node_id)
    if node is None:
        return
    newest_attempt = session.scalar(
        select(func.max(Job.attempt_number)).where(Job.workflow_node_id == job.workflow_node_id)
    )
    if newest_attempt is not None and job.attempt_number < newest_attempt:
        return
    if node.status == job.status and node.error_message == job.error_message:
        return
    node.status = job.status
    node.error_message = job.error_message
    node.version += 1


def _record_lineage(session: Session, workflow: WorkflowRun, nodes: list[WorkflowNode]) -> None:
    """State what this run changed relative to the one it is compared against.

    Computed at submission rather than when the link is drawn, because the parameters can
    still be edited afterwards; what matters is the diff at the moment the run actually
    happened. The author declares the ancestor, the platform decides what differs - so a
    "single-variable control" is an observation about the record, not an assertion in it.
    """
    from ..workflows.lineage import arm_label_for, diff_parameters

    baseline = session.get(WorkflowRun, workflow.derived_from_id) if workflow.derived_from_id else None
    if baseline is None:
        differences: dict[str, dict] = {}
    else:
        baseline_nodes = WorkflowRepository(session).nodes(baseline.id)
        differences = diff_parameters(
            {node.node_key: dict(node.parameters or {}) for node in baseline_nodes},
            {node.node_key: dict(node.parameters or {}) for node in nodes},
        )
    workflow.varied_parameters = differences
    workflow.arm_label = arm_label_for(baseline, differences)


def _payload_hash(workflow_id: uuid.UUID, payload: SubmissionCreate) -> str:
    canonical = json.dumps(
        {"workflow_id": str(workflow_id), **payload.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_submission(
    session: Session,
    *,
    workflow: WorkflowRun,
    project: Project,
    payload: SubmissionCreate,
    idempotency_key: str,
    user: User,
) -> tuple[JobSubmission, list[Job]]:
    repo = ComputeRepository(session)
    scope = f"workflow:{workflow.id}:submit"
    digest = _payload_hash(workflow.id, payload)
    existing = repo.idempotency(user.id, scope, idempotency_key)
    if existing:
        if existing.request_hash != digest:
            raise DomainError(
                "idempotency_conflict", "Idempotency-Key was already used with another payload", status_code=409
            )
        submission = repo.submission(existing.resource_id)
        if submission is None:
            raise DomainError(
                "idempotency_corrupt", "Idempotency record refers to a missing submission", status_code=500
            )
        return submission, repo.jobs_for_submission(submission.id)

    nodes = WorkflowRepository(session).nodes(workflow.id)
    if not nodes:
        raise DomainError("workflow_empty", "Workflow has no executable nodes", status_code=409)
    _record_lineage(session, workflow, nodes)
    settings = get_settings()
    backend = payload.compute_backend or settings.compute_backend
    if settings.is_production and backend == "demo":
        raise DomainError("demo_compute_forbidden", "Demo compute cannot run in production", status_code=409)
    # Refuse LSF before doing any work when no cluster is configured; the deployment
    # really can have an empty host, and failing at dispatch instead wastes a submission.
    if backend == "lsf" and not ((settings.lsf_ssh_host or "").strip() and (settings.lsf_remote_root or "").strip()):
        raise DomainError(
            "lsf_not_configured",
            "LSF compute requires a configured SSH host and remote root",
            status_code=409,
        )
    # Enforce the same readiness checks the preflight endpoint reports. Submitting past
    # a known blocker is how unvalidated commands used to reach the cluster.
    from ..workflows.preflight import evaluate_preflight

    blockers, _, _ = evaluate_preflight(session, workflow)
    if blockers:
        raise DomainError(
            "workflow_preflight_failed",
            "Workflow is not ready to submit",
            status_code=409,
            errors=blockers,
        )
    submission = JobSubmission(
        workflow_run_id=workflow.id,
        project_id=project.id,
        created_by=user.id,
        compute_backend=backend,
    )
    session.add(submission)
    session.flush()
    timeout_at = datetime.now(UTC) + timedelta(minutes=payload.timeout_minutes)
    jobs = []
    for node in nodes:
        # Manual stages are part of the route but are not run here, so they get no job.
        # Creating one would dispatch an empty command and report a human review step as a
        # failed cluster job.
        if getattr(node, "execution_mode", "dispatch") == "manual":
            continue
        plugin_snapshot = None
        plugin = None
        if node.model_plugin_id:
            from ..registry.models import ModelPlugin

            plugin = session.get(ModelPlugin, node.model_plugin_id)
            if plugin is None or not plugin.enabled:
                raise DomainError(
                    "plugin_unavailable", "Workflow references an unavailable model plugin", status_code=409
                )
            plugin_snapshot = {
                "id": str(plugin.id),
                "key": plugin.plugin_key,
                "version": plugin.plugin_version,
                "image": plugin.container_image,
                "command": plugin.command,
                "parameter_schema": plugin.parameter_schema,
                "output_schema": plugin.output_schema,
                "input_ports": plugin.input_ports,
                "output_ports": plugin.output_ports,
                "resources": plugin.resources,
                "runtime_mode": plugin.runtime_mode,
                "output_parser": plugin.output_parser,
                "input_adapter": plugin.input_adapter,
                "runtime_setup": plugin.runtime_setup,
            }
            plugin_snapshot["checksum_sha256"] = hashlib.sha256(
                json.dumps(plugin_snapshot, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        try:
            resolved_inputs, pending_inputs = resolve_artifact_bindings(
                session, node=node, plugin=plugin, project_id=project.id
            )
        except BindingError as exc:
            raise DomainError(
                "input_binding_unsatisfied",
                "Workflow inputs could not be resolved",
                status_code=409,
                errors=exc.blockers,
            ) from exc
        job = Job(
            submission_id=submission.id,
            workflow_run_id=workflow.id,
            workflow_node_id=node.id,
            project_id=project.id,
            compute_backend=backend,
            model_plugin=node.model_plugin,
            timeout_at=timeout_at,
            runtime_spec={
                "parameters": node.parameters,
                "node_key": node.node_key,
                "image": node.container_image,
                # The plugin owns the command; a node created through the UI never carries
                # one, and dispatching that as an empty command ran `true` instead of the
                # model. Same precedence as the preview endpoint, so what a scientist
                # reviewed is what runs.
                "command": (plugin.command if plugin else None) or node.command,
                "queue": node.queue,
                "plugin_snapshot": plugin_snapshot,
                "manifest_version": "1",
                "input_manifest": {
                    "schema_version": "1",
                    "parameters": node.parameters,
                    "inputs": resolved_inputs,
                    "pending_inputs": pending_inputs,
                },
            },
        )
        session.add(job)
        session.flush()
        job.runtime_spec = {
            **job.runtime_spec,
            "input_manifest_key": f"jobs/{job.id}/attempt-1/input-manifest.json",
            "output_manifest_key": f"jobs/{job.id}/attempt-1/output-manifest.json",
        }
        repo.append_event(job, "job.pending")
        _mirror_status_onto_node(session, job)
        jobs.append(job)
    schedule_ready_jobs(session, submission, workflow)
    session.add(
        IdempotencyRecord(
            actor_id=user.id,
            scope=scope,
            key=idempotency_key,
            request_hash=digest,
            resource_id=submission.id,
        )
    )
    set_workflow_status(workflow, "queued")
    record_audit(
        session,
        action="workflow.submit",
        entity_type="job_submission",
        entity_id=submission.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={"job_count": len(jobs), "compute_backend": backend},
    )
    return submission, jobs


def schedule_ready_jobs(session: Session, submission: JobSubmission, workflow: WorkflowRun) -> None:
    """Enqueue dependency-ready nodes and fail descendants blocked by terminal parents."""
    repo = ComputeRepository(session)
    by_key = {key: job for job, key in repo.jobs_and_node_keys(submission.id)}
    dependencies: dict[str, set[str]] = {key: set() for key in by_key}
    for edge in workflow.graph.get("edges", []):
        source, target = edge.get("source"), edge.get("target")
        if source in by_key and target in dependencies:
            dependencies[target].add(source)

    changed = True
    while changed:
        changed = False
        for key, job in by_key.items():
            if job.status != "pending":
                continue
            parents = [by_key[parent] for parent in dependencies[key]]
            if any(parent.status in {"failed", "cancelled"} for parent in parents):
                job.error_code = "upstream_failed"
                transition_job(session, job, "failed")
                changed = True
            elif all(parent.status == "succeeded" for parent in parents) and not repo.has_outbox_event(
                "job.dispatch", job.id
            ):
                if not _bind_upstream_inputs(session, job, dependencies[key], by_key):
                    changed = True
                    continue
                repo.enqueue("job.dispatch", job.id, {"job_id": str(job.id)})

    statuses = {job.status for job in by_key.values()}
    if statuses == {"succeeded"}:
        submission.status = "succeeded"
        set_workflow_status(workflow, "succeeded")
    elif statuses and statuses <= TERMINAL_STATES:
        outcome: Literal["failed", "cancelled"] = "failed" if "failed" in statuses else "cancelled"
        submission.status = outcome
        set_workflow_status(workflow, outcome)
    elif any(status in {"dispatching", "queued", "running", "collecting"} for status in statuses):
        submission.status = "running"
        set_workflow_status(workflow, "running")


def set_workflow_status(workflow: WorkflowRun, status: WorkflowRunStatus) -> None:
    """Move a run to a new status and bump its version.

    The version is the ETag (see core.etag), so a background transition that left it
    untouched made the ETag stop describing the resource it labels: a client holding a
    pre-submit ETag still satisfied If-Match after the run had already finished.
    """
    if workflow.status == status:
        return
    workflow.status = status
    workflow.version += 1


DEFAULT_JOB_TIMEOUT = timedelta(minutes=180)


def _original_timeout(job: Job) -> timedelta:
    """The wall-clock budget the job was originally granted."""
    if job.timeout_at is None:
        return DEFAULT_JOB_TIMEOUT
    created = job.created_at
    deadline = job.timeout_at
    if created is None:
        return DEFAULT_JOB_TIMEOUT
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    budget = deadline - created
    return budget if budget > timedelta(minutes=5) else DEFAULT_JOB_TIMEOUT


def _bind_upstream_inputs(
    session: Session, job: Job, parent_keys: set[str], by_key: dict[str, Job]
) -> bool:
    """Fold succeeded parents' outputs into ``job``'s input manifest.

    Returns False (and fails the job) when a declared upstream binding produced nothing,
    so a downstream model never silently runs without the data it was wired to consume.
    """
    manifest = dict(job.runtime_spec.get("input_manifest") or {})
    pending = list(manifest.get("pending_inputs") or [])
    if not pending:
        return True

    repo = ComputeRepository(session)
    produced = {key: repo.produced_artifacts(by_key[key].id) for key in parent_keys}
    plugin = _job_plugin(session, job)
    resolved, unresolved = resolve_pending_inputs(pending=pending, produced=produced, plugin=plugin)

    if unresolved:
        job.error_code = "upstream_output_missing"
        job.error_message = "; ".join(
            f"{item['from_node']}.{item['from_port']} produced no artifact for input '{item['port']}'"
            for item in unresolved
        )[:2000]
        transition_job(session, job, "failed")
        return False

    manifest["inputs"] = [*manifest.get("inputs", []), *resolved]
    manifest["pending_inputs"] = []
    job.runtime_spec = {**job.runtime_spec, "input_manifest": manifest}
    return True


def _job_plugin(session: Session, job: Job):
    """Reload the plugin a job was submitted against, for its port declarations."""
    snapshot = job.runtime_spec.get("plugin_snapshot")
    if not isinstance(snapshot, dict) or not snapshot.get("id"):
        return None
    from ..registry.models import ModelPlugin

    return session.get(ModelPlugin, uuid.UUID(str(snapshot["id"])))


def request_cancel(session: Session, job: Job, project: Project, user: User) -> Job:
    if job.status in TERMINAL_STATES:
        return job
    ComputeRepository(session).enqueue("job.cancel", job.id, {"job_id": str(job.id)})
    record_audit(
        session,
        action="job.cancel.request",
        entity_type="job",
        entity_id=job.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return job


def retry_job(session: Session, job: Job, project: Project, user: User) -> Job:
    if job.status not in {"failed", "cancelled"}:
        raise DomainError("job_not_retryable", "Only failed or cancelled jobs can be retried", status_code=409)
    attempt_number = job.attempt_number + 1
    runtime_spec = {**job.runtime_spec}
    retry = Job(
        submission_id=job.submission_id,
        workflow_run_id=job.workflow_run_id,
        workflow_node_id=job.workflow_node_id,
        project_id=job.project_id,
        status="pending",
        compute_backend=job.compute_backend,
        model_plugin=job.model_plugin,
        attempt_number=attempt_number,
        # Inherit the original submission's budget rather than silently granting a
        # different one; a retry is the same work, not a new request.
        timeout_at=datetime.now(UTC) + _original_timeout(job),
        runtime_spec=runtime_spec,
    )
    session.add(retry)
    session.flush()
    retry.runtime_spec = {
        **runtime_spec,
        "input_manifest_key": f"jobs/{retry.id}/attempt-{attempt_number}/input-manifest.json",
        "output_manifest_key": f"jobs/{retry.id}/attempt-{attempt_number}/output-manifest.json",
    }
    repo = ComputeRepository(session)
    repo.append_event(retry, "job.pending", {"retry_of": str(job.id), "requested_by": str(user.id)})
    _mirror_status_onto_node(session, retry)
    submission = repo.submission(job.submission_id)
    workflow = WorkflowRepository(session).get(job.workflow_run_id)
    if submission and workflow:
        schedule_ready_jobs(session, submission, workflow)
    record_audit(
        session,
        action="job.retry",
        entity_type="job",
        entity_id=retry.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={"retry_of": str(job.id), "attempt_number": retry.attempt_number},
    )
    return retry
