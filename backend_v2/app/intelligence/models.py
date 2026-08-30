from __future__ import annotations

import uuid

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class IntelligenceRun(UUIDVersionMixin, Base):
    __tablename__ = "intelligence_runs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("targets.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    query: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class IntelligenceReport(UUIDVersionMixin, Base):
    __tablename__ = "intelligence_reports"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intelligence_runs.id", ondelete="CASCADE"), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(40), default="draft")
    content: Mapped[dict] = mapped_column(JSON, default=dict)


class IntelligenceEvidence(UUIDVersionMixin, Base):
    __tablename__ = "intelligence_evidence"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intelligence_runs.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(80))
    citation: Mapped[dict] = mapped_column(JSON, default=dict)
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)


class IntelligenceHotspot(UUIDVersionMixin, Base):
    __tablename__ = "intelligence_hotspots"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intelligence_runs.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    residues: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)


class DesignRoute(UUIDVersionMixin, Base):
    __tablename__ = "design_routes"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intelligence_runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40), default="proposed")
    workflow_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    applied_workflow_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_runs.id"), nullable=True)
