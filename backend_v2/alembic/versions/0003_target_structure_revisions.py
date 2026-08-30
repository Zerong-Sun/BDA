"""Add auditable target structure preparation revisions.

Revision ID: 0003_target_structure_revisions
Revises: 0002_full_domains
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_target_structure_revisions"
down_revision: str | None = "0002_full_domains"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "target_structure_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("prepared_artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id")),
        sa.Column("options", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_target_structure_revisions_target_id", "target_structure_revisions", ["target_id"])
    op.create_index(
        "ix_target_structure_revisions_source_artifact_id", "target_structure_revisions", ["source_artifact_id"]
    )
    op.create_index("ix_target_structure_revisions_status", "target_structure_revisions", ["status"])
    op.create_index("ix_target_structure_revisions_created_by", "target_structure_revisions", ["created_by"])


def downgrade() -> None:
    op.drop_table("target_structure_revisions")
