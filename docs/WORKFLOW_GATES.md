# Workflow connections and result gates

状态：活跃

最后核验：2026-09-08（软件实现与合成测试）

权威范围：工作流连线、逐次结果门控、脚本辅助与迁移工具。

数据来源：版本化代码、自动化测试、隔离 PostgreSQL 和运行镜像验证。

替代关系：新增使用及部署指南；验证问题清单见 [Workflow gates review](WORKFLOW_GATES_REVIEW.md)。

A connection is an executable input binding. Drag a named output handle to a compatible input, or select a node and use **Connect previous / Connect next**. **Add next node** opens the node builder and then the connection picker. The server checks port compatibility, exclusive inputs and DAG cycles and saves the connection and bindings together. Moving a node only changes layout.

Click the badge on an arrow to edit ports, remove the connection, configure its gate, inspect evaluation history or select results. Port and rule editing is restricted to drafts; runtime manual selection remains available after submission. A failed save is reported and does not create a local-only execution edge.

## Output standards and release modes

The upstream node's **Output standard** applies before every outgoing branch's own rules. Branch Top N is applied to the survivors of the upstream standard. Each branch keeps an independent result selection.

- **Automatic:** apply conditions, optional script, ranking and Top N, then release survivors.
- **Manual:** choose from valid output records (the upstream standard still applies).
- **Screen then review:** apply the rules and choose a subset of qualified results.
- Reference data uses an explicit integrity gate; pure ordering dependencies carry no data.

AND/OR supports `gt`, `gte`, `lt`, `lte`, `eq` and `ne`. Missing or nonfinite metrics do not pass, including within OR. Ranking ties use stable result IDs. No configured automatic candidate rule means submission is blocked; an unconfigured connection never defaults to all results.

All rejected files and decisions are retained. An empty required input skips the dependent branch; empty optional inputs do not prevent other inputs from running. Gate errors require repair/retry and never count as a successful empty result. Waiting for review has no compute deadline. Repeated release requests are idempotent and stale or unqualified selections are rejected.

## Result identity and physical subsets

Collection captures immutable results per job attempt, including source plugin identity, metrics/methods, sequence, related files, and parent/input result IDs. Metrics are not reread from mutable candidate-wide summaries. File selectors are applied again when creating downstream artifacts.

Supported selectors cover PDB/mmCIF files, FASTA (`fa`, `faa`, `fas`, `fasta`), CSV/TSV, JSONL and ZIP members containing these formats. Tables require `result_id`, `candidate_key`, `candidate_id`, `id` or `name`. Duplicate record IDs, nested ZIPs, path traversal, unsupported ambiguous bundles and files exceeding 64 MiB cannot silently pass. ProteinMPNN sample headers are normalized to `filename_sampleN`; native input sequences are not design candidates. Output parsers should link their exact structure output indices and provide metric provenance; custom results should declare parent result IDs when the mapping is known.

A filtered FASTA/CSV/archive is a new artifact with `gate_subset` lineage. The input manifest references that artifact, so rejected records cannot reenter through a shared source file. Unknown formats need an explicit result adapter before use.

## Structure checks

DSSP is run from coordinates on the selected design chains/region; receptor chains are not implicitly included. Missing backbone atoms, absent chains and unassigned residues are shown as needing attention; a branch consisting only of these records is blocked for review/retry, rather than skipped as a measured empty result. Calculation failures are also distinct from a measured zero. Insertion-code residues do not split an otherwise contiguous helix.

Presets include multi-helix backbones (default: two H segments, each at least four residues), secondary structure required, and beta structure (two E segments, each at least two residues). Chains/regions and thresholds are visible configuration. The worker records helix count, strand count, structured residue count and helix/strand fractions, together with DSSP version and CCD provenance. These are project screening criteria, not universal protein-quality claims.

The worker image installs DSSP and the **uncompressed** wwPDB chemical component dictionary at build time. `scripts/install_dssp_data.py` validates the compressed download and writes its source SHA256. Runtime structure checks need no network access. A host worker must likewise install `mkdssp` and its CCD; missing runtime dependencies put the gate into error rather than rejecting every candidate.

## Scripts and parameter assistance

The node inspector shows plugin defaults and explicit upstream mappings with current value, proposed value, source and reason. Plugin schemas can declare semantic mappings using:

```json
{"x-bda-upstream-parameters": {"target_parameter": {"port": "input_port", "parameter": "source_parameter"}}}
```

The UI also supports explicit upstream-parameter links and selected-result-count links. Count values are resolved after screening and validated before dispatch. Same-named unrelated fields are not copied automatically. Suggestions become stale when node versions change; applying one does not save or submit the workflow.

Shell/Python imports are parsed statically. The original source, SHA256 and replaced script versions remain in node configuration. Static command and file observations are displayed for review, including uppercase shell variables; dynamic paths still require manual declarations. Recognized literal assignments can be replaced by reviewed node parameter values; dynamic code is preserved and reported. A bound script requires the plugin runtime, ports and output parser. Preview and execution use the same renderer; final runtime parameter resolution re-renders the executable command and records its checksum.

A gate Python script implements:

```python
def screen(records):
    return [
        {"id": r["id"], "passed": r["metrics"].get("score", 0) >= 80,
         "reason": "score threshold"}
        for r in records
    ]
```

It must return exactly one decision per input ID. Associated file **subsets** are available as `files[].content_base64`, with filenames and selectors; decode with Python's `base64` module. The worker sends a length-prefixed input stream to an isolated Docker container (no network, no host mounts or credentials, read-only root, unprivileged user, one CPU, 256 MiB RAM, 32 processes, 60-second limit). The image is selected with `BDA_GATE_SCRIPT_IMAGE`, default `python:3.13-slim`, and must be available on the worker's Docker daemon. The gate task runs on the existing `collect` queue.

Before submitting a scripted gate, preview the exact policy against a completed result set from the same project and plugin. Draft previews do not create compute submissions or release inputs. Changing the script, rules or inherited output standard invalidates the receipt. Save the preview receipt with the policy to enable submission.

## Deployment and existing workflows

1. Back up the database and apply Alembic revision `0056_workflow_gates` before starting the new API/worker image. This adds attempt-specific results, gate evaluations (with project/user/worker RLS) and node configuration; job/node `skipped` statuses are exposed in OpenAPI and the generated client.
2. Deploy the API, workers and frontend together. Keep the worker `collect` queue enabled and prepare the gate script image on its Docker daemon.
3. Audit workflows using the normal administrative database context:

```sh
python backend_v2/scripts/repair_workflow_gates.py --report /path/to/gate-audit.json
python backend_v2/scripts/repair_workflow_gates.py --apply --batch-id gates-v1 --report /path/to/gate-repair.json
```

Use `--project-id UUID` to scope a batch. The tool repairs drafts and derives new drafts from running/completed workflows without submitting or rewriting historical execution. Repeated applications do not duplicate derived drafts. Conflicting layout/execution/binding relationships and unresolved output standards remain explicit report items requiring configuration. No guessed threshold is used for historical data.

To restore an unchanged repaired draft, use `--rollback --apply --batch-id gates-v1 --report ...`. Subsequent edits/submissions prevent rollback; derived drafts and their ancestors are never deleted by this command. Configure outstanding gates and rerun preflight before submitting a repaired workflow.

## Validation

`test_workflow_gates.py` covers subset content, typed connections and cycles, automatic/manual/review flows, duplicate and stale releases, optional versus required empty inputs, inherited standards before branch ranking, static imports and applied parameters, draft previews and script receipts, and idempotent historical repair/rollback. Existing pre-gate jobs retain their legacy binding path. Frontend tests cover named handles, gate states, locked-graph review, qualified-only selection and the registry-control audit.
