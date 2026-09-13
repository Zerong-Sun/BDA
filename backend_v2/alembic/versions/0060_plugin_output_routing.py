"""Merge the published and previously deployed migration identifiers.

The data migration lives at 0057_plugin_output_routing. Databases already stamped
with 0060_plugin_output_routing have applied it; older deployments retain their original
revision chain. This merge prevents applying the same data rewrite twice.
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = "0060_plugin_output_routing"
down_revision: tuple[str, str] = ("0059_workflow_gates", "0057_plugin_output_routing")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
