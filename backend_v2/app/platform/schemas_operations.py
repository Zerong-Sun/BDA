from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    kind: str
    resource_type: str
    resource_id: uuid.UUID
    status: str
    progress: dict
    result: dict
    error_code: str | None
    error_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class OperationPage(BaseModel):
    items: list[OperationResponse]
    next_cursor: str | None = None


class OperationsSummary(BaseModel):
    jobs_by_status: dict[str, int]
    operations_by_status: dict[str, int]
    outbox_backlog: int
    missing_artifacts: int
    registry_health: dict[str, int]
    latest_migration_status: str | None


class MigrationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_fingerprint: str
    rehearsal: int
    status: str
    counts: dict
    checksums: dict
    id_map_digest: str | None
    rejection_summary: dict
    report_artifact_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class MigrationRunPage(BaseModel):
    items: list[MigrationRunResponse]
    next_cursor: str | None = None
