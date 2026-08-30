# QM cluster script library

Turn a small JSON config into a validated, reproducible LSF job bundle for
protein-design models — instead of copying and hand-editing `submit.lsf` scripts.

New here? Start with the **[step-by-step tutorial](TUTORIAL.md)**.

For the SUSTech-specific runtime environment, LSF resource rules and dated execution
history of each registered plugin, use the **[per-plugin QM runbooks](../plugins/README.md)**.
The upstream option catalog and the site runbooks are deliberately separate: a parameter
can exist upstream without having been observed on this cluster.

---

## Why this exists

Each model (RFdiffusion, ProteinMPNN, AlphaFold, Boltz, Chai-1, BindCraft,
Rosetta, MaskRGN) has a different, large command line. Editing scripts by hand
means typos in option names fail silently and it is hard to know which options
are valid. This tool:

- **Validates** your job against a catalog of the real options each model
  accepts, extracted from pinned upstream source (`catalog.json`).
- **Renders** a ready-to-run LSF bundle (`submit.lsf` + a resolved config).
- **Points to the exact file to fix** on any error, via a `[BDA_FIX_PATH]` line.

## What's covered

The catalog is generated from pinned upstream commits, so it matches real code:

- **RFdiffusion** — every key in the official `config/inference/base.yaml`.
- **ProteinMPNN** — every argument in `protein_mpnn_run.py`.
- **AlphaFold 2 / AlphaFold 3** — every flag in the official run entrypoint.
- **Boltz** — every `boltz predict` option.
- **Chai-1** — every argument of `chai_lab.chai1.run_inference`.
- **BindCraft** — target, advanced, and default filter settings.
- **Rosetta** — the supported BDA workflows (`rosetta_scripts`, `relax`,
  `InterfaceAnalyzer`, `cartesian_ddg`) and their common flags.
- **MaskRGN** — every Hydra key in the local inference/model/data configs.

`catalog.json` records the exact upstream Git commit used for extraction.
RFdiffusion checkpoint configuration may override values shown in `base.yaml`;
the catalog treats these as declared configuration defaults, not guaranteed
runtime defaults.

---

## Requirements

- Python 3.9+ (standard library only — no `pip install` needed for the CLI).
- `build_catalog.py` additionally needs `pyyaml` and `git` (only to regenerate
  the catalog from upstream; you do not need this for normal use).

## Quick start

```bash
cd qm-scripts/library

# See models and how many parameters each exposes.
python qm_job.py models

# See the bundled examples and what each one does.
python qm_job.py examples

# List every valid parameter for one model.
python qm_job.py params rfdiffusion
python qm_job.py params proteinmpnn | less

# Copy one example, edit only that JSON, then validate and render it.
cp examples/01-backbone-design/rfdiffusion-binder.json my-rfd-job.json
python qm_job.py validate my-rfd-job.json
python qm_job.py render my-rfd-job.json --output jobs/my-rfd-job

# Upload the complete bundle. This does NOT submit automatically.
bash upload_to_cluster.sh jobs/my-rfd-job <ssh-host>

# Submit only after reviewing the returned command.
ssh <ssh-host> "cd /opt/bda/bda/qm-script-library/my-rfd-job && bsub < submit.lsf"
```

## Commands

| Command | What it does |
|---------|--------------|
| `python qm_job.py models` | List catalogued models, parameter counts, and upstream commits. |
| `python qm_job.py examples` | List bundled example configs and their descriptions. |
| `python qm_job.py params <model>` | List every parameter for a model (`key  type  default  required  group  help`). |
| `python qm_job.py validate <config.json>` | Check a config against the catalog. |
| `python qm_job.py render <config.json> --output <dir>` | Write an LSF job bundle to `<dir>`. |

## Examples

Examples live in [`examples/`](examples/), grouped by pipeline stage. See
[`examples/README.md`](examples/README.md) for the full list and when to use
each one. There is one example per model, covering backbone design, sequence
design, structure prediction, binder design, and scoring/refinement.

## Configuration shape

```json
{
  "description": "Optional note, shown by `qm_job.py examples` and ignored by the renderer.",
  "model": "rfdiffusion",
  "executable": "/absolute/path/to/upstream/entrypoint",
  "scheduler": {
    "job_name": "rfd-binder",
    "queue": "4v100-16-e5",
    "cpus": 1,
    "gpus": 1
  },
  "setup": [
    "module purge",
    "source activate /path/to/environment"
  ],
  "parameters": {}
}
```

Only keys present in `catalog.json` are accepted in `parameters`. Set
`"include_defaults": true` only when you intentionally want every non-null
upstream default written to the command line; normally it is safer to pass only
explicit overrides.

## Rendered bundle

`render` writes into your `--output` directory:

| File | Purpose |
|------|---------|
| `submit.lsf` | The LSF batch script (`#BSUB` header, safety trap, setup, model command). |
| `config.resolved.json` | The exact parameters used plus upstream repo/commit — the reproducibility record. |
| `EDIT_THIS_PATH.txt` | Path back to the source config, so you always know what to edit. |

At runtime the script creates `logs/` and `output/`. Every validate, render,
upload, and cluster runtime error prints:

```text
[BDA_FIX_PATH] /absolute/path/to/the/config/to-edit.json
```

The generated cluster script additionally prints `[BDA_JOB_SCRIPT]` and
`[BDA_LOG_DIR]` on failure.

## Troubleshooting

| Message | Cause and fix |
|---------|---------------|
| `unknown model '<x>'` | `model` is not in the catalog. Run `python qm_job.py models`. |
| `unknown parameters for <model>: ...` | A key isn't valid for that model. Run `python qm_job.py params <model>`. |
| `parameter '<k>' must be <type>` | Wrong value type (e.g. string instead of integer). Fix the value in the JSON. |
| `missing required parameters: ...` | Add the listed keys to `parameters`. |
| `invalid JSON at line ...` | A syntax error in the config; the line/column is reported. |

Every error also prints `[BDA_FIX_PATH]` pointing at the file to edit.

## Refreshing the catalog from upstream

The committed catalog is reproducible from pinned Git revisions:

```bash
pip install pyyaml
python build_catalog.py --clone-root /tmp/bda-qm-upstreams
```

To update a model: review its current upstream entrypoint/config, bump the
commit in `build_catalog.py`, regenerate `catalog.json`, inspect the diff, and
run the tests. Never silently track a moving `main` branch on the cluster.
