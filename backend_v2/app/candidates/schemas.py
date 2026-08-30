from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CandidateCreate(BaseModel):
    candidate_key: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=240)
    candidate_kind: str = Field(default="design_candidate", pattern="^(design_candidate|research_target)$")
    status: str = "proposed"
    rank: int | None = Field(default=None, ge=1)
    score: float | None = None
    scores: dict = Field(default_factory=dict)
    properties: dict = Field(default_factory=dict)
    structure_artifact_id: uuid.UUID | None = None
    complex_artifact_id: uuid.UUID | None = None
    source_job_id: uuid.UUID | None = None


class CandidateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = None
    rank: int | None = Field(default=None, ge=1)
    score: float | None = None
    scores: dict | None = None
    properties: dict | None = None
    structure_artifact_id: uuid.UUID | None = None
    complex_artifact_id: uuid.UUID | None = None


class CandidateResponse(CandidateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class CandidatePage(BaseModel):
    items: list[CandidateResponse]
    next_cursor: str | None = None


class CandidateMetricResponse(BaseModel):
    """One number, with enough provenance to judge how much it is worth."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    metric_key: str
    value: float
    method: str
    model_variant: str
    evidence_kind: str
    # "design_model" marks a self-assessment: the model that produced the design also
    # scored it. Surfaced so a reader can tell corroboration from self-report.
    assessor: str
    # The assay condition the value belongs to, e.g. the ligand screened against.
    condition: str
    unit: str
    context: dict
    source_job_id: uuid.UUID | None = None
    # Set on measured values instead of source_job_id: a bench number traces to
    # the experiment result that recorded it, which points at the instrument
    # file it was read from.
    source_experiment_result_id: uuid.UUID | None = None
    created_at: datetime


class CandidateMetricList(BaseModel):
    items: list[CandidateMetricResponse]
