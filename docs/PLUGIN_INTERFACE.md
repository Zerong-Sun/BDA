# Plugin interface

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

How to make a new model or method runnable in the workbench.

A plugin is a row in `model_plugins`. Registering one requires no backend code: the
platform reads its declarations to validate parameters, wire workflow edges, render the
submitted script, and interpret its outputs.

## 1. Declare the plugin

`POST /api/v2/registry/model-plugins`

```json
{
  "plugin_key": "ProteinMPNN",
  "plugin_version": "1.0.0",
  "name": "ProteinMPNN",
  "runtime_mode": "container",
  "container_image": "ghcr.io/example/proteinmpnn:1.0.0",
  "command": "run_mpnn.sh --num_seq_per_target ${num_seq}",
  "parameter_schema": {
    "type": "object",
    "properties": {"num_seq": {"type": "integer", "minimum": 1, "maximum": 64}},
    "required": ["num_seq"]
  },
  "input_ports": [
    {
      "name": "backbone",
      "kind": "protein_structure",
      "accepts": ["backbone_set", "target_structure"],
      "required": true,
      "multiple": true,
      "description": "Backbones to design sequences for"
    }
  ],
  "output_ports": [
    {
      "name": "sequences",
      "kind": "protein_sequence",
      "artifact_type": "sequence_set",
      "filename_glob": "*.fa",
      "description": "Designed sequences"
    }
  ],
  "resources": {"cpus": 4, "memory_gb": 32, "gpu": true, "walltime_minutes": 120},
  "output_parser": "proteinmpnn_fasta"
}
```

`plugin_key` + `plugin_version` is unique. Submitting a workflow snapshots the whole
declaration (with a checksum) onto the job, so editing a plugin never changes what a
past run did.

### runtime_mode

| mode | `container_image` means | Use when |
|---|---|---|
| `container` | image reference | Docker / Kubernetes backends |
| `module` | module name, `module load <name>` is emitted | HPC sites using environment modules |
| `conda` | env name, `conda activate <name>` is emitted | HPC sites using conda |
| `script` | unused | The command is fully self-contained |

An explicit `runtime_setup` list overrides the mode default entirely. It is needed when a
conda installation belongs to another account and is not on PATH, so
`conda shell.bash hook` would fail and the profile must be sourced by absolute path:

```json
"runtime_setup": [
  "source /work/other-group/miniconda3/etc/profile.d/conda.sh",
  "conda activate /work/other-group/miniconda3/envs/model",
  "export DEPENDENCY_DIR=/work/other-group/software/dep"
]
```

These lines are declared at registration, not by workflow authors.

This exists because most LSF sites do not run Docker; declaring `container` there would
make `container_image` meaningless.

### Ports

Ports are what make edges type-checkable and let one node consume another's output.

- `kind` — semantic type. Two ports connect only if their `kind` matches. Valid values
  are in `PORT_KINDS` (`backend_v2/app/registry/ports.py`); add one there if nothing fits.
- `accepts` (input) — allowlist of `artifact_type`. Empty means any artifact of the
  right `kind`.
- `artifact_type` (output) — what the produced artifact is registered as.
- `content_types` is **advisory only**. Browsers mis-sniff scientific formats (real
  `.pdb` uploads in this deployment carry `application/vnd.palm`), so compatibility is
  never gated on it.

### Alternative inputs

Some models accept the same data through more than one route. Give those ports a shared
`exclusive_group`: at most one may be bound, and if any member is `required` then exactly
one must be.

```json
"input_ports": [
  {"name": "pdb_path",   "kind": "protein_structure", "required": true,
   "exclusive_group": "backbone_source"},
  {"name": "jsonl_path", "kind": "params",            "required": true,
   "exclusive_group": "backbone_source"}
]
```

Without this, both ports have to be optional and a node with neither passes preflight and
fails on the cluster instead. The binding panel clears the other alternatives when one is
chosen, so an invalid pair cannot be authored in the first place.

Input port names are also the staged directory names below `BDA_INPUT_DIR`. A command
must read the exact ports it declares. The built-in scientific plugins use these
contracts:

- ProteinMPNN accepts exactly one of `pdb_path` (`$BDA_INPUT_DIR/pdb_path`) or
  `jsonl_path` (`$BDA_INPUT_DIR/jsonl_path`). Its fixed-position parameter guard applies
  to either source mode.
- Rosetta reads structures from `s` (`$BDA_INPUT_DIR/s`).
- superfold accepts exactly one of `structures` (`$BDA_INPUT_DIR/structures`) or
  `sequences` (`$BDA_INPUT_DIR/sequences`). The first consumes a structure-producing
  node; the second consumes a sequence-producing node such as ProteinMPNN.

Validation reports structural problems into `validation_status` / `validation_errors`:

```
POST /api/v2/registry/model-plugins/{id}/validations
```

A plugin whose status is not `valid` produces a preflight warning.

## 2. Wire it into a workflow

Each node binds every required input port, either to a project artifact or to an
upstream node's output port:

```json
{
  "key": "mpnn",
  "node_type": "model",
  "model_plugin": "ProteinMPNN",
  "model_plugin_id": "…",
  "parameters": {"num_seq": 8},
  "input_bindings": [
    {"port": "pdb_path", "source": "upstream", "from_node": "rfd", "from_port": "backbones"}
  ]
}
```

`{"port": "pdb_path", "source": "artifact", "artifact_id": "…"}` binds a specific file
instead.

Every upstream input binding is checked directly against the source and target plugin
ports, whether or not its graph edge names ports. Edges may also carry `source_port` /
`target_port`; those explicit ports are checked as well. Edges without ports otherwise
express ordering only.

`GET /api/v2/workflow-runs/{id}/preflight` reports every blocker. Submission enforces
the same checks, so a workflow that preflights clean is exactly one that will submit.

## 3. The runtime contract

The job receives two environment variables:

- `BDA_INPUT_MANIFEST_URL` — presigned GET for the input manifest
- `BDA_OUTPUT_MANIFEST_URL` — presigned PUT for the output manifest

URL lifetime covers the job's whole deadline, so a job that pends for hours in a queue
can still fetch its inputs when it starts.

Input manifest:

```json
{
  "schema_version": "1",
  "parameters": {"num_seq": 8},
  "inputs": [
    {
      "port": "pdb_path",
      "artifact_id": "…",
      "filename": "design_0.pdb",
      "object_key": "projects/…/sha256/…",
      "content_type": "chemical/x-pdb",
      "checksum_sha256": "…",
      "size_bytes": 12345,
      "url": "https://…"
    }
  ]
}
```

The runner writes an output manifest listing what it produced:

```json
{
  "schema_version": "1",
  "outputs": [
    {
      "object_key": "jobs/<job_id>/attempt-1/outputs/designs.fa",
      "filename": "designs.fa",
      "content_type": "text/x-fasta",
      "artifact_type": "sequence_set",
      "port": "sequences",
      "checksum_sha256": "…",
      "size_bytes": 2048
    }
  ]
}
```

`object_key` must start with `jobs/<job_id>/attempt-<n>/outputs/`; checksums are
re-verified on collection. `port` is optional — when omitted, the port is inferred from
`artifact_type` and `filename_glob`.

Preview the exact script before running anything:

```
POST /api/v2/workflow-nodes/{node_id}/script-previews  {"compute_backend": "lsf"}
```

This renders through the same code path the adapter uses, so the preview is what runs.

## 3b. Cluster staging modes

`BDA_V2_LSF_STAGING_MODE` decides how data reaches and leaves a compute node.

### `ssh` (default)

The API stages inputs onto the shared filesystem over SFTP and retrieves outputs the
same way. **The job needs no network access and the cluster needs no software
installed** — the output manifest is generated by a snippet inlined into the submit
script, so onboarding a cluster requires only SSH access.

This is the default because compute nodes commonly have no route to the object store.

The job sees:

| Variable | Meaning |
|---|---|
| `BDA_REMOTE_DIR` | Per-attempt working directory |
| `BDA_INPUT_DIR` | Staged inputs, one subdirectory per port |
| `BDA_INPUT_MANIFEST` | Local path to the input manifest |
| `BDA_OUTPUT_DIR` | Where to write outputs (already created) |

A bound input on port `backbone` arrives at `$BDA_INPUT_DIR/backbone/<filename>`.

Write outputs under a directory named after the output port to have them typed
automatically:

```bash
mkdir -p "$BDA_OUTPUT_DIR/designs"
run_model.sh --out "$BDA_OUTPUT_DIR/designs"
```

Files under `outputs/designs/` are collected as the `designs` port and registered with
that port's `artifact_type`. Checksums are computed on the node and re-verified after
transfer; a mismatch fails collection.

### `presigned`

The original contract from section 3: the job fetches `BDA_INPUT_MANIFEST_URL` and
uploads to `BDA_OUTPUT_MANIFEST_URL` itself. Use it only where compute nodes really can
reach the object store.

### Network requirements

Only one direction is needed: **API/worker → cluster over SSH**. The cluster never
connects back. Verify with `backend_v2/scripts/verify_lsf_e2e.py`.

Note that the worker process must itself have a route to the cluster. If that route is a
VPN on the host, a containerised worker will not inherit it.

## 4. Output parsers (optional)

By default (`manifest_metadata`) the platform reads `metadata.candidate` and
`metadata.experiment_result` from each output entry — the runner declares its own
results.

To read a model's *native* output instead, register a parser:

```python
# backend_v2/app/compute/parsers/my_model.py
from .base import ParseContext, ParsedCandidate, ParsedOutputs, register_parser

@register_parser("my_model")
def parse(ctx: ParseContext) -> ParsedOutputs:
    for output in ctx.outputs:
        raw = ctx.read_bytes(output["object_key"])
        ...
    return ParsedOutputs(candidates=[...], results=[...], warnings=[...])
```

Import it in `parsers/__init__.py` and set `"output_parser": "my_model"`.
`backend_v2/app/compute/parsers/proteinmpnn.py` is a worked example that reads
ProteinMPNN's FASTA score headers.

## 5. Adding a compute backend

`adapter_for` resolves from a registry, so a scheduler can be added without editing the
compute module:

```python
from backend_v2.app.compute.adapters import register_adapter

class SlurmAdapter:
    def ensure_submitted(self, job) -> str: ...
    def status(self, job, external_id): ...
    def cancel(self, external_id) -> bool: ...
    def collect(self, job, external_id) -> list[dict]: ...

register_adapter("slurm", SlurmAdapter)
```

The backend name is then accepted by `POST /workflow-runs/{id}/submissions`.

## 6. SUSTech QM cluster runbooks

Every registered model-plugin key has a dated cluster runbook under
[`qm-scripts/plugins/`](../qm-scripts/plugins/README.md). The runbooks document LSF
resources, environment setup, plugin-specific review rules and source-backed execution
observations. They complement, but do not replace, the executable `ModelPlugin`
snapshot used for submission.

A historical observation is deliberately kept separate from current runtime proof.
After a command, port, resource, environment or output contract changes, only evidence
recorded against the matching declaration fingerprint may set runtime validation to
`proven`.
