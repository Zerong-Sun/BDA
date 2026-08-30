"""Add Copilot turn context and Research generation drafts.

Revision ID: 0010_copilot_research_generation
Revises: 0009_research_package_projects
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_copilot_research_generation"
down_revision = "0009_research_package_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    message_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("copilot_messages")
    }
    if "context" not in message_columns:
        op.add_column(
            "copilot_messages",
            sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
    op.create_table(
        "research_generations",
        sa.Column("source_project_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("imported_project_id", sa.Uuid(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legacy_id", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["copilot_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["imported_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_id"),
    )
    op.create_index("ix_research_generations_source_project_id", "research_generations", ["source_project_id"])
    op.create_index("ix_research_generations_organization_id", "research_generations", ["organization_id"])
    op.create_index("ix_research_generations_created_by", "research_generations", ["created_by"])
    op.create_index("ix_research_generations_status", "research_generations", ["status"])
    op.create_index("ix_research_generations_checksum", "research_generations", ["checksum"])


def downgrade() -> None:
    op.drop_index("ix_research_generations_checksum", table_name="research_generations")
    op.drop_index("ix_research_generations_status", table_name="research_generations")
    op.drop_index("ix_research_generations_created_by", table_name="research_generations")
    op.drop_index("ix_research_generations_organization_id", table_name="research_generations")
    op.drop_index("ix_research_generations_source_project_id", table_name="research_generations")
    op.drop_table("research_generations")
    message_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("copilot_messages")
    }
    if "context" in message_columns:
        op.drop_column("copilot_messages", "context")
