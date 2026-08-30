"""Add the explicit target-to-artifact foreign key.

Revision ID: 0008_target_artifact_fk
Revises: 0007_data_flow_closure
"""

from __future__ import annotations

from alembic import op

revision = "0008_target_artifact_fk"
down_revision = "0007_data_flow_closure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_targets_structure_artifact",
        "targets",
        "artifacts",
        ["structure_artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_targets_structure_artifact", "targets", type_="foreignkey")
