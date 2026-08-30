"""candidate metric traces to the experiment result that measured it

Revision ID: 0042_measured_metric_provenance
Revises: 0041_wetlab_proteins_and_goals
Create Date: 2026-08-24 01:02:08.412800
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0042_measured_metric_provenance"
down_revision: str | None = "0041_wetlab_proteins_and_goals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Named explicitly: autogenerate emits an unnamed constraint, and a constraint
#: with no name cannot be dropped, so the downgrade fails to compile at all.
FOREIGN_KEY = "fk_candidate_metrics_source_experiment_result"


def upgrade() -> None:
    op.add_column(
        "candidate_metrics", sa.Column("source_experiment_result_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        op.f("ix_candidate_metrics_source_experiment_result_id"),
        "candidate_metrics",
        ["source_experiment_result_id"],
        unique=False,
    )
    op.create_foreign_key(
        FOREIGN_KEY,
        "candidate_metrics",
        "experiment_results",
        ["source_experiment_result_id"],
        ["id"],
        # The measurement still happened; losing the row that recorded it must
        # not quietly erase it from the candidate.
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(FOREIGN_KEY, "candidate_metrics", type_="foreignkey")
    op.drop_index(
        op.f("ix_candidate_metrics_source_experiment_result_id"),
        table_name="candidate_metrics",
    )
    op.drop_column("candidate_metrics", "source_experiment_result_id")
