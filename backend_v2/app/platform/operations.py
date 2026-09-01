from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..compute.models import OutboxEvent
from ..identity.models import User
from .models import Operation


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
) -> Operation:
    operation = Operation(
        project_id=project_id,
        organization_id=organization_id,
        created_by=user.id,
        kind=topic,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    session.add(operation)
    session.flush()
    session.add(
        OutboxEvent(
            id=operation.id,
            topic=topic,
            aggregate_id=resource_id,
            payload={
                **(payload or {}),
                "operation_id": str(operation.id),
                **({"project_id": str(project_id)} if project_id else {}),
                **({"organization_id": str(organization_id)} if organization_id else {}),
            },
        )
    )
    return operation


def mark_operation_running(session: Session, operation_id: uuid.UUID) -> None:
    operation = session.get(Operation, operation_id)
    if operation is None or operation.status in {"succeeded", "failed", "cancelled"}:
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
    operation = session.get(Operation, operation_id)
    if operation is None:
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
    from ..compute.models import OutboxEvent

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
