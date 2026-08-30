"""Add ModelPlugin.runtime_setup.

HPC installations need environment preparation that neither a container image nor a conda
environment name can express: sourcing a conda profile by absolute path because it belongs
to another account and is not on PATH, module loads, exporting a dependency directory.
Declaring those lines keeps site knowledge as data instead of a per-model Python module.

Revision ID: 0021_plugin_runtime_setup
Revises: 0019_plugin_required_inputs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_plugin_runtime_setup"
down_revision: str | None = "0019_plugin_required_inputs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("model_plugins")}
    if "runtime_setup" not in columns:
        op.add_column(
            "model_plugins",
            sa.Column("runtime_setup", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        )


def downgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("model_plugins")}
    if "runtime_setup" in columns:
        op.drop_column("model_plugins", "runtime_setup")
