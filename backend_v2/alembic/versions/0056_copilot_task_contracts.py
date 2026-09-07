"""Persist task scope and delivery outcomes independently of execution status."""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0056_copilot_task_contracts"
down_revision: str | None = "0055_autopilot_worker_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("task_contract", "outcome"):
        op.add_column("copilot_agent_runs", sa.Column(column, sa.JSON(), nullable=False, server_default="{}"))
        op.alter_column("copilot_agent_runs", column, server_default=None)
    # Historical empty lists meant inherited defaults. Preserve that decision;
    # newly saved empty lists mean no tools, while omitted values inherit.
    op.execute("""UPDATE copilot_configs SET enabled_skills = '["research"]' WHERE CAST(enabled_skills AS TEXT) = '[]'""")


def downgrade() -> None:
    op.drop_column("copilot_agent_runs", "outcome")
    op.drop_column("copilot_agent_runs", "task_contract")
