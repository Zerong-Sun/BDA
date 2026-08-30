"""Point the registered model plugins at their real qm installs, and fix parameter names.

Two defects, both of which make a plugin unrunnable rather than merely misconfigured.

**1. Placeholder commands.** AlphaFold2, ProteinMPNN, RFdiffusion and Rosetta were
registered with ``command = "python run.py"`` against a ``bda/<model>:<ver>`` image that
does not exist. ``compute.scripts.render_script`` builds the LSF script straight from
``plugin.command``, so submitting any of them runs ``python run.py`` on a login-class
node and fails. Every real sweet-protein job so far went through the hand-rendered
``qm-scripts/library`` path instead, which is why nobody hit this. ``proteinhunter_boltz``
(0021) is the only plugin wired to qm, and it is the pattern followed here: conda runtime,
``container_image`` naming the environment prefix, ``runtime_setup`` sourcing it by
absolute path, and an absolute entrypoint.

**2. Parameter names the renderer drops.** ``_parameter_exports`` only exports names
matching ``^[a-z][a-z0-9_]*$`` - deliberately, so parameters cannot collide with PATH or
LD_*. Every RFdiffusion parameter was authored in Hydra form (``inference.num_designs``),
and Rosetta's in flag form (``score:weights``), so **none of them ever reached the
script**. A node could set ``inference.num_designs=100`` and the job would silently run
the model's default. The keys are renamed to renderer-safe names here and each field
keeps its real CLI spelling in a new ``cli`` entry, which is what the command templates
map back to.

Entry points and environments come from job scripts that actually ran on qm
(``qm-scripts/rfd/rfd-binder.lsf``, ``qm-scripts/mpnn/mpnn1.lsf``, the sweet-protein
``deliverables/.../submit*.lsf``) and from the curated configs in
``qm-scripts/library/examples/``. See ``docs/QM_MODEL_AVAILABILITY_AND_SUBSTITUTES.md``.

Enabled flags are left exactly as they were. Pointing a plugin at a real install is a
repair; enabling one is a product decision that needs a smoke test first, and for
AlphaFold 3 a licensing decision as well.

Revision ID: 0024_plugins_point_at_qm
Revises: 0023_outbox_dead_letter
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024_plugins_point_at_qm"
down_revision: str | None = "0023_outbox_dead_letter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONDA_PROFILE = "/work/bme-liz/miniconda3/etc/profile.d/conda.sh"

# Installs owned by other accounts. We are authorised to *run* these; nothing may be
# written into them, so every command below sends its output to $BDA_OUTPUT_DIR.
LIZ = "/work/bme-liz"
# Our own account. New installs and new conda environments belong here.
OWN = "/work/bme-sunzr"

# Hydra/flag spellings a plugin's CLI needs, keyed by the renderer-safe parameter name.
# Renaming is what makes the parameter reach the script at all; the `cli` field records
# what it becomes on the command line so the mapping is data, not folklore.
RENAMES: dict[str, dict[str, str]] = {
    "RFdiffusion": {
        "inference.input_pdb": "input_pdb",
        "contigmap.contigs": "contigs",
        "ppi.hotspot_res": "hotspot_res",
        "inference.num_designs": "num_designs",
        "inference.output_prefix": "output_prefix",
        "diffuser.partial_T": "partial_t",
        "diffuser.T": "diffuser_t",
        "denoiser.noise_scale_ca": "noise_scale_ca",
        "denoiser.noise_scale_frame": "noise_scale_frame",
        "contigmap.inpaint_seq": "inpaint_seq",
        "contigmap.inpaint_str": "inpaint_str",
        "contigmap.provide_seq": "provide_seq",
        "inference.ckpt_override_path": "ckpt_override_path",
        "inference.symmetry": "symmetry",
        "potentials.guiding_potentials": "guiding_potentials",
        "potentials.guide_scale": "guide_scale",
    },
    "ProteinMPNN": {
        "omit_AAs": "omit_aas",
        "bias_AA_jsonl": "bias_aa_jsonl",
        "omit_AA_jsonl": "omit_aa_jsonl",
    },
    "Rosetta": {
        "parser:protocol": "parser_protocol",
        "score:weights": "score_weights",
        "relax:constrain_relax_to_start_coords": "relax_constrain_to_start_coords",
        "relax:ramp_constraints": "relax_ramp_constraints",
        "relax:script": "relax_script",
        "parser:script_vars": "parser_script_vars",
        "constraints:cst_fa_file": "cst_fa_file",
        "out:suffix": "out_suffix",
        "out:file:scorefile": "out_scorefile",
    },
}

# RFdiffusion is a Hydra CLI: every argument is key=value, and a list value must stay
# quoted or the shell globs the brackets in "[A1-50/2-4/B1-19]". Optional arguments use
# ${var:+...} so an empty parameter drops the argument entirely rather than passing an
# empty value the model rejects - the same shape 0021 established for ProteinHunter.
#
# Paths are written out rather than interpolated: these are shell templates, and reading
# them next to a real submit.lsf is how they get reviewed.
RFDIFFUSION_COMMAND = """\
rfd_input="$(find "$BDA_INPUT_DIR/input_structure" -name '*.pdb' 2>/dev/null | sort | head -1)"
/work/bme-liz/software/RFdiffusion/scripts/run_inference.py \
  ${rfd_input:+inference.input_pdb="$rfd_input"} \
  ${contigs:+contigmap.contigs="$contigs"} \
  ${hotspot_res:+ppi.hotspot_res="$hotspot_res"} \
  ${provide_seq:+contigmap.provide_seq="$provide_seq"} \
  ${inpaint_seq:+contigmap.inpaint_seq="$inpaint_seq"} \
  ${inpaint_str:+contigmap.inpaint_str="$inpaint_str"} \
  ${symmetry:+inference.symmetry="$symmetry"} \
  ${ckpt_override_path:+inference.ckpt_override_path="$ckpt_override_path"} \
  ${guiding_potentials:+potentials.guiding_potentials="$guiding_potentials"} \
  ${guide_scale:+potentials.guide_scale="$guide_scale"} \
  inference.num_designs="${num_designs:-10}" \
  diffuser.partial_T="${partial_t:-0}" \
  diffuser.T="${diffuser_t:-50}" \
  denoiser.noise_scale_ca="${noise_scale_ca:-1.0}" \
  denoiser.noise_scale_frame="${noise_scale_frame:-1.0}" \
  inference.output_prefix="$BDA_OUTPUT_DIR/${output_prefix:-design}"\
"""

# ProteinMPNN needs its three-step helper pipeline: parse every staged backbone into a
# JSONL, declare which chains are designable, then run. The staged port directory is the
# input, so a node binding 1 or 500 backbones uses the same command.
PROTEINMPNN_COMMAND = """\
python /work/bme-liz/software/proteinmpnn-main/helper_scripts/parse_multiple_chains.py \
  --input_path="$BDA_INPUT_DIR/backbone" --output_path="$BDA_OUTPUT_DIR/parsed_pdbs.jsonl"
python /work/bme-liz/software/proteinmpnn-main/helper_scripts/assign_fixed_chains.py \
  --input_path="$BDA_OUTPUT_DIR/parsed_pdbs.jsonl" \
  --output_path="$BDA_OUTPUT_DIR/assigned_pdbs.jsonl" \
  --chain_list "${pdb_path_chains:-A}"
python /work/bme-liz/software/proteinmpnn-main/protein_mpnn_run.py \
  --jsonl_path "$BDA_OUTPUT_DIR/parsed_pdbs.jsonl" \
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
  ${ca_only:+--ca_only}\
"""

# AlphaFold2 databases live under the shared install and are read-only to us; only
# --output_dir points into our own space. model_preset=multimer is what Route 3 calls
# "AlphaFold-Multimer" - it is a preset here, not a separate model.
ALPHAFOLD2_COMMAND = """\
af2_fasta="$(find "$BDA_INPUT_DIR/sequences" -name '*.fa*' 2>/dev/null | sort | paste -sd, -)"
python /work/bme-liz/software/alphafold/run_alphafold.py \
  --fasta_paths="$af2_fasta" \
  --output_dir="$BDA_OUTPUT_DIR" \
  --data_dir=/work/bme-liz/db/alphafold \
  --uniref90_database_path=/work/bme-liz/db/alphafold/uniref90/uniref90.fasta \
  --mgnify_database_path=/work/bme-liz/db/alphafold/mgnify/mgy_clusters.fa \
  --template_mmcif_dir=/work/bme-liz/db/alphafold/pdb_mmcif/mmcif_files \
  --obsolete_pdbs_path=/work/bme-liz/db/alphafold/pdb_mmcif/obsolete.dat \
  --model_preset="${model_preset:-monomer}" \
  --db_preset="${db_preset:-full_dbs}" \
  --max_template_date="${max_template_date:-2026-01-01}" \
  --models_to_relax="${models_to_relax:-best}" \
  ${num_multimer_predictions_per_model:+--num_multimer_predictions_per_model="$num_multimer_predictions_per_model"} \
  ${use_gpu_relax:+--use_gpu_relax} \
  ${use_precomputed_msas:+--use_precomputed_msas}\
"""

# score_jd2 for plain scoring; rosetta_scripts once an XML protocol is given, which is
# the route to InterfaceAnalyzer/ddG without installing anything (see the qm doc).
#
# -parser:script_vars is the one flag left unquoted on purpose: Rosetta reads it as a
# list of key=value pairs, so quoting would hand it a single argument "a=1 b=2".
ROSETTA_COMMAND = """\
find "$BDA_INPUT_DIR/structure" -name '*.pdb' 2>/dev/null | sort > "$BDA_OUTPUT_DIR/inputs.list"
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
  -ignore_unrecognized_res\
"""

BINDCRAFT_COMMAND = """\
python -u /work/bme-sunzr/software/BindCraft/bindcraft.py \
  --settings "$settings" \
  ${filters:+--filters "$filters"} \
  ${advanced:+--advanced "$advanced"}\
"""

BOLTZ_COMMAND = """\
boltz predict "$input_path" \
  --out_dir "$BDA_OUTPUT_DIR" \
  ${use_msa_server:+--use_msa_server} \
  ${msa_server_url:+--msa_server_url "$msa_server_url"} \
  ${predict_affinity:+--affinity} \
  ${num_samples:+--diffusion_samples "$num_samples"} \
  ${recycling_steps:+--recycling_steps "$recycling_steps"}\
"""

CHAI1_COMMAND = """\
chai-lab fold "$input_fasta" "$BDA_OUTPUT_DIR" \
  ${num_samples:+--num-diffn-samples "$num_samples"} \
  ${use_msa_server:+--use-msa-server} \
  ${msa_server_url:+--msa-server-url "$msa_server_url"} \
  ${use_templates_server:+--use-templates-server} \
  ${restraints_json:+--constraint-path "$restraints_json"}\
"""

ALPHAFOLD3_COMMAND = """\
python /share/apps/alphafold3-v3.0.1/run_alphafold.py \
  --json_path "$json_path" \
  --model_dir /work/bme-liz/db/af3/models \
  --db_dir /share/apps/alphafold3-data \
  --output_dir "$BDA_OUTPUT_DIR"\
"""

# plugin_key -> what to write. `enabled` is deliberately absent: this migration repairs
# how a plugin runs, it does not decide whether it may be run.
TARGETS: dict[str, dict] = {
    "RFdiffusion": {
        "container_image": f"{LIZ}/miniconda3/envs/SE3nv-gpu",
        "command": RFDIFFUSION_COMMAND,
        "runtime_setup": [f"source {CONDA_PROFILE}", f"conda activate {LIZ}/miniconda3/envs/SE3nv-gpu"],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 1, "walltime_minutes": 1440},
    },
    "ProteinMPNN": {
        "container_image": f"{LIZ}/miniconda3/envs/mlfold",
        "command": PROTEINMPNN_COMMAND,
        "runtime_setup": [f"source {CONDA_PROFILE}", f"conda activate {LIZ}/miniconda3/envs/mlfold"],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 1, "walltime_minutes": 720},
    },
    "AlphaFold2": {
        "container_image": f"{LIZ}/miniconda3/envs/alphafold",
        "command": ALPHAFOLD2_COMMAND,
        "runtime_setup": [
            "module purge",
            f"source {CONDA_PROFILE}",
            f"conda activate {LIZ}/miniconda3/envs/alphafold",
        ],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 8, "walltime_minutes": 1440},
    },
    "Rosetta": {
        # Rosetta is a plain binary: no environment to activate, but runtime_mode stays
        # non-container so the renderer does not try to wrap it in an image.
        "container_image": f"{LIZ}/software/rosetta",
        "command": ROSETTA_COMMAND,
        "runtime_setup": ["module purge"],
        "resources": {"cpus": 1, "memory_gb": 2, "walltime_minutes": 240},
    },
    "BindCraft": {
        "container_image": f"{OWN}/.conda/envs/BindCraft",
        "command": BINDCRAFT_COMMAND,
        "runtime_setup": ["module purge", f"source activate {OWN}/.conda/envs/BindCraft"],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 16, "walltime_minutes": 2880},
    },
    "Boltz": {
        "container_image": f"{OWN}/.conda/envs/boltz",
        "command": BOLTZ_COMMAND,
        "runtime_setup": ["module purge", f"source activate {OWN}/.conda/envs/boltz"],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 8, "walltime_minutes": 1440},
    },
    "Chai-1": {
        "container_image": f"{OWN}/.conda/envs/chai1",
        "command": CHAI1_COMMAND,
        "runtime_setup": ["module purge", f"source activate {OWN}/.conda/envs/chai1"],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 8, "walltime_minutes": 1440},
    },
    "AlphaFold 3": {
        "container_image": "/share/apps/anaconda3/envs/alphafold3-v3.0.1",
        "command": ALPHAFOLD3_COMMAND,
        "runtime_setup": [
            "module purge",
            "module load cuda/12.6",
            "source /share/apps/anaconda3/bin/activate /share/apps/anaconda3/envs/alphafold3-v3.0.1",
            "export XLA_FLAGS=--xla_gpu_enable_triton_gemm=false",
            "export XLA_PYTHON_CLIENT_PREALLOCATE=true",
            "export XLA_CLIENT_MEM_FRACTION=0.95",
        ],
        "resources": {"gpu": True, "gpu_count": 1, "cpus": 16, "walltime_minutes": 1440},
    },
}


def _rename_fields(schema: dict, mapping: dict[str, str]) -> dict:
    """Rename parameter keys to renderer-safe names, recording the real CLI spelling."""
    fields = schema.get("fields")
    if not isinstance(fields, list):
        return schema
    for item in fields:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        if key in mapping:
            item["cli"] = key
            item["key"] = mapping[key]
    return schema


def upgrade() -> None:
    bind = op.get_bind()
    for plugin_key, target in TARGETS.items():
        row = bind.execute(
            sa.text("SELECT id, parameter_schema FROM model_plugins WHERE plugin_key = :key"),
            {"key": plugin_key},
        ).fetchone()
        if row is None:
            print(f"0024: {plugin_key} not registered, skipped")
            continue
        schema = row.parameter_schema
        if isinstance(schema, str):
            schema = json.loads(schema)
        schema = _rename_fields(dict(schema or {}), RENAMES.get(plugin_key, {}))
        bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET container_image = :container_image,
                    command = :command,
                    runtime_mode = 'conda',
                    runtime_setup = CAST(:runtime_setup AS json),
                    resources = CAST(:resources AS json),
                    parameter_schema = CAST(:parameter_schema AS json),
                    validation_status = 'unknown',
                    validation_errors = '[]'::json,
                    version = version + 1,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": row.id,
                "container_image": target["container_image"],
                "command": target["command"],
                "runtime_setup": json.dumps(target["runtime_setup"]),
                "resources": json.dumps(target["resources"]),
                "parameter_schema": json.dumps(schema),
            },
        )
        print(f"0024: {plugin_key} now points at {target['container_image']}")


def downgrade() -> None:
    # Deliberately not restoring `python run.py` against a non-existent image: that state
    # renders a script that cannot run, and reintroducing it would be reintroducing the
    # defect. Parameter keys are left renamed for the same reason - the old names never
    # reached the rendered script at all.
    pass
