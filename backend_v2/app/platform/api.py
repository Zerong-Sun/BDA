from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..core.database import SessionFactory, get_session
from ..core.pagination import decode_time_cursor, encode_time_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_roles, streaming_user
from ..identity.models import User
from ..projects.service import require_project, visible_project_ids
from .models import Operation
from .repository import PlatformRepository
from .schemas import HealthResponse, LegacyIdResolution
from .schemas_operations import (
    MigrationRunPage,
    MigrationRunResponse,
    OperationPage,
    OperationResponse,
    OperationsSummary,
)
from .service import dependency_health, operations_summary, visible_operation

router = APIRouter(tags=["platform"])


def _authorize_operation(session: Session, operation: Operation, user: User) -> None:
    if user.role == "admin":
        return
    if operation.project_id is None:
        raise DomainError("forbidden", "This operation is only visible to administrators", status_code=403)
    require_project(session, operation.project_id, user)


#: How far back a listing reaches when the caller does not say. Not a retention
#: policy - nothing deletes operations - but every copilot reply and agent step
#: lands a row here, so an unbounded default would page through months of them to
#: answer "what did I just submit". `since` widens it whenever that is the question.
DEFAULT_OPERATION_WINDOW = timedelta(days=30)


@router.get("/operations", response_model=OperationPage)
def list_operations(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    project_id: uuid.UUID | None = Query(default=None),
    kind: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    mine: bool = Query(default=False),
    since: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> OperationPage:
    """Asynchronous work, newest first.

    Every domain that queues something records an operation, and until this existed
    there was no way to list them: an operation was only ever held as a local
    variable by whichever component started it, so navigating away lost the handle
    to work that kept running.

    Visibility mirrors the per-operation check exactly. An administrator sees
    everything, including the platform-level operations that belong to no project;
    everyone else sees only projects they can already read, and never a
    project-less one.
    """
    fence = visible_project_ids(session, user)
    if project_id is not None:
        require_project(session, project_id, user)
    rows = PlatformRepository(session).list_operations(
        decode_time_cursor(cursor),
        limit,
        project_ids=fence,
        include_projectless=fence is None,
        created_by=user.id if mine else None,
        project_id=project_id,
        kind=kind,
        status=status_filter,
        since=since or datetime.now(UTC) - DEFAULT_OPERATION_WINDOW,
    )
    page = rows[:limit]
    return OperationPage(
        items=[OperationResponse.model_validate(row) for row in page],
        next_cursor=(
            encode_time_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit and page else None
        ),
    )


@router.get("/operations/{operation_id}", response_model=OperationResponse)
def get_operation(
    operation_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> OperationResponse:
    operation = visible_operation(session, operation_id)
    if operation is None:
        raise DomainError("operation_not_found", "Operation was not found", status_code=404)
    _authorize_operation(session, operation, user)
    response.headers["ETag"] = f'W/"{operation.version}"'
    return OperationResponse.model_validate(operation)


@router.get("/operations/{operation_id}/events")
def operation_events(operation_id: uuid.UUID, user: User = Depends(streaming_user)) -> EventSourceResponse:
    with SessionFactory() as session:
        operation = visible_operation(session, operation_id)
        if operation is None:
            raise DomainError("operation_not_found", "Operation was not found", status_code=404)
        _authorize_operation(session, operation, user)

    async def stream() -> AsyncIterator[dict[str, str]]:
        previous_version = 0
        while True:
            with SessionFactory() as session:
                current = visible_operation(session, operation_id)
                if current is None:
                    return
                payload = OperationResponse.model_validate(current).model_dump(mode="json")
                changed = current.version != previous_version
                previous_version = current.version
                terminal = current.status in {"succeeded", "failed", "cancelled"}
            if changed:
                yield {"id": str(previous_version), "event": "operation", "data": json.dumps(payload)}
            if terminal:
                yield {"event": "done", "data": json.dumps({"operation_id": str(operation_id)})}
                return
            await asyncio.sleep(1)

    return EventSourceResponse(stream())


@router.get("/platform/operations/summary", response_model=OperationsSummary)
def get_operations_summary(
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> OperationsSummary:
    del user
    return operations_summary(session)


@router.get("/platform/migration-runs", response_model=MigrationRunPage)
def list_migration_runs(
    cursor: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> MigrationRunPage:
    del user
    rows = PlatformRepository(session).list_migration_runs(cursor, limit)
    page = rows[:limit]
    return MigrationRunPage(
        items=[MigrationRunResponse.model_validate(row) for row in page],
        next_cursor=str(page[-1].id) if len(rows) > limit and page else None,
    )


@router.get("/legacy-ids/{entity_type}/{legacy_id}", response_model=LegacyIdResolution)
def resolve_legacy_id(
    entity_type: str,
    legacy_id: str,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> LegacyIdResolution:
    supported = {"artifacts", "candidates", "projects", "targets", "workflow-runs"}
    if entity_type not in supported:
        raise DomainError("legacy_entity_unsupported", "Legacy entity type is not supported", status_code=404)
    row = PlatformRepository(session).resolve_legacy_id(entity_type, legacy_id)
    if row is None:
        raise DomainError("legacy_id_not_found", "Legacy ID was not found", status_code=404)
    project_id: uuid.UUID | None = row.id if entity_type == "projects" else getattr(row, "project_id", None)
    if project_id:
        require_project(session, project_id, user)
    return LegacyIdResolution(entity_type=entity_type, legacy_id=legacy_id, id=row.id)


@router.get("/health/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "A required dependency is unavailable"}},
)
def readiness(response: Response) -> HealthResponse:
    checks = dependency_health()
    health_status = "ok" if all(value == "ok" for value in checks.values()) else "unavailable"
    if health_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status=health_status, checks=checks)
