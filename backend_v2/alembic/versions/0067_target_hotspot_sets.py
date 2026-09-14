"""The residues a design targets, as a row a person can confirm.

`ppi.hotspot_res` (RFdiffusion) and `target_hotspot_residues` (BindCraft) have
been in the plugin registry since those plugins were registered, and nothing
produced them: the residues lived in a sentence and were retyped into a
parameter box. This table is the object in between - proposed by an operator,
confirmed by a person, and only then usable as a design parameter.

`origin` carries the same three states as `project_timeline_entries.decided_by`
and is spelled the same way on purpose: it is the same question about the same
kind of judgement.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0067_target_hotspot_sets"
down_revision: str | None = "0066_copilot_decision_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "target_hotspot_sets",
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
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "structure_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("residues", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("origin", sa.String(length=40), nullable=False, server_default="agent"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="proposed"),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "confirmed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.CheckConstraint(
            "origin in ('agent', 'human', 'agent_proposed_human_confirmed')",
            name="ck_target_hotspot_set_origin",
        ),
        sa.CheckConstraint(
            "status in ('proposed', 'confirmed', 'rejected')",
            name="ck_target_hotspot_set_status",
        ),
    )
    op.create_index("ix_target_hotspot_sets_project_id", "target_hotspot_sets", ["project_id"])
    op.create_index("ix_target_hotspot_sets_status", "target_hotspot_sets", ["status"])
    op.create_index(
        "ix_target_hotspot_sets_target", "target_hotspot_sets", ["target_id", "status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_target_hotspot_sets_target", table_name="target_hotspot_sets")
    op.drop_index("ix_target_hotspot_sets_status", table_name="target_hotspot_sets")
    op.drop_index("ix_target_hotspot_sets_project_id", table_name="target_hotspot_sets")
    op.drop_table("target_hotspot_sets")
