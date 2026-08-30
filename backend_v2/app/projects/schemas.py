from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    project_type: str = Field(min_length=1, max_length=80)
    summary: str | None = Field(default=None, max_length=5000)
    prompt: str = Field(min_length=1, max_length=20000)
    source_package_id: str | None = Field(default=None, max_length=240)
    source_project_key: str | None = Field(default=None, max_length=80)
    localized_content: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=5000)
    prompt: str | None = Field(default=None, max_length=20000)
    status: str | None = Field(default=None, pattern="^(draft|active|paused|completed)$")
    localized_content: dict | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legacy_id: str | None
    organization_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    project_type: str
    summary: str | None
    prompt: str | None
    status: str
    source_package_id: str | None
    source_project_key: str | None
    localized_content: dict
    primary_target_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectResponse]
    next_cursor: str | None = None


class ProjectLibraryItem(ProjectResponse):
    research_candidate_count: int = 0
    finding_count: int = 0
    reference_count: int = 0
    knowledge_count: int = 0
    structure_count: int = 0
    primary_structure_ready: bool = False
    package_version: str | None = None
    evidence_as_of: str | None = None


class ProjectLibraryPage(BaseModel):
    items: list[ProjectLibraryItem]
    next_cursor: str | None = None


class DeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool
    retention_days: int = 30


class CandidateFunnelResponse(BaseModel):
    generated: int
    designed: int
    folded: int
    scored: int
    ordered: int


class TargetReadinessResponse(BaseModel):
    stage: str
    ready_for_workflow: bool
    blockers: list[str]
    next_action: str
    target_id: uuid.UUID | None
    structure_artifact_id: uuid.UUID | None
    identity_status: str | None
    structure_status: str | None


class ProjectOverviewResponse(BaseModel):
    project: ProjectResponse
    funnel: CandidateFunnelResponse
    candidate_count: int
    experiment_result_count: int
    available_artifact_count: int
    active_job_count: int
    latest_workflow_id: uuid.UUID | None
    target_readiness: TargetReadinessResponse
    next_action: str


class ProjectResearchSummaryResponse(BaseModel):
    brief: dict | None
    findings: list[dict]
    literature_document_count: int
    intelligence_run_count: int
    knowledge_entry_count: int


class ProjectPromptDraftCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    project_type: str = Field(min_length=1, max_length=80)
    summary: str | None = Field(default=None, max_length=5000)
    llm_provider_id: uuid.UUID | None = None


class ProjectPromptDraftAccepted(BaseModel):
    draft_id: uuid.UUID


class ProjectPromptDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    prompt: str | None
    error: str | None
