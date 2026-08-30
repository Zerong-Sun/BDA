from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class LiteratureDocument(UUIDVersionMixin, Base):
    __tablename__ = "literature_documents"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(80))
    external_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")


class LiteratureChunk(UUIDVersionMixin, Base):
    __tablename__ = "literature_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("literature_documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)


class LiteratureClaim(UUIDVersionMixin, Base):
    __tablename__ = "literature_claims"
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("literature_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("literature_chunks.id"), nullable=True)
    claim: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(40), default="unknown")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LiteratureEvidence(UUIDVersionMixin, Base):
    __tablename__ = "literature_evidence"
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("literature_claims.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[dict] = mapped_column(JSON, default=dict)


class LiteratureRelation(UUIDVersionMixin, Base):
    __tablename__ = "literature_relations"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("literature_claims.id", ondelete="CASCADE"))
    target_claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("literature_claims.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(String(80))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LiteratureSubscription(UUIDVersionMixin, Base):
    __tablename__ = "literature_subscriptions"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(Text)
    cadence: Mapped[str] = mapped_column(String(80), default="weekly")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LiteratureSearchRun(UUIDVersionMixin, Base):
    __tablename__ = "literature_search_runs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    requested_limit: Mapped[int] = mapped_column(Integer, default=10)
    fetch_full_text: Mapped[bool] = mapped_column(default=True)
    extract_claims: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LiteratureRetrievalTrace(UUIDVersionMixin, Base):
    __tablename__ = "literature_retrieval_traces"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    search_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("literature_search_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("literature_documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    request_json: Mapped[dict] = mapped_column(JSON, default=dict)
    response_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    byte_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
