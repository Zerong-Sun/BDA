"""Let a target be a small molecule, and be ready without a protein structure.

Some binder projects use a small molecule as their primary target. The readiness gate -
confirmed protein identity plus an uploaded
structure artifact - can never be satisfied by one: a small molecule has no UniProt
accession and no sequence, so `identity_status` never leaves "unconfirmed", and the
Workflow page stays read-only forever. The project worked around it by keeping a receptor
as the primary target, which misdescribes what is being designed against.

The fix is not to relax the gate but to ask the right question of each kind of target. A
protein target is ready when its identity is confirmed and a structure has been uploaded,
because the design needs those coordinates. A small-molecule target is ready when its
chemical identity resolves - a CCD code, an InChIKey or a SMILES string - because its
three-dimensional structure is produced from that identifier at run time by the model's own
component library, not supplied as a file. Requiring an uploaded structure for a ligand
asks for something that does not exist and would not be used.

`target_kind` defaults to "protein" and every existing row is one, so the protein path is
unchanged.

Revision ID: 0032_ligand_targets
Revises: 0031_run_lineage_outcome
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032_ligand_targets"
down_revision: str | None = "0031_run_lineage_outcome"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    columns = _columns("targets")
    if "target_kind" not in columns:
        op.add_column(
            "targets",
            sa.Column("target_kind", sa.String(length=40), nullable=False, server_default="protein"),
        )
    if "chemical_identity" not in columns:
        op.add_column(
            "targets",
            sa.Column("chemical_identity", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        )


def downgrade() -> None:
    # Drop by inspection: 0002_full_domains creates this table from the live ORM metadata,
    # so on a database built after the models changed these columns already exist and were
    # never added by this revision. See 0026 for the same hazard.
    columns = _columns("targets")
    if "chemical_identity" in columns:
        op.drop_column("targets", "chemical_identity")
    if "target_kind" in columns:
        op.drop_column("targets", "target_kind")
