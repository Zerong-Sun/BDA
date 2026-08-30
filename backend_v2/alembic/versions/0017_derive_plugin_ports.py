"""Derive plugin ports from the declarations that already exist.

Migration 0016 hand-wrote ``input_ports``/``output_ports`` for the four enabled plugins.
That was wrong twice over: the names it invented disagree with the port names each plugin
already declares under ``output_schema.ports``, and it left the six disabled plugins empty
when their declarations were equally present.

Both port sets are derivable:

* output ports  <- ``output_schema.ports`` (legacy shape: name, artifact_types[], help)
* input ports   <- ``parameter_schema.fields`` entries whose ``type`` is ``artifact_ref``

``parameter_schema.ports`` is empty for every plugin, which is why inputs come from the
fields instead.

Derived input ports are all ``required: false``. A wrongly-required port blocks
submission outright, whereas a wrongly-optional one merely goes unenforced - so the
failure mode of guessing is chosen deliberately. Mark the genuinely mandatory ones by
hand afterwards.

Revision ID: 0017_derive_plugin_ports
Revises: 0016_compute_dataflow_ports
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_derive_plugin_ports"
down_revision: str | None = "0016_compute_dataflow_ports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# artifact_type -> semantic kind. Two ports connect only when their kind matches.
ARTIFACT_KIND = {
    "backbone_set": "protein_structure",
    "target_structure": "protein_structure",
    "predicted_structure": "protein_structure",
    "complex_structure": "protein_structure",
    "candidate_structure": "protein_structure",
    "candidate_complex": "protein_structure",
    "relaxed_structure": "protein_structure",
    "structure": "protein_structure",
    "sequence_set": "protein_sequence",
    "score_table": "tabular",
    "interface_metrics": "tabular",
    "pae_matrix": "tabular",
    "confidence_record": "tabular",
    "embedding": "opaque",
    "manifest": "params",
}

# Every structure-ish artifact_type an input port of that kind should accept. Derived
# inputs carry no declared allowlist, so they accept anything of the right kind.
STRUCTURE_TYPES = sorted(
    {key for key, kind in ARTIFACT_KIND.items() if kind == "protein_structure"}
)

# Field key / help keywords -> input kind, most specific first.
INPUT_KIND_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"msa|a3m|alignment", re.I), "msa"),
    (re.compile(r"fasta|sequence|seqs?\b", re.I), "protein_sequence"),
    (re.compile(r"pdb|structure|antigen|backbone|scaffold|template", re.I), "protein_structure"),
    (re.compile(r"ligand|sdf|smiles|mol2", re.I), "ligand"),
]


def _slug(value: str) -> str:
    """Port names become directory segments under the job working directory."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "input"


def _input_kind(key: str, help_text: str) -> str:
    for pattern, kind in INPUT_KIND_HINTS:
        if pattern.search(key) or pattern.search(help_text):
            return kind
    # Config blobs (jsonl, settings, filters, resfile, protocol...) are opaque parameters.
    return "params"


def _derive_input_ports(parameter_schema: dict) -> list[dict]:
    fields = parameter_schema.get("fields")
    if not isinstance(fields, list):
        return []
    ports: list[dict] = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, dict) or field.get("type") != "artifact_ref":
            continue
        key = str(field.get("key") or "")
        if not key:
            continue
        name = _slug(key)
        if name in seen:
            continue
        seen.add(name)
        help_text = str(field.get("help") or "")
        kind = _input_kind(key, help_text)
        label = str(field.get("label") or key)
        ports.append(
            {
                "name": name,
                "kind": kind,
                "accepts": STRUCTURE_TYPES if kind == "protein_structure" else [],
                "content_types": [],
                # Derived, so not enforced. Promote the real ones by hand.
                "required": False,
                "multiple": False,
                "description": f"{label}. {help_text}".strip() + f" (from field '{key}')",
            }
        )
    return ports


def _derive_output_ports(output_schema: dict) -> list[dict]:
    declared = output_schema.get("ports")
    if not isinstance(declared, list):
        return []
    ports: list[dict] = []
    for entry in declared:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        types = entry.get("artifact_types")
        if not name or not isinstance(types, list) or not types:
            continue
        artifact_type = str(types[0])
        ports.append(
            {
                "name": _slug(name),
                "kind": ARTIFACT_KIND.get(artifact_type, "opaque"),
                "artifact_type": artifact_type,
                "filename_glob": "*",
                "description": str(entry.get("help") or ""),
            }
        )
    return ports


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, plugin_key, parameter_schema::text, output_schema::text FROM model_plugins")
    ).fetchall()

    for row in rows:
        plugin_id, plugin_key, raw_parameters, raw_outputs = row
        try:
            parameter_schema = json.loads(raw_parameters or "{}")
            output_schema = json.loads(raw_outputs or "{}")
        except json.JSONDecodeError:
            print(f"0017: {plugin_key} has unparsable schema, skipped")
            continue

        input_ports = _derive_input_ports(parameter_schema)
        output_ports = _derive_output_ports(output_schema)
        if not input_ports and not output_ports:
            print(f"0017: {plugin_key} declares nothing to derive, ports left empty")
            continue

        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET input_ports = CAST(:input_ports AS json),
                    output_ports = CAST(:output_ports AS json),
                    version = version + 1,
                    updated_at = now()
                WHERE id = :plugin_id
                """
            ),
            {
                "plugin_id": plugin_id,
                "input_ports": json.dumps(input_ports),
                "output_ports": json.dumps(output_ports),
            },
        )
        print(f"0017: {plugin_key} -> {len(input_ports)} input, {len(output_ports)} output port(s)")


def downgrade() -> None:
    # Derived ports are a repair of 0016's hand-written values; reverting would restore
    # names that disagree with each plugin's own declaration.
    pass
