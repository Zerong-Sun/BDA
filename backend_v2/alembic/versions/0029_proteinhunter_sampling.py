"""Expose ProteinHunter's remaining sampling knobs and encode its documented rules.

0021 made the plugin runnable and passes every target argument. Two gaps remain.

PROTEINHUNTER_BOLTZ.md tells users they can adjust the initial X fraction, the excluded
amino acids and the alanine bias, but the schema never declared them, so the model always
ran at its own defaults. They are declared here with upstream's defaults, so leaving a
field alone reproduces `design.py`'s behaviour. The variable names are lowercase because
the renderer only exports lowercase names - keeping parameters clear of PATH, HOME and
LD_* - while the flags design.py expects keep their upstream spelling (`--percent_X`,
`--omit_AA`).

The same document states four validation rules; 0021 encoded only the ligand exclusion.
A binder run with no target passed preflight and would have spent a GPU day designing
against nothing, so the remaining rules are expressed as schema and enforced by preflight
and submission alike. The one rule JSON Schema cannot state -
`min_protein_length <= max_protein_length` - has no cross-field arithmetic and is left to
the model.

Also carries the UI hints the workflow parameter form reads: a target sequence or SMILES
gets a multi-line control, and knobs that are rarely touched fold into the advanced
section. They are additive annotations; a client that ignores them sees the schema
unchanged.

The model installation on qm is untouched: same entrypoint, same environment, same
weights. Only the arguments BDA hands it change, which the version suffix records.

Revision ID: 0029_proteinhunter_sampling
Revises: 0028_superfold_af3_real_runs
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_proteinhunter_sampling"
down_revision: str | None = "0028_superfold_af3_real_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLUGIN_KEY = "proteinhunter_boltz"
PREVIOUS_VERSION = "d4bd951-qm-c18-20260416"
# Same model install, a wider set of arguments handed to it; the suffix records which.
PLUGIN_VERSION = "d4bd951-qm-c18-20260416-sampling"

ENTRYPOINT = "/work/bme-liz/software/Protein-Hunter/Protein-Hunter/boltz_ph/design.py"
BOLTZ_CACHE = "/work/bme-liz/.boltz"

_BASE_COMMAND = (
    f'python {ENTRYPOINT} --gpu_id 0 --name "$BDA_JOB_NAME"'
    f' --boltz_model_path {BOLTZ_CACHE}/boltz2_conf.ckpt'
    f' --ccd_path {BOLTZ_CACHE}/mols'
    ' --mode "$mode"'
    ' --num_designs "$num_designs"'
    ' --num_cycles "$num_cycles"'
    ' --min_protein_length "$min_protein_length"'
    ' --max_protein_length "$max_protein_length"'
    ' --temperature "$temperature"'
    ' --diffuse_steps "$diffuse_steps"'
    ' --recycling_steps "$recycling_steps"'
    ' --high_iptm_threshold "$high_iptm_threshold"'
    ' --high_plddt_threshold "$high_plddt_threshold"'
    ' ${protein_seqs:+--protein_seqs "$protein_seqs"}'
    ' ${msa_mode:+--msa_mode "$msa_mode"}'
    ' ${ligand_smiles:+--ligand_smiles "$ligand_smiles"}'
    ' ${ligand_ccd:+--ligand_ccd "$ligand_ccd"}'
    ' ${nucleic_seq:+--nucleic_type "$nucleic_type" --nucleic_seq "$nucleic_seq"}'
    ' ${seq:+--seq "$seq"}'
    ' ${contact_residues:+--contact_residues "$contact_residues"}'
    ' ${cyclic:+--cyclic}'
)

PREVIOUS_COMMAND = _BASE_COMMAND + ' --save_dir "$BDA_OUTPUT_DIR"'

# The CLI keeps upstream's capitalised flags; the shell variables stay lowercase because
# that is what the renderer exports.
COMMAND = (
    _BASE_COMMAND
    + ' ${percent_x:+--percent_X "$percent_x"}'
    + ' ${omit_aa:+--omit_AA "$omit_aa"}'
    + " ${alanine_bias:+--alanine_bias}"
    + ' --save_dir "$BDA_OUTPUT_DIR"'
)

_BASE_PROPERTIES = {
    "mode": {
        "type": "string",
        "enum": ["binder", "unconditional"],
        "default": "binder",
        "description": "Design chain A against supplied targets, or generate an unconditional protein.",
    },
    "protein_seqs": {
        "type": "string",
        "default": "",
        "description": "Target sequences. Separate chains with ':'; ProteinHunter assigns B, C, ….",
    },
    "msa_mode": {
        "type": "string",
        "enum": ["single", "mmseqs"],
        "default": "single",
        "description": "Empty/single-sequence MSA, or request MMseqs target MSAs.",
    },
    "ligand_smiles": {"type": "string", "default": "", "description": "SMILES target."},
    "ligand_ccd": {"type": "string", "default": "", "description": "PDB CCD code target."},
    "nucleic_type": {"type": "string", "enum": ["dna", "rna"], "default": "dna"},
    "nucleic_seq": {"type": "string", "default": "", "description": "DNA/RNA target sequence."},
    "num_designs": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 3},
    "num_cycles": {"type": "integer", "minimum": 1, "maximum": 100, "default": 3},
    "min_protein_length": {"type": "integer", "minimum": 4, "maximum": 2000, "default": 60},
    "max_protein_length": {"type": "integer", "minimum": 4, "maximum": 2000, "default": 120},
    "seq": {"type": "string", "default": "", "description": "Fixed starting sequence."},
    "cyclic": {"type": "boolean", "default": False},
    "temperature": {"type": "number", "minimum": 0.0, "maximum": 10.0, "default": 1.0},
    "diffuse_steps": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
    "recycling_steps": {"type": "integer", "minimum": 0, "maximum": 20, "default": 3},
    "contact_residues": {"type": "string", "default": "", "description": "Residues to bias contacts toward."},
    "high_iptm_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.8},
    "high_plddt_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.8},
}

LIGANDS_ARE_EXCLUSIVE = {
    "required": ["ligand_smiles", "ligand_ccd"],
    "properties": {"ligand_smiles": {"minLength": 1}, "ligand_ccd": {"minLength": 1}},
}

PREVIOUS_PARAMETER_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": _BASE_PROPERTIES,
    "required": ["mode", "num_designs", "num_cycles"],
    "not": LIGANDS_ARE_EXCLUSIVE,
}

# Control hints for the workflow parameter form. A JSON Schema type cannot say "this
# string is 300 residues long" or "this knob is rarely touched".
UI_HINTS = {
    "protein_seqs": {"x-bda-field-type": "textarea"},
    "ligand_smiles": {"x-bda-field-type": "textarea"},
    "nucleic_seq": {"x-bda-field-type": "textarea"},
    "contact_residues": {"x-bda-field-type": "textarea"},
    "seq": {"x-bda-field-type": "textarea", "x-bda-advanced": True},
    "cyclic": {"x-bda-advanced": True},
    "diffuse_steps": {"x-bda-advanced": True},
    "recycling_steps": {"x-bda-advanced": True},
}

ADDED_PROPERTIES = {
    "percent_x": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 90,
        "description": (
            "Share of the starting binder sequence left as X, passed as --percent_X. Lower "
            "values mix in random amino acids and diversify folds; too low yields "
            "disconnected structures."
        ),
    },
    "omit_aa": {
        "type": "string",
        "default": "C",
        "description": (
            "Amino acids LigandMPNN may not sample, passed as --omit_AA. Upstream excludes "
            "cysteine."
        ),
        "x-bda-advanced": True,
    },
    "alanine_bias": {
        "type": "boolean",
        "default": False,
        "description": (
            "Discourage alanine during redesign. Designs above 20% alanine are dropped from "
            "the high-confidence set regardless."
        ),
        "x-bda-advanced": True,
    },
}


def _with_hints(properties: dict) -> dict:
    return {key: {**definition, **UI_HINTS.get(key, {})} for key, definition in properties.items()}


PARAMETER_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {**_with_hints(_BASE_PROPERTIES), **ADDED_PROPERTIES},
    "required": ["mode", "num_designs", "num_cycles"],
    # A ligand target is given one way or the other, never both.
    "not": LIGANDS_ARE_EXCLUSIVE,
    "allOf": [
        {
            "if": {"properties": {"mode": {"const": "binder"}}, "required": ["mode"]},
            "then": {
                "anyOf": [
                    {"properties": {"protein_seqs": {"minLength": 1}}, "required": ["protein_seqs"]},
                    {"properties": {"ligand_smiles": {"minLength": 1}}, "required": ["ligand_smiles"]},
                    {"properties": {"ligand_ccd": {"minLength": 1}}, "required": ["ligand_ccd"]},
                    {"properties": {"nucleic_seq": {"minLength": 1}}, "required": ["nucleic_seq"]},
                ]
            },
        },
        {
            "if": {"properties": {"mode": {"const": "unconditional"}}, "required": ["mode"]},
            "then": {
                "properties": {
                    "protein_seqs": {"maxLength": 0},
                    "ligand_smiles": {"maxLength": 0},
                    "ligand_ccd": {"maxLength": 0},
                    "nucleic_seq": {"maxLength": 0},
                }
            },
        },
        {
            # Upstream only checks binder-to-target contacts for protein chains.
            "if": {"properties": {"contact_residues": {"minLength": 1}}, "required": ["contact_residues"]},
            "then": {"properties": {"protein_seqs": {"minLength": 1}}, "required": ["protein_seqs"]},
        },
    ],
}


def _apply(version: str, command: str, parameter_schema: dict) -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET plugin_version = :version,
                command = :command,
                parameter_schema = CAST(:parameter_schema AS json),
                version = version + 1,
                validation_status = 'unknown',
                updated_at = now()
            WHERE plugin_key = :key
            """
        ),
        {
            "key": PLUGIN_KEY,
            "version": version,
            "command": command,
            "parameter_schema": json.dumps(parameter_schema),
        },
    )
    print(f"0029: updated {result.rowcount} {PLUGIN_KEY} row(s) to {version}")


def upgrade() -> None:
    _apply(PLUGIN_VERSION, COMMAND, PARAMETER_SCHEMA)


def downgrade() -> None:
    _apply(PREVIOUS_VERSION, PREVIOUS_COMMAND, PREVIOUS_PARAMETER_SCHEMA)
