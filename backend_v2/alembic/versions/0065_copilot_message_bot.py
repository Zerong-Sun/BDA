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
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0065_copilot_message_bot"
down_revision: str | None = "0064_public_integration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("copilot_messages", sa.Column("bot", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("copilot_messages", "bot")
