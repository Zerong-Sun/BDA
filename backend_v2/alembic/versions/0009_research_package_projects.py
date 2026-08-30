"""Add research package identity, localization, and candidate kinds.

Revision ID: 0009_research_package_projects
Revises: 0008_target_artifact_fk
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_research_package_projects"
down_revision = "0008_target_artifact_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("source_package_id", sa.String(length=240), nullable=True))
    op.add_column("projects", sa.Column("source_project_key", sa.String(length=80), nullable=True))
    op.add_column("projects", sa.Column("localized_content", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_index("ix_projects_source_package_id", "projects", ["source_package_id"])
    op.create_unique_constraint(
        "uq_project_research_package_source",
        "projects",
        ["organization_id", "source_package_id", "source_project_key"],
    )
    inspector = sa.inspect(op.get_bind())
    candidate_columns = {column["name"] for column in inspector.get_columns("candidates")}
    if "candidate_kind" not in candidate_columns:
        op.add_column(
            "candidates",
            sa.Column("candidate_kind", sa.String(length=40), nullable=False, server_default="design_candidate"),
        )
    candidate_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("candidates")}
    if "ix_candidates_candidate_kind" not in candidate_indexes:
        op.create_index("ix_candidates_candidate_kind", "candidates", ["candidate_kind"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ix_candidates_candidate_kind" in {index["name"] for index in inspector.get_indexes("candidates")}:
        op.drop_index("ix_candidates_candidate_kind", table_name="candidates")
    if "candidate_kind" in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("candidates")}:
        op.drop_column("candidates", "candidate_kind")
    op.drop_constraint("uq_project_research_package_source", "projects", type_="unique")
    op.drop_index("ix_projects_source_package_id", table_name="projects")
    op.drop_column("projects", "localized_content")
    op.drop_column("projects", "source_project_key")
    op.drop_column("projects", "source_package_id")
