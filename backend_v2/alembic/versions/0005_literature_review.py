"""Add literature claim and relation review metadata.

Revision ID: 0005_literature_review
Revises: 0004_campaign_decision_review
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_literature_review"
down_revision: str | None = "0004_campaign_decision_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_review(table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table)}
    additions = {
        "review_status": sa.Column("review_status", sa.String(40), nullable=False, server_default="pending"),
        "reviewed_by": sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        "reviewed_at": sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column(table, column)
    inspector = sa.inspect(op.get_bind())
    if not any(fk["constrained_columns"] == ["reviewed_by"] for fk in inspector.get_foreign_keys(table)):
        op.create_foreign_key(f"fk_{table}_reviewed_by", table, "users", ["reviewed_by"], ["id"])
    index_name = f"ix_{table}_review_status"
    if index_name not in {index["name"] for index in inspector.get_indexes(table)}:
        op.create_index(index_name, table, ["review_status"])


def upgrade() -> None:
    _add_review("literature_claims")
    _add_review("literature_relations")


def downgrade() -> None:
    for table in ("literature_relations", "literature_claims"):
        inspector = sa.inspect(op.get_bind())
        index_name = f"ix_{table}_review_status"
        if index_name in {index["name"] for index in inspector.get_indexes(table)}:
            op.drop_index(index_name, table_name=table)
        for fk in inspector.get_foreign_keys(table):
            if fk["constrained_columns"] == ["reviewed_by"] and fk["name"]:
                op.drop_constraint(fk["name"], table, type_="foreignkey")
        columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
        for name in ("reviewed_at", "reviewed_by", "review_status"):
            if name in columns:
                op.drop_column(table, name)
