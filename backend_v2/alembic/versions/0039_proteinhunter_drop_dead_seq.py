"""Stop offering ``seq``: ProteinHunter's entrypoint declares it and never reads it.

0021 registered ``seq`` ("Fixed starting sequence.") and 0029 kept it, marked advanced,
rendered as ``${seq:+--seq "$seq"}``. Upstream ``boltz_ph/design.py`` adds the argument to
its parser and then never touches ``args.seq`` — ``grep "args.seq"`` over the qm install is
empty. So a user who pastes a scaffold sequence into that box gets a job that silently
ignores it and designs from scratch, which is the worst failure mode a parameter can have:
it looks like it worked.

This came out of the cannabinoid project, where "redesign from the 6MP4 pocket" and "refine
the three winners for a few more cycles" were both planned around this field before the
source was read (CANNABINOID_PHASE2_BROAD_SPECTRUM_DESIGN.md §6.14.5). Scaffold-conditioned
design needs RFdiffusion partial diffusion, not this entrypoint.

Patched surgically rather than by restating the schema: 0034 later annotated the same row
with ``x-bda-order-pairs`` and a wholesale rewrite would drop it.

``seq`` leaves ``properties`` so the parameter form stops showing it, but a guard stays
behind in ``allOf``. ``additionalProperties`` is ``True`` here, so deleting the property
alone would let a non-empty ``seq`` through again — silently, which is what we are fixing.
The guard permits ``""`` so the saved nodes that carry the old default still validate, and
rejects anything else with a real error.

Revision ID: 0039_proteinhunter_drop_dead_seq
Revises: 0038_sweetprotein_runtime_guards
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039_proteinhunter_drop_dead_seq"
down_revision: str | None = "0038_sweetprotein_runtime_guards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLUGIN_KEY = "proteinhunter_boltz"

#: Exactly the fragment 0029 rendered, so removal is a string match rather than a rewrite.
SEQ_COMMAND_FRAGMENT = ' ${seq:+--seq "$seq"}'

#: What 0021/0029 stored, restored verbatim on downgrade.
SEQ_PROPERTY = {
    "type": "string",
    "default": "",
    "description": "Fixed starting sequence.",
    "x-bda-field-type": "textarea",
    "x-bda-advanced": True,
}

SEQ_GUARD = {
    "properties": {
        "seq": {
            "type": "string",
            "maxLength": 0,
            "description": (
                "Not supported: the ProteinHunter entrypoint parses --seq and never reads "
                "it. Use RFdiffusion partial diffusion for scaffold-conditioned design."
            ),
        }
    }
}

_SELECT = sa.text("SELECT command, parameter_schema FROM model_plugins WHERE plugin_key = :key")
_UPDATE = sa.text(
    """
    UPDATE model_plugins
    SET command = :command,
        parameter_schema = CAST(:parameter_schema AS json),
        version = version + 1,
        validation_status = 'unknown',
        updated_at = now()
    WHERE plugin_key = :key
    """
)


def _load() -> tuple[str, dict] | None:
    row = op.get_bind().execute(_SELECT, {"key": PLUGIN_KEY}).first()
    if row is None:
        print(f"0039: no {PLUGIN_KEY} row; nothing to patch")
        return None
    schema = row.parameter_schema
    if isinstance(schema, str):  # some drivers hand back `json` columns as text
        schema = json.loads(schema)
    return row.command, dict(schema)


def _store(command: str, schema: dict) -> None:
    op.get_bind().execute(
        _UPDATE,
        {"key": PLUGIN_KEY, "command": command, "parameter_schema": json.dumps(schema)},
    )


def upgrade() -> None:
    loaded = _load()
    if loaded is None:
        return
    command, schema = loaded

    command = command.replace(SEQ_COMMAND_FRAGMENT, "")

    properties = dict(schema.get("properties") or {})
    removed = properties.pop("seq", None)
    schema["properties"] = properties

    all_of = [clause for clause in (schema.get("allOf") or []) if clause != SEQ_GUARD]
    all_of.append(SEQ_GUARD)
    schema["allOf"] = all_of

    _store(command, schema)
    print(
        f"0039: dropped seq from {PLUGIN_KEY} "
        f"(property {'removed' if removed else 'already absent'}, guard added, flag unrendered)"
    )


def downgrade() -> None:
    loaded = _load()
    if loaded is None:
        return
    command, schema = loaded

    if SEQ_COMMAND_FRAGMENT not in command:
        # Re-inserted where 0029 put it: after the nucleic block, before contact_residues.
        anchor = ' ${contact_residues:+--contact_residues "$contact_residues"}'
        command = (
            command.replace(anchor, SEQ_COMMAND_FRAGMENT + anchor, 1)
            if anchor in command
            else command + SEQ_COMMAND_FRAGMENT
        )

    properties = dict(schema.get("properties") or {})
    properties.setdefault("seq", SEQ_PROPERTY)
    schema["properties"] = properties

    schema["allOf"] = [clause for clause in (schema.get("allOf") or []) if clause != SEQ_GUARD]

    _store(command, schema)
    print(f"0039 downgrade: restored seq on {PLUGIN_KEY}")
