"""Make new plugin definitions checksum-pinned manifest deployments.

Revision ID: 0050_plugin_manifest_deployments
Revises: 0049_autopilot_formalization
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0050_plugin_manifest_deployments"
down_revision: str | None = "0049_autopilot_formalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


IMMUTABLE_COLUMNS = (
    "plugin_key",
    "plugin_version",
    "name",
    "container_image",
    "command",
    "parameter_schema",
    "output_schema",
    "input_ports",
    "output_ports",
    "resources",
    "runtime_mode",
    "output_parser",
    "input_adapter",
    "runtime_setup",
    "manifest_id",
    "manifest_schema_version",
    "manifest_checksum",
)
JSON_COLUMNS = {
    "parameter_schema",
    "output_schema",
    "input_ports",
    "output_ports",
    "resources",
    "runtime_setup",
}


def upgrade() -> None:
    # Revision 0002 historically creates domain tables from live ORM metadata. Until
    # that legacy bootstrap is replaced, a clean install can therefore see these
    # columns and ORM-declared indexes before this revision, while an upgrade from
    # 0049 cannot. Keep both paths replayable without changing existing databases.
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("model_plugins")}
    additions = (
        sa.Column("manifest_id", sa.String(length=240), nullable=True),
        sa.Column("manifest_schema_version", sa.String(length=20), nullable=True),
        sa.Column("manifest_checksum", sa.String(length=64), nullable=True),
        sa.Column("deployment_status", sa.String(length=32), server_default="legacy", nullable=False),
        sa.Column("site_overrides", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("model_plugins", column)

    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("model_plugins")}
    if "ix_model_plugins_manifest_id" not in indexes:
        op.create_index("ix_model_plugins_manifest_id", "model_plugins", ["manifest_id"])
    if "ix_model_plugins_manifest_checksum" not in indexes:
        op.create_index("ix_model_plugins_manifest_checksum", "model_plugins", ["manifest_checksum"])
    op.create_check_constraint(
        "ck_model_plugins_manifest_identity",
        "model_plugins",
        "(manifest_checksum IS NULL AND manifest_id IS NULL AND manifest_schema_version IS NULL) OR "
        "(manifest_checksum ~ '^[0-9a-f]{64}$' AND manifest_id IS NOT NULL AND manifest_schema_version IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_model_plugins_deployment_status",
        "model_plugins",
        "deployment_status IN ('legacy', 'installed', 'disabled', 'error')",
    )
    comparisons = " OR ".join(
        (
            f"NEW.{column}::jsonb IS DISTINCT FROM OLD.{column}::jsonb"
            if column in JSON_COLUMNS
            else f"NEW.{column} IS DISTINCT FROM OLD.{column}"
        )
        for column in IMMUTABLE_COLUMNS
    )
    op.execute(
        f"""
        CREATE FUNCTION bda_reject_plugin_manifest_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.manifest_checksum IS NOT NULL AND ({comparisons}) THEN
            RAISE EXCEPTION 'plugin manifest definitions are immutable; deploy a new version';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER model_plugins_manifest_immutable "
        "BEFORE UPDATE ON model_plugins FOR EACH ROW "
        "EXECUTE FUNCTION bda_reject_plugin_manifest_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS model_plugins_manifest_immutable ON model_plugins")
    op.execute("DROP FUNCTION IF EXISTS bda_reject_plugin_manifest_mutation()")
    op.drop_constraint("ck_model_plugins_deployment_status", "model_plugins", type_="check")
    op.drop_constraint("ck_model_plugins_manifest_identity", "model_plugins", type_="check")
    op.drop_index("ix_model_plugins_manifest_checksum", table_name="model_plugins")
    op.drop_index("ix_model_plugins_manifest_id", table_name="model_plugins")
    op.drop_column("model_plugins", "site_overrides")
    op.drop_column("model_plugins", "deployment_status")
    op.drop_column("model_plugins", "manifest_checksum")
    op.drop_column("model_plugins", "manifest_schema_version")
    op.drop_column("model_plugins", "manifest_id")
