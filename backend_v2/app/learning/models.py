from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class LearningAssay(UUIDVersionMixin, Base):
    """Immutable measurement contract; a changed method is a new row."""

    __tablename__ = "learning_assays"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(40))
    conditions: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LearningStudy(UUIDVersionMixin, Base):
    """Frozen optimization contract linked to the existing research goal."""

    __tablename__ = "learning_studies"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    assay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_assays.id"), index=True)
    research_goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_goals.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    goal_snapshot: Mapped[dict] = mapped_column(JSON)
    direction: Mapped[str] = mapped_column(String(10))
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    batch_budget_cents: Mapped[int] = mapped_column(Integer)
    max_batch_size: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("learning_studies.id"), nullable=True)
    stop_on_threshold: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    max_rounds: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LearningDataset(UUIDVersionMixin, Base):
    __tablename__ = "learning_datasets"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_studies.id"), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LearningModel(UUIDVersionMixin, Base):
    __tablename__ = "learning_models"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_studies.id"), index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_datasets.id"), index=True)
    algorithm: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="shadow")
    parameters: Mapped[dict] = mapped_column(JSON)
    evaluation: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LearningDecision(UUIDVersionMixin, Base):
    """An immutable proposal plus an explicit human review; never a purchase."""

    __tablename__ = "learning_decisions"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_studies.id"), index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_models.id"), index=True)
    timeline_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_timeline_entries.id", ondelete="SET NULL"), nullable=True
    )
    proposal_digest: Mapped[str] = mapped_column(String(64))
    proposal: Mapped[dict] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(24), default="pending")
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LearningEvidence(UUIDVersionMixin, Base):
    """Sourced learning state; withdrawal keeps the original assertion and sources."""

    __tablename__ = "learning_evidence"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_studies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    statement: Mapped[str] = mapped_column(Text)
    sources: Mapped[dict] = mapped_column(JSON)
    withdrawal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class LearningBatch(UUIDVersionMixin, Base):
    """Evidence bridge to a campaign round; Campaign owns execution state."""

    __tablename__ = "learning_batches"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_studies.id"), index=True)
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_decisions.id"), unique=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign_rounds.id"), unique=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
