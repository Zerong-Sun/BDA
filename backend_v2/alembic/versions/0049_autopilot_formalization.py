"""Formalize immutable Autopilot drafts, budgets and audit identity.

Revision ID: 0049_autopilot_formalization
Revises: 0048_project_rls
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0049_autopilot_formalization"
down_revision: str | None = "0048_project_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _version_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), nullable=True, unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "autopilot_service_principals",
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allowed_actions", sa.JSON(), nullable=False),
        *_version_columns(),
    )
    op.create_table(
        "autopilot_drafts",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("structured_brief", sa.JSON(), nullable=False),
        sa.Column("normalized_spec", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("confirmed_campaign_id", sa.Uuid(), nullable=True, unique=True),
        *_version_columns(),
    )
    op.create_index("ix_autopilot_drafts_project_id", "autopilot_drafts", ["project_id"])
    op.create_index("ix_autopilot_drafts_created_by", "autopilot_drafts", ["created_by"])
    op.create_index("ix_autopilot_drafts_status", "autopilot_drafts", ["status"])
    op.create_table(
        "autopilot_campaigns",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_id", sa.Uuid(), sa.ForeignKey("autopilot_drafts.id"), nullable=False, unique=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("manual_campaign_id", sa.Uuid(), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("autonomy", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("frozen_prompt", sa.Text(), nullable=False),
        sa.Column("frozen_spec", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_operation_id", sa.Uuid(), sa.ForeignKey("operations.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("autonomy in ('supervised', 'plan_only')", name="ck_autopilot_autonomy"),
        *_version_columns(),
    )
    op.create_index("ix_autopilot_campaigns_project_id", "autopilot_campaigns", ["project_id"])
    op.create_index("ix_autopilot_campaigns_created_by", "autopilot_campaigns", ["created_by"])
    op.create_index("ix_autopilot_campaigns_manual_campaign_id", "autopilot_campaigns", ["manual_campaign_id"])
    op.create_index("ix_autopilot_campaigns_status", "autopilot_campaigns", ["status"])
    op.create_foreign_key(
        "fk_autopilot_draft_confirmed_campaign",
        "autopilot_drafts",
        "autopilot_campaigns",
        ["confirmed_campaign_id"],
        ["id"],
    )
    op.create_table(
        "autopilot_campaign_budgets",
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("gpu_seconds_limit", sa.Integer(), nullable=True),
        sa.Column("money_micros_limit", sa.Integer(), nullable=True),
        sa.Column("gpu_seconds_reserved", sa.Integer(), nullable=False),
        sa.Column("gpu_seconds_committed", sa.Integer(), nullable=False),
        sa.Column("money_micros_reserved", sa.Integer(), nullable=False),
        sa.Column("money_micros_committed", sa.Integer(), nullable=False),
        sa.CheckConstraint("gpu_seconds_limit is null or gpu_seconds_limit >= 0", name="ck_budget_gpu_limit"),
        sa.CheckConstraint("money_micros_limit is null or money_micros_limit >= 0", name="ck_budget_money_limit"),
        sa.CheckConstraint("gpu_seconds_reserved >= 0 and gpu_seconds_committed >= 0", name="ck_budget_gpu_used"),
        sa.CheckConstraint("money_micros_reserved >= 0 and money_micros_committed >= 0", name="ck_budget_money_used"),
        sa.CheckConstraint("gpu_seconds_limit is null or gpu_seconds_reserved + gpu_seconds_committed <= gpu_seconds_limit", name="ck_budget_gpu_hard_limit"),
        sa.CheckConstraint("money_micros_limit is null or money_micros_reserved + money_micros_committed <= money_micros_limit", name="ck_budget_money_hard_limit"),
        *_version_columns(),
    )
    op.create_table(
        "autopilot_stages",
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_key", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("operation_id", sa.Uuid(), sa.ForeignKey("operations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resource_type", sa.String(80), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.UniqueConstraint("campaign_id", "stage_key", name="uq_autopilot_stage_key"),
        *_version_columns(),
    )
    op.create_index("ix_autopilot_stages_campaign_id", "autopilot_stages", ["campaign_id"])
    op.create_index("ix_autopilot_stages_status", "autopilot_stages", ["status"])
    op.create_table(
        "autopilot_budget_reservations",
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.Uuid(), sa.ForeignKey("operations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("gpu_seconds", sa.Integer(), nullable=False),
        sa.Column("money_micros", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.UniqueConstraint("campaign_id", "idempotency_key", name="uq_autopilot_reservation_key"),
        sa.CheckConstraint("gpu_seconds >= 0 and money_micros >= 0", name="ck_reservation_nonnegative"),
        *_version_columns(),
    )
    op.create_index("ix_autopilot_budget_reservations_campaign_id", "autopilot_budget_reservations", ["campaign_id"])
    op.create_index("ix_autopilot_budget_reservations_operation_id", "autopilot_budget_reservations", ["operation_id"])
    op.create_index("ix_autopilot_budget_reservations_status", "autopilot_budget_reservations", ["status"])
    op.create_table(
        "autopilot_ledger_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("autopilot_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("writer_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("service_principal_id", sa.Uuid(), sa.ForeignKey("autopilot_service_principals.id"), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("(writer_user_id is not null and service_principal_id is null) or (writer_user_id is null and service_principal_id is not null)", name="ck_autopilot_ledger_one_writer"),
    )
    op.create_index("ix_autopilot_ledger_entries_campaign_id", "autopilot_ledger_entries", ["campaign_id"])
    op.create_index("ix_autopilot_ledger_entries_event_type", "autopilot_ledger_entries", ["event_type"])
    op.create_index("ix_autopilot_ledger_campaign_time", "autopilot_ledger_entries", ["campaign_id", "occurred_at", "id"])
    direct_expression = """
        current_setting('bda.is_global_admin', true) = 'true'
        OR EXISTS (
            SELECT 1 FROM projects p
            JOIN organization_members om ON om.organization_id = p.organization_id
            WHERE p.id = {table}.project_id
              AND om.user_id::text = current_setting('bda.user_id', true)
        )
    """
    for table in ("autopilot_drafts", "autopilot_campaigns"):
        expression = direct_expression.format(table=table)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_project_fence ON {table} USING ({expression}) WITH CHECK ({expression})")
    indirect_expression = """
        current_setting('bda.is_global_admin', true) = 'true'
        OR EXISTS (
            SELECT 1 FROM autopilot_campaigns ac
            JOIN projects p ON p.id = ac.project_id
            JOIN organization_members om ON om.organization_id = p.organization_id
            WHERE ac.id = {table}.campaign_id
              AND om.user_id::text = current_setting('bda.user_id', true)
        )
    """
    for table in (
        "autopilot_campaign_budgets",
        "autopilot_budget_reservations",
        "autopilot_stages",
        "autopilot_ledger_entries",
    ):
        expression = indirect_expression.format(table=table)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_project_fence ON {table} USING ({expression}) WITH CHECK ({expression})")


def downgrade() -> None:
    op.drop_table("autopilot_ledger_entries")
    op.drop_table("autopilot_budget_reservations")
    op.drop_table("autopilot_stages")
    op.drop_table("autopilot_campaign_budgets")
    op.drop_constraint("fk_autopilot_draft_confirmed_campaign", "autopilot_drafts", type_="foreignkey")
    op.drop_table("autopilot_campaigns")
    op.drop_table("autopilot_drafts")
    op.drop_table("autopilot_service_principals")
