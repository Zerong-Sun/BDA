"""Declare the min/max ordering rules JSON Schema cannot express.

0029 documented that ``min_protein_length <= max_protein_length`` "has no cross-field
arithmetic and is left to the model" — a bad value would only surface after a GPU day on
qm. 0033 registered BindCraft with the identical shape (``min_binder_length`` /
``max_binder_length``) and the same gap.

Draft 2020-12 genuinely cannot compare two sibling properties without a ``$data``
extension the ``jsonschema`` validator here does not support, so this adds a small
out-of-band annotation, ``x-bda-order-pairs``, that ``app/workflows/preflight.py``
reads and checks in Python alongside the schema. Neither plugin's command or ports
change, so ``plugin_version`` and ``validation_status`` are left alone; only the stored
``parameter_schema`` gains the annotation.

Revision ID: 0034_parameter_order_pairs
Revises: 0033_register_design_plugins
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0034_parameter_order_pairs"
down_revision: str | None = "0033_register_design_plugins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (plugin_key, [[low, high], ...])
ORDER_PAIRS = (
    ("proteinhunter_boltz", [["min_protein_length", "max_protein_length"]]),
    ("BindCraft", [["min_binder_length", "max_binder_length"]]),
)

_SET_SQL = """
    UPDATE model_plugins
    -- parameter_schema is stored as `json`, which has no merge operator, so this
    -- round-trips through `jsonb` (the only type `||` and `-` are defined on) and back.
    SET parameter_schema = CAST(parameter_schema::jsonb || CAST(:patch AS jsonb) AS json),
        version = version + 1,
        updated_at = now()
    WHERE plugin_key = :key
"""


def upgrade() -> None:
    bind = op.get_bind()
    for key, pairs in ORDER_PAIRS:
        result = bind.execute(
            sa.text(_SET_SQL),
            {"key": key, "patch": json.dumps({"x-bda-order-pairs": pairs})},
        )
        print(f"0034: annotated {result.rowcount} {key} row(s) with x-bda-order-pairs={pairs}")


def downgrade() -> None:
    bind = op.get_bind()
    for key, _pairs in ORDER_PAIRS:
        result = bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET parameter_schema = CAST(parameter_schema::jsonb - 'x-bda-order-pairs' AS json),
                    version = version + 1,
                    updated_at = now()
                WHERE plugin_key = :key
                """
            ),
            {"key": key},
        )
        print(f"0034 downgrade: removed x-bda-order-pairs from {result.rowcount} {key} row(s)")
