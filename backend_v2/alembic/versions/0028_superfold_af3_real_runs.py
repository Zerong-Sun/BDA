"""Correct superfold and AlphaFold 3 against how they were actually run on qm.

Both tools have been run on this cluster before, by hand, through
``qm-scripts/af2/superfold.lsf`` and ``qm-scripts/af3/predict.sh`` plus the AF3 LSF
wrapper. Those scripts are ground truth for the plugin definitions and they contradicted
them in three places.

**superfold refuses to start inside a conda environment.** Its wrapper checks
``CONDA_DEFAULT_ENV`` and exits, because it calls its own interpreter
(``envs/pyroml-gpu/bin/python3.8``) by absolute path. 0025 already declared an empty
``runtime_setup`` so nothing would activate an environment - but that is not the same as
guaranteeing none is active. The hand-written job starts with ``source deactivate base``,
which means this cluster does leave one active. The preamble now clears it, with an
unconditional ``unset`` as the deterministic fallback: the wrapper tests that one variable,
so unsetting it is what actually satisfies the check.

**superfold's input glob picked up macOS resource forks.** The hand-written loop skips
``._*.pdb`` explicitly. Those files are 4 KB of AppleDouble metadata that parse as neither
PDB nor FASTA, and they appear whenever inputs have been through a Mac. The find now
excludes them.

**AlphaFold 3's output ports all globbed ``*``.** Three ports each matching every file
means collection cannot tell the predicted structure from the confidence JSON from the
manifest. Real runs write ``*_model.cif`` (optionally gzipped) and
``*summary_confidences.json``, so the globs are set from that. ``num_diffusion_samples``
is also exposed, since the real invocation passes it.

Revision ID: 0028_superfold_af3_real_runs
Revises: 0027_ip_and_physics_tools
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_superfold_af3_real_runs"
down_revision: str | None = "0027_ip_and_physics_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `source deactivate base` is what the working hand-written job uses; `conda deactivate` is
# the modern spelling and may not exist as a shell function in a non-interactive job. The
# unset is the one that deterministically satisfies superfold's check.
SUPERFOLD_SETUP = [
    "source deactivate base 2>/dev/null || conda deactivate 2>/dev/null || true",
    "unset CONDA_DEFAULT_ENV",
]

SUPERFOLD_COMMAND = """\
superfold_inputs="$(find "$BDA_INPUT_DIR/structures" \\( -name '*.pdb' -o -name '*.fa*' \\) ! -name '._*' 2>/dev/null | sort)"
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

AF3_COMMAND = """\
python /share/apps/alphafold3-v3.0.1/run_alphafold.py \
  --json_path "$json_path" \
  --model_dir /work/bme-liz/db/af3/models \
  --db_dir /share/apps/alphafold3-data \
  --output_dir "$BDA_OUTPUT_DIR" \
  --num_diffusion_samples "${num_diffusion_samples:-1}"\
"""

# Globs taken from what real AF3 runs write: the collector in af3_cs.lsf harvests
# `*_model.cif(.gz)` and `*summary_confidences.json` from each job's top-level directory.
AF3_OUTPUT_PORTS = [
    {
        "name": "predicted_complex",
        "kind": "protein_structure",
        "artifact_type": "complex_structure",
        "filename_glob": "*_model.cif*",
        "description": "Predicted complex, mmCIF (sometimes gzipped).",
    },
    {
        "name": "confidence_json",
        "kind": "tabular",
        "artifact_type": "score_table",
        "filename_glob": "*summary_confidences.json",
        "description": "Per-prediction ipTM/pTM and chain-pair confidences.",
    },
    {
        "name": "run_manifest",
        "kind": "params",
        "artifact_type": "manifest",
        "filename_glob": "*_data.json",
        "description": "The resolved fold input AF3 echoes back for the run.",
    },
]


def upgrade() -> None:
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET command = :command,
                runtime_setup = CAST(:runtime_setup AS json),
                version = version + 1,
                updated_at = now()
            WHERE plugin_key = 'superfold'
            """
        ),
        {"command": SUPERFOLD_COMMAND, "runtime_setup": json.dumps(SUPERFOLD_SETUP)},
    )
    print(f"0028: superfold command and preamble corrected ({result.rowcount} row)")

    schema_row = bind.execute(
        sa.text("SELECT parameter_schema FROM model_plugins WHERE plugin_key = 'AlphaFold 3'")
    ).fetchone()
    if schema_row is None:
        print("0028: AlphaFold 3 not registered, skipped")
        return
    schema = schema_row.parameter_schema
    if isinstance(schema, str):
        schema = json.loads(schema)
    fields = list(schema.get("fields", []))
    if not any(str(item.get("key")) == "num_diffusion_samples" for item in fields):
        fields.append(
            {
                "key": "num_diffusion_samples",
                "label": "Diffusion samples",
                "type": "integer",
                "default": 1,
                "help": "Predictions per seed. The hand-written qm job uses 1.",
                "advanced": False,
            }
        )
    schema["fields"] = fields

    result = bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET command = :command,
                parameter_schema = CAST(:parameter_schema AS json),
                output_ports = CAST(:output_ports AS json),
                version = version + 1,
                updated_at = now()
            WHERE plugin_key = 'AlphaFold 3'
            """
        ),
        {
            "command": AF3_COMMAND,
            "parameter_schema": json.dumps(schema),
            "output_ports": json.dumps(AF3_OUTPUT_PORTS),
        },
    )
    print(f"0028: AlphaFold 3 output ports and parameters corrected ({result.rowcount} row)")


def downgrade() -> None:
    # Restoring `filename_glob: "*"` on three ports would put back a state where collection
    # cannot type any AF3 output, and restoring an empty superfold preamble would put back
    # a job that exits on contact with an active conda environment.
    pass
