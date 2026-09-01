from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.models import Base, UUIDVersionMixin, utcnow


class AutopilotServicePrincipal(UUIDVersionMixin, Base):
    __tablename__ = "autopilot_service_principals"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    allowed_actions: Mapped[list[str]] = mapped_column(JSON, default=list)


class AutopilotDraft(UUIDVersionMixin, Base):
    __tablename__ = "autopilot_drafts"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    structured_brief: Mapped[dict] = mapped_column(JSON, default=dict)
    normalized_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    confirmed_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "autopilot_campaigns.id",
            name="fk_autopilot_draft_confirmed_campaign",
            use_alter=True,
        ),
        nullable=True,
        unique=True,
    )


class AutopilotCampaign(UUIDVersionMixin, Base):
    __tablename__ = "autopilot_campaigns"
    __table_args__ = (CheckConstraint("autonomy in ('supervised', 'plan_only')", name="ck_autopilot_autonomy"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("autopilot_drafts.id"), unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    manual_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(240))
    autonomy: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), default="confirmed", index=True)
    frozen_prompt: Mapped[str] = mapped_column(Text)
    frozen_spec: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operations.id", ondelete="SET NULL"), nullable=True
    )


class CampaignBudget(UUIDVersionMixin, Base):
    __tablename__ = "autopilot_campaign_budgets"
    __table_args__ = (
        CheckConstraint("gpu_seconds_limit is null or gpu_seconds_limit >= 0", name="ck_budget_gpu_limit"),
        CheckConstraint("money_micros_limit is null or money_micros_limit >= 0", name="ck_budget_money_limit"),
        CheckConstraint("gpu_seconds_reserved >= 0 and gpu_seconds_committed >= 0", name="ck_budget_gpu_used"),
        CheckConstraint("money_micros_reserved >= 0 and money_micros_committed >= 0", name="ck_budget_money_used"),
        CheckConstraint(
            "gpu_seconds_limit is null or gpu_seconds_reserved + gpu_seconds_committed <= gpu_seconds_limit",
            name="ck_budget_gpu_hard_limit",
        ),
        CheckConstraint(
            "money_micros_limit is null or money_micros_reserved + money_micros_committed <= money_micros_limit",
            name="ck_budget_money_hard_limit",
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), unique=True
    )
    gpu_seconds_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    money_micros_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpu_seconds_reserved: Mapped[int] = mapped_column(Integer, default=0)
    gpu_seconds_committed: Mapped[int] = mapped_column(Integer, default=0)
    money_micros_reserved: Mapped[int] = mapped_column(Integer, default=0)
    money_micros_committed: Mapped[int] = mapped_column(Integer, default=0)


class BudgetReservation(UUIDVersionMixin, Base):
    __tablename__ = "autopilot_budget_reservations"
    __table_args__ = (
        UniqueConstraint("campaign_id", "idempotency_key", name="uq_autopilot_reservation_key"),
        CheckConstraint("gpu_seconds >= 0 and money_micros >= 0", name="ck_reservation_nonnegative"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), index=True
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160))
    gpu_seconds: Mapped[int] = mapped_column(Integer)
    money_micros: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="reserved", index=True)


class AutopilotStage(UUIDVersionMixin, Base):
    __tablename__ = "autopilot_stages"
    __table_args__ = (UniqueConstraint("campaign_id", "stage_key", name="uq_autopilot_stage_key"),)

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), index=True
    )
    stage_key: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operations.id", ondelete="SET NULL"), nullable=True
    )
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class AutopilotLedgerEntry(Base):
    __tablename__ = "autopilot_ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "(writer_user_id is not null and service_principal_id is null) or "
            "(writer_user_id is null and service_principal_id is not null)",
            name="ck_autopilot_ledger_one_writer",
        ),
        Index("ix_autopilot_ledger_campaign_time", "campaign_id", "occurred_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), index=True
    )
    writer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    service_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("autopilot_service_principals.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
