"""Give the design plugins output patterns, and point RFdiffusion at the port it declares.

Collection attaches a collected file to a declared output port in one of two ways: the
file sits under ``outputs/<port>/``, or its name matches the port's ``filename_glob``. A
glob of ``*`` is deliberately never matched - it would claim every file for whichever
port happened to be declared first - so a port left at the default can only be filled by
the directory route, and these models do not write that way.

The consequence was measured on 2026-09-11. ProteinMPNN ran on Qiming (LSF 4267551),
succeeded, and three outputs were collected and checksum-verified; every one was stored
untyped because all three output ports were left at ``*``. The gate on the connection
then found no results on ``sequence_set`` and settled as ``error``, and the downstream
node waited on a release that could never come. The route was correct; nothing could
tell the platform which file was the sequence set.

Only a port still at the default is filled in, so a declaration that already carries a
pattern is left alone - ProteinMPNN 1.0.1 already declared ``*.fa`` and keeps it.

RFdiffusion 1.1.0 additionally probes ``$BDA_INPUT_DIR/input_structure`` while declaring
its input port as ``inference_input_pdb``. Staging writes to ``inputs/<port>/``, so that
directory is never created and the bound structure is placed somewhere the command does
not look. The parameter ``requires_input_structure`` is a different thing and is left
untouched.

Revision ID: 0060_plugin_output_routing
Revises: 0059_workflow_gates
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0060_plugin_output_routing"
down_revision: str | None = "0059_workflow_gates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: plugin_key -> output port name -> filename pattern, matched against the file's own
#: name. Grounded in observed output: ProteinMPNN writes ``seqs/<name>.fa`` plus the
#: ``parsed_pdbs.jsonl``/``assigned_pdbs.jsonl`` it derives on the way, and RFdiffusion
#: writes its backbones as PDB. Ports whose output has not been observed are left at the
#: default rather than given a guess - an unmatched pattern is harmless, a wrong one
#: silently files the wrong artifact.
GLOBS: dict[str, dict[str, str]] = {
    "ProteinMPNN": {
        "sequence_set": "*.fa*",
        "sequences": "*.fa*",
        "score_table": "*.csv",
        "run_manifest": "*.jsonl",
    },
    "ProteinMPNN-authoring-6810138a": {
        "sequence_set": "*.fa*",
        "score_table": "*.csv",
        "run_manifest": "*.jsonl",
    },
    "RFdiffusion": {"backbone_set": "*.pdb"},
    "RFdiffusion-authoring-6810138a": {"backbone_set": "*.pdb"},
}

DEFAULT_GLOBS = {"", "*"}

#: The directory RFdiffusion 1.1.0's command probes, and the port it actually declares.
WRONG_INPUT_DIR = "$BDA_INPUT_DIR/input_structure"
RIGHT_INPUT_DIR = "$BDA_INPUT_DIR/inference_input_pdb"


def _rows(bind, plugin_key: str):
    return bind.execute(
        sa.text(
            "SELECT id, plugin_version, output_ports::text FROM model_plugins WHERE plugin_key = :key"
        ),
        {"key": plugin_key},
    ).fetchall()


def _write_ports(bind, plugin_id, ports: list) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET output_ports = CAST(:ports AS json), version = version + 1, updated_at = now()
            WHERE id = :plugin_id
            """
        ),
        {"ports": json.dumps(ports), "plugin_id": plugin_id},
    )


def _retarget_command(bind, *, frm: str, to: str) -> None:
    row = bind.execute(
        sa.text(
            "SELECT id, command FROM model_plugins WHERE plugin_key = 'RFdiffusion' AND plugin_version = '1.1.0'"
        )
    ).fetchone()
    if row is None:
        print("0060: RFdiffusion 1.1.0 is not registered, command left alone")
        return
    plugin_id, command = row
    if frm not in (command or ""):
        print(f"0060: RFdiffusion 1.1.0 does not probe {frm}, command left alone")
        return
    bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET command = :command, version = version + 1, updated_at = now()
            WHERE id = :plugin_id
            """
        ),
        {"command": command.replace(frm, to), "plugin_id": plugin_id},
    )


def _apply_globs(bind, *, fill_defaults: bool) -> None:
    """Set patterns (upgrade) or restore the defaults this migration filled (downgrade)."""
    for plugin_key, patterns in GLOBS.items():
        for plugin_id, plugin_version, raw in _rows(bind, plugin_key):
            try:
                ports = json.loads(raw or "[]")
            except json.JSONDecodeError:
                print(f"0060: {plugin_key} {plugin_version} has unparsable output_ports, skipped")
                continue
            if not isinstance(ports, list):
                continue
            updated: list = []
            changed = False
            for port in ports:
                name = port.get("name") if isinstance(port, dict) else None
                wanted = patterns.get(str(name)) if name else None
                current = str(port.get("filename_glob") or "") if isinstance(port, dict) else ""
                if wanted and (current in DEFAULT_GLOBS if fill_defaults else current == wanted):
                    updated.append({**port, "filename_glob": wanted if fill_defaults else "*"})
                    changed = True
                else:
                    updated.append(port)
            if changed:
                _write_ports(bind, plugin_id, updated)


def upgrade() -> None:
    bind = op.get_bind()
    _apply_globs(bind, fill_defaults=True)
    _retarget_command(bind, frm=WRONG_INPUT_DIR, to=RIGHT_INPUT_DIR)


def downgrade() -> None:
    bind = op.get_bind()
    _apply_globs(bind, fill_defaults=False)
    _retarget_command(bind, frm=RIGHT_INPUT_DIR, to=WRONG_INPUT_DIR)
