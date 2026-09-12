"""Let three plugins read their required input from the port that stages it.

Boltz, AlphaFold 3 and BindCraft each pass a required input straight to the tool as a
bare shell variable - ``boltz predict "$input_path"``, ``--json_path "$json_path"``,
``--settings "$settings"``. Nothing ever sets those names. Staging writes the bound file
to ``inputs/<port>/``; it does not export a variable per port, and the platform should
not start: eight of the eighteen registered plugins declare a port and a parameter with
the same name, so exporting port paths under the port's name would shadow, or be
shadowed by, parameters in plugins that work today.

Under the ``set -Eeuo pipefail`` the renderer emits, an unset name is fatal on sight, so
the job died before the tool ran. Measured 2026-09-11 on Qiming (LSF 4267853):
``input_path: unbound variable``, exit 1, seven seconds, nothing else written.

Each of these names is also declared as a parameter, and in all three cases it is an
``artifact_ref`` with an empty default - the pre-port way the UI let someone pick a file.
It holds an artifact reference, not a path on the cluster, so it is not what the tool
should receive. The port is the current mechanism and is declared ``required``, which
preflight already enforces; this reads the file the port staged and says so plainly when
there is none, rather than failing as an unset variable.

The thirteen plugins that already resolve their inputs with
``find "$BDA_INPUT_DIR/<port>"`` are untouched - this gives the other three the same
idiom, written the safe way, with ``|| true`` so the lookup cannot abort the job even on
a deployment whose renderer does not pre-create the port directories.

Revision ID: 0061_staged_port_paths
Revises: 0060_plugin_output_routing
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0061_staged_port_paths"
down_revision: str | None = "0060_plugin_output_routing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MARKER = "# bda: resolve required input from its staged port"

#: (plugin_key, plugin_version) -> (port/variable name, label used in the error)
TARGETS: dict[tuple[str, str], tuple[str, str]] = {
    ("Boltz", "2.x"): ("input_path", "Boltz"),
    ("Boltz-authoring-6810138a", "2.x-draft.1"): ("input_path", "Boltz"),
    ("AlphaFold 3", "3.0"): ("json_path", "AlphaFold 3"),
    ("BindCraft", "2025.09"): ("settings", "BindCraft"),
}


def _prelude(name: str, label: str) -> str:
    return (
        f"{MARKER}\n"
        f'{name}="$(find "$BDA_INPUT_DIR/{name}" -maxdepth 1 -type f 2>/dev/null'
        f' | sort | head -1 || true)"\n'
        f'if [ -z "${{{name}:-}}" ]; then\n'
        f'  echo "{label}: nothing is staged on the {name} port; bind it before submitting" >&2\n'
        f"  exit 64\n"
        f"fi\n"
    )


def upgrade() -> None:
    bind = op.get_bind()
    for (plugin_key, plugin_version), (name, label) in TARGETS.items():
        row = bind.execute(
            sa.text(
                "SELECT id, command FROM model_plugins WHERE plugin_key = :key AND plugin_version = :ver"
            ),
            {"key": plugin_key, "ver": plugin_version},
        ).fetchone()
        if row is None:
            print(f"0061: {plugin_key} {plugin_version} is not registered, skipped")
            continue
        plugin_id, command = row
        command = command or ""
        if MARKER in command:
            continue
        if f'"${name}"' not in command:
            print(f"0061: {plugin_key} {plugin_version} does not read ${name} directly, skipped")
            continue
        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET command = :command, version = version + 1, updated_at = now()
                WHERE id = :plugin_id
                """
            ),
            {"command": _prelude(name, label) + command, "plugin_id": plugin_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for (plugin_key, plugin_version), (name, label) in TARGETS.items():
        row = bind.execute(
            sa.text(
                "SELECT id, command FROM model_plugins WHERE plugin_key = :key AND plugin_version = :ver"
            ),
            {"key": plugin_key, "ver": plugin_version},
        ).fetchone()
        if row is None:
            continue
        plugin_id, command = row
        prelude = _prelude(name, label)
        if not (command or "").startswith(prelude):
            continue
        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET command = :command, version = version + 1, updated_at = now()
                WHERE id = :plugin_id
                """
            ),
            {"command": command[len(prelude) :], "plugin_id": plugin_id},
        )
