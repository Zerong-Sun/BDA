"""Give the bots a channel to hand work to each other across.

Revision ID: 0060_copilot_handoffs
Revises: 0059_copilot_agent_run_bot

`0059` gave a run its operator. It did not give two operators anything to say to each
other. `BotSpec.handoff` named a successor in prose and the module said so outright -
handoffs are advisory - so nothing crossed the boundary between one phase of the chain
and the next. That is what made the roster a split of tools rather than a split of
responsibilities: an operator that cannot hand anything over also cannot be held to what
it handed over, and nobody can check work they cannot read.

A row here is one handover. Append-only, and that is the point rather than an
implementation convenience: an edited handover stops being a record of the chain and
becomes the last operator's account of it, which is exactly the thing a reviewer is there
to not have to trust.

`claims` is why this is a table and not a text column on the run. A prose summary can only
be read. A list of {statement, evidence_ref, confidence} can be checked - "claim 3 cites
nothing" is a lookup, not an interpretation - and a defined output is what separates a
review stance from a second opinion.

`from_bot` and `to_bot` are strings, not foreign keys. The roster lives in code, and
retiring a bot must not take its history with it; the ids are validated against the roster
at write time, where a wrong one is a caller error, rather than at read time, where it
would turn old rows unreadable.

`produced_by_run` is nullable because a chat turn has no transcript behind it. That is a
real state and not a missing value: the auditor reports a note with no run as unreviewable
rather than as clean.

The downgrade drops the table. The notes are copilot bookkeeping - no domain row points at
one - so dropping it loses the conversation between operators and nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0060_copilot_handoffs"
down_revision: str | None = "0059_copilot_agent_run_bot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "copilot_handoffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # From `UUIDVersionMixin`, like every other table here. Unused by this
        # domain - nothing was migrated into it - but `alembic check` compares
        # against the model, and a table missing it is drift.
        sa.Column("legacy_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_bot", sa.String(length=80), nullable=False),
        sa.Column("to_bot", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("claims", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("open_questions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "produced_by_run",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot_agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.CheckConstraint("length(from_bot) > 0", name="ck_copilot_handoff_from_bot"),
        sa.CheckConstraint("length(to_bot) > 0", name="ck_copilot_handoff_to_bot"),
    )
    op.create_index("ix_copilot_handoffs_project_id", "copilot_handoffs", ["project_id"])
    op.create_index("ix_copilot_handoffs_from_bot", "copilot_handoffs", ["from_bot"])
    op.create_index("ix_copilot_handoffs_created_by", "copilot_handoffs", ["created_by"])
    op.create_index("ix_copilot_handoffs_produced_by_run", "copilot_handoffs", ["produced_by_run"])
    # The recipient's read is "addressed to me, in this project, newest first".
    op.create_index(
        "ix_copilot_handoffs_inbox",
        "copilot_handoffs",
        ["project_id", "to_bot", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_copilot_handoffs_inbox", table_name="copilot_handoffs")
    op.drop_index("ix_copilot_handoffs_produced_by_run", table_name="copilot_handoffs")
    op.drop_index("ix_copilot_handoffs_created_by", table_name="copilot_handoffs")
    op.drop_index("ix_copilot_handoffs_from_bot", table_name="copilot_handoffs")
    op.drop_index("ix_copilot_handoffs_project_id", table_name="copilot_handoffs")
    op.drop_table("copilot_handoffs")
