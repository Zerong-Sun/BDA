from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..core.trace import current_trace_id
from .models import AuditLog


def record_audit(
    session: Session,
    *,
    action: str,
    entity_type: str,
    actor_id: uuid.UUID | None,
    entity_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    result: str = "success",
    payload: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            organization_id=organization_id,
            project_id=project_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            trace_id=current_trace_id(),
            result=result,
            payload=payload or {},
        )
    )
