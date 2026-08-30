"""Fail closed when scaffold-design plugins are missing required scientific inputs.

Revision ID: 0038_sweetprotein_runtime_guards
Revises: 0037_exec_mode_runtime_valid
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0038_sweetprotein_runtime_guards"
down_revision: str | None = "0037_exec_mode_runtime_valid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _row(plugin_key: str):
    return op.get_bind().execute(
        sa.text("SELECT id, command, input_ports::text FROM model_plugins WHERE plugin_key = :key"),
        {"key": plugin_key},
    ).fetchone()


def _update(plugin_id, command: str, ports: list[dict]) -> None:
    op.get_bind().execute(
        sa.text(
            """
            UPDATE model_plugins
            SET command = :command,
                input_ports = CAST(:ports AS json),
                validation_status = 'unknown',
                runtime_validation_status = 'unproven',
                runtime_validated_at = NULL,
                runtime_validation_evidence = '{}'::json,
                version = version + 1,
                updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": plugin_id, "command": command, "ports": json.dumps(ports)},
    )


def upgrade() -> None:
    rfd = _row("RFdiffusion")
    if rfd is not None:
        command = str(rfd.command or "")
        marker = 'rfd_input="$(find "$BDA_INPUT_DIR/input_structure"'
        if marker in command and "requires_input_structure is true" not in command:
            line_end = command.index("\n", command.index(marker)) + 1
            guard = (
                'if [ -n "${requires_input_structure:-}" ] && [ -z "$rfd_input" ]; then\n'
                '  echo "RFdiffusion: requires_input_structure is true but no input PDB was staged" >&2\n'
                "  exit 64\n"
                "fi\n"
            )
            command = command[:line_end] + guard + command[line_end:]
        ports = json.loads(rfd.input_ports or "[]")
        _update(rfd.id, command, ports if isinstance(ports, list) else [])

    mpnn = _row("ProteinMPNN")
    if mpnn is not None:
        command = str(mpnn.command or "")
        if "requires_fixed_positions is true" not in command:
            guard = (
                'fixed_positions_staged="$(find "$BDA_INPUT_DIR/fixed_positions" -type f '
                "\\( -name '*.jsonl' -o -name '*.json' \\) 2>/dev/null | sort | head -1)" + '"\n'
                'if [ -n "${requires_fixed_positions:-}" ] && [ -z "$fixed_positions_staged" ]; then\n'
                '  echo "ProteinMPNN: requires_fixed_positions is true but no position map was staged" >&2\n'
                "  exit 64\n"
                "fi\n"
                'if [ -n "$fixed_positions_staged" ]; then fixed_positions_jsonl="$fixed_positions_staged"; fi\n'
            )
            command = guard + command
        ports = json.loads(mpnn.input_ports or "[]")
        if isinstance(ports, list) and not any(
            isinstance(item, dict) and item.get("name") == "fixed_positions" for item in ports
        ):
            ports.append(
                {
                    "name": "fixed_positions",
                    "kind": "params",
                    "accepts": ["parameter_file", "fixed_positions"],
                    "content_types": ["application/json", "application/x-ndjson", "text/plain"],
                    "required": False,
                    "multiple": False,
                    "description": "Immutable fixed-position map for constrained sequence design.",
                }
            )
        _update(mpnn.id, command, ports if isinstance(ports, list) else [])


def downgrade() -> None:
    # These guards prevent scientifically different runs from being submitted under the
    # same route name. Downgrade deliberately keeps them rather than restoring unsafe
    # execution semantics.
    pass
