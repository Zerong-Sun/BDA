"""Separate stages that dispatch from stages a person does, and declaration-valid from proven-to-run.

Two gaps found while auditing why the sweet-protein project has never dispatched a single
job through this platform.

**`workflow_nodes.execution_mode`.** Preflight blocks any node without a registry plugin,
and submission turns every node into a job. But a real design route contains stages that
are not models and never will be: importing the target structure, a scientist reviewing
candidates, a hotspot map assembled by hand. Those stages carry names like
``Imported project inputs`` which resolve to nothing in the registry, so a workflow that
is otherwise perfectly configured reports ``plugin_snapshot_missing`` and cannot be
submitted - which is exactly the state the sweet-protein routes have been in. The fix is
not to weaken the blocker (it exists because unvalidated free-text commands used to reach
the cluster) but to let a node declare that it is not dispatched at all. Default
``dispatch`` keeps every existing node behaving as before.

**Runtime validation on `model_plugins`.** ``validation_status`` is written by
``registry_model_plugin_validate``, which checks the *declaration*: image tag present,
command non-empty, JSON Schema well-formed, ports coherent. It never executes anything.
So ``valid`` means "this record is well-formed", and there has been no way to record the
different and more valuable fact that the plugin was observed to produce correct output on
the cluster. Conflating them is how sixteen plugins came to sit at ``unknown`` with no
distinction between "nobody checked the declaration" and "nobody ever ran it". The new
columns record the second fact, with evidence, and leave the first alone.

Revision ID: 0037_exec_mode_runtime_valid
Revises: 0036_timeline_entry_key
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is varchar(32); a longer id fails only at the final UPDATE,
# after the DDL has already run.
revision: str = "0037_exec_mode_runtime_valid"
down_revision: str | None = "0036_timeline_entry_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # model_plugins is created from live model metadata in 0002, so on a fresh database
    # these columns already exist by the time this revision runs and adding them again
    # fails. Same guard as 0020, for the same reason.
    if "execution_mode" not in _columns("workflow_nodes"):
        op.add_column(
            "workflow_nodes",
            sa.Column(
                "execution_mode",
                sa.String(length=20),
                nullable=False,
                server_default="dispatch",
            ),
        )
    plugin_columns = _columns("model_plugins")
    if "runtime_validation_status" not in plugin_columns:
        op.add_column(
            "model_plugins",
            sa.Column(
                "runtime_validation_status",
                sa.String(length=32),
                nullable=False,
                server_default="unproven",
            ),
        )
        op.create_index(
            "ix_model_plugins_runtime_validation_status",
            "model_plugins",
            ["runtime_validation_status"],
        )
    if "runtime_validated_at" not in plugin_columns:
        op.add_column(
            "model_plugins",
            sa.Column("runtime_validated_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "runtime_validation_evidence" not in plugin_columns:
        op.add_column(
            "model_plugins",
            sa.Column(
                "runtime_validation_evidence",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
        )


def downgrade() -> None:
    plugin_columns = _columns("model_plugins")
    if "runtime_validation_evidence" in plugin_columns:
        op.drop_column("model_plugins", "runtime_validation_evidence")
    if "runtime_validated_at" in plugin_columns:
        op.drop_column("model_plugins", "runtime_validated_at")
    if "runtime_validation_status" in plugin_columns:
        op.drop_index("ix_model_plugins_runtime_validation_status", table_name="model_plugins")
        op.drop_column("model_plugins", "runtime_validation_status")
    if "execution_mode" in _columns("workflow_nodes"):
        op.drop_column("workflow_nodes", "execution_mode")
