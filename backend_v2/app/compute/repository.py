from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..workflows.models import WorkflowNode
from .models import ComputeDraft, IdempotencyRecord, Job, JobEvent, JobSubmission, OutboxEvent


class ComputeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def submission(self, submission_id: uuid.UUID) -> JobSubmission | None:
        return self.session.get(JobSubmission, submission_id)

    def draft(self, draft_id: uuid.UUID) -> ComputeDraft | None:
        return self.session.get(ComputeDraft, draft_id)

    def list_drafts(self, project_id: uuid.UUID, *, after: uuid.UUID | None, limit: int) -> list[ComputeDraft]:
        query = select(ComputeDraft).where(ComputeDraft.project_id == project_id)
        if after:
            query = query.where(ComputeDraft.id > after)
        return list(self.session.scalars(query.order_by(ComputeDraft.id).limit(limit + 1)))

    def jobs_for_submission(self, submission_id: uuid.UUID) -> list[Job]:
        return list(self.session.scalars(select(Job).where(Job.submission_id == submission_id).order_by(Job.id)))

    def jobs_for_workflow(self, workflow_id: uuid.UUID) -> list[Job]:
        return list(
            self.session.scalars(select(Job).where(Job.workflow_run_id == workflow_id).order_by(Job.created_at, Job.id))
        )

    def jobs_and_node_keys(self, submission_id: uuid.UUID) -> list[tuple[Job, str]]:
        return list(
            self.session.execute(
                select(Job, WorkflowNode.node_key)
                .join(WorkflowNode, WorkflowNode.id == Job.workflow_node_id)
                .where(Job.submission_id == submission_id)
                .order_by(WorkflowNode.node_key, Job.attempt_number)
            ).tuples()
        )

    def job(self, job_id: uuid.UUID, *, for_update: bool = False) -> Job | None:
        query = select(Job).where(Job.id == job_id)
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_project_jobs(self, project_id: uuid.UUID, *, after: uuid.UUID | None, limit: int) -> list[Job]:
        query = select(Job).where(Job.project_id == project_id)
        if after:
            query = query.where(Job.id > after)
        return list(self.session.scalars(query.order_by(Job.id).limit(limit + 1)))

    def idempotency(self, actor_id: uuid.UUID, scope: str, key: str) -> IdempotencyRecord | None:
        return self.session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.key == key,
            )
        )

    def events_after(self, job_id: uuid.UUID, after: datetime | None) -> list[JobEvent]:
        query = select(JobEvent).where(JobEvent.job_id == job_id)
        if after:
            query = query.where(JobEvent.created_at > after)
        return list(self.session.scalars(query.order_by(JobEvent.created_at).limit(100)))

    def events_page(self, job_id: uuid.UUID, *, after: uuid.UUID | None, limit: int) -> list[JobEvent]:
        query = select(JobEvent).where(JobEvent.job_id == job_id)
        if after:
            query = query.where(JobEvent.id > after)
        return list(self.session.scalars(query.order_by(JobEvent.id).limit(limit + 1)))

    def append_event(self, job: Job, event_type: str, payload: dict | None = None) -> None:
        self.session.add(JobEvent(job_id=job.id, event_type=event_type, payload=payload or {}))

    def produced_artifacts(self, job_id: uuid.UUID) -> list[Artifact]:
        """Artifacts collected from a succeeded job, in collection order.

        Reads the ids recorded on the ``job.succeeded`` event rather than filtering on
        the artifact lineage JSON, which keeps the query dialect-agnostic (tests run on
        SQLite, production on PostgreSQL).
        """
        event = self.session.scalar(
            select(JobEvent)
            .where(JobEvent.job_id == job_id, JobEvent.event_type == "job.succeeded")
            .order_by(JobEvent.created_at.desc())
        )
        raw_ids = (event.payload or {}).get("artifact_ids", []) if event else []
        parsed: list[uuid.UUID] = []
        for value in raw_ids:
            try:
                parsed.append(uuid.UUID(str(value)))
            except (ValueError, TypeError):
                continue
        if not parsed:
            return []
        found = {
            artifact.id: artifact
            for artifact in self.session.scalars(
                select(Artifact).where(Artifact.id.in_(parsed), Artifact.deleted_at.is_(None))
            )
        }
        return [found[item] for item in parsed if item in found]

    def enqueue(self, topic: str, aggregate_id: uuid.UUID, payload: dict | None = None) -> None:
        self.session.add(OutboxEvent(topic=topic, aggregate_id=aggregate_id, payload=payload or {}))

    def has_outbox_event(self, topic: str, aggregate_id: uuid.UUID) -> bool:
        return (
            self.session.scalar(
                select(OutboxEvent.id).where(
                    OutboxEvent.topic == topic,
                    OutboxEvent.aggregate_id == aggregate_id,
                )
            )
            is not None
        )
