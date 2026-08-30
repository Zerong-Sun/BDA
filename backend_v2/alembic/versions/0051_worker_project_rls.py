"""Allow the restricted worker role to access only its operation project.

Revision ID: 0051_worker_project_rls
Revises: 0050_plugin_manifest_deployments
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0051_worker_project_rls"
down_revision: str | None = "0050_plugin_manifest_deployments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


USER_OR_WORKER_EXPRESSION = """
    current_setting('bda.is_global_admin', true) = 'true'
    OR projects.id::text = current_setting('bda.worker_project_id', true)
    OR EXISTS (
        SELECT 1 FROM organization_members om
        WHERE om.organization_id = projects.organization_id
          AND om.user_id::text = current_setting('bda.user_id', true)
    )
"""

USER_EXPRESSION = """
    current_setting('bda.is_global_admin', true) = 'true'
    OR EXISTS (
        SELECT 1 FROM organization_members om
        WHERE om.organization_id = projects.organization_id
          AND om.user_id::text = current_setting('bda.user_id', true)
    )
"""


def _replace(expression: str) -> None:
    op.execute("DROP POLICY IF EXISTS projects_organization_fence ON projects")
    op.execute(
        f"CREATE POLICY projects_organization_fence ON projects USING ({expression}) WITH CHECK ({expression})"
    )


def upgrade() -> None:
    _replace(USER_OR_WORKER_EXPRESSION)


def downgrade() -> None:
    _replace(USER_EXPRESSION)
