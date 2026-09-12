"""Record which bot a durable agent run was created for.

Revision ID: 0059_copilot_agent_run_bot
Revises: 0058_autopilot_stage_gates

`allowed_tools` already records what a run may do, and until now that was taken to be the
whole of a run's mandate. It is not. A bot is two things: a capability set, which
`allowed_tools` captures, and a charter - what the operator is accountable for and, mostly,
what it must refuse - which nothing in the schema held. A run created for the medic and a
run created for the planner could end up with the same tools and the same instructions,
which makes selecting a bot a UI gesture rather than a decision about how the work is done.

So the run remembers its bot, and the loop reads the charter from the roster each turn
rather than copying the text into the row. The roster is source, the charter is edited with
the code that enforces it, and a run resumed after a deploy gets the current wording instead
of a snapshot of what the charter said the day the run started.

Nullable, with no default. A run created without a bot is the ordinary
undifferentiated case and must stay distinguishable from one created for a bot that was
later removed from the roster; a `server_default` would erase that difference. Existing
rows are left null, which is what they were.

No index. It is read one run at a time, by primary key.

The downgrade drops the column. A run in flight keeps its tools - those are on the row -
and loses its charter, which is the honest outcome: the charter lives in the roster and
the column was the only thing pointing at it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0059_copilot_agent_run_bot"
down_revision: str | None = "0058_autopilot_stage_gates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("copilot_agent_runs", sa.Column("bot", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("copilot_agent_runs", "bot")
