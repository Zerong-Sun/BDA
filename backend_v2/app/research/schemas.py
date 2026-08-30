from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


class BriefCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = ""
    scope: dict = Field(default_factory=dict)


class BriefResponse(BriefCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class BriefUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = None
    scope: dict | None = None
    status: str | None = Field(default=None, min_length=1, max_length=40)


class BriefPage(BaseModel):
    items: list[BriefResponse]
    next_cursor: str | None = None


FindingOutcome = Literal["supported", "refuted", "inconclusive", "unspecified"]


class FindingCreate(BaseModel):
    brief_id: uuid.UUID | None = None
    finding_type: str = "observation"
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    evidence: dict = Field(default_factory=dict)
    # How the question resolved. "refuted" is a first-class result, not a failure state.
    outcome: FindingOutcome = "unspecified"
    # The finding this one overturns, if any.
    supersedes_id: uuid.UUID | None = None
    # {"job_ids": [...], "candidate_ids": [...], "artifact_ids": [...]}
    provenance: dict = Field(default_factory=dict)


class FindingResponse(FindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class FindingUpdate(BaseModel):
    brief_id: uuid.UUID | None = None
    finding_type: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1)
    evidence: dict | None = None
    outcome: FindingOutcome | None = None
    supersedes_id: uuid.UUID | None = None
    provenance: dict | None = None


class FindingPage(BaseModel):
    items: list[FindingResponse]
    next_cursor: str | None = None


class ResearchOverview(BaseModel):
    briefs: list[BriefResponse]
    findings: list[FindingResponse]


class LocalizedResearchText(BaseModel):
    zh: str | None = None
    en: str | None = None
    default: str = ""


class ResearchWorkspaceProject(BaseModel):
    id: uuid.UUID
    name: LocalizedResearchText
    summary: LocalizedResearchText
    project_type: str
    source_package_id: str | None = None
    source_project_key: str | None = None
    package: dict[str, Any] = Field(default_factory=dict)
    primary_target: dict[str, Any] | None = None


class ResearchWorkspaceReviewDocument(BaseModel):
    id: uuid.UUID
    title: LocalizedResearchText
    content: LocalizedResearchText
    status: str
    scope: dict[str, Any] = Field(default_factory=dict)
    version: int
    updated_at: datetime


class ResearchWorkspaceFinding(BaseModel):
    id: uuid.UUID
    finding_type: str
    title: LocalizedResearchText
    content: LocalizedResearchText
    evidence: dict[str, Any] = Field(default_factory=dict)
    version: int
    created_at: datetime
    updated_at: datetime


class ResearchWorkspaceSection(BaseModel):
    track: str
    items: list[ResearchWorkspaceFinding] = Field(default_factory=list)


class ResearchWorkspaceGraphNode(BaseModel):
    id: str
    kind: str = "evidence"
    label: LocalizedResearchText
    description: LocalizedResearchText
    reference_ids: list[str] = Field(default_factory=list)
    review_status: str = "accepted"


class ResearchWorkspaceGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    source_label: LocalizedResearchText
    target_label: LocalizedResearchText
    predicate: str
    summary: LocalizedResearchText
    context: LocalizedResearchText
    assertion: str
    evidence_grade: str
    reference_ids: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    review_status: str = "pending_review"


class ResearchWorkspaceReference(BaseModel):
    document_id: uuid.UUID
    ref_id: str
    title: LocalizedResearchText
    authors: str = ""
    journal: str = ""
    year: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    abstract: str = ""
    url: str = ""
    verification_status: str = ""
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchWorkspaceStructure(BaseModel):
    artifact_id: uuid.UUID
    pdb_id: str | None = None
    name: LocalizedResearchText
    role: LocalizedResearchText
    method: LocalizedResearchText
    resolution: float | None = None
    reference_id: str = ""
    rcsb_url: str = ""
    download_url: str | None = None
    status: str
    lineage: dict[str, Any] = Field(default_factory=dict)


class ResearchWorkspaceTarget(BaseModel):
    id: uuid.UUID
    candidate_key: str
    name: LocalizedResearchText
    pain_group: LocalizedResearchText
    gene: str = ""
    protein_type: LocalizedResearchText
    localization: LocalizedResearchText
    axis: LocalizedResearchText
    score: float | None = None
    rank: int | None = None
    scores: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)
    reference_ids: list[str] = Field(default_factory=list)
    review_status: str = ""


class ResearchWorkspaceKnowledge(BaseModel):
    id: uuid.UUID
    key: str
    title: LocalizedResearchText
    content: LocalizedResearchText
    data: Any | None = None
    display_data: Any | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    version: int


class ResearchWorkspaceResponse(BaseModel):
    project: ResearchWorkspaceProject
    review_document: ResearchWorkspaceReviewDocument | None = None
    review_sections: list[ResearchWorkspaceSection] = Field(default_factory=list)
    graph_nodes: list[ResearchWorkspaceGraphNode] = Field(default_factory=list)
    graph_edges: list[ResearchWorkspaceGraphEdge] = Field(default_factory=list)
    references: list[ResearchWorkspaceReference] = Field(default_factory=list)
    structures: list[ResearchWorkspaceStructure] = Field(default_factory=list)
    research_targets: list[ResearchWorkspaceTarget] = Field(default_factory=list)
    methods: list[ResearchWorkspaceKnowledge] = Field(default_factory=list)
    datasets: list[ResearchWorkspaceKnowledge] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class ResearchGenerationCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    strata: str = Field(default="", max_length=1000)
    candidate_count: int = Field(default=10, ge=1, le=100)
    evidence_cutoff: date | None = None
    language: Literal["en", "zh"] = "en"
    conversation_id: uuid.UUID | None = None
    use_external_evidence: bool = True


class ResearchGapResolutionCreate(BaseModel):
    resolve_references: bool = True
    resolve_structure: bool = True

    @model_validator(mode="after")
    def require_resolution_scope(self) -> ResearchGapResolutionCreate:
        if not self.resolve_references and not self.resolve_structure:
            raise PydanticCustomError(
                "gap_resolution_scope_required",
                "At least one gap resolution scope must be enabled",
            )
        return self


class ResearchGapResolutionAccepted(BaseModel):
    operation_id: uuid.UUID
    research_target_id: uuid.UUID
    status: str = "pending"


class ResearchDraftV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"]
    project: dict[str, Any]
    primary_target: dict[str, Any] | None = None
    review_document: dict[str, Any] | None = None
    review_sections: list[dict[str, Any]] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    graph_nodes: list[dict[str, Any]] = Field(default_factory=list)
    graph_edges: list[dict[str, Any]] = Field(default_factory=list)
    structures: list[dict[str, Any]] = Field(default_factory=list)
    research_targets: list[dict[str, Any]] = Field(default_factory=list)
    methods: list[dict[str, Any]] = Field(default_factory=list)
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any]
    counts: dict[str, int]


class ResearchGenerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_project_id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: uuid.UUID | None
    status: str
    request: dict
    draft: dict
    validation: dict
    checksum: str | None
    imported_project_id: uuid.UUID | None
    error: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ResearchGenerationAccepted(BaseModel):
    generation_id: uuid.UUID
    operation_id: uuid.UUID
    status: Literal["pending"] = "pending"


class ResearchGenerationImportCreate(BaseModel):
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class ResearchGenerationImportResponse(BaseModel):
    generation_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    status: Literal["created", "unchanged"]
    checksum: str
    counts: dict[str, int]


class ResearchPackageImportCreate(BaseModel):
    organization_id: uuid.UUID
    package: dict


class ResearchPackageDescriptor(BaseModel):
    package_id: str
    version: str
    display_name: LocalizedResearchText
    license: str
    checksum: str
    size: int
    installed: bool = False


class ResearchPackageCatalogImportCreate(BaseModel):
    organization_id: uuid.UUID
    package_id: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class ResearchPackageProjectResult(BaseModel):
    source_project_key: str
    project_id: uuid.UUID
    status: str


class ResearchPackageImportResponse(BaseModel):
    package_id: str
    version: str
    projects: list[ResearchPackageProjectResult]
    counts: dict[str, int]
    pdb_operation_ids: list[uuid.UUID]
    conflicts: list[str] = Field(default_factory=list)


class CopilotResearchProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(min_length=1, max_length=200)
    project_type: str = Field(default="research", min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=10000)
    research_question: str = Field(min_length=1, max_length=5000)
    project_review: str = Field(min_length=1, max_length=100000, title="Project Review")
    methods: str = Field(default="", max_length=50000)


class CopilotResearchPrimaryTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=300)
    gene: str | None = Field(default=None, max_length=80)
    uniprot: str | None = Field(default=None, max_length=40)
    organism: str | None = Field(default=None, max_length=200)


class CopilotResearchReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    title: str = Field(min_length=1, max_length=500)
    authors: str = Field(default="", max_length=2000)
    journal: str = Field(default="", max_length=500)
    year: int | None = Field(default=None, ge=1600, le=2200)
    pmid: str | None = Field(default=None, max_length=20)
    doi: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=2000)


class CopilotResearchNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    kind: Literal["topic", "target", "disease", "pathway", "mechanism", "compound", "outcome", "evidence"]
    label: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    reference_ids: list[str] = Field(default_factory=list, max_length=100)


class CopilotResearchEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    predicate: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=10000)
    assertion: Literal["established_fact", "evidence_based_inference", "hypothesis", "counterevidence"]
    evidence_grade: Literal["A", "B", "C", "D"]
    reference_ids: list[str] = Field(min_length=1, max_length=100)


class CopilotResearchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    name: str = Field(min_length=1, max_length=240)
    summary: str = Field(default="", max_length=10000)
    score: float | None = Field(default=None, ge=0, le=100)
    reference_ids: list[str] = Field(default_factory=list, max_length=100)


class CopilotResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    project: CopilotResearchProject
    primary_target: CopilotResearchPrimaryTarget | None = None
    references: list[CopilotResearchReference] = Field(min_length=1, max_length=1000)
    nodes: list[CopilotResearchNode] = Field(min_length=1, max_length=2000)
    edges: list[CopilotResearchEdge] = Field(default_factory=list, max_length=5000)
    candidates: list[CopilotResearchCandidate] = Field(default_factory=list, max_length=1000)


class CopilotResearchResultCreate(BaseModel):
    organization_id: uuid.UUID
    result: str | dict


class CopilotResearchValidationResponse(BaseModel):
    valid: Literal[True] = True
    checksum: str
    project_name: str
    counts: dict[str, int]
    normalized: CopilotResearchResult


class CopilotResearchImportResponse(BaseModel):
    project_id: uuid.UUID
    project_name: str
    status: Literal["created", "unchanged"]
    checksum: str
    counts: dict[str, int]


# --- Research goal tree ------------------------------------------------------


class ResearchGoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = ""
    parent_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)


class ResearchGoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    detail: str | None = None
    status: str | None = Field(default=None, pattern="^(open|answered|abandoned)$")
    tags: list[str] | None = None
    #: Sent together: `parent_id` alone cannot express "make this a root", because
    #: null is also "field omitted". `reparent` says the move was intended.
    reparent: bool = False
    parent_id: uuid.UUID | None = None


class ResearchGoalLinkCreate(BaseModel):
    resource_type: str = Field(pattern="^(experiment_result|finding|candidate|job|protein)$")
    resource_id: uuid.UUID
    note: str = ""


class ResearchGoalLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    note: str


class ResearchGoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str
    detail: str
    status: str
    sort_order: int
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
    links: list[ResearchGoalLinkResponse] = Field(default_factory=list)


class ResearchGoalDeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool = True
    #: How many goals went with it, the subtree included.
    removed_goals: int = 1


class ResearchGoalLinkDeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool = True


class ResearchGoalTree(BaseModel):
    """Flat list plus parent pointers, not nested objects.

    A nested shape would have to pick a depth limit for its own type, and the
    client already has to index by id to render a tree it can expand and move.
    """

    items: list[ResearchGoalResponse]
