"""Record which operator is accountable for each stage of a campaign.

Revision ID: 0061_autopilot_stage_operator
Revises: 0060_copilot_handoffs

A stage carried a tier and a resource and no operator. `gates.py` answered whether a step
may act without a person; nothing answered whose job it was when it did - so a campaign,
which is the platform's own name for running the research phases in order, was the one
place the chain ran with none of the roster's charters applying to it.

Frozen at confirmation rather than looked up at execution, exactly like `risk_tier` beside
it. Who carries a stage is part of the protocol a person approved: re-staffing a stage key
later must not change who ran a campaign somebody already confirmed, any more than
reclassifying its risk may re-open one.

Nullable, with no default. Some stages deliberately have no operator - collection moves
artifacts rather than reasoning about them, and a review stage is a person's judgement -
so NULL is a real state and `operators.UNSTAFFED` records which keys are in it and why. A
`server_default` would erase the difference between "no operator by design" and "confirmed
before this column existed".

No index. It is read one stage at a time, alongside the row.

The downgrade drops the column. A campaign in flight keeps its stages, its tiers and its
holds; it loses the name of who was carrying each step, which is the honest outcome - the
accountability lives in the roster and this column was the pointer at it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0061_autopilot_stage_operator"
down_revision: str | None = "0060_copilot_handoffs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("autopilot_stages", sa.Column("operator", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("autopilot_stages", "operator")
