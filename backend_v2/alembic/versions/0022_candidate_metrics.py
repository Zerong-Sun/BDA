"""Give model-produced numbers a queryable home.

Metrics lived in ``candidates.scores``, a JSON blob. That could not be indexed, could
not answer "every design above pLDDT 90 that AlphaFold2 also gave ipTM 0.8", and
recorded neither which run nor which model produced a number. Worse, collection skipped
candidates that already existed, so a second method scoring an earlier design - the
ordinary case, since AlphaFold2 folds what ProteinMPNN wrote - silently dropped its
results.

``scores`` stays as the denormalised view the UI reads; this table is the record.

Revision ID: 0022_candidate_metrics
Revises: 0021_register_proteinhunter
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_candidate_metrics"
down_revision: str | None = "0021_register_proteinhunter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("metric_key", sa.String(length=60), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("method", sa.String(length=60), nullable=False),
        sa.Column("model_variant", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("evidence_kind", sa.String(length=20), nullable=False, server_default="predicted"),
        sa.Column("unit", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("source_job_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_job_id"], ["jobs.id"]),
        sa.UniqueConstraint(
            "candidate_id", "metric_key", "method", "model_variant", name="uq_candidate_metric_source"
        ),
    )
    op.create_index("ix_candidate_metrics_candidate_id", "candidate_metrics", ["candidate_id"])
    op.create_index("ix_candidate_metrics_metric_key", "candidate_metrics", ["metric_key"])
    op.create_index("ix_candidate_metrics_method", "candidate_metrics", ["method"])
    op.create_index("ix_candidate_metrics_evidence_kind", "candidate_metrics", ["evidence_kind"])
    # The index this table exists for: bounded search on one metric.
    op.create_index("ix_candidate_metrics_key_value", "candidate_metrics", ["metric_key", "value"])


def downgrade() -> None:
    op.drop_index("ix_candidate_metrics_key_value", table_name="candidate_metrics")
    op.drop_index("ix_candidate_metrics_evidence_kind", table_name="candidate_metrics")
    op.drop_index("ix_candidate_metrics_method", table_name="candidate_metrics")
    op.drop_index("ix_candidate_metrics_metric_key", table_name="candidate_metrics")
    op.drop_index("ix_candidate_metrics_candidate_id", table_name="candidate_metrics")
    op.drop_table("candidate_metrics")
