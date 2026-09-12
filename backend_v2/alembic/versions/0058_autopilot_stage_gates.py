"""Decide per stage whether a person has to let it through, not per campaign.

Revision ID: 0058_autopilot_stage_gates
Revises: 0057_timeline_decided_by

`autonomy` is a campaign-level dial with two positions, and that granularity is the
failure mode rather than the control: a supervised campaign either asks about every step,
in which case the reviewer approves without reading, or it asks about none. What decides
whether a step needs a person is not a dial set once - it is whether the step is
reversible, and whether it is a value question or an empirical one.

Three columns:

* ``risk_tier`` - copied from `gates.STAGE_TIERS` at confirmation rather than looked up on
  each read. The tier is part of what was approved: reclassifying a stage key later must
  not silently re-open a campaign somebody confirmed under the old classification.
* ``released_at`` / ``released_by`` - when a held stage was let through, and by whom. A
  held stage with both NULL is exactly the state the worker refuses to advance past.

Existing stages backfill to ``reversible_draft``. That is not a guess: every stage adapter
that exists today produces a draft, and there is no path from an Autopilot stage to a
submission - so no existing row is being relabelled as safer than it was. New campaigns get
their tier from the table, where an unclassified stage key is held.

The downgrade drops all three. A campaign mid-hold loses the hold, which is the honest
consequence: the worker on the older code has no concept of one, so leaving the columns
would preserve a fence nothing reads.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0058_autopilot_stage_gates"
down_revision: str | None = "0057_timeline_decided_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "autopilot_stages",
        sa.Column("risk_tier", sa.String(length=32), nullable=False, server_default="reversible_draft"),
    )
    op.add_column(
        "autopilot_stages", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("autopilot_stages", sa.Column("released_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_autopilot_stages_released_by_users",
        "autopilot_stages",
        "users",
        ["released_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_autopilot_stages_released_by_users", "autopilot_stages", type_="foreignkey")
    op.drop_column("autopilot_stages", "released_by")
    op.drop_column("autopilot_stages", "released_at")
    op.drop_column("autopilot_stages", "risk_tier")
