"""Give a project somewhere to keep its decision record.

An early multi-arm study produced a valuable chain of reasoning - what was tried, what
was ruled out, which conclusions were later overturned - and all of it lived
in hand-written markdown. That is unqueryable, unlinked to the jobs and candidates it
describes, and free to drift from the data it claims to summarise. Meanwhile the
platform stored plenty of *outputs* (jobs, candidates, metrics) and plenty of *system*
actions (audit log, job events), but had no place for the judgement connecting them.

``project_timeline_entries`` is that place, and is deliberately domain-neutral: the
`entry_type` and `outcome` vocabularies are ones any project can fill, so the next
project gets a timeline by inserting rows rather than by adding tables.

Indexes are chosen for how the table is actually read, not by reflex:

- ``(project_id, occurred_at, id)`` - every read is "this project, in time order", and
  paging uses a keyset cursor on exactly that pair. Without it each page is a scan+sort.
- ``(project_id, entry_type)`` and ``(project_id, phase)`` - the filtered reads the
  table exists to support ("only the problems", "only phase 2").

``outcome`` reuses research_findings' vocabulary verbatim so that "what did this project
rule out" is one question with one set of values across both tables, rather than two
near-synonymous enums that have to be reconciled by hand later.

Revision ID: 0035_project_timeline
Revises: 0034_parameter_order_pairs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0035_project_timeline"
down_revision: str | None = "0034_parameter_order_pairs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "project_timeline_entries"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Distinct from created_at on purpose: entries are frequently written up after
        # the fact, and without this the whole timeline collapses onto the day it was typed.
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_type", sa.String(length=40), nullable=False, server_default="decision"),
        sa.Column("phase", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(length=40), nullable=False, server_default="unspecified"),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("code_refs", sa.JSON(), nullable=False, server_default="[]"),
        # SET NULL rather than CASCADE: deleting a superseded entry must not silently
        # delete the entry that replaced it.
        sa.Column(
            "supersedes_id",
            sa.Uuid(),
            sa.ForeignKey(f"{TABLE}.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "caused_by_id",
            sa.Uuid(),
            sa.ForeignKey(f"{TABLE}.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_timeline_project_occurred", TABLE, ["project_id", "occurred_at", "id"])
    op.create_index("ix_timeline_project_type", TABLE, ["project_id", "entry_type"])
    op.create_index("ix_timeline_project_phase", TABLE, ["project_id", "phase"])
    # Only outcome gets a standalone index: project_id / occurred_at / entry_type /
    # phase are each already the leading column of a composite above, so separate indexes
    # would cost every write and buy nothing. "What did we rule out" is asked across
    # projects, so it cannot use a project_id-leading index.
    op.create_index("ix_project_timeline_entries_outcome", TABLE, ["outcome"])
    print(f"0035: created {TABLE}")


def downgrade() -> None:
    for name in (
        "ix_project_timeline_entries_outcome",
        "ix_timeline_project_phase",
        "ix_timeline_project_type",
        "ix_timeline_project_occurred",
    ):
        op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
