"""Join task contracts, bot governance and workflow gate migration branches.

Each branch keeps its original revision IDs so existing deployments can upgrade.
"""

from collections.abc import Sequence

revision: str = "0064_public_integration"
down_revision: tuple[str, ...] = (
    "0056_copilot_task_contracts",
    "0061_autopilot_stage_operator",
    "0063_proteinmpnn_parser",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
