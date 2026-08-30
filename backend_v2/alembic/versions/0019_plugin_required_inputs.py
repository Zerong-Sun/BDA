"""Set each plugin's required inputs on its own merits, and close the AlphaFold 3 gap.

0017 derived every input port as optional because guessing wrong toward "required" blocks
submission outright. The right value differs per model, so each is decided here from that
plugin's own field help plus what the tool cannot run without.

| Plugin       | Required                | Why |
|--------------|-------------------------|-----|
| AlphaFold2   | fasta_paths             | Nothing to fold without sequences |
| AlphaFold 3  | json_path               | Unconditional in the command template |
| BindCraft    | settings                | Names the binding target; the other two ship defaults |
| Boltz        | input_path              | Unconditional in the command template (set in 0018) |
| Chai-1       | input_fasta             | Unconditional; restraints_json is documented "Optional" |
| DiffAb       | antigen_pdb             | Antibody design needs something to design against |
| ProteinMPNN  | pdb_path / jsonl_path   | Either route, as an exclusive group (set in 0018) |
| Rosetta      | s                       | Nothing to score without a structure |
| RFdiffusion  | *(none)*                | Unconditional generation legitimately takes no input PDB |
| Mask RGN     | *(none)*                | Declares no artifact inputs at all |

RFdiffusion staying optional is a deliberate decision, not an omission: motif scaffolding
and binder design need an input PDB, but unconditional generation does not, and marking it
required would block a legitimate mode.

AlphaFold 3 additionally gains a ``sequences`` input port and the ``af3_fold_input``
adapter. Its sequences live inside the JSON job specification, so as declared it could not
sit downstream of anything; the adapter builds that JSON at dispatch from bound sequences,
leaving ``json_path`` available for a hand-authored specification that takes precedence.

Revision ID: 0019_plugin_required_inputs
Revises: 0018_correct_inferred_port_kinds
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_plugin_required_inputs"
down_revision: str | None = "0018_correct_inferred_port_kinds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# plugin_key -> port names that the model cannot run without.
REQUIRED_INPUTS: dict[str, set[str]] = {
    "AlphaFold2": {"fasta_paths"},
    "AlphaFold 3": {"json_path"},
    "BindCraft": {"settings"},
    "Chai-1": {"input_fasta"},
    "DiffAb": {"antigen_pdb"},
    "Rosetta": {"s"},
    # Boltz and ProteinMPNN were decided in 0018; RFdiffusion and Mask RGN stay optional.
}

AF3_SEQUENCE_PORT = {
    "name": "sequences",
    "kind": "protein_sequence",
    "accepts": ["sequence_set", "sequence"],
    "content_types": [],
    "required": False,
    "multiple": True,
    "description": (
        "Sequences to fold. Converted into fold_input.json by the af3_fold_input adapter, "
        "so this can be wired from an upstream design node."
    ),
    "exclusive_group": "af3_input_source",
}


def _add_column_if_missing() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("model_plugins")}
    if "input_adapter" not in columns:
        op.add_column("model_plugins", sa.Column("input_adapter", sa.String(80), nullable=True))


def upgrade() -> None:
    _add_column_if_missing()
    bind = op.get_bind()

    for plugin_key, required in REQUIRED_INPUTS.items():
        row = bind.execute(
            sa.text("SELECT id, input_ports::text FROM model_plugins WHERE plugin_key = :key"),
            {"key": plugin_key},
        ).fetchone()
        if row is None:
            print(f"0019: {plugin_key} not present, skipped")
            continue
        plugin_id, raw = row
        try:
            ports = json.loads(raw or "[]")
        except json.JSONDecodeError:
            print(f"0019: {plugin_key} has unparsable input_ports, skipped")
            continue
        if not isinstance(ports, list):
            continue

        names = {port.get("name") for port in ports if isinstance(port, dict)}
        missing = sorted(required - names)
        if missing:
            print(f"0019: {plugin_key} has no port(s) named {missing}; nothing marked required for them")

        updated = [
            {**port, "required": True} if isinstance(port, dict) and port.get("name") in required else port
            for port in ports
        ]

        if plugin_key == "AlphaFold 3":
            # json_path becomes one of two ways in; the adapter supplies the other.
            updated = [
                {**port, "exclusive_group": "af3_input_source"}
                if isinstance(port, dict) and port.get("name") == "json_path"
                else port
                for port in updated
            ]
            if "sequences" not in names:
                updated.append(AF3_SEQUENCE_PORT)

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
        print(f"0019: {plugin_key} required={sorted(required & names)}")

    result = bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET input_adapter = 'af3_fold_input', version = version + 1, updated_at = now()
            WHERE plugin_key = 'AlphaFold 3' AND input_adapter IS NULL
            """
        )
    )
    print(f"0019: attached af3_fold_input adapter to {result.rowcount} plugin(s)")


def downgrade() -> None:
    op.execute("UPDATE model_plugins SET input_adapter = NULL WHERE input_adapter = 'af3_fold_input'")
    # Required flags reflect what each model cannot run without; reverting them would
    # reinstate a state where a node with no inputs passes preflight.
