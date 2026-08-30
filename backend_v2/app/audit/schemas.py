from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    trace_id: str
    result: str
    payload: dict
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    next_cursor: str | None = None
