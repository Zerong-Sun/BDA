"""Merge the published and previously deployed migration identifiers.

The data migration lives at 0062_proteinmpnn_parser. Databases already stamped
with 0063_proteinmpnn_parser have applied it; older deployments retain their original
revision chain. This merge prevents applying the same data rewrite twice.
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = "0063_proteinmpnn_parser"
down_revision: tuple[str, str] = ("0061_staged_port_paths", "0062_proteinmpnn_parser")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
