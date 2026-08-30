# Example job configs

Each file here is a small, self-contained JSON config for one model. Copy one,
edit only the values you need, then validate and render it with `qm_job.py`
(see the [tutorial](../TUTORIAL.md)).

List them from the command line at any time:

```bash
cd qm-scripts/library
python qm_job.py examples
```

The folders follow the usual protein-design pipeline, roughly in the order you
would run them:

| Folder | Stage | Example | Model | When to use it |
|--------|-------|---------|-------|----------------|
| `01-backbone-design/` | Generate a shape | `rfdiffusion-binder.json` | RFdiffusion | Create de novo binder backbones against a target. **Start here.** |
| `02-sequence-design/` | Choose amino acids | `proteinmpnn.json` | ProteinMPNN | Design sequences for a fixed backbone (inverse folding). |
| `02-sequence-design/` | Choose amino acids | `maskrgn.json` | MaskRGN | Local alternative sequence-design model. |
| `03-structure-prediction/` | Fold & check | `alphafold2.json` | AlphaFold2 | Predict a multimer with full local databases. |
| `03-structure-prediction/` | Fold & check | `alphafold3.json` | AlphaFold3 | Predict from a fold-input JSON. |
| `03-structure-prediction/` | Fold & check | `boltz.json` | Boltz-2 | Predict from YAML, no local databases (hosted MSA). |
| `03-structure-prediction/` | Fold & check | `chai1.json` | Chai-1 | Predict from FASTA, no local databases (hosted MSA). |
| `04-binder-design/` | End-to-end | `bindcraft.json` | BindCraft | One job that designs, folds, and filters binders. |
| `05-scoring-and-refinement/` | Rank | `rosetta-interface.json` | Rosetta | Score and refine designed complexes. |

## Config shape

Every example uses the same top-level keys:

```json
{
  "description": "Free-text note shown by `qm_job.py examples` (optional).",
  "model": "rfdiffusion",
  "executable": "/absolute/path/to/the/model/entrypoint",
  "scheduler": { "job_name": "rfd-binder", "queue": "4v100-16-e5", "cpus": 1, "gpus": 1 },
  "setup": ["source activate /path/to/conda/env"],
  "parameters": { "inference.num_designs": 50 }
}
```

- `description` — optional, ignored by the renderer, echoed in listings.
- `model` — must be one of the models in `catalog.json` (`python qm_job.py models`).
- `executable` — path to the upstream entrypoint **on the cluster**.
- `scheduler` — LSF resources written into the `#BSUB` header.
- `setup` — shell lines run before the model command (module loads, conda).
- `parameters` — only keys that exist in the catalog for that model are allowed.
  See them with `python qm_job.py params <model>`.

> The `/work/...` and `/share/...` paths in these examples come from one specific
> cluster. Replace them with the paths on your own cluster before submitting.
