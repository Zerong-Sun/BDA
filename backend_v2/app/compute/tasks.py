"""Job lifecycle tasks and the transactional outbox publisher.

This module used to hold roughly forty tasks spanning every domain in the application,
which is why ``compute`` imported all nineteen of its siblings and needed dozens of
function-local imports to break the resulting cycles. Each domain now owns its own
``tasks`` module; see ``core.celery_app.TASK_MODULES``.

``celery_app`` is re-exported here because ``-A backend_v2.app.compute.tasks.celery_app``
is the documented worker entry point in Compose, Helm and the runbooks.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact, ArtifactLineageEdge, ArtifactUpload
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.config import get_settings
from ..core.database import SessionFactory, session_scope
from ..core.metrics import (
    ARTIFACT_CHECKSUM_FAILURES,
    JOB_QUEUE_LAG_SECONDS,
    LSF_FAILURES,
    OUTBOX_BACKLOG,
    OUTBOX_DEAD_LETTERED,
    STUCK_OPERATIONS,
)
from ..platform.models import Operation
from ..projects.models import Project
from ..registry.ports import output_port_for_artifact, parse_output_ports
from ..workflows.models import WorkflowNode, WorkflowRun
from ..workflows.repository import WorkflowRepository
from .adapters import RuntimeJob, adapter_for
from .models import Job, JobAttempt, JobSubmission, OutboxEvent
from .repository import ComputeRepository
from .service import TERMINAL_STATES, _mirror_status_onto_node, schedule_ready_jobs, transition_job

if TYPE_CHECKING:  # imported lazily at runtime to avoid a circular import
    from ..candidates.models import Candidate
    from .parsers import ParsedMetric

settings = get_settings()

__all__ = ["celery_app"]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _runtime(job: Job) -> RuntimeJob:
    return RuntimeJob(
        id=job.id,
        attempt_number=job.attempt_number,
        model_plugin=job.model_plugin,
        runtime_spec=job.runtime_spec,
    )


def _apply_input_adapter(session: Session, job: Job) -> dict:
    """Let the plugin synthesise inputs it needs but a workflow cannot bind directly.

    Runs at dispatch rather than inside an adapter so it applies to every compute backend
    and needs nothing installed on the cluster.
    """
    from .input_adapters import AdapterContext, get_input_adapter

    spec = dict(job.runtime_spec)
    snapshot = spec.get("plugin_snapshot")
    name = snapshot.get("input_adapter") if isinstance(snapshot, dict) else None
    adapter = get_input_adapter(name)
    if adapter is None:
        return spec

    manifest = dict(spec.get("input_manifest") or {})
    raw_inputs = manifest.get("inputs")
    inputs: list = raw_inputs if isinstance(raw_inputs, list) else []
    storage = ObjectStorage()
    result = adapter(
        AdapterContext(
            job_id=job.id,
            project_id=job.project_id,
            attempt_number=job.attempt_number,
            inputs=inputs,
            parameters=manifest.get("parameters") or {},
            read_bytes=lambda key: storage.read_bytes(key, max_bytes=32 * 1024 * 1024),
            job_name=str(spec.get("node_key") or ""),
        )
    )
    if result.warnings:
        ComputeRepository(session).append_event(job, "job.input_adapter", {"warnings": result.warnings})
    if not result.generated:
        return spec

    generated_entries = []
    for item in result.generated:
        object_key = f"jobs/{job.id}/attempt-{job.attempt_number}/generated/{item.filename}"
        storage.put_bytes(object_key, item.content, item.content_type)
        generated_entries.append(
            {
                "port": item.port,
                "artifact_id": None,
                "filename": item.filename,
                "object_key": object_key,
                "content_type": item.content_type,
                "checksum_sha256": hashlib.sha256(item.content).hexdigest(),
                "size_bytes": len(item.content),
                "generated_by": name,
            }
        )
    manifest["inputs"] = [*inputs, *generated_entries]
    spec["input_manifest"] = manifest
    return spec


def _manifest_ttl_seconds(job: Job) -> int:
    """How long the job's input URLs must stay valid.

    Measured from dispatch to the job's own deadline, so a job that sits in an LSF queue
    for hours can still fetch its inputs when it finally starts. Bounded by the S3
    presigned-URL maximum of seven days.
    """
    deadline = _as_utc(job.timeout_at) if job.timeout_at else None
    remaining = int((deadline - datetime.now(UTC)).total_seconds()) if deadline else 0
    return max(get_settings().upload_url_ttl_seconds, min(remaining + 3600, 7 * 24 * 3600))


def _manifest_with_urls(manifest: dict, ttl_seconds: int) -> dict:
    """Attach freshly minted download URLs to each manifest input."""
    storage = ObjectStorage()
    raw = manifest.get("inputs")
    inputs: list = raw if isinstance(raw, list) else []
    return {
        **manifest,
        "inputs": [
            {**item, "url": storage.download_url(str(item["object_key"]), ttl_seconds=ttl_seconds)}
            for item in inputs
            if isinstance(item, dict) and item.get("object_key")
        ],
    }


def _resolved_output_port(job: Job, output: dict) -> str | None:
    """Name the output port a collected file belongs to.

    Trusts the runner's explicit ``port`` when present, otherwise reverse-looks-up the
    plugin's declared output ports by artifact_type and filename.
    """
    if output.get("port"):
        return str(output["port"])
    snapshot = job.runtime_spec.get("plugin_snapshot")
    if not isinstance(snapshot, dict):
        return None
    port = output_port_for_artifact(
        parse_output_ports(snapshot.get("output_ports")), output["artifact_type"], output["filename"]
    )
    return port.name if port else None


def _input_artifact_ids(runtime_spec: dict) -> set[uuid.UUID]:
    identifiers: set[uuid.UUID] = set()
    manifest = runtime_spec.get("input_manifest")
    inputs = manifest.get("inputs", []) if isinstance(manifest, dict) else []
    for item in inputs:
        if not isinstance(item, dict) or not item.get("artifact_id"):
            continue
        try:
            identifiers.add(uuid.UUID(str(item["artifact_id"])))
        except ValueError:
            continue
    return identifiers


MAX_OUTBOX_ATTEMPTS = 12


MAX_OUTBOX_BACKOFF_SECONDS = 300


def _defer_event(event: OutboxEvent, reason: str) -> None:
    """Back an undeliverable event off, and dead-letter it once attempts run out.

    Every failure path goes through here so none of them can reintroduce an event that
    stays permanently at the head of the queue.
    """
    now = datetime.now(UTC)
    event.attempts += 1
    event.last_error = reason[:1000]
    if event.attempts >= MAX_OUTBOX_ATTEMPTS:
        event.dead_lettered_at = now
        return
    event.available_at = now + timedelta(seconds=min(MAX_OUTBOX_BACKOFF_SECONDS, 2**event.attempts))


@celery_app.task(name="bda_v2.publish_outbox")
def publish_outbox(batch_size: int = 100) -> dict:
    published = 0
    with session_scope() as session:
        events = list(
            session.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.published_at.is_(None),
                    OutboxEvent.dead_lettered_at.is_(None),
                    OutboxEvent.available_at <= datetime.now(UTC),
                )
                .order_by(OutboxEvent.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        # topic -> the task, or the tasks, that consume it. A tuple is a genuine
        # fan-out: `job.settled` is read by campaigns and by the copilot's agent
        # runs, and neither is the other's business.
        topic_tasks: dict[str, str | tuple[str, ...]] = {
            "job.dispatch": "bda_v2.dispatch_job",
            "job.cancel": "bda_v2.cancel_job",
            "job.collect": "bda_v2.collect_job",
            "delivery.build": "bda_v2.delivery_build",
            "literature.ingest": "bda_v2.literature_ingest",
            "literature.search": "bda_v2.literature_search",
            "literature.subscription.run": "bda_v2.subscription_run",
            "intelligence.run": "bda_v2.intelligence_run",
            "intelligence.export": "bda_v2.intelligence_export",
            "copilot.respond": "bda_v2.copilot_respond",
            "copilot.agent_step": "bda_v2.copilot_agent_step",
            "project.prompt_generate": "bda_v2.project_prompt_generate",
            "research.generate": "bda_v2.research_generate",
            "research.gaps.resolve": "bda_v2.research_gaps_resolve",
            "research.decision_tree_draft": "bda_v2.research_decision_tree_draft",
            "ligand.import": "bda_v2.ligand_import",
            "compute_draft.confirm": "bda_v2.compute_draft_confirm",
            "autopilot.execute": "bda_v2.autopilot_execute",
            "autopilot.cancel": "bda_v2.autopilot_cancel",
            "experiment_results.import": "bda_v2.experiment_results_import",
            "target.structure.import": "bda_v2.target_structure_import",
            "target.structure.prepare": "bda_v2.target_structure_prepare",
            # Retained so events written by a previous release still drain during a
            # rolling deploy; nothing produces this topic any more.
            "job.succeeded": "bda_v2.campaign_advance",
            "job.settled": ("bda_v2.campaign_advance", "bda_v2.copilot_agent_task_settled"),
            "operation.settled": "bda_v2.copilot_agent_operation_settled",
            "campaign.evaluate": "bda_v2.campaign_evaluate",
            "literature.relations.detect": "bda_v2.literature_relations_detect",
            "registry.model_plugin.validate": "bda_v2.registry_model_plugin_validate",
            "registry.compute_node.health": "bda_v2.registry_compute_node_health",
            "registry.server.test": "bda_v2.registry_server_test",
        }
        for event in events:
            subscribers = topic_tasks.get(event.topic)
            if subscribers is None:
                # A worker that predates the topic, which is what a rolling deploy or a
                # rollback produces. Backing off matters more than the individual event:
                # this branch used to leave available_at alone, so the row was re-read
                # every tick and eventually filled the batch, starving every real event.
                _defer_event(event, f"unknown_topic:{event.topic}")
                continue
            operation = session.get(Operation, event.id)
            project_id = event.payload.get("project_id")
            if not project_id and operation is not None and operation.project_id is not None:
                project_id = str(operation.project_id)
            if not project_id and event.topic.startswith("job."):
                project_id = session.scalar(select(Job.project_id).where(Job.id == event.aggregate_id))
            project_scoped = not event.topic.startswith("registry.")
            if project_scoped and not project_id:
                _defer_event(event, "missing_project_context")
                continue
            try:
                args: list[object] = [str(event.aggregate_id)]
                if event.topic in {"target.structure.import", "research.gaps.resolve"}:
                    args.append(event.payload)
                elif event.topic == "experiment_results.import":
                    args.append(bool(event.payload.get("dry_run")))
                names = (subscribers,) if isinstance(subscribers, str) else subscribers
                message_headers = {"bda_project_id": str(project_id)} if project_id else None
                for index, task_name in enumerate(names):
                    # The first subscriber keeps the event id, because an Operation
                    # row is keyed on it. Any further subscriber gets a task id
                    # derived from that same id, so redelivery of the event still
                    # deduplicates per subscriber instead of colliding between them.
                    task_id = str(event.id) if index == 0 else str(uuid.uuid5(event.id, task_name))
                    celery_app.send_task(task_name, args=args, task_id=task_id, headers=message_headers)
                event.published_at = datetime.now(UTC)
                if operation is not None and operation.status == "pending":
                    operation.status = "queued"
                    operation.version += 1
                published += 1
            except Exception as exc:
                _defer_event(event, str(exc))
    with SessionFactory() as session:
        backlog = session.scalar(
            select(sa.func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None), OutboxEvent.dead_lettered_at.is_(None))
        )
        dead = session.scalar(
            select(sa.func.count()).select_from(OutboxEvent).where(OutboxEvent.dead_lettered_at.is_not(None))
        )
    OUTBOX_BACKLOG.set(backlog or 0)
    OUTBOX_DEAD_LETTERED.set(dead or 0)
    return {"published": published, "backlog": backlog or 0, "dead_lettered": dead or 0}


@celery_app.task(name="bda_v2.dispatch_job", bind=True, max_retries=5)
def dispatch_job(self, job_id: str) -> dict:
    parsed = uuid.UUID(job_id)
    with session_scope() as session:
        job = ComputeRepository(session).job(parsed, for_update=True)
        if job is None or job.status in TERMINAL_STATES:
            return {"job_id": job_id, "status": "ignored"}
        if job.external_id:
            return {"job_id": job_id, "status": job.status, "external_id": job.external_id}
        if job.status == "pending":
            transition_job(session, job, "dispatching")
        attempt = session.scalar(
            select(JobAttempt).where(
                JobAttempt.job_id == job.id,
                JobAttempt.attempt_number == job.attempt_number,
            )
        )
        if attempt is None:
            session.add(JobAttempt(job_id=job.id, attempt_number=job.attempt_number, status="dispatching"))
        manifest_ttl = _manifest_ttl_seconds(job)
        spec = _apply_input_adapter(session, job)
        job.runtime_spec = {**spec, "manifest_ttl_seconds": manifest_ttl}
        runtime = _runtime(job)
        backend = job.compute_backend
    try:
        adapter = adapter_for(backend)
        # Only mint presigned URLs when the runner actually fetches them. Under ssh
        # staging the adapter copies inputs onto the cluster and writes its own manifest
        # there, so publishing long-lived credentials to object storage is pure exposure.
        if getattr(adapter, "staging_mode", None) != "ssh":
            ObjectStorage().put_json(
                str(runtime.runtime_spec["input_manifest_key"]),
                _manifest_with_urls(runtime.runtime_spec["input_manifest"], manifest_ttl),
            )
        external_id = adapter.ensure_submitted(runtime)
    except Exception as exc:
        if backend == "lsf":
            LSF_FAILURES.labels("dispatch").inc()
        if self.request.retries >= self.max_retries:
            with session_scope() as session:
                failed = ComputeRepository(session).job(parsed, for_update=True)
                if failed and failed.status == "dispatching":
                    failed.error_code = "dispatch_failed"
                    failed.error_message = str(exc)[:2000]
                    transition_job(session, failed, "failed")
                    _advance_submission(session, failed)
            raise
        raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1))) from exc
    with session_scope() as session:
        job = ComputeRepository(session).job(parsed, for_update=True)
        if job is None:
            return {"job_id": job_id, "status": "missing"}
        if not job.external_id:
            job.external_id = external_id
            transition_job(session, job, "queued", payload={"external_id": external_id})
            job.next_poll_at = datetime.now(UTC) + timedelta(seconds=5)
    return {"job_id": job_id, "status": "queued", "external_id": external_id}


@celery_app.task(name="bda_v2.reap_stale_jobs")
def reap_stale_jobs(batch_size: int = 200) -> dict:
    """Fail jobs that blew past their deadline in a state nothing else polls.

    poll_job only enforces timeouts for jobs in 'queued'/'running'. A job that dies in
    'dispatching' or 'collecting' - because the worker was killed mid-collection, say -
    is otherwise stuck forever and blocks its whole submission.
    """
    now = datetime.now(UTC)
    reaped = []
    with session_scope() as session:
        jobs = list(
            session.scalars(
                select(Job)
                .where(Job.status.not_in(TERMINAL_STATES), Job.timeout_at.is_not(None), Job.timeout_at <= now)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            job.error_code = "job_timeout"
            job.error_message = f"Job exceeded its deadline while in '{job.status}'"
            transition_job(session, job, "failed")
            _advance_submission(session, job)
            reaped.append(str(job.id))
    return {"reaped": len(reaped), "job_ids": reaped}


@celery_app.task(name="bda_v2.poll_due_jobs")
def poll_due_jobs(batch_size: int = 100) -> dict:
    queued = 0
    now = datetime.now(UTC)
    with session_scope() as session:
        jobs = list(
            session.scalars(
                select(Job)
                .where(Job.status.in_(["queued", "running"]), Job.next_poll_at <= now)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            celery_app.send_task(
                "bda_v2.poll_job",
                args=[str(job.id)],
                queue="poll",
                headers={"bda_project_id": str(job.project_id)},
            )
            job.next_poll_at = now + timedelta(seconds=15)
            queued += 1
    return {"queued": queued}


@celery_app.task(name="bda_v2.poll_job", bind=True, max_retries=5)
def poll_job(self, job_id: str) -> dict:
    parsed = uuid.UUID(job_id)
    with SessionFactory() as session:
        job = ComputeRepository(session).job(parsed)
        if job is None or job.status in TERMINAL_STATES or not job.external_id:
            return {"job_id": job_id, "status": "ignored"}
        runtime, backend, external_id = _runtime(job), job.compute_backend, job.external_id
    try:
        live = adapter_for(backend).status(runtime, external_id)
    except Exception as exc:
        if backend == "lsf":
            LSF_FAILURES.labels("poll").inc()
        raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1))) from exc
    with session_scope() as session:
        job = ComputeRepository(session).job(parsed, for_update=True)
        if job is None or job.status in TERMINAL_STATES:
            return {"job_id": job_id, "status": "ignored"}
        if job.timeout_at and _as_utc(job.timeout_at) <= datetime.now(UTC):
            job.error_code = "job_timeout"
            transition_job(session, job, "failed")
            _advance_submission(session, job)
        elif live.status == "running" and job.status == "queued":
            transition_job(session, job, "running")
        elif live.status == "succeeded" and job.status in {"queued", "running"}:
            transition_job(session, job, "collecting")
            ComputeRepository(session).enqueue(
                "job.collect",
                job.id,
                project_id=job.project_id,
            )
        elif live.status == "failed":
            job.error_code = "compute_failed"
            job.error_message = live.error
            transition_job(session, job, "failed")
            _advance_submission(session, job)
        else:
            # Non-terminal: 'queued', or 'unknown' when the backend cannot answer. Keep
            # polling and let the timeout_at guard above end it, rather than resolving a
            # job here on no evidence.
            job.next_poll_at = datetime.now(UTC) + timedelta(seconds=15)
        current_status = job.status
    return {"job_id": job_id, "status": current_status}


@celery_app.task(name="bda_v2.collect_job", bind=True, max_retries=3)
def collect_job(self, job_id: str) -> dict:
    parsed = uuid.UUID(job_id)
    with SessionFactory() as session:
        job = ComputeRepository(session).job(parsed)
        if job is None or job.status != "collecting" or not job.external_id:
            return {"job_id": job_id, "status": "ignored"}
        runtime, backend, external_id = _runtime(job), job.compute_backend, job.external_id
    try:
        outputs = adapter_for(backend).collect(runtime, external_id)
        storage = ObjectStorage()
        verified = []
        for output in outputs:
            size, checksum = storage.inspect_and_hash(output["object_key"])
            if size != output["size_bytes"] or checksum.lower() != output["checksum_sha256"]:
                raise ValueError("collect_output_checksum_mismatch")
            verified.append(output)
    except Exception as exc:
        if "checksum" in str(exc).lower():
            ARTIFACT_CHECKSUM_FAILURES.labels("compute_output").inc()
        if backend == "lsf":
            LSF_FAILURES.labels("collect").inc()
        if self.request.retries >= self.max_retries:
            with session_scope() as session:
                failed = ComputeRepository(session).job(parsed, for_update=True)
                if failed and failed.status == "collecting":
                    failed.error_code = "collect_failed"
                    failed.error_message = str(exc)[:2000]
                    transition_job(session, failed, "failed")
                    _advance_submission(session, failed)
            raise
        raise self.retry(exc=exc, countdown=10) from exc
    with session_scope() as session:
        job = ComputeRepository(session).job(parsed, for_update=True)
        if job and job.status == "collecting":
            submission = session.get(JobSubmission, job.submission_id)
            if submission is None:
                raise RuntimeError("job_submission_missing")
            artifacts = _persist_outputs(session, job, submission, verified)
            _apply_parsed_outputs(session, job, submission, verified, artifacts)
            transition_job(
                session, job, "succeeded", payload={"artifact_ids": [str(item.id) for item in artifacts]}
            )
            # The terminal event is emitted by `transition_job` for every terminal
            # state, so success no longer needs its own enqueue here.
            _advance_submission(session, job)
    return {"job_id": job_id, "status": "succeeded", "outputs": outputs}


@celery_app.task(name="bda_v2.collect_operational_metrics")
def collect_operational_metrics() -> dict:
    """Refresh gauges whose values live in PostgreSQL rather than one process."""
    now = datetime.now(UTC)
    lags: dict[str, float] = {backend: 0.0 for backend in ("docker", "lsf", "demo")}
    with SessionFactory() as session:
        rows = session.execute(
            select(Job.compute_backend, sa.func.min(Job.created_at))
            .where(Job.status.in_(["pending", "dispatching", "queued"]))
            .group_by(Job.compute_backend)
        )
        for backend, oldest in rows:
            if oldest is not None:
                lags[str(backend)] = max(0.0, (now - _as_utc(oldest)).total_seconds())
        stuck = int(
            session.scalar(
                select(sa.func.count(Operation.id)).where(
                    Operation.status.in_(["pending", "running", "cancel_requested"]),
                    Operation.updated_at <= now - timedelta(minutes=15),
                )
            )
            or 0
        )
    for backend, seconds in lags.items():
        JOB_QUEUE_LAG_SECONDS.labels(backend).set(seconds)
    STUCK_OPERATIONS.set(stuck)
    return {"queue_lag_seconds": lags, "stuck_operations": stuck}


def _persist_outputs(session: Session, job: Job, submission: JobSubmission, verified: list[dict]) -> list[Artifact]:
    """Register collected files as artifacts and link them to the job's inputs."""
    input_artifacts = list(
        session.scalars(
            select(Artifact).where(
                Artifact.id.in_(_input_artifact_ids(job.runtime_spec)),
                Artifact.project_id == job.project_id,
                Artifact.deleted_at.is_(None),
            )
        )
    )
    artifacts: list[Artifact] = []
    for output in verified:
        artifact = Artifact(
            project_id=job.project_id,
            created_by=submission.created_by,
            artifact_type=output["artifact_type"],
            filename=output["filename"],
            content_type=output["content_type"],
            object_key=output["object_key"],
            size_bytes=output["size_bytes"],
            checksum_sha256=output["checksum_sha256"],
            lineage={
                "job_id": str(job.id),
                "attempt": job.attempt_number,
                "external_id": job.external_id,
                # Recorded so a downstream node bound to this output port can find
                # exactly these artifacts (see compute/binding.py).
                "output_port": _resolved_output_port(job, output),
                "metadata": output["metadata"],
            },
        )
        session.add(artifact)
        session.flush()
        session.add_all(
            [
                ArtifactLineageEdge(
                    project_id=job.project_id,
                    parent_artifact_id=parent.id,
                    child_artifact_id=artifact.id,
                    relation="compute_input",
                    details={"job_id": str(job.id), "attempt": job.attempt_number},
                )
                for parent in input_artifacts
            ]
        )
        artifacts.append(artifact)
    return artifacts


def _record_metrics(
    session: Session,
    candidate: Candidate,
    metrics: list[ParsedMetric],
    job_id: uuid.UUID | None,
) -> None:
    """Upsert a candidate's metrics, keyed by where each number came from.

    Re-collecting an attempt must not duplicate rows, so a metric is matched on
    (candidate, key, method, variant, condition) - the same tuple the table's unique
    constraint uses. Condition has to be part of the match: a design scored against a
    panel of ligands reports the same (key, method, variant) once per ligand, and
    without condition in the WHERE clause the second ligand's row would be found as
    "existing" and silently overwrite the first instead of accumulating beside it.
    """
    from ..candidates.models import CandidateMetric

    for metric in metrics:
        existing = session.scalar(
            select(CandidateMetric).where(
                CandidateMetric.candidate_id == candidate.id,
                CandidateMetric.metric_key == metric.key,
                CandidateMetric.method == metric.method,
                CandidateMetric.model_variant == metric.model_variant,
                CandidateMetric.condition == metric.condition,
            )
        )
        if existing is not None:
            existing.value = metric.value
            existing.unit = metric.unit
            existing.evidence_kind = metric.evidence_kind
            existing.assessor = metric.assessor
            existing.context = metric.context
            existing.source_job_id = job_id
            continue
        session.add(
            CandidateMetric(
                candidate_id=candidate.id,
                metric_key=metric.key,
                value=metric.value,
                method=metric.method,
                model_variant=metric.model_variant,
                evidence_kind=metric.evidence_kind,
                assessor=metric.assessor,
                condition=metric.condition,
                unit=metric.unit,
                context=metric.context,
                source_job_id=job_id,
            )
        )


def backfill_candidate_structures(existing, item, artifact_at) -> None:
    """Point an already-existing candidate at any coordinates this collection produced.

    Both slots are filled, not just the monomer. ProteinHunter only ever reports a
    *complex* (the binder with its ligand in place), so filling only
    ``structure_artifact_id`` left every re-collected ProteinHunter candidate with no
    structure at all, and the UI then reported "no structure file for this candidate yet"
    for a design whose PDB had in fact been collected and stored.

    Neither slot is overwritten once set: whichever collection first produced coordinates
    keeps them, so a later job cannot silently repoint a candidate at a different
    structure.
    """
    if existing.structure_artifact_id is None:
        structure = artifact_at(item.structure_output_index)
        if structure is not None:
            existing.structure_artifact_id = structure.id
    if existing.complex_artifact_id is None:
        complex_artifact = artifact_at(item.complex_output_index)
        if complex_artifact is not None:
            existing.complex_artifact_id = complex_artifact.id


def _apply_parsed_outputs(
    session: Session,
    job: Job,
    submission: JobSubmission,
    verified: list[dict],
    artifacts: list[Artifact],
) -> None:
    """Run the plugin's output parser and persist the candidates/results it found."""
    from ..candidates.models import Candidate
    from ..experiments.models import ExperimentResult
    from .parsers import ParseContext, get_parser

    snapshot = job.runtime_spec.get("plugin_snapshot")
    parser_name = snapshot.get("output_parser") if isinstance(snapshot, dict) else None
    storage = ObjectStorage()
    context = ParseContext(
        job_id=job.id,
        project_id=job.project_id,
        attempt_number=job.attempt_number,
        outputs=verified,
        parameters=job.runtime_spec.get("parameters") or {},
        read_bytes=lambda key: storage.read_bytes(key, max_bytes=32 * 1024 * 1024),
    )
    parsed = get_parser(parser_name)(context)
    if parsed.warnings:
        ComputeRepository(session).append_event(job, "job.parse_warning", {"warnings": parsed.warnings})

    def artifact_at(index: int | None) -> Artifact | None:
        return artifacts[index] if index is not None and 0 <= index < len(artifacts) else None

    by_key: dict[str, Candidate] = {}
    for item in parsed.candidates:
        existing = session.scalar(
            select(Candidate).where(
                Candidate.project_id == job.project_id,
                Candidate.candidate_key == item.candidate_key,
            )
        )
        if existing is not None:
            by_key[item.candidate_key] = existing
            # An existing candidate keeps the identity its creator gave it, but a later
            # method still has something to say about it: AlphaFold2 folding a
            # ProteinMPNN design is the ordinary case, and its confidence numbers used
            # to be dropped here. Metrics are recorded below for new and existing alike.
            backfill_candidate_structures(existing, item, artifact_at)
            _record_metrics(session, existing, item.metrics, job.id)
            continue
        structure = artifact_at(item.structure_output_index)
        complex_artifact = artifact_at(item.complex_output_index)
        candidate = Candidate(
            project_id=job.project_id,
            candidate_key=item.candidate_key,
            name=item.name or item.candidate_key,
            status=item.status,
            rank=item.rank,
            score=item.score,
            scores=item.scores,
            properties=item.properties,
            structure_artifact_id=structure.id if structure else None,
            complex_artifact_id=complex_artifact.id if complex_artifact else None,
            source_job_id=job.id,
        )
        session.add(candidate)
        session.flush()
        _record_metrics(session, candidate, item.metrics, job.id)
        by_key[item.candidate_key] = candidate

    if by_key:
        from ..candidates.delta import upsert_condition_deltas

        for touched in by_key.values():
            upsert_condition_deltas(session, touched.id)

    for result in parsed.results:
        linked = by_key.get(result.candidate_ref) if result.candidate_ref else None
        if linked is None and result.candidate_ref:
            linked = session.scalar(
                select(Candidate).where(
                    Candidate.project_id == job.project_id,
                    Candidate.candidate_key == result.candidate_ref,
                )
            )
        source = artifact_at(result.source_output_index)
        session.add(
            ExperimentResult(
                project_id=job.project_id,
                candidate_id=linked.id if linked else None,
                candidate_ref=result.candidate_ref,
                source_artifact_id=source.id if source else None,
                batch_key=result.batch_key,
                experiment_type=result.experiment_type,
                pass_status=result.pass_status,
                value=result.value,
                unit=result.unit,
                conclusion=result.conclusion,
                failure_reason=result.failure_reason,
                result_metadata=result.metadata,
                created_by=submission.created_by,
            )
        )


@celery_app.task(name="bda_v2.cancel_job", bind=True, max_retries=3)
def cancel_job(self, job_id: str) -> dict:
    parsed = uuid.UUID(job_id)
    with SessionFactory() as session:
        job = ComputeRepository(session).job(parsed)
        if job is None or job.status in TERMINAL_STATES:
            return {"job_id": job_id, "status": "ignored"}
        backend, external_id = job.compute_backend, job.external_id
    try:
        cancelled = True if not external_id else adapter_for(backend).cancel(external_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10) from exc
    if cancelled:
        with session_scope() as session:
            job = ComputeRepository(session).job(parsed, for_update=True)
            if job and job.status not in TERMINAL_STATES:
                transition_job(session, job, "cancelled")
                _advance_submission(session, job)
    return {"job_id": job_id, "status": "cancelled" if cancelled else "unchanged"}


def _advance_submission(session: Session, job: Job) -> None:
    submission = session.get(JobSubmission, job.submission_id)
    workflow = WorkflowRepository(session).get(job.workflow_run_id)
    if submission and workflow:
        schedule_ready_jobs(session, submission, workflow)


GC_PROTECTED_PREFIXES = ("literature/", "research-generations/")


GC_PROTECTED_SEGMENTS = ("/literature/", "/delivery/", "/research/")


def _gc_protected(object_name: str, live_job_prefixes: tuple[str, ...]) -> bool:
    if object_name.startswith(live_job_prefixes):
        return True
    if object_name.startswith(GC_PROTECTED_PREFIXES):
        return True
    return any(segment in object_name for segment in GC_PROTECTED_SEGMENTS)


@celery_app.task(name="bda_v2.reconcile_artifacts")
def reconcile_artifacts() -> dict:
    now = datetime.now(UTC)
    with SessionFactory() as session:
        expired = list(
            session.scalars(
                select(ArtifactUpload).where(
                    ArtifactUpload.status == "uploading",
                    ArtifactUpload.expires_at < now,
                )
            )
        )
        available = list(session.scalars(select(Artifact).where(Artifact.status == "available")))
        known_staging = set(
            session.scalars(
                select(ArtifactUpload.object_key).where(
                    ArtifactUpload.status == "uploading",
                    ArtifactUpload.expires_at >= now,
                )
            )
        )
        known_artifacts = set(session.scalars(select(Artifact.object_key).where(Artifact.deleted_at.is_(None))))
        expired_data = [(item.id, item.object_key) for item in expired]
        available_data = [(item.id, item.object_key) for item in available]
        # Job manifests and staged outputs never become Artifact rows, so they look
        # orphaned to the sweep below. Deleting them out from under a queued job
        # destroys its inputs, so live jobs' prefixes are held back explicitly.
        live_job_prefixes = tuple(
            f"jobs/{job_id}/"
            for job_id in session.scalars(select(Job.id).where(Job.status.not_in(TERMINAL_STATES)))
        )

    storage = ObjectStorage()
    for _, key in expired_data:
        if storage.exists(key):
            storage.remove(key)
    missing = [artifact_id for artifact_id, key in available_data if not storage.exists(key)]
    orphaned = [
        item.object_name
        for item in storage.list_objects()
        if item.object_name not in known_staging | known_artifacts
        and not _gc_protected(item.object_name, live_job_prefixes)
        and item.last_modified
        and item.last_modified < now - timedelta(hours=1)
    ]
    for key in orphaned:
        storage.remove(key)

    with session_scope() as session:
        for upload_id, _ in expired_data:
            upload = session.get(ArtifactUpload, upload_id)
            if upload and upload.status == "uploading":
                upload.status = "failed"
                upload.error = "upload_expired"
        for artifact_id in missing:
            artifact = session.get(Artifact, artifact_id)
            if artifact and artifact.status == "available":
                artifact.status = "failed"
    return {"expired_uploads": len(expired_data), "missing_objects": len(missing), "orphaned_objects": len(orphaned)}


@celery_app.task(name="bda_v2.purge_deleted_projects")
def purge_deleted_projects() -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    with SessionFactory() as session:
        projects = list(session.scalars(select(Project).where(Project.deleted_at < cutoff)))
        project_ids = [item.id for item in projects]
        object_keys = list(session.scalars(select(Artifact.object_key).where(Artifact.project_id.in_(project_ids))))
    storage = ObjectStorage()
    for key in set(object_keys):
        if storage.exists(key):
            storage.remove(key)
    with session_scope() as session:
        for project_id in project_ids:
            project = session.get(Project, project_id)
            if project and project.deleted_at and _as_utc(project.deleted_at) < cutoff:
                session.delete(project)
    return {"purged_projects": len(project_ids), "removed_objects": len(set(object_keys))}


@celery_app.task(name="bda_v2.compute_draft_confirm")
def compute_draft_confirm(draft_id: str) -> dict:
    from .models import ComputeDraft

    parsed = uuid.UUID(draft_id)
    with session_scope() as session:
        draft = session.get(ComputeDraft, parsed)
        if draft is None:
            return {"draft_id": draft_id, "status": "ignored"}
        if draft.confirmed_job_id:
            return {"draft_id": draft_id, "status": "accepted", "job_id": str(draft.confirmed_job_id)}
        specification = draft.specification
        workflow = WorkflowRun(
            project_id=draft.project_id,
            name=f"Compute draft: {draft.name}",
            status="queued",
            graph={"nodes": [{"key": "compute"}], "edges": [], "source_compute_draft_id": draft_id},
            created_by=draft.created_by,
        )
        session.add(workflow)
        session.flush()
        node = WorkflowNode(
            workflow_run_id=workflow.id,
            node_key="compute",
            node_type="compute",
            model_plugin=str(specification.get("model_plugin") or "custom"),
            container_image=specification.get("image"),
            command=specification.get("command"),
            queue=specification.get("queue"),
            status="draft",
            parameters=specification.get("parameters") or {},
        )
        submission = JobSubmission(
            workflow_run_id=workflow.id,
            project_id=draft.project_id,
            created_by=draft.created_by,
            compute_backend=draft.backend,
        )
        session.add_all([node, submission])
        session.flush()
        job = Job(
            submission_id=submission.id,
            workflow_run_id=workflow.id,
            workflow_node_id=node.id,
            project_id=draft.project_id,
            compute_backend=draft.backend,
            model_plugin=node.model_plugin,
            timeout_at=datetime.now(UTC) + timedelta(minutes=int(specification.get("timeout_minutes") or 180)),
            runtime_spec={
                **specification,
                "manifest_version": "1",
                "input_manifest": specification.get("input_manifest")
                or {"schema_version": "1", "parameters": node.parameters, "inputs": []},
            },
        )
        session.add(job)
        session.flush()
        job.runtime_spec = {
            **job.runtime_spec,
            "input_manifest_key": f"jobs/{job.id}/attempt-1/input-manifest.json",
            "output_manifest_key": f"jobs/{job.id}/attempt-1/output-manifest.json",
        }
        repo = ComputeRepository(session)
        repo.append_event(job, "job.pending", {"compute_draft_id": draft_id})
        _mirror_status_onto_node(session, job)
        repo.enqueue(
            "job.dispatch",
            job.id,
            project_id=job.project_id,
            payload={"job_id": str(job.id)},
        )
        draft.confirmed_job_id = job.id
        draft.status = "submitted"
        draft.version += 1
        return {"draft_id": draft_id, "status": "accepted", "job_id": str(job.id)}
