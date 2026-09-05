"""Let a person take an automatic campaign back, on the record.

Revision ID: 0054_autopilot_takeover
Revises: 0053_decision_tree_drafts

A confirmed campaign's protocol is immutable, and that is right: budget and permission
checks rest on the spec not changing under them. Its *products* are a different matter.
Once a stage adapter creates a real workflow run and real candidates, an automatic
campaign can be wrong in the ordinary way research is wrong, and the person who notices
has to be able to correct it.

Doing that by quietly editing the products would give two authorities over one campaign
with no record of which was acting. So takeover is a state, not a convention:

* ``taken_over_at`` / ``taken_over_by`` - when, and who. Nullable because most campaigns
  are never taken over, and a default would claim a handover that never happened.
* ``status`` gains ``manual_takeover`` as a value. No CHECK constraint is added: the
  column never had one (unlike ``autonomy``), the vocabulary is enforced in the service,
  and adding one here would fail on any row a future status lands in before its migration.

The ledger entry that accompanies the transition is written by the service, not here.

The downgrade drops both columns. Campaigns sitting in ``manual_takeover`` are moved back
to ``running`` rather than being left holding a status the code no longer knows - a
downgrade that leaves unreadable rows behind is not reversible, it is just quiet.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0054_autopilot_takeover"
down_revision: str | None = "0053_decision_tree_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "autopilot_campaigns",
        sa.Column("taken_over_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "autopilot_campaigns",
        sa.Column("taken_over_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_autopilot_campaigns_taken_over_by_users",
        "autopilot_campaigns",
        "users",
        ["taken_over_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute("update autopilot_campaigns set status = 'running' where status = 'manual_takeover'")
    op.drop_constraint(
        "fk_autopilot_campaigns_taken_over_by_users", "autopilot_campaigns", type_="foreignkey"
    )
    op.drop_column("autopilot_campaigns", "taken_over_by")
    op.drop_column("autopilot_campaigns", "taken_over_at")
