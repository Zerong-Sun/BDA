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


class SelectionConstraints(Input):
    min_length: int = Field(default=1, ge=1, le=10000)
    max_length: int = Field(default=10000, ge=1, le=10000)
    max_candidate_cost_cents: int | None = Field(default=None, ge=1, le=100_000_000)
    forbidden_motifs: list[str] = Field(default_factory=list, max_length=20)
    allow_out_of_domain: bool = True

    @model_validator(mode="after")
    def valid_bounds(self) -> SelectionConstraints:
        if self.min_length > self.max_length:
            raise ValueError("Minimum sequence length exceeds maximum")
        if any(not m or len(m) > 100 or set(m) - set("ACDEFGHIKLMNPQRSTVWY") for m in self.forbidden_motifs):
            raise ValueError("Forbidden motifs must be canonical amino acid strings of 1–100 residues")
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
    supersedes_id: uuid.UUID | None = None
    stop_on_threshold: bool = False
    max_rounds: int = Field(default=12, ge=1, le=100)
    selection_constraints: SelectionConstraints = Field(default_factory=SelectionConstraints)


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
    family_key: str | None = Field(default=None, min_length=1, max_length=120)
    observed_at: datetime | None = None
    sample_role: Literal["candidate", "positive_control", "negative_control"] = "candidate"
    measurement_key: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def timestamp_has_timezone(self) -> ObservationCreate:
        if self.observed_at is not None and self.observed_at.utcoffset() is None:
            raise ValueError("Observation time must include a timezone")
        return self

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
    algorithm: Literal["knn", "ridge"] = "knn"
    validation: Literal["sequence", "family", "batch", "time"] = "sequence"
    calibrate: bool = False


class ModelReview(Input):
    action: Literal["promote", "retire", "rollback"]
    rationale: str = Field(min_length=1, max_length=2000)


class CandidateCost(Input):
    candidate_id: uuid.UUID
    cost_cents: int = Field(ge=1, le=100_000_000)


class LearningDecisionCreate(Input):
    study_id: uuid.UUID
    model_id: uuid.UUID
    candidates: list[CandidateCost] = Field(min_length=1, max_length=256)
    exploration_fraction: float = Field(ge=0, le=1, default=0.25)
    retest_candidates: list[uuid.UUID] = Field(default_factory=list, max_length=96)
    secondary_model_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def unique_candidates(self) -> LearningDecisionCreate:
        if len({row.candidate_id for row in self.candidates}) != len(self.candidates):
            raise ValueError("Candidates must be unique")
        if len(set(self.retest_candidates)) != len(self.retest_candidates) or not set(self.retest_candidates) <= {
            r.candidate_id for r in self.candidates
        }:
            raise ValueError("Retest candidates must be unique members of the candidate pool")
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
    supersedes_id: uuid.UUID | None
    stop_on_threshold: bool
    max_rounds: int


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


class LearningPackage(BaseModel):
    schema_version: int = 1
    checksum: str
    content: dict


class ObservationImport(Input):
    assay_id: uuid.UUID
    artifact_id: uuid.UUID
    dry_run: bool = True


class ObservationImportResult(BaseModel):
    dry_run: bool
    row_count: int
    result_ids: list[uuid.UUID]
    observations: list[ObservationCreate]


class EvidenceCreate(Input):
    study_id: uuid.UUID
    kind: Literal["fact", "hypothesis", "conflict", "unknown"]
    statement: str = Field(min_length=1, max_length=4000)
    result_ids: list[uuid.UUID] = Field(default_factory=list, max_length=256)
    artifact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def facts_need_sources(self) -> EvidenceCreate:
        if self.kind == "fact" and not self.result_ids and not self.artifact_ids:
            raise ValueError("A fact needs a project result or artifact source")
        return self


class EvidenceWithdraw(Input):
    rationale: str = Field(min_length=1, max_length=2000)


class EvidenceResponse(RecordResponse):
    study_id: uuid.UUID
    kind: str
    statement: str
    sources: dict
    withdrawal: dict | None


class BatchCreate(Input):
    decision_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    rationale: str = Field(min_length=1, max_length=2000)
    workflow_run_id: uuid.UUID | None = None


class BatchComplete(Input):
    result_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    actual_cost_cents: int = Field(ge=0, le=100_000_000)
    note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def unique_results(self) -> BatchComplete:
        if len(set(self.result_ids)) != len(self.result_ids):
            raise ValueError("Results must be unique")
        return self


class BatchResponse(RecordResponse):
    study_id: uuid.UUID
    decision_id: uuid.UUID
    campaign_id: uuid.UUID
    round_id: uuid.UUID
    manifest: dict
    digest: str
    receipt: dict | None


class LearningPage(BaseModel):
    items: list[
        AssayResponse
        | StudyResponse
        | DatasetResponse
        | ModelResponse
        | LearningDecisionResponse
        | EvidenceResponse
        | BatchResponse
    ]
    next_cursor: str | None = None
