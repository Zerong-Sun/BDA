"""Let a seeder own its timeline rows, so re-running one does not duplicate history.

``project_timeline_entries`` as shipped in 0035 has no natural key, which is correct for
entries a person writes through the API but wrong for entries generated from a source
file. A seeder that reads a project's reasoning out of markdown and inserts it has to be
re-runnable - the source file keeps changing while the project is live - and without a
key its only options are "append duplicates" or "delete the project's history first".
Both are worse than the problem they solve; the second also destroys any hand-written
entry that happened to be in the same project.

``entry_key`` is that natural key, scoped per project. It is deliberately nullable:
Postgres treats NULLs as distinct in a UNIQUE constraint, so scripted history gets
idempotent upserts on (project_id, entry_key) while API-created entries stay
unconstrained and need no synthetic key invented for them.

Adopted from the parallel `journal_entries` design, which reached the same conclusion
independently and was consolidated into this table rather than shipped alongside it.

Revision ID: 0036_timeline_entry_key
Revises: 0035_project_timeline
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0036_timeline_entry_key"
down_revision: str | None = "0035_project_timeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "project_timeline_entries"
CONSTRAINT = "uq_timeline_entry_key"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("entry_key", sa.String(length=160), nullable=True))
    op.create_unique_constraint(CONSTRAINT, TABLE, ["project_id", "entry_key"])
    print(f"0036: added {TABLE}.entry_key")


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
    op.drop_column(TABLE, "entry_key")
