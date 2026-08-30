"""Correct two inferred port kinds and declare ProteinMPNN's alternative inputs.

0017 derived ports from each plugin's own declarations, inferring the semantic ``kind``
from field names and help text. Two inferences were wrong, and one relationship could not
be expressed at all until ``exclusive_group`` existed:

* ``Boltz.input_path`` was read as an opaque parameter. Boltz takes a FASTA/YAML
  specification of what to fold, so it is a sequence input and can be fed from upstream.
* ``ProteinMPNN.pssm_jsonl`` was read as a sequence because "pssm" looks sequence-like.
  A position-specific scoring matrix is a parameter file, not a sequence.
* ``ProteinMPNN`` accepts a backbone as *either* ``pdb_path`` or ``jsonl_path``. Both were
  optional, so a node with neither passed preflight and failed on the cluster instead.

Revision ID: 0018_correct_inferred_port_kinds
Revises: 0017_derive_plugin_ports
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_correct_inferred_port_kinds"
down_revision: str | None = "0017_derive_plugin_ports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# plugin_key -> port name -> field updates
CORRECTIONS: dict[str, dict[str, dict]] = {
    "Boltz": {
        "input_path": {
            "kind": "protein_sequence",
            "accepts": ["sequence_set", "sequence"],
            "required": True,
        }
    },
    "ProteinMPNN": {
        "pssm_jsonl": {"kind": "params", "accepts": []},
        # Either route satisfies the backbone requirement; binding both is an error.
        "pdb_path": {"required": True, "exclusive_group": "backbone_source"},
        "jsonl_path": {"required": True, "exclusive_group": "backbone_source"},
    },
}


def _apply(ports: list, corrections: dict[str, dict]) -> tuple[list, list[str]]:
    applied: list[str] = []
    updated = []
    for port in ports:
        if isinstance(port, dict) and port.get("name") in corrections:
            name = str(port["name"])
            updated.append({**port, **corrections[name]})
            applied.append(name)
        else:
            updated.append(port)
    return updated, applied


def upgrade() -> None:
    bind = op.get_bind()
    for plugin_key, corrections in CORRECTIONS.items():
        row = bind.execute(
            sa.text("SELECT id, input_ports::text FROM model_plugins WHERE plugin_key = :key"),
            {"key": plugin_key},
        ).fetchone()
        if row is None:
            print(f"0018: {plugin_key} not present, skipped")
            continue
        plugin_id, raw = row
        try:
            ports = json.loads(raw or "[]")
        except json.JSONDecodeError:
            print(f"0018: {plugin_key} has unparsable input_ports, skipped")
            continue
        updated, applied = _apply(ports if isinstance(ports, list) else [], corrections)
        missing = sorted(set(corrections) - set(applied))
        if missing:
            print(f"0018: {plugin_key} has no port(s) named {missing}; they were not corrected")
        if not applied:
            continue
        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET input_ports = CAST(:ports AS json), version = version + 1, updated_at = now()
                WHERE id = :plugin_id
                """
            ),
            {"plugin_id": plugin_id, "ports": json.dumps(updated)},
        )
        print(f"0018: {plugin_key} corrected {sorted(applied)}")


def downgrade() -> None:
    # These replace demonstrably wrong inferences; restoring them would reintroduce a
    # sequence port that is a parameter file and a backbone requirement nothing enforces.
    pass
