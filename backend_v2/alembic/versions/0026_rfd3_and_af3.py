"""Register RFdiffusion3 and enable AlphaFold 3.

Both are owner decisions recorded as data rather than left in a chat log.

**RFdiffusion3.** Route A needs atom-level, sequence-position-agnostic motif scaffolding;
the protocol asked for RFdiffusion2, which is not on qm. RFdiffusion3 is, and reading
``rfd3/inference/input_parsing.py`` shows it does more than RFD2 was wanted for:
``select_fixed_atoms`` takes a per-residue, per-atom-name mapping
(``{"A43": "NE,CZ,NH1,NH2"}``), so the brazzein charge pharmacophore can be pinned atom by
atom while ``select_unfixed_sequence`` frees everything else.

The plugin runs the existing ``foundry`` environment in place, read-only, exactly as the
other plugins run BindCraft, Boltz and RFdiffusion out of ``/work/bme-liz``. Cloning it into
our own account was tried first and abandoned at 12 GB and still copying: an environment
carrying torch, JAX and CUDA is not worth duplicating per user on a shared filesystem, and
a clone would drift from the copy that is known to work. Checkpoints are referenced the
same way - ``/work/bme-rongx/.foundry/checkpoints`` is world-readable and holds
``rfd3_latest.ckpt``, so ``FOUNDRY_CHECKPOINT_DIRS`` points at it rather than copying 12 GB.

The cost of that choice is a dependency on another account's directory, which is why
``runtime_setup`` fails loudly if the environment disappears rather than half-starting.

Two things that differ from RFdiffusion 1 and will silently produce nonsense if copied
across: ``partial_t`` is **Angstroms of noise** (<=15 recommended), not a diffusion step
count, and outputs are ``.cif``/``.cif.gz`` plus a sidecar JSON rather than ``.pdb``.

**AlphaFold 3** is enabled at the owner's instruction. It stays the multimer path for
route 3 now that AlphaFold-Multimer is confirmed absent and superfold refuses multimer.
The non-commercial terms on its weights are the owner's call, not this migration's.

Neither has been executed. The command templates are transcribed from the package's own
CLI (``rfd3/cli.py`` -> Hydra ``compose``) and from the qm AF3 job script.

Revision ID: 0026_rfd3_and_af3
Revises: 0025_qm_paths_verified
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_rfd3_and_af3"
down_revision: str | None = "0025_qm_paths_verified"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Another account's environment, used in place and read-only.
RFD3_ENV = "/work/bme-rongx/.conda/envs/foundry"
OUR_CONDA_PROFILE = "/work/bme-sunzr/miniconda3/etc/profile.d/conda.sh"
# Read-only: 12 GB of checkpoints owned by another account, including rfd3_latest.ckpt.
SHARED_CHECKPOINTS = "/work/bme-rongx/.foundry/checkpoints"

# `rfd3 design` is a Hydra CLI (rfd3/cli.py composes configs/inference.yaml). Verified
# against `configs/inference_engine/rfdiffusion3.yaml`, which is `# @package _global_`:
# `out_dir`, `inputs`, `ckpt_path`, `n_batches`, `diffusion_batch_size` and `specification`
# are all top-level keys, so each is a plain override.
#
# `inputs` accepts a JSON *or* a PDB. The per-design specification - contigs,
# select_fixed_atoms, hotspots - goes in the JSON rather than on the command line, because
# a nested mapping is not expressible as a shell override. (`specification.length=80` style
# overrides do work for single scalars, and override whatever the JSON said.)
RFD3_COMMAND = """\
rfd3_spec="$(find "$BDA_INPUT_DIR/design_spec" -name '*.json' 2>/dev/null | sort | head -1)"
if [ -z "$rfd3_spec" ]; then echo "bda: no RFdiffusion3 design spec staged" >&2; exit 2; fi
rfd3 design \
  inputs="$rfd3_spec" \
  out_dir="$BDA_OUTPUT_DIR" \
  n_batches="${n_batches:-1}" \
  diffusion_batch_size="${diffusion_batch_size:-5}" \
  ckpt_path="${ckpt_path:-rfd3}" \
  ${seed:+seed="$seed"} \
  ${low_memory_mode:+low_memory_mode=true} \
  ${dump_trajectories:+dump_trajectories=true}\
"""

RFD3_SCHEMA = {
    "fields": [
        {
            "key": "n_batches",
            "label": "Batches",
            "type": "integer",
            "default": 1,
            "help": "Number of diffusion batches per input specification.",
            "advanced": False,
        },
        {
            "key": "diffusion_batch_size",
            "label": "Designs per batch",
            "type": "integer",
            "default": 5,
            "help": "Structures generated per batch.",
            "advanced": False,
        },
        {
            "key": "ckpt_path",
            "label": "Checkpoint",
            "type": "string",
            "default": "rfd3",
            "help": (
                "Registered checkpoint name (resolved from FOUNDRY_CHECKPOINT_DIRS) or an "
                "absolute path. 'rfd3' resolves to rfd3_latest.ckpt."
            ),
            "advanced": False,
        },
        {"key": "seed", "label": "Seed", "type": "integer", "default": 0, "advanced": True},
        {
            "key": "low_memory_mode",
            "label": "Low-memory tokenization",
            "type": "boolean",
            "default": False,
            "advanced": True,
        },
        {
            "key": "dump_trajectories",
            "label": "Dump trajectories",
            "type": "boolean",
            "default": False,
            "help": "Writes the diffusion trajectory; large, useful only for debugging.",
            "advanced": True,
        },
    ]
}

RFD3_INPUT_PORTS = [
    {
        "name": "design_spec",
        "kind": "params",
        "accepts": ["design_spec", "params", "json"],
        "content_types": ["application/json"],
        "required": True,
        "multiple": False,
        "description": (
            "RFdiffusion3 input JSON: contig/length plus conditioning such as "
            "select_fixed_atoms, select_unfixed_sequence, select_hotspots, partial_t."
        ),
    },
    {
        "name": "input_structure",
        "kind": "protein_structure",
        "accepts": ["target_structure", "backbone_set", "complex_structure", "structure"],
        "content_types": [],
        "required": False,
        "multiple": True,
        "description": "Structures the specification refers to (motif source, receptor).",
    },
]

RFD3_OUTPUT_PORTS = [
    {
        "name": "backbones",
        "kind": "protein_structure",
        "artifact_type": "backbone_set",
        "filename_glob": "*.cif",
        "description": "Generated backbones. RFdiffusion3 writes mmCIF, not PDB.",
    },
    {
        "name": "metadata",
        "kind": "tabular",
        "artifact_type": "confidence_record",
        "filename_glob": "*.json",
        "description": "Per-design sidecar metadata written next to each structure.",
    },
]

RFD3 = {
    "plugin_key": "RFdiffusion3",
    "plugin_version": "foundry-2025-12-01",
    "name": "RFdiffusion3 (atom-level motif)",
    "container_image": RFD3_ENV,
    "command": RFD3_COMMAND,
    "runtime_mode": "conda",
    "runtime_setup": [
        # Fail with a named dependency rather than a confusing activation error if the
        # borrowed environment is moved or removed.
        f'test -d {RFD3_ENV} || {{ echo "bda: missing dependency {RFD3_ENV}" >&2; exit 3; }}',
        f"source {OUR_CONDA_PROFILE}",
        f"conda activate {RFD3_ENV}",
        # Read-only checkpoint search path; the engine looks here before ~/.foundry.
        f"export FOUNDRY_CHECKPOINT_DIRS={SHARED_CHECKPOINTS}",
    ],
    "resources": {"gpu": True, "gpu_count": 1, "cpus": 4, "walltime_minutes": 1440},
}


def upgrade() -> None:
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            UPDATE model_plugins
            SET enabled = true, version = version + 1, updated_at = now()
            WHERE plugin_key = 'AlphaFold 3'
            """
        )
    )
    print(f"0026: AlphaFold 3 enabled ({result.rowcount} row)")

    existing = bind.execute(
        sa.text("SELECT id FROM model_plugins WHERE plugin_key = :key"),
        {"key": RFD3["plugin_key"]},
    ).fetchone()
    if existing is not None:
        print("0026: RFdiffusion3 already registered")
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
            **{
                key: RFD3[key]
                for key in ("plugin_key", "plugin_version", "name", "container_image", "command", "runtime_mode")
            },
            "parameter_schema": json.dumps(RFD3_SCHEMA),
            "input_ports": json.dumps(RFD3_INPUT_PORTS),
            "output_ports": json.dumps(RFD3_OUTPUT_PORTS),
            "resources": json.dumps(RFD3["resources"]),
            "runtime_setup": json.dumps(RFD3["runtime_setup"]),
        },
    )
    print("0026: registered RFdiffusion3")


def downgrade() -> None:
    # workflow_nodes.model_plugin_id has no ON DELETE clause, so the delete
    # below is refused while any node still points at this plugin. The column
    # is nullable precisely so a node can name a plugin by key without one
    # being registered, which is the state a downgrade returns it to.
    op.execute(
        sa.text(
            "UPDATE workflow_nodes SET model_plugin_id = NULL WHERE model_plugin_id IN ("
            " SELECT id FROM model_plugins WHERE plugin_key = 'RFdiffusion3')"
        )
    )
    op.execute(sa.text("DELETE FROM model_plugins WHERE plugin_key = 'RFdiffusion3'"))
    op.execute(sa.text("UPDATE model_plugins SET enabled = false WHERE plugin_key = 'AlphaFold 3'"))
