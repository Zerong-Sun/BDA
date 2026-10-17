# Extension readiness and model qualification

状态：活跃

最后核验：2026-10-11（UTC；登记检查、资格预检与自动化测试）

权威范围：2.6 开发分支的扩展中心、只读配置评估及模型权重用途资格。

数据来源：扩展清单、登记模型、运行指纹与本文列明的测试；未来方案标明来源和规划估算。

替代关系：补充模型插件及工作流说明，不替代真实环境、许可复核与科研验收。

Status: implemented for the 2.6 development branch. This is an inspection and
qualification layer; future adapters are explicitly not installed or executable.

## Extension center

The authenticated `/extensions` page combines the versioned bundled integration
catalog with current model, compute-node and local-provider registry declarations.
It distinguishes built-in implementations, records needing configuration/review,
disabled records, absent registrations, and planned integrations. It does not
probe hosts, read credentials, load weights, call an inference endpoint, create
jobs, install packages, connect robots or approve spending.

The 13 entries cover existing durable execution, scientific method packages,
registered scientific models, local LLM hosting, Nextflow/Temporal pipelines,
multimodal data, robot assays, physics simulation, fine-tuning, foundation model
pretraining, external agent collaboration, collaborative canvases, and evaluation
and trace extensions. Each has resource/license/data requirements, a rollout
trigger, references and planning-cost boundaries. Labor ranges are estimates,
not measured delivery times or supplier quotes. Compute/hardware costs must be
measured or quoted for the intended workload.

The source is `backend_v2/app/registry/extension_manifests.json`. Pydantic validates
its shape and IDs. The API includes a catalog version, SHA-256, assessment time
and `observation_scope=registry_declarations_only`. Inventory lists cap at 500
per resource kind and disclose truncation.

## Read-only assessments

- `GET /api/v2/registry/extensions`: authenticated catalog and public readiness
  summaries. Endpoints, commands, environment values, host paths and credential
  references are excluded from these summaries.
- `POST /api/v2/registry/extensions/{id}/assessments`: administrator-only, bounded
  input; compares proposed resource IDs and review references to existing records.
  It creates no persistent record or execution operation. Normal write-mode and
  role gates still apply to this POST.
- `GET /api/v2/registry/model-plugins/{id}/qualification`: authenticated public
  summary of the model's declaration, immutable-manifest and runtime-proof state,
  plus checkpoint/use-review gaps.

The assessment never infers that a URL is local hosting. A local inference
provider must explicitly declare `config.deployment_kind="local"`; connection,
identity, throughput and data egress still require separate tests. Planned
adapters stay planned even when all proposed review fields are filled.

A registered model can meet controlled-trial prerequisites only when enabled,
declaration-valid, manifest-pinned, backed by a current runtime fingerprint,
qualified for its intended use, and associated with an enabled real backend,
stored healthy node status, resolving runtime and sufficient declared GPU count.
License/data/validation/budget review references must also be supplied. These
references and resource labels remain declarations; their documents and host
capacity are not independently inspected. `scientific_validation` always remains
`not_assessed`. The existing workflow preflight remains authoritative for an
actual submission, including parameters, artifacts, permissions and budget.

## Versioned model/checkpoint use review

The optional `ModelPlugin.resources.scientific_qualification` object stores the
review alongside the executable resource declaration, without a new table.
The `ScientificQualification` Pydantic model in `registry/qualification.py`
defines the full contract. For example (illustrative fields, not an approval):

```json
{
  "schema_version": "1.0",
  "plugin_key": "example-model",
  "plugin_version": "1.0",
  "code_reference": "https://example.org/reviewed-code-version",
  "code_license": "license identifier for this code version",
  "checkpoint_identifier": "exact checkpoint name/version",
  "checkpoint_sha256": "replace with the actual 64-character lowercase SHA-256",
  "checkpoint_license": "terms for these exact weights",
  "license_reference": "https://example.org/exact-checkpoint-terms",
  "license_mode": "restricted",
  "intended_use": "research",
  "allowed_uses": [],
  "review_status": "pending",
  "reviewer": "",
  "reviewed_at": null,
  "expires_at": null,
  "validation_scope": "Named task, inputs and planned acceptance benchmark",
  "limitations": ["No scientific performance claim"]
}
```

The illustrative placeholder hash deliberately cannot pass schema validation.
An approved review needs a reviewer, an aware timestamp and an allowed intended
use. Code and checkpoint licenses are separate. Restricted weights, research-only
terms, auxiliary dependencies and outputs may differ even under the same project
name; use the exact versions' reviewed terms. BDA records a maintainer's review;
it does not infer legal permission from a repository's top-level license.

Registry create/update/deploy validates explicit qualification records. Pinned
plugin resources remain immutable: change the versioned manifest and redeploy
under an appropriate new version to change its qualification. The existing
runtime declaration fingerprint includes resources, so a checkpoint/review change
invalidates old runtime proof. The hash is a recorded checkpoint identity, not
proof that a host loaded that file; actual run validation must establish that.

`model_qualification_issues(plugin)` returns blockers and warnings consumed by
workflow preflight and the same preflight used in `create_submission`:

- Legacy records with no qualification remain warnings for compatibility; this
  does not declare their weights qualified.
- An explicit malformed, pending, rejected, identity-mismatched, future-dated,
  expired, unknown-license or disallowed-use review blocks submission.
- Research-only weights with commercial intended use block even if the
  recorded allowed-use array mistakenly includes commercial use.
- A valid review carries a scope warning; it never replaces runtime, assay or
  prospective scientific validation.

## Validation

`test_extension_readiness.py` covers catalog status from live records, registry
changes, secret/connection-detail redaction, admin assessment permissions,
bounded inputs, no false ready state for planned adapters, site/runtime/GPU
checks and qualification invalidation. `test_model_qualification_submission.py`
checks the actual preflight and submission boundary: legacy records can create
a demo submission with a warning; explicit pending/restricted use creates no
jobs. UI tests cover selection, explicit inspection, reset after config changes,
read-only access and error states. No HPC, GPU, device or paid provider is used
by these tests. Production scientific and infrastructure acceptance remains
site-specific work.
