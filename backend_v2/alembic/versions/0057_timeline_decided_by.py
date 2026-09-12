"""Record whose judgement a timeline entry was.

Revision ID: 0057_timeline_decided_by
Revises: 0056_copilot_mcp_sessions

The platform is about to be asked whether an agent's parameters were better than a
person's. That question cannot be answered retrospectively: nothing in the schema said
who decided, so every row looked the same whether a researcher reasoned to it, a model
drafted it and someone accepted it, or a model decided it unreviewed.

`created_by` does not answer it either. An orchestrator recording an agent's judgement is
still a person's account of it, so the two columns are kept and they mean different
things: who wrote it down, and whose call it was.

The default is `unspecified` rather than `human`. Backfilling the existing rows to
`human` would be a guess stated as a record - the seeded history includes decisions taken
on the cluster with scripts in the loop - and a column whose first act is to assert
something nobody checked is worse than one that admits it does not know yet.

No index. `decided_by` is only ever filtered inside one project, where
`ix_timeline_project_occurred` already leads with `project_id` and the per-project row
count is in the tens; a single-column index would cost every write and answer nothing new.
Same reasoning `0052` recorded for `lane`.

The downgrade drops the column. The attribution is lost, which is the honest outcome:
there is nowhere else it was written.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0057_timeline_decided_by"
down_revision: str | None = "0056_copilot_mcp_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_timeline_entries",
        sa.Column("decided_by", sa.String(length=40), nullable=False, server_default="unspecified"),
    )


def downgrade() -> None:
    op.drop_column("project_timeline_entries", "decided_by")
