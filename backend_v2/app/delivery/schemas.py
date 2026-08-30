from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliveryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    candidate_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    include_experiment_results: bool = True


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    name: str
    selection: dict
    artifact_id: uuid.UUID | None
    error: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class DeliveryPage(BaseModel):
    items: list[DeliveryResponse]
    next_cursor: str | None = None


class DeliveryAccepted(BaseModel):
    operation_id: uuid.UUID
    delivery_package: DeliveryResponse


class ResultSummary(BaseModel):
    project_id: uuid.UUID
    candidate_count: int
    experiment_result_count: int
    available_artifact_count: int
    tested_candidate_count: int
    passed_result_count: int
    failed_result_count: int
    unknown_result_count: int
    pass_rate: float | None
    top_candidate_ids: list[uuid.UUID]
    best_result_id: uuid.UUID | None
    best_result_value: float | None
    best_result_unit: str | None
