"""Project-scoped, append-only design learning and frozen reviews."""

import sqlalchemy as sa

from alembic import op

revision = "0078_design_memory"
down_revision = "0077_copilot_call_guard"
branch_labels = None
depends_on = None


def base():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    ]


def upgrade():
    op.create_table(
        "design_reviews",
        *base(),
        sa.Column("workflow_run_id", sa.Uuid(), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("memory_digest", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "design_lessons",
        *base(),
        sa.Column("review_id", sa.Uuid(), sa.ForeignKey("design_reviews.id", ondelete="CASCADE")),
        sa.Column("item_key", sa.String(120)),
        sa.Column("supersedes_id", sa.Uuid(), sa.ForeignKey("design_lessons.id")),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    for table, columns in {
        "design_reviews": ["project_id", "workflow_run_id"],
        "design_lessons": ["project_id", "review_id", "supersedes_id"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
        if op.get_bind().dialect.name == "postgresql":
            expr = f"current_setting('bda.is_global_admin', true) = 'true' OR {table}.project_id::text = current_setting('bda.worker_project_id', true) OR EXISTS (SELECT 1 FROM projects p JOIN organization_members om ON om.organization_id = p.organization_id WHERE p.id = {table}.project_id AND om.user_id::text = current_setting('bda.user_id', true))"
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY {table}_project_fence ON {table} USING ({expr}) WITH CHECK ({expr})")
    # Existing unsubmitted plans are still future designs. Enable their gate without
    # inventing approvals or rewriting any submitted execution record.
    workflows = sa.table("workflow_runs", sa.column("id", sa.Uuid()), sa.column("status", sa.String()), sa.column("graph", sa.JSON()))
    connection = op.get_bind()
    for row in connection.execute(sa.select(workflows.c.id, workflows.c.graph).where(workflows.c.status == "draft")).mappings():
        connection.execute(workflows.update().where(workflows.c.id == row["id"]).values(graph={**(row["graph"] or {}), "design_learning_required": True}))


def downgrade():
    op.drop_table("design_lessons")
    op.drop_table("design_reviews")
