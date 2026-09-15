"""A bot can ask the person to settle one thing, with the options and evidence.

Until now "what needs a person" was *inferred* from five lists - a task waiting
for input, an unreviewed delivery, an unconfirmed draft, a pending claim, a
handover citing nothing. Inference has a ceiling: it can say a delivery is
unreviewed, and it can never say "I narrowed the hotspots to three sets and the
choice between them is yours, here is what each costs".

The row is the question. Its answer is written back as a timeline entry
attributed `agent_proposed_human_confirmed`, which is exactly what it is: the
options were drafted by an operator and the call was made by a person.

Column types follow `0060_copilot_handoffs` rather than being chosen afresh -
`postgresql.UUID(as_uuid=True)` and `sa.JSON`, which is what the ORM declares,
so `alembic check` compares equal instead of reporting drift on every run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0066_copilot_decision_requests"
down_revision: str | None = "0065_copilot_message_bot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "copilot_decision_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("legacy_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("copilot_agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("asked_by", sa.String(length=80), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommended", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("answer", sa.String(length=80), nullable=True),
        sa.Column("answer_note", sa.Text(), nullable=True),
        sa.Column(
            "answered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decision_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_timeline_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.CheckConstraint(
            "status in ('open', 'answered', 'withdrawn')",
            name="ck_copilot_decision_request_status",
        ),
        # An answered question names who answered and when; an open one names
        # neither. The pair is what makes the row readable as "a person settled
        # this", and a half-written answer would look like one.
        sa.CheckConstraint(
            "(status = 'answered') = (answered_by is not null and answered_at is not null)",
            name="ck_copilot_decision_request_answered",
        ),
    )
    # The inbox read is "still open, in this project, newest first".
    op.create_index(
        "ix_copilot_decision_requests_open",
        "copilot_decision_requests",
        ["project_id", "status", "created_at"],
    )
    op.create_index(
        "ix_copilot_decision_requests_run_id", "copilot_decision_requests", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_copilot_decision_requests_run_id", table_name="copilot_decision_requests")
    op.drop_index("ix_copilot_decision_requests_open", table_name="copilot_decision_requests")
    op.drop_table("copilot_decision_requests")
