"""Register ProteinHunter (Boltz) as a registry plugin.

The model is installed on qm under another group's account. Everything the platform needs
to run it — entrypoint, conda environment, dependency directory, parameters, I/O ports,
resources — is declared here as data, so onboarding it required no model-specific Python.

Deliberately expressed through the generic seams:

* ``runtime_mode="conda"`` with ``runtime_setup`` sourcing the profile by absolute path,
  because that conda installation is not on PATH for our account.
* ``output_parser="proteinhunter_boltz"`` reads the run summary CSV into candidates.
* ``resources`` drives the #BSUB directives rather than a hand-written script.

The shared installation and the reference production directory are never written to: jobs
run under the configured BDA job root, and collection refuses paths outside it.

Revision ID: 0020_register_proteinhunter
Revises: 0020_plugin_runtime_setup
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_register_proteinhunter"
down_revision: str | None = "0020_plugin_runtime_setup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLUGIN_KEY = "proteinhunter_boltz"
# Upstream commit plus the qm production fingerprint it was verified against.
PLUGIN_VERSION = "d4bd951-qm-c18-20260416"

ENTRYPOINT = "/work/bme-liz/software/Protein-Hunter/Protein-Hunter/boltz_ph/design.py"
CONDA_PROFILE = "/work/bme-liz/miniconda3/etc/profile.d/conda.sh"
CONDA_ENV = "/work/bme-liz/miniconda3/envs/proteinhunter"
LIGAND_MPNN = "/work/bme-liz/software/LigandMPNN"
# design.py defaults the Boltz checkpoint and the CCD component library to ``~/.boltz``,
# which only exists under the account that installed the model. Any other account then
# fails at startup with "CCD component ALA not found". Pointing both at the shared
# install is what makes the plugin runnable by whoever the worker authenticates as.
BOLTZ_CACHE = "/work/bme-liz/.boltz"

# Boltz writes everything under --save_dir. Pointing it at the port directory is what
# lets collection type the outputs without the wrapper declaring anything.
# Verified against `design.py --help` on qm. Parameters are exported as shell variables
# by the renderer, so optional ones use ${var:+...}: an empty value drops the flag
# entirely rather than passing "" to a model that would reject it.
COMMAND = (
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
    ' --save_dir "$BDA_OUTPUT_DIR"'
)

PARAMETER_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
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
    },
    "required": ["mode", "num_designs", "num_cycles"],
    # A ligand target is given one way or the other, never both.
    "not": {"required": ["ligand_smiles", "ligand_ccd"], "properties": {
        "ligand_smiles": {"minLength": 1}, "ligand_ccd": {"minLength": 1},
    }},
}

INPUT_PORTS = [
    {
        "name": "target_structure",
        "kind": "protein_structure",
        "accepts": ["target_structure", "backbone_set", "predicted_structure", "complex_structure"],
        "content_types": [],
        "required": False,
        "multiple": False,
        "description": "Optional target structure. Sequence targets are given via the protein_seqs parameter.",
    }
]

# Named after the directories ProteinHunter actually writes under --save_dir, because
# collection types an output by the port directory it lands in. The summaries sit at the
# root, so they are typed by filename_glob instead.
OUTPUT_PORTS = [
    # Named for the directory the model writes, because collection types a file by its
    # top-level directory before falling back to filename globs. Without this port the
    # per-cycle intermediates below would fall through to the `*.pdb` glob and be
    # promoted to high-confidence candidates - 11k of them on a production-size run.
    # `opaque` keeps them off downstream structure ports: this is the working trajectory,
    # not something to feed forward. Retained because it is what a scientist reads when
    # asking why a design failed to converge.
    {
        "name": "0_protein_hunter_design",
        "kind": "opaque",
        "artifact_type": "design_trajectory",
        "description": "Per-run trajectory: every cycle's predicted structure and the convergence plot.",
    },
    {
        "name": "high_iptm_pdb",
        "kind": "protein_structure",
        "artifact_type": "candidate_complex",
        "filename_glob": "*.pdb",
        "description": "High-confidence ProteinHunter complex structures.",
    },
    {
        "name": "high_iptm_yaml",
        "kind": "params",
        "artifact_type": "design_spec",
        "filename_glob": "*.yaml",
        "description": "Boltz specifications paired with the high-confidence complexes.",
    },
    {
        "name": "summaries",
        "kind": "tabular",
        "artifact_type": "score_table",
        "filename_glob": "summary_*.csv",
        "description": "All-run and high-confidence summaries; the latter promotes candidates.",
    },
]

DEFINITION = {
    "plugin_key": PLUGIN_KEY,
    "plugin_version": PLUGIN_VERSION,
    "name": "ProteinHunter (Boltz)",
    # runtime_mode is conda, so this names the environment prefix rather than an image.
    "container_image": CONDA_ENV,
    "command": COMMAND,
    "runtime_mode": "conda",
    "runtime_setup": [
        f"source {CONDA_PROFILE}",
        f"conda activate {CONDA_ENV}",
        f"export LIGAND_MPNN_DIR={LIGAND_MPNN}",
    ],
    "parameter_schema": PARAMETER_SCHEMA,
    "output_schema": {},
    "input_ports": INPUT_PORTS,
    "output_ports": OUTPUT_PORTS,
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 1, "walltime_minutes": 1440},
    "output_parser": "proteinhunter_boltz",
    "enabled": True,
}


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM model_plugins WHERE plugin_key = :key AND plugin_version = :version"),
        {"key": PLUGIN_KEY, "version": PLUGIN_VERSION},
    ).fetchone()
    if existing is not None:
        print(f"0020: {PLUGIN_KEY} {PLUGIN_VERSION} already registered")
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO model_plugins (
                id, plugin_key, plugin_version, name, container_image, command,
                parameter_schema, output_schema, input_ports, output_ports, resources,
                runtime_mode, runtime_setup, output_parser, enabled,
                validation_status, validation_errors, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), :plugin_key, :plugin_version, :name, :container_image, :command,
                CAST(:parameter_schema AS json), CAST(:output_schema AS json),
                CAST(:input_ports AS json), CAST(:output_ports AS json), CAST(:resources AS json),
                :runtime_mode, CAST(:runtime_setup AS json), :output_parser, true,
                'unknown', '[]'::json, 1, now(), now()
            )
            """
        ),
        {
            **{
                key: DEFINITION[key]
                for key in ("plugin_key", "plugin_version", "name", "container_image", "command",
                            "runtime_mode", "output_parser")
            },
            "parameter_schema": json.dumps(DEFINITION["parameter_schema"]),
            "output_schema": json.dumps(DEFINITION["output_schema"]),
            "input_ports": json.dumps(DEFINITION["input_ports"]),
            "output_ports": json.dumps(DEFINITION["output_ports"]),
            "resources": json.dumps(DEFINITION["resources"]),
            "runtime_setup": json.dumps(DEFINITION["runtime_setup"]),
        },
    )
    print(f"0020: registered {PLUGIN_KEY} {PLUGIN_VERSION}")


def downgrade() -> None:
    # workflow_nodes.model_plugin_id has no ON DELETE clause, so the delete
    # below is refused while any node still points at this plugin. The column
    # is nullable precisely so a node can name a plugin by key without one
    # being registered, which is the state a downgrade returns it to.
    op.execute(
        sa.text(
            "UPDATE workflow_nodes SET model_plugin_id = NULL WHERE model_plugin_id IN ("
            " SELECT id FROM model_plugins WHERE plugin_key = :key AND plugin_version = :version)"
        ).bindparams(key=PLUGIN_KEY, version=PLUGIN_VERSION)
    )
    op.execute(
        sa.text("DELETE FROM model_plugins WHERE plugin_key = :key AND plugin_version = :version").bindparams(
            key=PLUGIN_KEY, version=PLUGIN_VERSION
        )
    )
