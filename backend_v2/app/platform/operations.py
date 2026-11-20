from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..identity.models import User
from .models import Operation, OutboxEvent, WorkerHeartbeat


def record_worker_heartbeat(
    session: Session,
    instance_id: str,
    *,
    service: str,
    queues: list[str],
    build_revision: str,
    schema_revision: str,
) -> WorkerHeartbeat:
    row = session.get(WorkerHeartbeat, instance_id)
    if row is None:
        row = WorkerHeartbeat(instance_id=instance_id, service=service)
        session.add(row)
    row.queues = queues
    row.build_revision = build_revision
    row.schema_revision = schema_revision
    row.last_seen_at = datetime.now(UTC)
    return row


def enqueue_project_event(
    session: Session,
    topic: str,
    aggregate_id: uuid.UUID,
    *,
    project_id: uuid.UUID,
    payload: dict | None = None,
) -> None:
    """Queue project work with the RLS fence required by restricted workers."""
    session.add(
        OutboxEvent(
            topic=topic,
            aggregate_id=aggregate_id,
            payload={**(payload or {}), "project_id": str(project_id)},
        )
    )


def enqueue_operation(
    session: Session,
    *,
    topic: str,
    resource_type: str,
    resource_id: uuid.UUID,
    user: User,
    project_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    payload: dict | None = None,
    progress: dict | None = None,
) -> Operation:
    from ..copilot.call_guard import current_scope_id

    # This field is server-owned. Never let caller payloads choose a new budget.
    event_payload = {key: value for key, value in (payload or {}).items() if key != "_llm_call_scope"}
    scope_id = current_scope_id()
    if scope_id is not None:
        event_payload["_llm_call_scope"] = scope_id
    operation = Operation(
        project_id=project_id,
        organization_id=organization_id,
        created_by=user.id,
        kind=topic,
        resource_type=resource_type,
        resource_id=resource_id,
        progress=progress or {},
    )
    session.add(operation)
    session.flush()
    session.add(
        OutboxEvent(
            id=operation.id,
            topic=topic,
            aggregate_id=resource_id,
            payload={
                **event_payload,
                "operation_id": str(operation.id),
                **({"project_id": str(project_id)} if project_id else {}),
                **({"organization_id": str(organization_id)} if organization_id else {}),
            },
        )
    )
    return operation


def project_operations(
    session: Session, project_id: uuid.UUID, kind: str, statuses: Iterable[str]
) -> list[Operation]:
    return list(
        session.scalars(
            select(Operation).where(
                Operation.project_id == project_id,
                Operation.kind == kind,
                Operation.status.in_(list(statuses)),
            )
        )
    )


def cancel_pending_operation(session: Session, operation: Operation, now: datetime) -> None:
    """Withdraw an operation no worker has picked up, along with its unpublished event."""
    event = session.get(OutboxEvent, operation.id)
    if event is not None and event.published_at is None:
        session.delete(event)
    operation.status = "cancelled"
    operation.finished_at = now
    operation.version += 1


def mark_operation_running(session: Session, operation_id: uuid.UUID) -> None:
    operation = session.scalar(
        select(Operation).where(Operation.id == operation_id).with_for_update().execution_options(populate_existing=True)
    )
    if operation is None or operation.status in {"running", "succeeded", "failed", "cancelled"}:
        return
    operation.status = "running"
    operation.started_at = operation.started_at or datetime.now(UTC)
    operation.version += 1


def finish_operation(
    session: Session,
    operation_id: uuid.UUID,
    *,
    result: dict | None = None,
    error: Exception | None = None,
) -> None:
    session.flush()
    operation = session.scalar(
        select(Operation).where(Operation.id == operation_id).with_for_update().execution_options(populate_existing=True)
    )
    if operation is None or operation.status in {"succeeded", "failed", "cancelled"}:
        return
    operation.finished_at = datetime.now(UTC)
    if error is None:
        operation.status = "succeeded"
        operation.result = result or {}
        operation.error_code = None
        operation.error_message = None
    else:
        operation.status = "failed"
        operation.error_code = error.__class__.__name__.lower()
        operation.error_message = str(error)[:4000]
    operation.version += 1
    _announce_settled(session, operation)


def _announce_settled(session: Session, operation: Operation) -> None:
    """Say that this operation reached a terminal state, whoever is listening.

    Emitted for succeeded and failed alike, for the reason compute learned the
    hard way: a consumer told only about success has to poll to find out about
    failure, and something waiting on a failed run would otherwise wait forever.

    One row per operation, on top of the one that started it. That is the cost of
    the queued work being observable at all; the alternative - asking the waiting
    side to poll - trades a cheap write for a permanent one.
    """
    session.add(
        OutboxEvent(
            topic="operation.settled",
            aggregate_id=operation.id,
            payload={
                "operation_id": str(operation.id),
                "status": operation.status,
                "kind": operation.kind,
                "resource_id": str(operation.resource_id),
                **({"project_id": str(operation.project_id)} if operation.project_id else {}),
            },
        )
    )
