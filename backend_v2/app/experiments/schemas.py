from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExperimentResultCreate(BaseModel):
    candidate_id: uuid.UUID | None = None
    candidate_ref: str | None = Field(default=None, max_length=255)
    source_artifact_id: uuid.UUID | None = None
    batch_key: str | None = Field(default=None, max_length=255)
    experiment_type: str = Field(min_length=1, max_length=120)
    pass_status: str = Field(default="unknown", pattern="^(pass|fail|unknown)$")
    value: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    conclusion: str | None = Field(default=None, max_length=5000)
    failure_reason: str | None = Field(default=None, max_length=5000)
    result_metadata: dict = Field(default_factory=dict)


class ExperimentResultBatch(BaseModel):
    results: list[ExperimentResultCreate] = Field(min_length=1, max_length=1000)


class ExperimentResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    candidate_id: uuid.UUID | None
    candidate_ref: str | None
    source_artifact_id: uuid.UUID | None
    batch_key: str | None
    experiment_type: str
    pass_status: str
    value: float | None
    unit: str | None
    conclusion: str | None
    failure_reason: str | None
    result_metadata: dict
    version: int
    created_at: datetime
    updated_at: datetime


class ExperimentResultPage(BaseModel):
    items: list[ExperimentResultResponse]
    next_cursor: str | None = None


class ExperimentResultImportCreate(BaseModel):
    artifact_id: uuid.UUID
    # Validate and report without writing, so an uploader can check a file's columns
    # and candidate references before committing rows.
    dry_run: bool = False


class ExperimentResultImportAccepted(BaseModel):
    operation_id: uuid.UUID
    artifact_id: uuid.UUID
    status: str = "pending"
