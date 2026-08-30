from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    objective: str | None = None
    config: dict = Field(default_factory=dict)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    objective: str | None = None
    status: str | None = None
    config: dict | None = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    objective: str | None
    status: str
    config: dict
    version: int
    created_at: datetime
    updated_at: datetime


class CampaignPage(BaseModel):
    items: list[CampaignResponse]
    next_cursor: str | None = None


class RoundCreate(BaseModel):
    workflow_run_id: uuid.UUID | None = None
    hypothesis: str | None = None


class RoundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campaign_id: uuid.UUID
    round_number: int
    status: str
    workflow_run_id: uuid.UUID | None
    submission_id: uuid.UUID | None
    hypothesis: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class RoundPage(BaseModel):
    items: list[RoundResponse]
    next_cursor: str | None = None


class EvaluationCreate(BaseModel):
    candidate_id: uuid.UUID | None = None
    metrics: dict = Field(default_factory=dict)
    outcome: str = "pending"
    notes: str | None = None


class EvaluationResponse(EvaluationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    round_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class EvaluationPage(BaseModel):
    items: list[EvaluationResponse]
    next_cursor: str | None = None


class DecisionCreate(BaseModel):
    decision: str = Field(min_length=1, max_length=80)
    rationale: str = Field(min_length=1)
    parameter_patch: dict = Field(default_factory=dict)


class DecisionUpdate(BaseModel):
    decision: str | None = Field(default=None, min_length=1, max_length=80)
    rationale: str | None = Field(default=None, min_length=1)
    parameter_patch: dict | None = None


class DecisionReview(BaseModel):
    approve: bool


class DecisionResponse(DecisionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    round_id: uuid.UUID
    decided_by: uuid.UUID
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class DecisionPage(BaseModel):
    items: list[DecisionResponse]
    next_cursor: str | None = None


class EvaluationRunAccepted(BaseModel):
    operation_id: uuid.UUID
    round_id: uuid.UUID
    status: str = "pending"
