"""Versioned learning studies, sourced evidence and campaign round handoffs."""

import sqlalchemy as sa

from alembic import op

revision = "0073_learning_lifecycle"
down_revision = "0072_project_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_studies", sa.Column("supersedes_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_learning_study_supersedes", "learning_studies", "learning_studies", ["supersedes_id"], ["id"]
    )
    op.add_column(
        "learning_studies", sa.Column("stop_on_threshold", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("learning_studies", sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="12"))
    for table, columns in {
        "learning_evidence": [
            sa.Column("kind", sa.String(24), nullable=False),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("sources", sa.JSON(), nullable=False),
            sa.Column("withdrawal", sa.JSON()),
        ],
        "learning_batches": [
            sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("learning_decisions.id"), unique=True, nullable=False),
            sa.Column("campaign_id", sa.Uuid(), sa.ForeignKey("campaigns.id"), nullable=False),
            sa.Column("round_id", sa.Uuid(), sa.ForeignKey("campaign_rounds.id"), unique=True, nullable=False),
            sa.Column("manifest", sa.JSON(), nullable=False),
            sa.Column("digest", sa.String(64), nullable=False),
            sa.Column("receipt", sa.JSON()),
        ],
    }.items():
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("legacy_id", sa.String(255), unique=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("study_id", sa.Uuid(), sa.ForeignKey("learning_studies.id"), nullable=False),
            sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            *columns,
        )
        for column in ["project_id", "study_id", *(["campaign_id"] if table == "learning_batches" else [])]:
            op.create_index(f"ix_{table}_{column}", table, [column])
        expr = f"current_setting('bda.is_global_admin', true) = 'true' OR {table}.project_id::text = current_setting('bda.worker_project_id', true) OR EXISTS (SELECT 1 FROM projects p JOIN organization_members om ON om.organization_id = p.organization_id WHERE p.id = {table}.project_id AND om.user_id::text = current_setting('bda.user_id', true))"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_project_fence ON {table} USING ({expr}) WITH CHECK ({expr})")


def downgrade() -> None:
    op.drop_table("learning_batches")
    op.drop_table("learning_evidence")
    op.drop_column("learning_studies", "max_rounds")
    op.drop_column("learning_studies", "stop_on_threshold")
    op.drop_constraint("fk_learning_study_supersedes", "learning_studies", type_="foreignkey")
    op.drop_column("learning_studies", "supersedes_id")
