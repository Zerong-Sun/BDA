"""Persist private provider reasoning for faithful thinking-mode replay."""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0071_copilot_reasoning_content"
down_revision: str | None = "0070_af3_msa_port"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Historical messages remain NULL: their provider reasoning is unavailable.
    # Early bootstrap revisions create some tables from current metadata, so a
    # fresh install can already have these columns before reaching this revision.
    inspector = sa.inspect(op.get_bind())
    for table in ("copilot_agent_turns", "copilot_messages"):
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "reasoning_content" not in columns:
            op.add_column(table, sa.Column("reasoning_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("copilot_messages", "reasoning_content")
    op.drop_column("copilot_agent_turns", "reasoning_content")
