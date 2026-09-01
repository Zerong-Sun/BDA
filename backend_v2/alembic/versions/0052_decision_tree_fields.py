"""Give the timeline the three fields a decision *tree* needs, and nothing more.

Revision ID: 0052_decision_tree_fields
Revises: 0051_worker_project_rls

``project_timeline_entries`` could already record what happened and in what order. What
it could not record is the three things that separate a decision record from a diary:

* ``decision_ref`` - the number the researchers actually cite. The sweet-protein project
  lost D080-D099 because the numbers lived only in cluster submission scripts and free
  text; a column plus a unique constraint is what lets a checker answer "is D064
  recorded" at all.
* ``lane`` - dry / wet / both. The interesting decisions are ``both``: D109 used dry
  re-analysis to revoke a *wet* authorisation. Existing rows become ``unspecified``
  rather than being labelled ``dry`` in bulk, because a backfilled claim is still a
  claim and nobody made it.
* ``alternatives`` - the branches that were closed off. A record that shows only the
  path taken is a flowchart, and the option nobody can see the reason for is the one
  that gets re-opened.

No new table and no new index. ``lane`` is only ever filtered inside one project, where
``ix_timeline_project_occurred`` already leads with ``project_id``.

The downgrade drops all three columns and the constraint, which loses the decision
numbers. That is the honest behaviour for a reversible migration - the numbers exist in
``docs/*/DECISIONS.md`` and in the seeders, which is where they are re-derived from.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0052_decision_tree_fields"
down_revision: str | None = "0051_worker_project_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_timeline_entries",
        sa.Column("decision_ref", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "project_timeline_entries",
        # server_default so the ALTER can fill existing rows in one pass; the model
        # carries the same default for rows written afterwards.
        sa.Column("lane", sa.String(length=16), nullable=False, server_default="unspecified"),
    )
    op.add_column(
        "project_timeline_entries",
        sa.Column("alternatives", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_unique_constraint(
        "uq_timeline_decision_ref",
        "project_timeline_entries",
        ["project_id", "decision_ref"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_timeline_decision_ref", "project_timeline_entries", type_="unique")
    op.drop_column("project_timeline_entries", "alternatives")
    op.drop_column("project_timeline_entries", "lane")
    op.drop_column("project_timeline_entries", "decision_ref")
