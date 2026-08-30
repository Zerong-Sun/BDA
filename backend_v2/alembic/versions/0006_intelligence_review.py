"""Add review state to intelligence evidence and hotspots.

Revision ID: 0006_intelligence_review
Revises: 0005_literature_review
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_intelligence_review"
down_revision: str | None = "0005_literature_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("intelligence_evidence", "intelligence_hotspots"):
        inspector = sa.inspect(op.get_bind())
        if "review_status" not in {item["name"] for item in inspector.get_columns(table)}:
            op.add_column(table, sa.Column("review_status", sa.String(40), nullable=False, server_default="pending"))
        index_name = f"ix_{table}_review_status"
        if index_name not in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}:
            op.create_index(index_name, table, ["review_status"])


def downgrade() -> None:
    for table in ("intelligence_hotspots", "intelligence_evidence"):
        inspector = sa.inspect(op.get_bind())
        index_name = f"ix_{table}_review_status"
        if index_name in {index["name"] for index in inspector.get_indexes(table)}:
            op.drop_index(index_name, table_name=table)
        if "review_status" in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}:
            op.drop_column(table, "review_status")
