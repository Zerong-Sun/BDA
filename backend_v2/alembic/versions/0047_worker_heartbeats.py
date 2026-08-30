"""Track worker build/schema/queue heartbeats for readiness.

Revision ID: 0047_worker_heartbeats
Revises: 0046_workflow_plugin_ports
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0047_worker_heartbeats"
down_revision: str | None = "0046_workflow_plugin_ports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("instance_id", sa.String(length=255), primary_key=True),
        sa.Column("service", sa.String(length=80), nullable=False),
        sa.Column("queues", sa.JSON(), nullable=False),
        sa.Column("build_revision", sa.String(length=80), nullable=False),
        sa.Column("schema_revision", sa.String(length=80), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worker_heartbeats_service", "worker_heartbeats", ["service"])
    op.create_index("ix_worker_heartbeats_build_revision", "worker_heartbeats", ["build_revision"])
    op.create_index("ix_worker_heartbeats_schema_revision", "worker_heartbeats", ["schema_revision"])
    op.create_index("ix_worker_heartbeats_last_seen_at", "worker_heartbeats", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
    op.drop_index("ix_worker_heartbeats_schema_revision", table_name="worker_heartbeats")
    op.drop_index("ix_worker_heartbeats_build_revision", table_name="worker_heartbeats")
    op.drop_index("ix_worker_heartbeats_service", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
