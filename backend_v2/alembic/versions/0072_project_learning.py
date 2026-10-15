"""Frozen project learning contracts, datasets, models and reviewed proposals."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0072_project_learning"
down_revision: str | None = "0071_copilot_reasoning_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base() -> list:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "learning_assays",
        *_base(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
    )
    op.create_table(
        "learning_studies",
        *_base(),
        sa.Column("assay_id", sa.Uuid(), sa.ForeignKey("learning_assays.id"), nullable=False),
        sa.Column("research_goal_id", sa.Uuid(), sa.ForeignKey("research_goals.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("goal_snapshot", sa.JSON(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Float()),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("batch_budget_cents", sa.Integer(), nullable=False),
        sa.Column("max_batch_size", sa.Integer(), nullable=False),
    )
    op.create_table(
        "learning_datasets",
        *_base(),
        sa.Column("study_id", sa.Uuid(), sa.ForeignKey("learning_studies.id"), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
    )
    op.create_table(
        "learning_models",
        *_base(),
        sa.Column("study_id", sa.Uuid(), sa.ForeignKey("learning_studies.id"), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("learning_datasets.id"), nullable=False),
        sa.Column("algorithm", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=False),
    )
    op.create_table(
        "learning_decisions",
        *_base(),
        sa.Column("study_id", sa.Uuid(), sa.ForeignKey("learning_studies.id"), nullable=False),
        sa.Column("model_id", sa.Uuid(), sa.ForeignKey("learning_models.id"), nullable=False),
        sa.Column("timeline_entry_id", sa.Uuid(), sa.ForeignKey("project_timeline_entries.id", ondelete="SET NULL")),
        sa.Column("proposal", sa.JSON(), nullable=False),
        sa.Column("proposal_digest", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("review_note", sa.Text()),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id")),
    )
    for table, fields in {
        "learning_assays": ["project_id"],
        "learning_studies": ["project_id", "assay_id", "research_goal_id"],
        "learning_datasets": ["project_id", "study_id"],
        "learning_models": ["project_id", "study_id", "dataset_id"],
        "learning_decisions": ["project_id", "study_id", "model_id"],
    }.items():
        for field in fields:
            op.create_index(f"ix_{table}_{field}", table, [field])
        if op.get_bind().dialect.name == "postgresql":
            expr = f"current_setting('bda.is_global_admin', true) = 'true' OR {table}.project_id::text = current_setting('bda.worker_project_id', true) OR EXISTS (SELECT 1 FROM projects p JOIN organization_members om ON om.organization_id = p.organization_id WHERE p.id = {table}.project_id AND om.user_id::text = current_setting('bda.user_id', true))"
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY {table}_project_fence ON {table} USING ({expr}) WITH CHECK ({expr})")


def downgrade() -> None:
    for table in ["learning_decisions", "learning_models", "learning_datasets", "learning_studies", "learning_assays"]:
        op.drop_table(table)
