"""Register the de novo binder design models as registry plugins.

The Workflow route planner proposes RFdiffusion, ProteinMPNN, AlphaFold2, Rosetta and
BindCraft (``copilot/route_catalog.py``), but only ProteinHunter was ever registered, so
every proposed route came back with no modules. This registers the five so a route can
be created, previewed and preflighted.

**Runtime placeholders.** ``container_image`` and the paths inside ``command`` are
deliberate placeholders (``PLACEHOLDER_PREFIX`` below) because this repository has no
site installation for these models — unlike ProteinHunter in 0021, which was written
against a verified qm install. What is *not* placeholder is the part the platform
reasons about: parameter schemas, ports, resources. Those are complete, so parameter
validation, edge type-checking and script preview are all real before a site swaps in
its own image. ``validation_status`` stays ``unknown``, which makes preflight emit
``plugin_unvalidated`` until an operator runs registry validation against their install.

Parameter names are lowercase snake_case on purpose: ``compute/scripts.py`` only exports
parameters matching ``^[a-z][a-z0-9_]*$`` as shell variables, so a Hydra-style
``denoiser.noise_scale_ca`` would be silently dropped from the rendered command. The
commands below therefore pass Hydra arguments built from safe variable names.

Revision ID: 0033_register_design_plugins
Revises: 0032_ligand_targets
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033_register_design_plugins"
down_revision: str | None = "0032_ligand_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Greppable marker for everything a site must replace before these plugins can run.
PLACEHOLDER_PREFIX = "bda-placeholder"

STRUCTURE_ACCEPTS = ["target_structure", "prepared_structure", "predicted_structure", "backbone_set"]
STRUCTURE_CONTENT_TYPES = ["chemical/x-pdb", "chemical/x-mmcif"]

RFDIFFUSION = {
    "plugin_key": "RFdiffusion",
    "plugin_version": "1.1.0",
    "name": "RFdiffusion",
    "container_image": f"{PLACEHOLDER_PREFIX}/rfdiffusion:unset",
    "command": (
        "python run_inference.py"
        ' inference.output_prefix="$BDA_OUTPUT_DIR/$output_prefix"'
        ' inference.input_pdb="$BDA_INPUT_DIR/target.pdb"'
        " inference.num_designs=\"$num_designs\""
        " diffuser.T=\"$diffuser_t\""
        " denoiser.noise_scale_ca=\"$noise_scale_ca\""
        " denoiser.noise_scale_frame=\"$noise_scale_frame\""
        " 'contigmap.contigs=[$contigs]'"
        " ${hotspot_res:+'ppi.hotspot_res=[$hotspot_res]'}"
        " ${partial_t:+diffuser.partial_T=\"$partial_t\"}"
        " ${ckpt_override_path:+inference.ckpt_override_path=\"$ckpt_override_path\"}"
    ),
    "parameter_schema": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "contigs": {
                "type": "string",
                "default": "A20-330/0 60-80",
                "description": "Hydra contig expression. The trailing range is the binder length window.",
            },
            "hotspot_res": {
                "type": "string",
                "default": "",
                "description": "Comma-separated hotspot residues, e.g. A164,A168,A171. 2-6 residues on one face.",
            },
            "num_designs": {"type": "integer", "minimum": 1, "maximum": 200000, "default": 10000},
            "binder_length": {
                "type": "integer",
                "minimum": 40,
                "maximum": 150,
                "default": 70,
                "description": "Target binder length; 60-75 keeps a design inside one oligo-pool member.",
            },
            "diffuser_t": {
                "type": "integer",
                "minimum": 10,
                "maximum": 200,
                "default": 50,
                "description": "Denoising steps. 50 is the binder-design standard; 200 is the upstream default.",
            },
            "partial_t": {
                "type": "integer",
                "minimum": 0,
                "maximum": 50,
                "default": 0,
                "description": "Partial diffusion depth for affinity maturation. 0 disables it; 5-20 diversifies a hit.",
            },
            "noise_scale_ca": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0,
                "description": "Zeroed noise lowers diversity but raises experimental success on interface design.",
            },
            "noise_scale_frame": {"type": "number", "minimum": 0, "maximum": 1, "default": 0},
            "ckpt_override_path": {
                "type": "string",
                "default": "",
                "description": "Optional checkpoint, e.g. Complex_beta for more diverse topologies on flat epitopes.",
            },
            "output_prefix": {"type": "string", "default": "design"},
        },
        "required": ["contigs", "num_designs", "diffuser_t", "noise_scale_ca", "noise_scale_frame"],
    },
    "input_ports": [
        {
            "name": "target_structure",
            "kind": "protein_structure",
            "accepts": STRUCTURE_ACCEPTS,
            "content_types": STRUCTURE_CONTENT_TYPES,
            "required": True,
            "multiple": False,
            "description": "Prepared target. Trim the fusion partners but keep the transmembrane bundle.",
        }
    ],
    "output_ports": [
        {
            "name": "backbones",
            "kind": "protein_structure",
            "artifact_type": "backbone_set",
            "filename_glob": "*.pdb",
            "description": "Generated binder backbones.",
        }
    ],
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 4, "memory_gb": 32, "walltime_minutes": 1440},
}

PROTEINMPNN = {
    "plugin_key": "ProteinMPNN",
    "plugin_version": "1.0.1",
    "name": "ProteinMPNN",
    "container_image": f"{PLACEHOLDER_PREFIX}/proteinmpnn:unset",
    "command": (
        "python dl_interface_design.py"
        ' -pdbdir "$BDA_INPUT_DIR" -outpdbdir "$BDA_OUTPUT_DIR"'
        ' -relax_cycles "$relax_cycles"'
        ' -seqs_per_struct "$seqs_per_struct"'
        ' -temperature "$sampling_temp"'
        " ${use_soluble_model:+-use_soluble_model}"
    ),
    "parameter_schema": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "sampling_temp": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.0001,
                "description": "Near-argmax for binder design; 0.1-0.2 only to build display-library diversity.",
            },
            "seqs_per_struct": {
                "type": "integer",
                "minimum": 1,
                "maximum": 64,
                "default": 8,
                "description": "8 is the cost/benefit point; 32 quadruples downstream folding cost.",
            },
            "use_soluble_model": {
                "type": "boolean",
                "default": True,
                "description": "Soluble weights. The default weights place hydrophobics on the binder surface.",
            },
            "relax_cycles": {"type": "integer", "minimum": 0, "maximum": 10, "default": 0},
            "fixed_positions": {
                "type": "string",
                "default": "",
                "description": "Positions to hold, used when grafting a motif. Empty designs the whole binder.",
            },
        },
        "required": ["sampling_temp", "seqs_per_struct"],
    },
    "input_ports": [
        {
            "name": "backbone",
            "kind": "protein_structure",
            "accepts": ["backbone_set", "target_structure", "predicted_structure"],
            "content_types": STRUCTURE_CONTENT_TYPES,
            "required": True,
            "multiple": True,
            "description": "Backbones to design sequences onto. The target chain is held fixed.",
        }
    ],
    "output_ports": [
        {
            "name": "sequences",
            "kind": "protein_sequence",
            "artifact_type": "sequence_set",
            "filename_glob": "*.fa",
            "description": "Designed binder sequences.",
        }
    ],
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 4, "memory_gb": 16, "walltime_minutes": 240},
}

ALPHAFOLD2 = {
    "plugin_key": "AlphaFold2",
    "plugin_version": "2.3.2",
    "name": "AlphaFold2 (initial guess)",
    "container_image": f"{PLACEHOLDER_PREFIX}/alphafold2-initial-guess:unset",
    "command": (
        "python predict.py"
        ' -indir "$BDA_INPUT_DIR" -outdir "$BDA_OUTPUT_DIR"'
        ' -recycles "$recycles" -models "$models" -db_preset "$db_preset"'
        " ${initial_guess:+-initial_guess}"
    ),
    "parameter_schema": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "initial_guess": {
                "type": "boolean",
                "default": True,
                "description": "Initial-guess mode. pae_interaction, the best-calibrated binder filter, comes from this.",
            },
            "recycles": {"type": "integer", "minimum": 0, "maximum": 20, "default": 3},
            "models": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1},
            "db_preset": {
                "type": "string",
                "enum": ["reduced_dbs", "full_dbs"],
                "default": "reduced_dbs",
            },
            "ensemble_predictions": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 1,
                "description": "Seeds per input. Raise to 20+ when building a target ensemble rather than scoring designs.",
            },
        },
        "required": ["recycles", "models", "db_preset"],
    },
    "input_ports": [
        {
            "name": "complex_input",
            "kind": "protein_structure",
            "accepts": ["backbone_set", "target_structure", "sequence_set", "prepared_structure"],
            "content_types": STRUCTURE_CONTENT_TYPES,
            "required": True,
            "multiple": True,
            "description": "Designed complexes to score, or a target to predict.",
        }
    ],
    "output_ports": [
        {
            "name": "predictions",
            "kind": "protein_structure",
            "artifact_type": "predicted_structure",
            "filename_glob": "*.pdb",
            "description": "Predicted complexes.",
        },
        {
            "name": "scores",
            "kind": "tabular",
            "artifact_type": "score_table",
            "filename_glob": "*.sc",
            "description": "Per-design pae_interaction, binder pLDDT, and RMSD to the design model.",
        },
    ],
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 8, "memory_gb": 64, "walltime_minutes": 1440},
}

ROSETTA = {
    "plugin_key": "Rosetta",
    "plugin_version": "2026.06",
    "name": "Rosetta InterfaceAnalyzer",
    "container_image": f"{PLACEHOLDER_PREFIX}/rosetta:unset",
    "command": (
        "rosetta_scripts.default.linuxgccrelease"
        ' -in:file:s "$BDA_INPUT_DIR"/*.pdb'
        ' -out:path:all "$BDA_OUTPUT_DIR"'
        ' -parser:protocol "$protocol".xml'
        ' -score:weights "$score_function"'
        ' -relax:default_repeats "$relax_repeats"'
    ),
    "parameter_schema": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "protocol": {
                "type": "string",
                "enum": ["interface_analyzer", "fast_relax", "relax_then_analyze"],
                "default": "interface_analyzer",
            },
            "score_function": {
                "type": "string",
                "enum": ["ref2015", "beta_nov16"],
                "default": "beta_nov16",
                "description": "REU values shift between functions; the ddG thresholds assume one is pinned.",
            },
            "relax_repeats": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            "compute_sap": {
                "type": "boolean",
                "default": True,
                "description": "Spatial aggregation propensity. A developability metric, not an affinity one.",
            },
        },
        "required": ["protocol", "score_function"],
    },
    "input_ports": [
        {
            "name": "complexes",
            "kind": "protein_structure",
            "accepts": ["predicted_structure", "backbone_set", "candidate_complex"],
            "content_types": STRUCTURE_CONTENT_TYPES,
            "required": True,
            "multiple": True,
            "description": "Complexes to score.",
        }
    ],
    "output_ports": [
        {
            "name": "scores",
            "kind": "tabular",
            "artifact_type": "score_table",
            "filename_glob": "*.sc",
            "description": "ddG, contact molecular surface, shape complementarity, SAP, unsatisfied buried polars.",
        }
    ],
    "resources": {"gpu": False, "cpus": 16, "memory_gb": 32, "walltime_minutes": 720},
}

BINDCRAFT = {
    "plugin_key": "BindCraft",
    "plugin_version": "2025.09",
    "name": "BindCraft",
    "container_image": f"{PLACEHOLDER_PREFIX}/bindcraft:unset",
    "command": (
        "python bindcraft.py"
        ' --settings "$BDA_INPUT_DIR"/target.json'
        ' --filters "$filters_preset".json'
        ' --advanced "$advanced_preset".json'
    ),
    "parameter_schema": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "target_hotspot_residues": {
                "type": "string",
                "default": "",
                "description": "Hotspot residues defining the epitope, e.g. A164,A168,A171.",
            },
            "min_binder_length": {"type": "integer", "minimum": 40, "maximum": 150, "default": 60},
            "max_binder_length": {"type": "integer", "minimum": 40, "maximum": 200, "default": 90},
            "number_of_final_designs": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 100,
                "description": "Budget 10-40 GPU-minutes per accepted design.",
            },
            "filters_preset": {"type": "string", "default": "default_filters"},
            "advanced_preset": {"type": "string", "default": "default_4stage_multimer"},
        },
        "required": ["min_binder_length", "max_binder_length", "number_of_final_designs"],
    },
    "input_ports": [
        {
            "name": "target_structure",
            "kind": "protein_structure",
            "accepts": STRUCTURE_ACCEPTS,
            "content_types": STRUCTURE_CONTENT_TYPES,
            "required": True,
            "multiple": False,
            "description": "Prepared target with the epitope reachable.",
        }
    ],
    "output_ports": [
        {
            "name": "designs",
            "kind": "protein_structure",
            "artifact_type": "candidate_complex",
            "filename_glob": "*.pdb",
            "description": "Accepted binder complexes.",
        },
        {
            "name": "scores",
            "kind": "tabular",
            "artifact_type": "score_table",
            "filename_glob": "*.csv",
            "description": "Per-design AF2 and PyRosetta metrics from the BindCraft filter stage.",
        },
    ],
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 8, "memory_gb": 48, "walltime_minutes": 2880},
}

PLUGINS = (RFDIFFUSION, PROTEINMPNN, ALPHAFOLD2, ROSETTA, BINDCRAFT)

INSERT = sa.text(
    """
    INSERT INTO model_plugins (
        id, plugin_key, plugin_version, name, container_image, command,
        parameter_schema, output_schema, input_ports, output_ports, resources,
        runtime_mode, runtime_setup, output_parser, enabled,
        validation_status, validation_errors, version, created_at, updated_at
    ) VALUES (
        gen_random_uuid(), :plugin_key, :plugin_version, :name, :container_image, :command,
        CAST(:parameter_schema AS json), '{}'::json,
        CAST(:input_ports AS json), CAST(:output_ports AS json), CAST(:resources AS json),
        'container', '[]'::json, NULL, true,
        'unknown', '[]'::json, 1, now(), now()
    )
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    for plugin in PLUGINS:
        existing = bind.execute(
            sa.text("SELECT id FROM model_plugins WHERE plugin_key = :key AND plugin_version = :version"),
            {"key": plugin["plugin_key"], "version": plugin["plugin_version"]},
        ).fetchone()
        if existing is not None:
            print(f"0033: {plugin['plugin_key']} {plugin['plugin_version']} already registered")
            continue
        bind.execute(
            INSERT,
            {
                "plugin_key": plugin["plugin_key"],
                "plugin_version": plugin["plugin_version"],
                "name": plugin["name"],
                "container_image": plugin["container_image"],
                "command": plugin["command"],
                "parameter_schema": json.dumps(plugin["parameter_schema"]),
                "input_ports": json.dumps(plugin["input_ports"]),
                "output_ports": json.dumps(plugin["output_ports"]),
                "resources": json.dumps(plugin["resources"]),
            },
        )
        print(f"0033: registered {plugin['plugin_key']} {plugin['plugin_version']}")


def downgrade() -> None:
    """Remove the plugins this migration registered.

    `workflow_nodes.model_plugin_id` references `model_plugins` with no ON
    DELETE clause, so the delete is refused while any node still points at one.
    Clearing that reference first is the honest order: after this downgrade the
    plugin genuinely no longer exists, and the column is nullable precisely so a
    node can name a plugin by key without one being registered.

    Without this the downgrade only worked on an empty database - which is what
    CI runs, so the reversibility gate passed while any database with real work
    in it could not be downgraded at all.
    """
    for plugin in PLUGINS:
        op.execute(
            sa.text(
                "UPDATE workflow_nodes SET model_plugin_id = NULL "
                "WHERE model_plugin_id IN ("
                "  SELECT id FROM model_plugins"
                "  WHERE plugin_key = :key AND plugin_version = :version"
                ")"
            ).bindparams(key=plugin["plugin_key"], version=plugin["plugin_version"])
        )
        op.execute(
            sa.text(
                "DELETE FROM model_plugins WHERE plugin_key = :key AND plugin_version = :version"
            ).bindparams(key=plugin["plugin_key"], version=plugin["plugin_version"])
        )
