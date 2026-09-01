"""A place to hold a proposed decision tree that nobody has agreed to yet.

Revision ID: 0053_decision_tree_drafts
Revises: 0052_decision_tree_fields

`projects.prompt` has been required since the project chooser started demanding it, and
nothing downstream ever read it: the goal tree and the open questions were written by
hand or not at all. This table is where a draft derived from that prompt waits while a
person goes through it item by item.

It is only a waiting room. No import path reads it - `POST /projects/{id}/decision-tree`
takes the tree the person submits, not a draft id - so the per-item review cannot be
skipped, and a model never gets to decide what a project's goals are. Same three columns
as `project_prompt_drafts` (`status` / `request` / `error`) plus the validated payload,
deliberately, rather than inventing a third draft mechanism beside that one and
`research_generations`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0053_decision_tree_drafts"
down_revision: str | None = "0052_decision_tree_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "research_decision_tree_drafts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("request", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("draft", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(f"ix_{TABLE}_project_id", TABLE, ["project_id"])
    op.create_index(f"ix_{TABLE}_created_by", TABLE, ["created_by"])
    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_created_by", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_project_id", table_name=TABLE)
    op.drop_table(TABLE)
