"""Add multi-target support and the complete v2 user-facing domains.

Revision ID: 0002_full_domains
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_full_domains"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_TABLES = (
    "registry_servers",
    "model_plugins",
    "method_plugins",
    "llm_providers",
    "compute_nodes",
    "parameter_catalog",
    "script_assets",
    "candidates",
    "delivery_packages",
    "campaigns",
    "campaign_rounds",
    "campaign_evaluations",
    "campaign_decisions",
    "knowledge_entries",
    "research_briefs",
    "research_findings",
    "literature_documents",
    "literature_chunks",
    "literature_claims",
    "literature_evidence",
    "literature_relations",
    "literature_subscriptions",
    "intelligence_runs",
    "intelligence_reports",
    "intelligence_evidence",
    "intelligence_hotspots",
    "design_routes",
    "compute_drafts",
    "copilot_conversations",
    "copilot_messages",
    "copilot_configs",
    "ligand_imports",
)


def upgrade() -> None:
    # Importing the complete model registry here keeps this revision in sync with the
    # initial v2 build while Alembic remains the only schema entry point.
    from backend_v2.app import all_models  # noqa: F401
    from backend_v2.app.core.models import Base

    bind = op.get_bind()
    for table_name in NEW_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

    op.drop_constraint("uq_target_project", "targets", type_="unique")
    op.add_column("projects", sa.Column("primary_target_id", sa.Uuid(), nullable=True))
    op.create_index("ix_projects_primary_target_id", "projects", ["primary_target_id"])
    op.create_foreign_key(
        "fk_projects_primary_target", "projects", "targets", ["primary_target_id"], ["id"], use_alter=True
    )
    op.add_column("workflow_nodes", sa.Column("model_plugin_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_nodes_model_plugin", "workflow_nodes", "model_plugins", ["model_plugin_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflow_nodes_model_plugin", "workflow_nodes", type_="foreignkey")
    op.drop_column("workflow_nodes", "model_plugin_id")
    op.drop_constraint("fk_projects_primary_target", "projects", type_="foreignkey")
    op.drop_index("ix_projects_primary_target_id", table_name="projects")
    op.drop_column("projects", "primary_target_id")
    op.create_unique_constraint("uq_target_project", "targets", ["project_id"])
    for table_name in reversed(NEW_TABLES):
        op.drop_table(table_name)
