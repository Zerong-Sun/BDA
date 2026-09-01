"""Record how runs relate to each other, and how findings resolve.

Both gaps were found while mapping a multi-arm binder study into the platform and
discovering the parts that had nowhere to go.

Workflow lineage. Every causal statement in the study came from comparing two runs:
`percent_x` 90 against 50, an independent replicate of the same settings, and an arm that
differed only by a contact constraint. Nothing recorded that those runs were related, so
"only one parameter changed" survived as a sentence in a document rather than as a fact the
platform could check. `varied_parameters` is therefore computed by the platform at
submission rather than typed by the author, which is what turns a single-variable control
from a claim into an observation. `arm_label` follows from the same diff: no baseline is a
baseline, an empty diff is a replicate, anything else is a variant.

Finding outcome. The most valuable results in the study were a refutation - the designs
have no selectivity - and a superseded intermediate conclusion: high ipTM looked like it
inherently required high alanine until `percent_x=50` disproved it. A free-text `content`
field holds the prose but cannot answer "show me what we ruled out" or "which conclusion
replaced which". `outcome` makes negative results searchable; `supersedes_id` records the
replacement; `provenance` ties a finding to the jobs, candidates and artifacts behind it
instead of naming them in prose.

Existing rows are backfilled with `unspecified` and no lineage rather than a guess, for the
same reason 0025 backfilled `assessor` as `unknown`: the honest value is unknown, and
inventing one would make the new columns untrustworthy from the first day.

Revision ID: 0031_run_lineage_outcome
Revises: 0030_candidate_metric_assessor
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031_run_lineage_outcome"
down_revision: str | None = "0030_candidate_metric_assessor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table) if item.get("name")}


def _drop_column_if_present(table: str, column: str) -> None:
    """Drop a column and let the database remove whatever depended on it.

    0002_full_domains builds these tables from the live ORM metadata, so on any database
    created after the models gained these fields the columns already exist - along with
    foreign keys and indexes under SQLAlchemy's generated names, not the names this
    revision would have chosen. Dropping by inspection rather than by assumed name is
    what makes the downgrade work on both a database that predates the models and one
    that was built from them. PostgreSQL drops the dependent constraints with the column.
    """
    if column in _columns(table):
        op.drop_column(table, column)


def _drop_index_if_present(table: str, index: str) -> None:
    if index in _indexes(table):
        op.drop_index(index, table_name=table)


def upgrade() -> None:
    workflow_columns = _columns("workflow_runs")
    if "derived_from_id" not in workflow_columns:
        op.add_column(
            "workflow_runs",
            sa.Column("derived_from_id", sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            "fk_workflow_runs_derived_from",
            "workflow_runs",
            "workflow_runs",
            ["derived_from_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_workflow_runs_derived_from_id", "workflow_runs", ["derived_from_id"])
    if "arm_label" not in workflow_columns:
        op.add_column(
            "workflow_runs",
            sa.Column("arm_label", sa.String(length=40), nullable=False, server_default="baseline"),
        )
    if "varied_parameters" not in workflow_columns:
        op.add_column(
            "workflow_runs",
            sa.Column("varied_parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        )

    finding_columns = _columns("research_findings")
    if "outcome" not in finding_columns:
        op.add_column(
            "research_findings",
            sa.Column("outcome", sa.String(length=40), nullable=False, server_default="unspecified"),
        )
        op.create_index("ix_research_findings_outcome", "research_findings", ["outcome"])
    if "supersedes_id" not in finding_columns:
        op.add_column(
            "research_findings",
            sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            "fk_research_findings_supersedes",
            "research_findings",
            "research_findings",
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "provenance" not in finding_columns:
        op.add_column(
            "research_findings",
            sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        )


def downgrade() -> None:
    _drop_column_if_present("research_findings", "provenance")
    _drop_column_if_present("research_findings", "supersedes_id")
    _drop_index_if_present("research_findings", "ix_research_findings_outcome")
    _drop_column_if_present("research_findings", "outcome")

    _drop_column_if_present("workflow_runs", "varied_parameters")
    _drop_column_if_present("workflow_runs", "arm_label")
    _drop_index_if_present("workflow_runs", "ix_workflow_runs_derived_from_id")
    _drop_column_if_present("workflow_runs", "derived_from_id")
