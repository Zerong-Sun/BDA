"""Give the transactional outbox a dead-letter column.

``publish_outbox`` selects unpublished events ordered by ``created_at`` with a batch
limit. An event it could not dispatch stayed selectable forever: the unknown-topic branch
set neither ``published_at`` nor a new ``available_at``, so the same rows were re-read
every two seconds and, once there were ``batch_size`` of them, no real event was ever
reached again. The send-failure branch backed off but had no ceiling, so a permanently
failing event degraded to the same behaviour at a slower rate.

Both paths now stop after ``MAX_OUTBOX_ATTEMPTS``. Marking the row instead of deleting it
keeps the evidence for an operator, and lets the backlog gauge report live work while a
separate gauge makes stuck events alertable.

The realistic trigger is a rolling deploy or a rollback: an old worker meets a topic a
newer API already writes, and head-of-line blocking stops every queue.

Revision ID: 0023_outbox_dead_letter
Revises: 0022_candidate_metrics
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_outbox_dead_letter"
down_revision: str | None = "0022_candidate_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_dead_lettered_at",
        "outbox_events",
        ["dead_lettered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_dead_lettered_at", table_name="outbox_events")
    op.drop_column("outbox_events", "dead_lettered_at")
