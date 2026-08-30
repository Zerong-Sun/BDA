"""Add operations, artifact lineage, migration runs, and typed result provenance.

Revision ID: 0007_data_flow_closure
Revises: 0006_intelligence_review
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_data_flow_closure"
down_revision: str | None = "0006_intelligence_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def entity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legacy_id", sa.String(255), unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _table_exists(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def _column_names(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _index_names(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _column_names(table):
        op.add_column(table, column)


def _create_index(table: str, column: str) -> None:
    name = f"ix_{table}_{column}"
    if name not in _index_names(table):
        op.create_index(name, table, [column])


def _create_fk(name: str, table: str, target: str, column: str) -> None:
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(table)
    if not any(item["constrained_columns"] == [column] for item in foreign_keys):
        op.create_foreign_key(name, table, target, [column], ["id"], ondelete="SET NULL")


def upgrade() -> None:
    if not _table_exists("operations"):
        op.create_table(
            "operations",
            *entity_columns(),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
            sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
            sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("kind", sa.String(120), nullable=False),
            sa.Column("resource_type", sa.String(80), nullable=False),
            sa.Column("resource_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("progress", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("error_code", sa.String(120)),
            sa.Column("error_message", sa.Text()),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
        )
    for column in ("project_id", "organization_id", "created_by", "kind", "resource_type", "resource_id", "status"):
        _create_index("operations", column)

    if not _table_exists("artifact_lineage_edges"):
        op.create_table(
            "artifact_lineage_edges",
            *entity_columns(),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "parent_artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "child_artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("relation", sa.String(80), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.UniqueConstraint("parent_artifact_id", "child_artifact_id", "relation", name="uq_artifact_lineage_edge"),
        )
    for column in ("project_id", "parent_artifact_id", "child_artifact_id", "relation"):
        _create_index("artifact_lineage_edges", column)

    if not _table_exists("migration_runs"):
        op.create_table(
            "migration_runs",
            *entity_columns(),
            sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("source_fingerprint", sa.String(64), nullable=False),
            sa.Column("rehearsal", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("counts", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("checksums", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("id_map_digest", sa.String(64)),
            sa.Column("rejection_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("report_artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id", ondelete="SET NULL")),
        )
    for column in ("created_by", "source_fingerprint", "status"):
        _create_index("migration_runs", column)

    _add_column("experiment_results", sa.Column("candidate_id", sa.Uuid()))
    _create_fk("fk_experiment_results_candidate_id", "experiment_results", "candidates", "candidate_id")
    _create_index("experiment_results", "candidate_id")
    _add_column("experiment_results", sa.Column("source_artifact_id", sa.Uuid()))
    _create_fk("fk_experiment_results_source_artifact_id", "experiment_results", "artifacts", "source_artifact_id")
    _create_index("experiment_results", "source_artifact_id")
    _add_column("experiment_results", sa.Column("batch_key", sa.String(255)))
    _create_index("experiment_results", "batch_key")
    _add_column("experiment_results", sa.Column("failure_reason", sa.Text()))
    _add_column(
        "experiment_results",
        sa.Column("result_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )

    for table in ("registry_servers", "compute_nodes"):
        _add_column(table, sa.Column("health_status", sa.String(32), nullable=False, server_default="unknown"))
        _add_column(table, sa.Column("health_checked_at", sa.DateTime(timezone=True)))
        _add_column(table, sa.Column("health_error", sa.Text()))
        _create_index(table, "health_status")
    _add_column(
        "model_plugins", sa.Column("validation_status", sa.String(32), nullable=False, server_default="unknown")
    )
    _add_column("model_plugins", sa.Column("validated_at", sa.DateTime(timezone=True)))
    _add_column(
        "model_plugins",
        sa.Column("validation_errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    _create_index("model_plugins", "validation_status")


def downgrade() -> None:
    if "ix_model_plugins_validation_status" in _index_names("model_plugins"):
        op.drop_index("ix_model_plugins_validation_status", table_name="model_plugins")
    for column in ("validation_errors", "validated_at", "validation_status"):
        if column in _column_names("model_plugins"):
            op.drop_column("model_plugins", column)
    for table in ("compute_nodes", "registry_servers"):
        if f"ix_{table}_health_status" in _index_names(table):
            op.drop_index(f"ix_{table}_health_status", table_name=table)
        for column in ("health_error", "health_checked_at", "health_status"):
            if column in _column_names(table):
                op.drop_column(table, column)

    for column in ("source_artifact_id", "candidate_id"):
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("experiment_results"):
            if foreign_key["constrained_columns"] == [column] and foreign_key["name"]:
                op.drop_constraint(foreign_key["name"], "experiment_results", type_="foreignkey")
        index = f"ix_experiment_results_{column}"
        if index in _index_names("experiment_results"):
            op.drop_index(index, table_name="experiment_results")
    if "ix_experiment_results_batch_key" in _index_names("experiment_results"):
        op.drop_index("ix_experiment_results_batch_key", table_name="experiment_results")
    for column in ("result_metadata", "failure_reason", "batch_key", "source_artifact_id", "candidate_id"):
        if column in _column_names("experiment_results"):
            op.drop_column("experiment_results", column)

    for table in ("migration_runs", "artifact_lineage_edges", "operations"):
        if _table_exists(table):
            op.drop_table(table)
