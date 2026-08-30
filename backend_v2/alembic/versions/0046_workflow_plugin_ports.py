"""Align workflow bindings with the plugin ports their commands actually consume.

Revision ID: 0046_workflow_plugin_ports
Revises: 0045_foldseek_threads
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "0046_workflow_plugin_ports"
down_revision: str | None = "0045_foldseek_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROTEINMPNN_COMMAND = r"""\
fixed_positions_staged="$(find "$BDA_INPUT_DIR/fixed_positions" -type f \( -name '*.jsonl' -o -name '*.json' \) 2>/dev/null | sort | head -1)"
if [ -n "${requires_fixed_positions:-}" ] && [ -z "$fixed_positions_staged" ]; then
  echo "ProteinMPNN: requires_fixed_positions is true but no position map was staged" >&2
  exit 64
fi
if [ -n "$fixed_positions_staged" ]; then fixed_positions_jsonl="$fixed_positions_staged"; fi

staged_pdb_count="$(find "$BDA_INPUT_DIR/pdb_path" -type f -name '*.pdb' 2>/dev/null | wc -l | tr -d ' ')"
staged_jsonl="$(find "$BDA_INPUT_DIR/jsonl_path" -type f -name '*.jsonl' 2>/dev/null | sort | head -1)"
if [ "${staged_pdb_count:-0}" -gt 0 ]; then
  parsed_jsonl="$BDA_OUTPUT_DIR/parsed_pdbs.jsonl"
  python /work/bme-liz/software/proteinmpnn-main/helper_scripts/parse_multiple_chains.py \
    --input_path="$BDA_INPUT_DIR/pdb_path" --output_path="$parsed_jsonl"
elif [ -n "$staged_jsonl" ]; then
  parsed_jsonl="$staged_jsonl"
else
  echo "ProteinMPNN: bind pdb_path or jsonl_path" >&2
  exit 64
fi

python /work/bme-liz/software/proteinmpnn-main/helper_scripts/assign_fixed_chains.py \
  --input_path="$parsed_jsonl" \
  --output_path="$BDA_OUTPUT_DIR/assigned_pdbs.jsonl" \
  --chain_list "${pdb_path_chains:-A}"
python /work/bme-liz/software/proteinmpnn-main/protein_mpnn_run.py \
  --jsonl_path "$parsed_jsonl" \
  --chain_id_jsonl "$BDA_OUTPUT_DIR/assigned_pdbs.jsonl" \
  --out_folder "$BDA_OUTPUT_DIR" \
  --num_seq_per_target "${num_seq_per_target:-5}" \
  --sampling_temp "${sampling_temp:-0.2}" \
  --batch_size "${batch_size:-1}" \
  --seed "${seed:-37}" \
  ${model_name:+--model_name "$model_name"} \
  ${omit_aas:+--omit_AAs "$omit_aas"} \
  ${fixed_positions_jsonl:+--fixed_positions_jsonl "$fixed_positions_jsonl"} \
  ${tied_positions_jsonl:+--tied_positions_jsonl "$tied_positions_jsonl"} \
  ${backbone_noise:+--backbone_noise "$backbone_noise"} \
  ${use_soluble_model:+--use_soluble_model} \
  ${ca_only:+--ca_only}"""


ROSETTA_COMMAND = r"""\
find "$BDA_INPUT_DIR/s" -type f \( -iname '*.pdb' -o -iname '*.cif' -o -iname '*.mmcif' \) 2>/dev/null \
  | sort > "$BDA_OUTPUT_DIR/inputs.list"
if [ ! -s "$BDA_OUTPUT_DIR/inputs.list" ]; then
  echo "Rosetta: required input port s contains no PDB/mmCIF structures" >&2
  exit 64
fi
rosetta_bin="/work/bme-liz/software/rosetta/source/bin/${application:-score_jd2}.default.linuxgccrelease"
"$rosetta_bin" \
  -in:file:l "$BDA_OUTPUT_DIR/inputs.list" \
  -out:path:all "$BDA_OUTPUT_DIR" \
  -out:file:scorefile "$BDA_OUTPUT_DIR/${out_scorefile:-score.sc}" \
  -nstruct "${nstruct:-1}" \
  ${score_weights:+-score:weights "$score_weights"} \
  ${parser_protocol:+-parser:protocol "$parser_protocol"} \
  ${parser_script_vars:+-parser:script_vars $parser_script_vars} \
  ${resfile:+-resfile "$resfile"} \
  ${cst_fa_file:+-constraints:cst_fa_file "$cst_fa_file"} \
  ${out_suffix:+-out:suffix "$out_suffix"} \
  ${ex1:+-ex1} ${ex2:+-ex2} ${constant_seed:+-constant_seed} \
  ${jran:+-jran "$jran"} \
  -ignore_unrecognized_res"""


SUPERFOLD_COMMAND = r"""\
superfold_inputs=()
while IFS= read -r -d '' superfold_input; do
  superfold_inputs+=("$superfold_input")
done < <(find "$BDA_INPUT_DIR/structures" "$BDA_INPUT_DIR/sequences" \
  \( -name '*.pdb' -o -name '*.fa*' \) ! -name '._*' -print0 2>/dev/null)
if [ "${#superfold_inputs[@]}" -eq 0 ]; then
  echo "bda: no structures/sequences staged for superfold" >&2
  exit 2
fi
/work/bme-liz/software/superfold/superfold "${superfold_inputs[@]}" \
  --out_dir "$BDA_OUTPUT_DIR" \
  --mock_msa_depth "${mock_msa_depth:-1}" \
  --models "${models:-all}" \
  --nstruct "${nstruct:-1}" \
  --max_recycles "${max_recycles:-3}" \
  --recycle_tol "${recycle_tol:-0.0}" \
  --seed_start "${seed_start:-0}" \
  --num_ensemble "${num_ensemble:-1}" \
  ${initial_guess:+--initial_guess} \
  ${reference_pdb:+--reference_pdb "$reference_pdb"} \
  ${enable_dropout:+--enable_dropout} \
  ${output_pae:+--output_pae} \
  ${output_summary:+--output_summary} \
  ${overwrite:+--overwrite}"""


SUPERFOLD_INPUT_PORTS = [
    {
        "name": "structures",
        "kind": "protein_structure",
        "accepts": [
            "backbone_set",
            "candidate_structure",
            "predicted_structure",
            "complex_structure",
            "target_structure",
        ],
        "content_types": [],
        "required": True,
        "multiple": True,
        "description": "PDB designs to predict, required when initial_guess is enabled.",
        "exclusive_group": "superfold_input_source",
    },
    {
        "name": "sequences",
        "kind": "protein_sequence",
        "accepts": ["sequence_set", "sequence"],
        "content_types": ["text/x-fasta", "text/plain"],
        "required": True,
        "multiple": True,
        "description": "FASTA sequences to predict without a coordinate initial guess.",
        "exclusive_group": "superfold_input_source",
    },
]


PROTEINMPNN_PDB_PORT = {
    "name": "pdb_path",
    "kind": "protein_structure",
    "accepts": [
        "backbone_set",
        "candidate_complex",
        "candidate_structure",
        "complex_structure",
        "predicted_structure",
        "relaxed_structure",
        "structure",
        "target_structure",
    ],
    "content_types": ["chemical/x-pdb"],
    "required": True,
    "multiple": True,
    "description": "Staged PDB backbones. Alternatively bind a parsed ProteinMPNN JSONL file.",
    "exclusive_group": "backbone_source",
}


PROTEINMPNN_JSONL_PORT = {
    "name": "jsonl_path",
    "kind": "params",
    "accepts": ["parameter_file", "proteinmpnn_jsonl"],
    "content_types": ["application/x-ndjson", "application/json", "text/plain"],
    "required": True,
    "multiple": False,
    "description": "Parsed ProteinMPNN JSONL input. Alternatively bind staged PDB backbones.",
    "exclusive_group": "backbone_source",
}


PROTEINMPNN_FIXED_POSITIONS_PORT = {
    "name": "fixed_positions",
    "kind": "params",
    "accepts": ["parameter_file", "fixed_positions"],
    "content_types": ["application/json", "application/x-ndjson", "text/plain"],
    "required": False,
    "multiple": False,
    "description": "Immutable fixed-position map for constrained sequence design.",
}


ROSETTA_STRUCTURE_PORT = {
    "name": "s",
    "kind": "protein_structure",
    "accepts": [
        "backbone_set",
        "candidate_complex",
        "candidate_structure",
        "complex_structure",
        "predicted_structure",
        "relaxed_structure",
        "structure",
        "target_structure",
    ],
    "content_types": ["chemical/x-pdb", "chemical/x-mmcif"],
    "required": True,
    "multiple": True,
    "description": "PDB structures staged for Rosetta's -in:file input.",
}


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value if value is not None else fallback


def canonical_input_ports(plugin_key: str, value: Any) -> list[dict]:
    """Replace legacy primary ports without discarding version-specific options."""
    ports = _json_value(value, [])
    ports = ports if isinstance(ports, list) else []
    if plugin_key == "ProteinMPNN":
        legacy_names = {"backbone", "pdb_path", "jsonl_path"}
        retained = [item for item in ports if not (isinstance(item, dict) and item.get("name") in legacy_names)]
        if not any(isinstance(item, dict) and item.get("name") == "fixed_positions" for item in retained):
            retained.append(PROTEINMPNN_FIXED_POSITIONS_PORT)
        return [PROTEINMPNN_PDB_PORT, PROTEINMPNN_JSONL_PORT, *retained]
    if plugin_key == "Rosetta":
        legacy_names = {"complexes", "structure", "s"}
        retained = [item for item in ports if not (isinstance(item, dict) and item.get("name") in legacy_names)]
        return [ROSETTA_STRUCTURE_PORT, *retained]
    if plugin_key == "superfold":
        return SUPERFOLD_INPUT_PORTS
    return ports


def rewrite_bindings(plugin_key: str, value: Any) -> tuple[list[dict], bool]:
    """Return bindings using the canonical registry port for ``plugin_key``."""
    bindings = _json_value(value, [])
    if not isinstance(bindings, list):
        return [], False
    changed = False
    rewritten: list[dict] = []
    for raw in bindings:
        if not isinstance(raw, dict):
            rewritten.append(raw)
            continue
        item = dict(raw)
        port = item.get("port")
        if plugin_key == "ProteinMPNN" and port == "backbone":
            item["port"] = "pdb_path"
        elif plugin_key == "Rosetta" and port == "structure":
            item["port"] = "s"
        elif (
            plugin_key == "superfold"
            and port == "structures"
            and item.get("source") == "upstream"
            and item.get("from_port") == "sequences"
        ):
            item["port"] = "sequences"
        changed = changed or item != raw
        rewritten.append(item)
    return rewritten, changed


def rewrite_edge(plugin_key: str, value: dict) -> tuple[dict, bool]:
    """Return an explicitly ported graph edge using the canonical target port."""
    edge = dict(value)
    target_port = edge.get("target_port")
    if plugin_key == "ProteinMPNN" and target_port == "backbone":
        edge["target_port"] = "pdb_path"
    elif plugin_key == "Rosetta" and target_port == "structure":
        edge["target_port"] = "s"
    elif plugin_key == "superfold" and target_port == "structures" and edge.get("source_port") == "sequences":
        edge["target_port"] = "sequences"
    return edge, edge != value


def _update_plugin(plugin_key: str, command: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, input_ports FROM model_plugins WHERE plugin_key = :plugin_key"),
        {"plugin_key": plugin_key},
    ).fetchall()
    assignments = [
        "command = :command",
        "input_ports = CAST(:input_ports AS json)",
        "validation_status = 'unknown'",
        "validated_at = NULL",
        "validation_errors = CAST(:validation_errors AS json)",
        "runtime_validation_status = 'unproven'",
        "runtime_validated_at = NULL",
        "runtime_validation_evidence = CAST(:runtime_evidence AS json)",
        "version = version + 1",
        "updated_at = now()",
    ]
    for row in rows:
        params: dict[str, Any] = {
            "plugin_id": row.id,
            "command": command,
            "input_ports": json.dumps(canonical_input_ports(plugin_key, row.input_ports)),
            "validation_errors": "[]",
            "runtime_evidence": "{}",
        }
        bind.execute(
            sa.text(f"UPDATE model_plugins SET {', '.join(assignments)} WHERE id = :plugin_id"),
            params,
        )


def _rewrite_workflow_nodes() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, workflow_run_id, node_key, model_plugin, input_bindings "
            "FROM workflow_nodes WHERE model_plugin IN ('ProteinMPNN', 'Rosetta', 'superfold')"
        )
    ).fetchall()
    bindings_by_workflow: dict[Any, dict[str, list[dict]]] = {}
    plugins_by_workflow: dict[Any, dict[str, str]] = {}
    for row in rows:
        plugin_key = str(row.model_plugin)
        node_key = str(row.node_key)
        bindings, changed = rewrite_bindings(plugin_key, row.input_bindings)
        bindings_by_workflow.setdefault(row.workflow_run_id, {})[node_key] = bindings
        plugins_by_workflow.setdefault(row.workflow_run_id, {})[node_key] = plugin_key
        if changed:
            bind.execute(
                sa.text(
                    "UPDATE workflow_nodes SET input_bindings = CAST(:bindings AS json), "
                    "version = version + 1, updated_at = now() WHERE id = :id"
                ),
                {"id": row.id, "bindings": json.dumps(bindings)},
            )

    # The graph is a denormalized workflow snapshot. Refresh it independently of whether
    # the row needed rewriting: a partially repaired database can have a canonical node
    # row and a stale embedded binding. Explicitly ported edges must move too, otherwise
    # preflight still sees the old target port after the node binding has been corrected.
    for workflow_id, node_bindings in bindings_by_workflow.items():
        row = bind.execute(sa.text("SELECT graph FROM workflow_runs WHERE id = :id"), {"id": workflow_id}).fetchone()
        if row is None:
            continue
        graph = _json_value(row.graph, {})
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
            continue
        rewritten_graph = dict(graph)
        rewritten_graph["nodes"] = [
            {**item, "input_bindings": node_bindings[str(item.get("key"))]}
            if isinstance(item, dict) and str(item.get("key")) in node_bindings
            else item
            for item in graph["nodes"]
        ]
        edges = graph.get("edges")
        if isinstance(edges, list):
            rewritten_graph["edges"] = [
                rewrite_edge(
                    plugins_by_workflow[workflow_id].get(str(edge.get("target")), ""),
                    edge,
                )[0]
                if isinstance(edge, dict)
                else edge
                for edge in edges
            ]
        if rewritten_graph == graph:
            continue
        bind.execute(
            sa.text(
                "UPDATE workflow_runs SET graph = CAST(:graph AS json), version = version + 1, "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": workflow_id, "graph": json.dumps(rewritten_graph)},
        )


def upgrade() -> None:
    _update_plugin("ProteinMPNN", PROTEINMPNN_COMMAND)
    _update_plugin("Rosetta", ROSETTA_COMMAND)
    _update_plugin("superfold", SUPERFOLD_COMMAND)
    _rewrite_workflow_nodes()


def downgrade() -> None:
    # Restoring commands that look in directories no declared port stages would make
    # these plugins silently unrunnable. Keep the corrected contract on downgrade.
    pass
