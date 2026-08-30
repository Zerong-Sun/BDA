"""Correct the qm plugin paths against the cluster, and register superfold.

0024 took its entry points from ``qm-scripts/library/examples/``. Checking them on qm
showed three of those curated configs are stale, and one model in them is not installed
at all. What the cluster actually has:

* **BindCraft** is at ``/work/bme-liz/software/BindCraft`` with env
  ``/work/bme-liz/miniconda3/envs/BindCraft`` - not under our own account as the example
  config claimed. ``/opt/bda/software`` is empty and our only env is ``gemmi``.
* **Boltz** is ``/work/bme-liz/miniconda3/envs/boltz/bin/boltz`` (plus source in
  ``software/boltz-2``), again not ours.
* **Chai-1 is not installed anywhere on qm.** Disabled: a plugin that names software that
  does not exist is worse than one that is switched off, because preflight passes it.
* **DeepMind AlphaFold2 is not installed either** - neither
  ``software/alphafold/run_alphafold.py`` nor the ``db/alphafold`` databases exist. What
  exists is ``superfold`` (AF2 monomer_ptm weights, bundled model code) and an unbuilt
  ``localcolabfold`` checkout. The AlphaFold2 plugin is disabled rather than left pointing
  at an absent path.

superfold is registered here because it closes the gap the routes care about most: it
implements ``--initial_guess``, the Bennett protocol that Route A's binder filter and
Route C's differential scoring are both specified against, and that the qm doc listed as
needing a dl_binder_design install. No install is required after all.

Two constraints the command encodes:

* superfold's wrapper **exits if a conda environment is active** - it calls its own
  interpreter by absolute path. So ``runtime_mode`` is ``script`` and ``runtime_setup`` is
  empty; nothing may activate an environment for this plugin.
* It always uses monomer_ptm weights and refuses multimer, so "AlphaFold-Multimer" for
  Route 3 is *not* available through it. That gap is still open.

Revision ID: 0025_qm_paths_verified
Revises: 0024_plugins_point_at_qm
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_qm_paths_verified"
down_revision: str | None = "0024_plugins_point_at_qm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONDA_PROFILE = "/work/bme-liz/miniconda3/etc/profile.d/conda.sh"

BINDCRAFT_COMMAND = """\
python -u /work/bme-liz/software/BindCraft/bindcraft.py \
  --settings "$settings" \
  ${filters:+--filters "$filters"} \
  ${advanced:+--advanced "$advanced"}\
"""

# Verified: /work/bme-liz/miniconda3/envs/boltz/bin/boltz
BOLTZ_COMMAND = """\
boltz predict "$input_path" \
  --out_dir "$BDA_OUTPUT_DIR" \
  ${use_msa_server:+--use_msa_server} \
  ${msa_server_url:+--msa_server_url "$msa_server_url"} \
  ${predict_affinity:+--affinity} \
  ${num_samples:+--diffusion_samples "$num_samples"} \
  ${recycling_steps:+--recycling_steps "$recycling_steps"}\
"""

# Inputs are passed positionally and unquoted on purpose: superfold takes any number of
# PDB/FASTA paths as positional arguments.
SUPERFOLD_COMMAND = """\
superfold_inputs="$(find "$BDA_INPUT_DIR/structures" \\( -name '*.pdb' -o -name '*.fa*' \\) 2>/dev/null | sort)"
if [ -z "$superfold_inputs" ]; then echo "bda: no structures/sequences staged for superfold" >&2; exit 2; fi
/work/bme-liz/software/superfold/superfold $superfold_inputs \
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
  ${overwrite:+--overwrite}\
"""

SUPERFOLD_SCHEMA = {
    "fields": [
        {
            "key": "initial_guess",
            "label": "Initial guess",
            "type": "boolean",
            "default": True,
            "help": (
                "Seed the prediction with the input PDB's coordinates (Bennett protocol). "
                "This is what makes pAE_interaction discriminative for binders; the published "
                "pAE_int < 10 threshold is calibrated for it. Input must be PDB."
            ),
            "advanced": False,
        },
        {
            "key": "mock_msa_depth",
            "label": "Mock MSA depth",
            "type": "integer",
            "default": 1,
            "help": "Fake MSA depth. 1 is single-sequence and fast; AF2's own default is 512.",
            "advanced": False,
        },
        {
            "key": "models",
            "label": "Models",
            "type": "string",
            "default": "all",
            "help": "Which of the five AF2 weight sets to run, e.g. 'all' or '4'.",
            "advanced": False,
        },
        {"key": "nstruct", "label": "Outputs per model", "type": "integer", "default": 1, "advanced": False},
        {"key": "max_recycles", "label": "Max recycles", "type": "integer", "default": 3, "advanced": False},
        {
            "key": "recycle_tol",
            "label": "Recycle tolerance",
            "type": "number",
            "default": 0.0,
            "help": "Stop recycling early when CA-RMSD between iterations is below this. 0 disables.",
            "advanced": True,
        },
        {"key": "seed_start", "label": "Seed start", "type": "integer", "default": 0, "advanced": True},
        {"key": "num_ensemble", "label": "Ensemble", "type": "integer", "default": 1, "advanced": True},
        {
            "key": "reference_pdb",
            "label": "Reference PDB",
            "type": "string",
            "default": "",
            "help": "Reference for RMSD; outputs are aligned to it.",
            "advanced": True,
        },
        {"key": "enable_dropout", "label": "Enable dropout", "type": "boolean", "default": False, "advanced": True},
        {"key": "output_pae", "label": "Write PAE matrix", "type": "boolean", "default": True, "advanced": False},
        {
            "key": "output_summary",
            "label": "Write reports.txt",
            "type": "boolean",
            "default": True,
            "help": "One line per prediction; this is what a scoring step reads.",
            "advanced": False,
        },
        {"key": "overwrite", "label": "Overwrite", "type": "boolean", "default": False, "advanced": True},
    ]
}

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
            "sequence_set",
        ],
        "content_types": [],
        "required": True,
        "multiple": True,
        "description": "Designs to predict. PDB is required when initial_guess is on.",
    }
]

SUPERFOLD_OUTPUT_PORTS = [
    {
        "name": "structures",
        "kind": "protein_structure",
        "artifact_type": "predicted_structure",
        "filename_glob": "*_unrelaxed.pdb",
        "description": "Predicted structures, pLDDT in the B-factor column.",
    },
    {
        "name": "metrics",
        "kind": "tabular",
        "artifact_type": "confidence_record",
        "filename_glob": "*_prediction_results.json",
        "description": "Per-prediction pLDDT, pTM and (with output_pae) PAE.",
    },
    {
        "name": "summary",
        "kind": "tabular",
        "artifact_type": "score_table",
        "filename_glob": "reports.txt",
        "description": "One line per prediction; the ranking input.",
    },
]

SUPERFOLD = {
    "plugin_key": "superfold",
    "plugin_version": "qm-20260803",
    "name": "superfold (AlphaFold2 + initial guess)",
    "container_image": "/work/bme-liz/software/superfold",
    "command": SUPERFOLD_COMMAND,
    # 'script', not 'conda': the superfold wrapper exits when CONDA_DEFAULT_ENV is set and
    # calls /work/bme-liz/miniconda3/envs/pyroml-gpu/bin/python3.8 by absolute path.
    "runtime_mode": "script",
    "runtime_setup": [],
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 2, "walltime_minutes": 720},
}

# Corrections to what 0024 wrote, from the cluster itself.
REPOINT: dict[str, dict] = {
    "BindCraft": {
        "container_image": "/work/bme-liz/miniconda3/envs/BindCraft",
        "command": BINDCRAFT_COMMAND,
        "runtime_setup": [
            f"source {CONDA_PROFILE}",
            "conda activate /work/bme-liz/miniconda3/envs/BindCraft",
        ],
    },
    "Boltz": {
        "container_image": "/work/bme-liz/miniconda3/envs/boltz",
        "command": BOLTZ_COMMAND,
        "runtime_setup": [
            f"source {CONDA_PROFILE}",
            "conda activate /work/bme-liz/miniconda3/envs/boltz",
        ],
    },
}

# plugin_key -> why it must not be dispatchable.
DISABLE = {
    "Chai-1": "not installed on qm: no chai environment or checkout exists",
    "AlphaFold2": "DeepMind AlphaFold2 and its databases are absent on qm; use the superfold plugin",
}


def upgrade() -> None:
    bind = op.get_bind()
    for plugin_key, target in REPOINT.items():
        result = bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET container_image = :container_image,
                    command = :command,
                    runtime_setup = CAST(:runtime_setup AS json),
                    version = version + 1,
                    updated_at = now()
                WHERE plugin_key = :key
                """
            ),
            {
                "key": plugin_key,
                "container_image": target["container_image"],
                "command": target["command"],
                "runtime_setup": json.dumps(target["runtime_setup"]),
            },
        )
        print(f"0025: {plugin_key} repointed ({result.rowcount} row)")

    for plugin_key, reason in DISABLE.items():
        result = bind.execute(
            sa.text(
                """
                UPDATE model_plugins
                SET enabled = false,
                    validation_status = 'invalid',
                    validation_errors = CAST(:errors AS json),
                    version = version + 1,
                    updated_at = now()
                WHERE plugin_key = :key
                """
            ),
            {"key": plugin_key, "errors": json.dumps([{"code": "not_installed", "message": reason}])},
        )
        print(f"0025: {plugin_key} disabled - {reason} ({result.rowcount} row)")

    existing = bind.execute(
        sa.text("SELECT id FROM model_plugins WHERE plugin_key = :key"),
        {"key": SUPERFOLD["plugin_key"]},
    ).fetchone()
    if existing is not None:
        print("0025: superfold already registered")
        return
    bind.execute(
        sa.text(
            """
            INSERT INTO model_plugins (
                id, plugin_key, plugin_version, name, container_image, command,
                parameter_schema, output_schema, input_ports, output_ports, resources,
                runtime_mode, runtime_setup, enabled,
                validation_status, validation_errors, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), :plugin_key, :plugin_version, :name, :container_image, :command,
                CAST(:parameter_schema AS json), '{}'::json,
                CAST(:input_ports AS json), CAST(:output_ports AS json), CAST(:resources AS json),
                :runtime_mode, CAST(:runtime_setup AS json), true,
                'unknown', '[]'::json, 1, now(), now()
            )
            """
        ),
        {
            **{k: SUPERFOLD[k] for k in ("plugin_key", "plugin_version", "name", "container_image", "command", "runtime_mode")},
            "parameter_schema": json.dumps(SUPERFOLD_SCHEMA),
            "input_ports": json.dumps(SUPERFOLD_INPUT_PORTS),
            "output_ports": json.dumps(SUPERFOLD_OUTPUT_PORTS),
            "resources": json.dumps(SUPERFOLD["resources"]),
            "runtime_setup": json.dumps(SUPERFOLD["runtime_setup"]),
        },
    )
    print("0025: registered superfold (AF2 + initial guess)")


def downgrade() -> None:
    # workflow_nodes.model_plugin_id has no ON DELETE clause, so the delete
    # below is refused while any node still points at this plugin. The column
    # is nullable precisely so a node can name a plugin by key without one
    # being registered, which is the state a downgrade returns it to.
    op.execute(
        sa.text(
            "UPDATE workflow_nodes SET model_plugin_id = NULL WHERE model_plugin_id IN ("
            " SELECT id FROM model_plugins WHERE plugin_key = 'superfold')"
        )
    )
    op.execute(sa.text("DELETE FROM model_plugins WHERE plugin_key = 'superfold'"))
    # Paths and enabled flags are left corrected: restoring them would point plugins back
    # at software that is not on the cluster.
