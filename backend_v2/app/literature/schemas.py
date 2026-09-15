from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LiteratureIngest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=80)
    external_id: str | None = None
    abstract: str | None = None
    artifact_id: uuid.UUID | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    source: str
    external_id: str | None
    abstract: str | None
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_json")
    artifact_id: uuid.UUID | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentResponse]
    next_cursor: str | None = None


class SubscriptionCreate(BaseModel):
    query: str = Field(min_length=1)
    cadence: str = "weekly"


class SubscriptionResponse(SubscriptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


class AsyncOperation(BaseModel):
    id: uuid.UUID
    status: str = "pending"


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    position: int
    content: str
    version: int
    created_at: datetime
    updated_at: datetime


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_id: uuid.UUID | None
    claim: str
    confidence: str
    attributes: dict
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    claim_id: uuid.UUID
    evidence_type: str
    content: str
    source_ref: dict
    version: int
    created_at: datetime
    updated_at: datetime


class RelationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    source_claim_id: uuid.UUID
    target_claim_id: uuid.UUID
    relation_type: str
    rationale: str | None
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class ReviewUpdate(BaseModel):
    review_status: str = Field(pattern="^(accepted|rejected|pending)$")


class DocumentDetail(BaseModel):
    document: DocumentResponse
    chunks: list[ChunkResponse]
    claims: list[ClaimResponse]
    evidence: list[EvidenceResponse]


class ClaimPage(BaseModel):
    items: list[ClaimResponse]
    next_cursor: str | None = None


class ChunkPage(BaseModel):
    items: list[ChunkResponse]
    next_cursor: str | None = None


class EvidencePage(BaseModel):
    items: list[EvidenceResponse]
    next_cursor: str | None = None


class RelationPage(BaseModel):
    items: list[RelationResponse]
    next_cursor: str | None = None


class SubscriptionPage(BaseModel):
    items: list[SubscriptionResponse]
    next_cursor: str | None = None


class SubscriptionUpdate(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    cadence: str | None = None
    enabled: bool | None = None


#: `europe_pmc_patents` is Europe PMC's patent index (`SRC:PAT`): CN, US, EP, WO,
#: JP and KR publications, searched and saved through the same audited path as
#: papers so a cited patent carries the same retrieval trace a cited paper does.
#: `epo_ops_patents` is EPO Open Patent Services: the DOCDB worldwide collection,
#: with a patent family id on every record. It needs a configured credential.
LiteratureSource = Literal["europe_pmc", "europe_pmc_patents", "epo_ops_patents"]
PATENT_SEARCH_SOURCES: frozenset[str] = frozenset({"europe_pmc_patents", "epo_ops_patents"})
PatentJurisdiction = Literal["CN", "US", "EP", "WO", "JP", "KR"]


def _default_literature_sources() -> list[LiteratureSource]:
    return ["europe_pmc"]


class LiteratureSearchCreate(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    sources: list[LiteratureSource] = Field(default_factory=_default_literature_sources, min_length=1)
    limit: int = Field(default=10, ge=1, le=25)
    fetch_full_text: bool = True
    extract_claims: bool = True
    #: Offices a patent search is restricted to. Stored apart from the query and
    #: applied after it is translated, so a rewrite of the words cannot drop it.
    jurisdictions: list[PatentJurisdiction] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _a_patent_search_is_one_source(self) -> LiteratureSearchCreate:
        patent_sources = PATENT_SEARCH_SOURCES.intersection(self.sources)
        if patent_sources and len(set(self.sources)) > 1:
            raise ValueError("A patent search names exactly one source.")
        if self.jurisdictions and not patent_sources:
            raise ValueError("Jurisdictions restrict a patent search only.")
        self.jurisdictions = list(dict.fromkeys(self.jurisdictions))
        return self


class LiteratureSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    query: str
    sources: list[str]
    jurisdictions: list[str] = Field(default_factory=list)
    requested_limit: int
    fetch_full_text: bool
    extract_claims: bool
    status: str
    result_count: int
    created_by: uuid.UUID
    error: str | None
    completed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class LiteratureSearchPage(BaseModel):
    items: list[LiteratureSearchResponse]
    next_cursor: str | None = None


class RetrievalTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    search_run_id: uuid.UUID | None
    document_id: uuid.UUID | None
    stage: str
    source: str
    request_json: dict
    response_metadata: dict
    status: str
    http_status: int | None
    response_checksum_sha256: str | None
    content_checksum_sha256: str | None
    content_type: str | None
    byte_count: int | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class RetrievalTracePage(BaseModel):
    items: list[RetrievalTraceResponse]
    next_cursor: str | None = None


class LiteratureSearchDetail(BaseModel):
    search: LiteratureSearchResponse
    traces: list[RetrievalTraceResponse]
