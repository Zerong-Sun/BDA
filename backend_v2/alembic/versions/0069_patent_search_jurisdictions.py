"""Record which patent offices a search was restricted to.

A patent search could only cover every office. The restriction had nowhere to
live except inside the query text, and a Chinese topic is rewritten into English
before it runs - a filter written into the words could be dropped by that
rewrite, and the run would record a search nobody asked for. The offices are
now their own column, and the search task applies them after translation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0069_patent_search_jurisdictions"
down_revision: str | None = "0068_alphafold3_parser"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every existing run searched every office, which is what an empty list says.
    op.add_column(
        "literature_search_runs",
        sa.Column("jurisdictions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("literature_search_runs", "jurisdictions")
