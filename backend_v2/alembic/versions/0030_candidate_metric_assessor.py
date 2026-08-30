"""Record who assessed a candidate metric, and under which condition.

Found by trying to load a real selectivity panel. A design was scored by AlphaFold3
against five ligands - the intended target and four negative controls - producing five
ipTM values for one candidate. The uniqueness key was
(candidate, metric_key, method, model_variant), so all five collided and each ligand
overwrote the previous one. The panel could not be stored at all, which meant the
platform could hold "this design scores 0.94" but not "…and it scores 0.87 against a
control, so the margin is 0.07". The second sentence is the one that decides whether work
continues.

Two columns:

``condition`` joins the uniqueness key, so one method may report the same metric once per
assay condition. Existing rows take "" and keep their current meaning.

``assessor`` records who produced the number, which ``method`` cannot: the same model is a
design model in one workflow and an independent check in another. It matters because a
design model scoring its own output is self-assessment. In one validation study, an
independent model substantially reordered the candidates produced by the design model.
A UI that shows both numbers the same way invites exactly that mistake. Backfilled as "unknown"
rather than guessed from the method name, because the answer depends on the workflow the
metric came from, not on the tool.

Revision ID: 0030_candidate_metric_assessor
Revises: 0029_proteinhunter_sampling
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_candidate_metric_assessor"
down_revision: str | None = "0029_proteinhunter_sampling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "uq_candidate_metric_source"
TABLE = "candidate_metrics"


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if "assessor" not in columns:
        op.add_column(
            TABLE,
            sa.Column("assessor", sa.String(24), nullable=False, server_default="unknown"),
        )
        op.create_index(f"ix_{TABLE}_assessor", TABLE, ["assessor"])
    if "condition" not in columns:
        op.add_column(
            TABLE, sa.Column("condition", sa.String(120), nullable=False, server_default="")
        )

    # Widen the uniqueness key. Dropping first keeps this runnable on a database that
    # already holds metrics: every existing row has condition "" so no pair that was
    # unique before becomes duplicate now.
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_unique_constraints(TABLE)}
    if CONSTRAINT in existing:
        op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
    op.create_unique_constraint(
        CONSTRAINT, TABLE, ["candidate_id", "metric_key", "method", "model_variant", "condition"]
    )


def downgrade() -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_unique_constraints(TABLE)}
    if CONSTRAINT in existing:
        op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
    # Rows that differ only by condition would violate the narrower key, so collapse them
    # to the first of each group before restoring it. Data loss is inherent to going back.
    op.execute(
        sa.text(
            """
            DELETE FROM candidate_metrics a
            USING candidate_metrics b
            WHERE a.candidate_id = b.candidate_id
              AND a.metric_key = b.metric_key
              AND a.method = b.method
              AND a.model_variant = b.model_variant
              AND a.ctid > b.ctid
            """
        )
    )
    op.create_unique_constraint(
        CONSTRAINT, TABLE, ["candidate_id", "metric_key", "method", "model_variant"]
    )
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if "condition" in columns:
        op.drop_column(TABLE, "condition")
    if "assessor" in columns:
        op.drop_index(f"ix_{TABLE}_assessor", table_name=TABLE)
        op.drop_column(TABLE, "assessor")
