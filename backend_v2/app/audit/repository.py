from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        *,
        after: uuid.UUID | None,
        limit: int,
        organization_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        action: str | None = None,
    ) -> list[AuditLog]:
        query = select(AuditLog)
        if after:
            query = query.where(AuditLog.id > after)
        if organization_id:
            query = query.where(AuditLog.organization_id == organization_id)
        if project_id:
            query = query.where(AuditLog.project_id == project_id)
        if actor_id:
            query = query.where(AuditLog.actor_id == actor_id)
        if action:
            query = query.where(AuditLog.action == action)
        return list(self.session.scalars(query.order_by(AuditLog.id).limit(limit + 1)))
