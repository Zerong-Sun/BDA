"""Persist model admission before network I/O, independent of task rollback."""
import sqlalchemy as sa

from alembic import op

revision = "0077_copilot_call_guard"
down_revision = "0076_account_audit_compat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("copilot_call_budgets",
        sa.Column("scope_hash", sa.String(64), primary_key=True),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("reserved_cny_micros", sa.Integer(), nullable=False),
        sa.Column("max_calls", sa.Integer(), nullable=False))
    op.create_table("copilot_call_reservations",
        sa.Column("scope_hash", sa.String(64), primary_key=True),
        sa.Column("request_hash", sa.String(64), primary_key=True),
        sa.Column("reserved_cny_micros", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_table("copilot_call_reservations")
    op.drop_table("copilot_call_budgets")
