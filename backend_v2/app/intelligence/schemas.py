from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IntelligenceCreate(BaseModel):
    target_id: uuid.UUID
    query: dict = Field(default_factory=dict)


class IntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    target_id: uuid.UUID
    status: str
    query: dict
    version: int
    created_at: datetime
    updated_at: datetime


class IntelligencePage(BaseModel):
    items: list[IntelligenceResponse]
    next_cursor: str | None = None


class ReportReview(BaseModel):
    review_status: str
    summary: str | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    title: str
    summary: str
    review_status: str
    content: dict
    version: int
    created_at: datetime
    updated_at: datetime


class RouteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    name: str
    status: str
    workflow_spec: dict
    applied_workflow_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class ExportResponse(BaseModel):
    run_id: uuid.UUID
    operation_id: uuid.UUID
    status: str = "pending"


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    evidence_type: str
    citation: dict
    content: str
    confidence: float | None
    review_status: str
    version: int
    created_at: datetime
    updated_at: datetime


class HotspotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    label: str
    residues: list
    rationale: str | None
    review_status: str
    version: int
    created_at: datetime
    updated_at: datetime


class IntelligenceDetail(BaseModel):
    run: IntelligenceResponse
    report: ReportResponse | None
    evidence: list[EvidenceResponse]
    hotspots: list[HotspotResponse]
    routes: list[RouteResponse]


class EvidenceReview(BaseModel):
    review_status: str = Field(pattern="^(accepted|rejected|pending)$")
    confidence: float | None = Field(default=None, ge=0, le=1)


class HotspotReview(BaseModel):
    review_status: str = Field(pattern="^(accepted|rejected|pending)$")
    rationale: str | None = None
