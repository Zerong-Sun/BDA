from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.statuses import ComputeDraftStatus, JobStatus, JobSubmissionStatus


class SubmissionCreate(BaseModel):
    compute_backend: str | None = Field(default=None, max_length=32)
    timeout_minutes: int = Field(default=180, ge=5, le=1440)

    @field_validator("compute_backend")
    @classmethod
    def validate_backend(cls, value: str | None) -> str | None:
        """Check against the adapter registry rather than a hardcoded pattern.

        A site that registers a Slurm or Kubernetes adapter can then select it without
        the API schema needing to know about it in advance.
        """
        if value is None:
            return value
        from .adapters import available_backends

        allowed = available_backends()
        if value not in allowed:
            raise ValueError(f"compute_backend must be one of: {', '.join(allowed)}")
        return value


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_node_id: uuid.UUID
    project_id: uuid.UUID
    status: JobStatus
    compute_backend: str
    model_plugin: str
    attempt_number: int
    external_id: str | None
    next_poll_at: datetime | None
    timeout_at: datetime | None
    error_code: str | None
    error_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    project_id: uuid.UUID
    status: JobSubmissionStatus
    compute_backend: str
    jobs: list[JobResponse]
    created_at: datetime


class JobPage(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None = None


class CancelResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus


class ComputeDraftCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=240)
    backend: str = Field(pattern="^(docker|lsf)$")
    specification: dict = Field(default_factory=dict)


class ComputeDraftResponse(ComputeDraftCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: ComputeDraftStatus
    confirmed_job_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class ComputeDraftPage(BaseModel):
    items: list[ComputeDraftResponse]
    next_cursor: str | None = None


class JobLogEntry(BaseModel):
    id: uuid.UUID
    event: str
    message: str
    level: str = "info"
    created_at: datetime


class JobLogPage(BaseModel):
    items: list[JobLogEntry]
    next_cursor: str | None = None
