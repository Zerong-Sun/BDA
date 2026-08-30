# Tutorial: your first cluster job with the QM script library

This is a hands-on walkthrough for someone who has never used this tool. By the
end you will understand what it does, how to run the simplest example, how to
change it, and how to read what it produces.

You do **not** need a GPU, a cluster, or any special Python packages to follow
along. Everything up to the final submit step runs on your laptop.

---

## 1. What this tool is for

Protein-design models (RFdiffusion, ProteinMPNN, AlphaFold, Boltz, Chai-1,
BindCraft, Rosetta, MaskRGN) each have their own command line with dozens or
hundreds of options. On an HPC cluster you normally run them by copying a
someone-else's `submit.lsf` script and editing it by hand. That is error-prone:
typos in option names fail silently, and it is hard to know which options are
even valid.

This library fixes that. You describe a job in a small **JSON file**, and
`qm_job.py`:

1. **validates** it against a catalog of the real options each model accepts
   (extracted from pinned upstream source code), and
2. **renders** a ready-to-run LSF job bundle (a `submit.lsf` plus a resolved
   config) that you can upload and submit.

If anything is wrong, it tells you exactly which file to fix.

---

## 2. Prerequisites

- Python 3.9+ (`python --version`). The tool uses only the standard library.
- A terminal opened in the library directory:

```bash
cd qm-scripts/library
```

That's it. No `pip install` needed for the CLI.

---

## 3. See what's available

List the models the catalog knows about:

```bash
python qm_job.py models
```

```text
alphafold2   31    https://github.com/google-deepmind/alphafold@c77e5d2a8961
proteinmpnn  34    https://github.com/dauparas/ProteinMPNN@8907e6671bfb
rfdiffusion  118   https://github.com/RosettaCommons/RFdiffusion@2d0c003df46b
...
```

The number is how many parameters that model exposes; the URL is the exact
upstream commit those parameters came from.

List the bundled examples and what each one does:

```bash
python qm_job.py examples
```

```text
01-backbone-design/rfdiffusion-binder.json   rfdiffusion   Generate de novo binder backbones ...
02-sequence-design/proteinmpnn.json          proteinmpnn   Design amino-acid sequences ...
...
```

---

## 4. Run the simplest example

We'll use the RFdiffusion binder example. First, copy it so you never edit the
original:

```bash
cp examples/01-backbone-design/rfdiffusion-binder.json my-rfd-job.json
```

Here is what that config looks like:

```json
{
  "description": "Generate de novo binder backbones ...",
  "model": "rfdiffusion",
  "executable": "/work/bme-liz/software/RFdiffusion/scripts/run_inference.py",
  "scheduler": { "job_name": "rfd-binder", "queue": "4v100-16-e5", "cpus": 1, "gpus": 1 },
  "setup": ["source activate /work/bme-liz/miniconda3/envs/SE3nv-gpu"],
  "parameters": {
    "inference.input_pdb": "./input/target.pdb",
    "contigmap.contigs": ["A1-150/0 70-100"],
    "ppi.hotspot_res": ["A59", "A83", "A91"],
    "inference.num_designs": 50,
    "inference.output_prefix": "./output/binder"
  }
}
```

Validate it:

```bash
python qm_job.py validate my-rfd-job.json
```

```text
[OK] valid: my-rfd-job.json
[INFO] Generate de novo binder backbones against a target protein with RFdiffusion, ...
[BDA_FIX_PATH] /abs/path/to/my-rfd-job.json
```

Render it into a job bundle:

```bash
python qm_job.py render my-rfd-job.json --output jobs/my-rfd-job
```

```text
[OK] rendered jobs/my-rfd-job/submit.lsf
[INFO] Generate de novo binder backbones ...
[BDA_FIX_PATH] /abs/path/to/my-rfd-job.json
```

---

## 5. Understand the workflow

The full path from idea to results is:

```text
edit JSON  ->  validate  ->  render  ->  upload  ->  submit  ->  read output
   you        qm_job.py    qm_job.py   upload.sh    bsub        logs/ + output/
```

- **validate** catches bad model names, unknown options, and wrong value types
  before you waste cluster time.
- **render** turns the config into files you can actually run.
- **upload** copies the bundle to the cluster (it does **not** submit).
- **submit** is a command *you* run after reviewing it, so nothing runs by
  surprise.

---

## 6. Understand the rendered output

`jobs/my-rfd-job/` now contains:

| File | What it is |
|------|------------|
| `submit.lsf` | The LSF batch script. This is what `bsub` runs. |
| `config.resolved.json` | The exact parameters used, plus the upstream repo/commit — your reproducibility record. |
| `EDIT_THIS_PATH.txt` | The path back to the source config, so you always know what to edit. |

Open `submit.lsf` and you'll see the `#BSUB` resource header, a `set -Eeuo
pipefail` safety block, your `setup` lines, and finally the model command with
every option filled in:

```bash
#BSUB -J rfd-binder
#BSUB -q 4v100-16-e5
#BSUB -n 1
#BSUB -gpu "num=1"
...
source activate /work/bme-liz/miniconda3/envs/SE3nv-gpu
/work/bme-liz/software/RFdiffusion/scripts/run_inference.py \
  inference.input_pdb=./input/target.pdb \
  'contigmap.contigs=["A1-150/0 70-100"]' \
  ... inference.num_designs=50 inference.output_prefix=./output/binder
```

When the job runs on the cluster it creates `logs/` (stdout/stderr) and
`output/` (the model's results, e.g. designed PDBs).

---

## 7. Modify the example

Say you want **200** designs instead of 50, and a different input structure.
Edit only `my-rfd-job.json`:

```json
"parameters": {
  "inference.input_pdb": "./input/my_target.pdb",
  "inference.num_designs": 200
}
```

Re-validate and re-render:

```bash
python qm_job.py validate my-rfd-job.json
python qm_job.py render my-rfd-job.json --output jobs/my-rfd-job
```

To discover what else you can set, list the model's parameters:

```bash
python qm_job.py params rfdiffusion | less
```

Each row is: `key  type  default  required?  group  help`. Only keys shown here
are accepted; anything else is rejected at validate time.

---

## 8. Interpret errors

Every error prints a `[BDA_FIX_PATH]` line pointing at the exact file to edit.
For example, a typo in an option name:

```text
[ERROR] unknown parameters for rfdiffusion: inference.num_design
[BDA_FIX_PATH] /abs/path/to/my-rfd-job.json
```

Fix the file at that path and run the command again. The same convention is used
at every stage — validate, render, upload, and even at runtime on the cluster
(the generated script prints `[BDA_FIX_PATH]`, `[BDA_JOB_SCRIPT]`, and
`[BDA_LOG_DIR]` if the model fails).

---

## 9. Submit on the cluster (optional)

When you have real cluster access, upload the bundle and submit it yourself:

```bash
# Copies the bundle to the cluster. Does NOT submit anything.
bash upload_to_cluster.sh jobs/my-rfd-job <ssh-host>

# Review the printed command, then submit:
ssh <ssh-host> "cd /work/bme-sunzr/bda/qm-script-library/my-rfd-job && bsub < submit.lsf"
```

Before submitting, replace the `/work/...` paths in the config with the paths
that exist on **your** cluster (model install, conda env, databases).

---

## 10. Where to go next

- [`README.md`](README.md) — reference for commands and the config schema.
- [`examples/README.md`](examples/README.md) — every example and when to use it.
- To follow a different model, copy its example (`python qm_job.py examples`)
  and repeat steps 4–8.
