from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class AssayCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    method: str = Field(min_length=1, max_length=4000)
    unit: str = Field(min_length=1, max_length=40)
    conditions: dict[str, str] = Field(default_factory=dict, max_length=30)

    @model_validator(mode="after")
    def bounded_conditions(self) -> AssayCreate:
        if len(json.dumps(self.conditions)) > 8000:
            raise ValueError("Assay conditions are too large")
        return self


class StudyCreate(Input):
    assay_id: uuid.UUID
    research_goal_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    direction: Literal["maximize", "minimize"]
    threshold: float | None = None
    currency: Literal["USD", "EUR", "GBP", "CNY"] = "USD"
    batch_budget_cents: int = Field(ge=1, le=100_000_000)
    max_batch_size: int = Field(ge=1, le=96, default=12)


class ObservationCreate(Input):
    assay_id: uuid.UUID
    candidate_id: uuid.UUID
    source_artifact_id: uuid.UUID
    batch_key: str = Field(min_length=1, max_length=200)
    replicate_key: str = Field(min_length=1, max_length=120)
    replicate_type: Literal["biological", "technical"]
    status: Literal["measured", "failed", "below_limit", "above_limit", "missing"]
    value: float | None = None
    unit: str = Field(min_length=1, max_length=40)
    qc_accepted: bool = Field(default=False, strict=True)
    note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def measured_or_missing(self) -> ObservationCreate:
        if self.status in {"measured", "below_limit", "above_limit"} and self.value is None:
            raise ValueError("A measurement or detection limit needs a numeric value")
        if self.status in {"failed", "missing"} and self.value is not None:
            raise ValueError("Failure/missing observations cannot be numeric zero placeholders")
        return self


class DatasetCreate(Input):
    study_id: uuid.UUID
    result_ids: list[uuid.UUID] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def unique_results(self) -> DatasetCreate:
        if len(set(self.result_ids)) != len(self.result_ids):
            raise ValueError("Results must be unique")
        return self


class ModelCreate(Input):
    dataset_id: uuid.UUID


class ModelReview(Input):
    action: Literal["promote", "retire"]
    rationale: str = Field(min_length=1, max_length=2000)


class CandidateCost(Input):
    candidate_id: uuid.UUID
    cost_cents: int = Field(ge=1, le=100_000_000)


class LearningDecisionCreate(Input):
    study_id: uuid.UUID
    model_id: uuid.UUID
    candidates: list[CandidateCost] = Field(min_length=1, max_length=256)
    exploration_fraction: float = Field(ge=0, le=1, default=0.25)

    @model_validator(mode="after")
    def unique_candidates(self) -> LearningDecisionCreate:
        if len({row.candidate_id for row in self.candidates}) != len(self.candidates):
            raise ValueError("Candidates must be unique")
        return self


class LearningDecisionReview(Input):
    approve: bool
    rationale: str = Field(min_length=1, max_length=2000)


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID


class AssayResponse(RecordResponse, AssayCreate):
    model_config = ConfigDict(from_attributes=True)


class StudyResponse(RecordResponse):
    assay_id: uuid.UUID
    research_goal_id: uuid.UUID | None
    name: str
    direction: str
    threshold: float | None
    currency: str
    batch_budget_cents: int
    max_batch_size: int
    goal_snapshot: dict


class DatasetResponse(RecordResponse):
    study_id: uuid.UUID
    digest: str
    manifest: dict


class ModelResponse(RecordResponse):
    study_id: uuid.UUID
    dataset_id: uuid.UUID
    algorithm: str
    status: str
    parameters: dict
    evaluation: dict


class LearningDecisionResponse(RecordResponse):
    study_id: uuid.UUID
    model_id: uuid.UUID
    timeline_entry_id: uuid.UUID | None
    proposal_digest: str
    proposal: dict
    review_status: str
    review_note: str | None
    reviewed_by: uuid.UUID | None


class LearningPage(BaseModel):
    items: list[AssayResponse | StudyResponse | DatasetResponse | ModelResponse | LearningDecisionResponse]
    next_cursor: str | None = None


class LearningPackage(BaseModel):
    schema_version: int = 1
    checksum: str
    content: dict
