"""Add campaign decision patches and human review metadata.

Revision ID: 0004_campaign_decision_review
Revises: 0003_target_structure_revisions
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_campaign_decision_review"
down_revision: str | None = "0003_target_structure_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "campaign_decisions"
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table)}
    additions = {
        "parameter_patch": sa.Column("parameter_patch", sa.JSON(), nullable=False, server_default="{}"),
        "review_status": sa.Column("review_status", sa.String(40), nullable=False, server_default="pending"),
        "reviewed_by": sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        "reviewed_at": sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column(table, column)
    inspector = sa.inspect(op.get_bind())
    if not any(fk["constrained_columns"] == ["reviewed_by"] for fk in inspector.get_foreign_keys(table)):
        op.create_foreign_key("fk_campaign_decisions_reviewed_by", table, "users", ["reviewed_by"], ["id"])
    if "ix_campaign_decisions_review_status" not in {index["name"] for index in inspector.get_indexes(table)}:
        op.create_index("ix_campaign_decisions_review_status", table, ["review_status"])


def downgrade() -> None:
    table = "campaign_decisions"
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes(table)}
    if "ix_campaign_decisions_review_status" in indexes:
        op.drop_index("ix_campaign_decisions_review_status", table_name=table)
    for fk in inspector.get_foreign_keys(table):
        if fk["constrained_columns"] == ["reviewed_by"] and fk["name"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    for name in ("reviewed_at", "reviewed_by", "review_status", "parameter_patch"):
        if name in columns:
            op.drop_column(table, name)
