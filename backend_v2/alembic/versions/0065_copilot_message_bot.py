"""Record which operator produced a Copilot message.

The roster gave every run an operator (`copilot_agent_runs.bot`) but left the
conversation anonymous: a turn's bot hint was written into the *user* message's
`context` and nothing on the assistant's reply said who answered. A transcript
that cannot name its speakers cannot be read as a room where several operators
work, which is what the research room needs.

Nullable and not backfilled. A message written before this column existed was
produced by an undifferentiated Copilot as far as the record knows, and guessing
an operator from a neighbouring context blob would put a name on work nobody
attributed at the time.

Guarded by an inspection, like `0010_copilot_research_generation` before it and
for the same reason: `0002_full_domains` builds `copilot_messages` from the
*live* ORM metadata rather than from a frozen column list, so on a database
created from scratch today the column already exists by revision 0002 and a
bare `add_column` here fails with DuplicateColumn. A deployed database that
reached 0064 before this branch does not have it. Both have to upgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0065_copilot_message_bot"
down_revision: str | None = "0064_public_integration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("copilot_messages")}


def upgrade() -> None:
    if "bot" not in _columns():
        op.add_column("copilot_messages", sa.Column("bot", sa.String(length=80), nullable=True))


def downgrade() -> None:
    if "bot" in _columns():
        op.drop_column("copilot_messages", "bot")
