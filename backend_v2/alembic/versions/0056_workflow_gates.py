"""Persist attempt-specific results and data-transfer decisions.

Revision ID: 0056_workflow_gates
Revises: 0055_autopilot_worker_rls
"""

import sqlalchemy as sa

from alembic import op

revision = "0056_workflow_gates"
down_revision = "0055_autopilot_worker_rls"
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    ]


def upgrade():
    op.add_column("workflow_nodes", sa.Column("configuration", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "workflow_results",
        *base_columns(),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("result_key", sa.String(500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("job_id", "result_key", name="uq_workflow_result_job_key"),
    )
    op.create_table(
        "workflow_gate_evaluations",
        *base_columns(),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("edge_id", sa.String(160), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("preview", sa.Boolean(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("selected_ids", sa.JSON(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("released_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("target_job_id", "edge_id", "revision", name="uq_gate_attempt_revision"),
    )
    for table, cols in {
        "workflow_results": ["project_id", "job_id"],
        "workflow_gate_evaluations": ["project_id", "workflow_run_id", "target_job_id"],
    }.items():
        for col in cols:
            op.create_index(f"ix_{table}_{col}", table, [col])
        if op.get_bind().dialect.name == "postgresql":
            expr = f"current_setting('bda.is_global_admin', true) = 'true' OR {table}.project_id::text = current_setting('bda.worker_project_id', true) OR EXISTS (SELECT 1 FROM projects p JOIN organization_members om ON om.organization_id = p.organization_id WHERE p.id = {table}.project_id AND om.user_id::text = current_setting('bda.user_id', true))"
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY {table}_project_fence ON {table} USING ({expr}) WITH CHECK ({expr})")


def downgrade():
    op.drop_table("workflow_gate_evaluations")
    op.drop_table("workflow_results")
    op.drop_column("workflow_nodes", "configuration")
