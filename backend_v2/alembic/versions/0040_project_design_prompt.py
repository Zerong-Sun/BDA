"""Add a required design prompt to project creation.

Each project now carries an LLM-drafted ``prompt`` (the design brief for the run),
generated through a short-lived ``project_prompt_drafts`` row before the project it
describes exists — see ``backend_v2/app/projects/service.py`` and ``tasks.py``. The
draft table is not scoped to a project (there isn't one yet), so it carries its own
``organization_id``/``created_by`` for authorization instead of a project FK.

``projects.prompt`` is nullable at the database level even though the API requires it
on creation going forward: existing rows predate the feature, and a handful of
system-driven imports (``research/generation.py``, ``research/copilot_import.py``,
``research/package_import.py``, ``scripts/migrate_v1.py``) construct projects without
running an LLM, supplying a deterministic fallback instead.

Revision ID: 0040_project_design_prompt
Revises: 0039_proteinhunter_drop_dead_seq
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0040_project_design_prompt"
down_revision: str | None = "0039_proteinhunter_drop_dead_seq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("prompt", sa.Text(), nullable=True))

    op.create_table(
        "project_prompt_drafts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legacy_id", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_id"),
    )
    op.create_index("ix_project_prompt_drafts_organization_id", "project_prompt_drafts", ["organization_id"])
    op.create_index("ix_project_prompt_drafts_created_by", "project_prompt_drafts", ["created_by"])
    op.create_index("ix_project_prompt_drafts_status", "project_prompt_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_project_prompt_drafts_status", table_name="project_prompt_drafts")
    op.drop_index("ix_project_prompt_drafts_created_by", table_name="project_prompt_drafts")
    op.drop_index("ix_project_prompt_drafts_organization_id", table_name="project_prompt_drafts")
    op.drop_table("project_prompt_drafts")
    op.drop_column("projects", "prompt")
