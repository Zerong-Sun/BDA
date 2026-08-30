from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin


class Campaign(UUIDVersionMixin, Base):
    __tablename__ = "campaigns"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class CampaignRound(UUIDVersionMixin, Base):
    __tablename__ = "campaign_rounds"
    __table_args__ = (UniqueConstraint("campaign_id", "round_number", name="uq_campaign_round_number"),)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="planned", index=True)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_runs.id"), nullable=True)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_submissions.id"), nullable=True)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)


class CampaignEvaluation(UUIDVersionMixin, Base):
    __tablename__ = "campaign_evaluations"
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign_rounds.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[str] = mapped_column(String(40), default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CampaignDecision(UUIDVersionMixin, Base):
    __tablename__ = "campaign_decisions"
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign_rounds.id", ondelete="CASCADE"), index=True)
    decision: Mapped[str] = mapped_column(String(80))
    rationale: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    parameter_patch: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
