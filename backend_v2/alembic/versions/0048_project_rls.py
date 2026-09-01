"""Enable organization-capped RLS on project-domain tables.

Revision ID: 0048_project_rls
Revises: 0047_worker_heartbeats
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0048_project_rls"
down_revision: str | None = "0047_worker_heartbeats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_TABLES = (
    "audit_logs",
    "artifact_uploads",
    "campaigns",
    "copilot_configs",
    "copilot_conversations",
    "knowledge_entries",
    "literature_search_runs",
    "literature_subscriptions",
    "operations",
    "project_members",
    "project_timeline_entries",
    "research_briefs",
    "research_goals",
    "workflow_runs",
    "artifacts",
    "copilot_agent_runs",
    "job_submissions",
    "research_findings",
    "artifact_lineage_edges",
    "delivery_packages",
    "jobs",
    "ligand_imports",
    "literature_documents",
    "targets",
    "candidates",
    "compute_drafts",
    "intelligence_runs",
    "literature_retrieval_traces",
    "experiment_results",
    "proteins",
    "literature_relations",
)


def _project_expression(table: str) -> str:
    return f"""
        current_setting('bda.is_global_admin', true) = 'true'
        OR {table}.project_id::text = current_setting('bda.worker_project_id', true)
        OR EXISTS (
            SELECT 1
            FROM projects p
            JOIN organization_members om ON om.organization_id = p.organization_id
            WHERE p.id = {table}.project_id
              AND om.user_id::text = current_setting('bda.user_id', true)
        )
    """


def upgrade() -> None:
    project_expression = """
        current_setting('bda.is_global_admin', true) = 'true'
        OR EXISTS (
            SELECT 1 FROM organization_members om
            WHERE om.organization_id = projects.organization_id
              AND om.user_id::text = current_setting('bda.user_id', true)
        )
    """
    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY projects_organization_fence ON projects USING ({project_expression}) WITH CHECK ({project_expression})"
    )
    for table in PROJECT_TABLES:
        expression = _project_expression(table)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_project_fence ON {table} USING ({expression}) WITH CHECK ({expression})"
        )


def downgrade() -> None:
    for table in reversed(PROJECT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_project_fence ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS projects_organization_fence ON projects")
    op.execute("ALTER TABLE projects DISABLE ROW LEVEL SECURITY")
