from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.pagination import decode_cursor, encode_cursor
from ..identity.deps import require_roles
from ..identity.models import User
from .repository import AuditRepository
from .schemas import AuditLogPage, AuditLogResponse

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> AuditLogPage:
    del user
    rows = AuditRepository(session).list(
        after=decode_cursor(cursor),
        limit=limit,
        organization_id=organization_id,
        project_id=project_id,
        actor_id=actor_id,
        action=action,
    )
    page = rows[:limit]
    return AuditLogPage(
        items=[AuditLogResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )
