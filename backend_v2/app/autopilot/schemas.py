from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AutopilotBudgetInput(BaseModel):
    gpu_seconds_limit: int | None = Field(default=None, ge=0)
    money_micros_limit: int | None = Field(default=None, ge=0)


class AutopilotDraftCreate(BaseModel):
    project_id: uuid.UUID
    prompt: str | None = Field(default=None, min_length=10, max_length=400_000)
    structured_brief: dict[str, Any] | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> AutopilotDraftCreate:
        if (self.prompt is None) == (self.structured_brief is None):
            raise ValueError("Supply exactly one of prompt or structured_brief")
        return self


class AutopilotDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    prompt: str
    structured_brief: dict
    normalized_spec: dict
    status: str
    confirmed_campaign_id: uuid.UUID | None
    version: int
    created_at: datetime


class AutopilotConfirm(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    autonomy: Literal["supervised", "plan_only"] = "supervised"
    budget: AutopilotBudgetInput | None = None
    manual_campaign_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def supervised_requires_budget(self) -> AutopilotConfirm:
        if self.autonomy == "supervised" and self.budget is None:
            raise ValueError("A supervised campaign requires an explicit budget")
        return self


class AutopilotCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    draft_id: uuid.UUID
    manual_campaign_id: uuid.UUID | None
    name: str
    autonomy: str
    status: str
    frozen_prompt: str
    frozen_spec: dict
    started_at: datetime | None
    cancelled_at: datetime | None
    version: int
    created_at: datetime


class AutopilotStart(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    gpu_seconds: int = Field(ge=0)
    money_micros: int = Field(default=0, ge=0)


class AutopilotOperationAccepted(BaseModel):
    campaign_id: uuid.UUID
    operation_id: uuid.UUID
    status: str
