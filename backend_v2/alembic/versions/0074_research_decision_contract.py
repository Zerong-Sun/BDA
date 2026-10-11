"""Explicit criteria and evidence links for a research goal, with no inferred backfill."""

import sqlalchemy as sa

from alembic import op

revision = "0074_research_decision_contract"
down_revision = "0073_learning_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("research_goals", sa.Column("decision_contract", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("research_goals", "decision_contract")
