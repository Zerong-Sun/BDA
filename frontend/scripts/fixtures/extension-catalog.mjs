// Static manifests with no configured external services.
export const EXTENSION_CATALOG = {
  "version": "1.0",
  "manifest_checksum_sha256": "1d8e14e6b21937d3eaf79a4111295bd248fcda4f4baeba5806208bbefb545b97",
  "assessed_at": "2026-10-11T00:00:00Z",
  "observation_scope": "registry_declarations_only",
  "inventory_truncated": false,
  "extensions": [
    {
      "manifest": {
        "id": "durable-platform",
        "version": "1.0.0",
        "title": "Durable BDA runtime",
        "title_zh": "BDA 持久执行底座",
        "description": "Existing outbox, worker, budget and cancellation contracts.",
        "description_zh": "现有 outbox、任务持久化、预算与取消契约。",
        "function_ids": [
          "F09",
          "F12",
          "F13",
          "F26",
          "F28"
        ],
        "adapter": "builtin",
        "resources": "Existing PostgreSQL, Redis, workers and artifact storage; size by measured load.",
        "license_boundary": "Use BDA and dependency licenses; optional vendors remain separate.",
        "data_boundary": "Existing project and artifact boundaries.",
        "rollout_trigger": "Baseline for every extension; verify actual environment recovery.",
        "effort": "Bundled; deployment acceptance remains site-specific.",
        "sources": [
          "https://github.com/celery/celery"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "durable-platform",
        "state": "built_in",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "recorded",
            "message": "Implementation is bundled with BDA; deployment health and performance are not probed."
          }
        ],
        "blockers": [],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "scientific-methods",
        "version": "1.0.0",
        "title": "Scientific method packages",
        "title_zh": "科学方法包",
        "description": "Versioned bundled methods with frozen inputs and typed deliveries.",
        "description_zh": "有版本与校验值的流程包，冻结方法并验证交付。",
        "function_ids": [
          "F09",
          "F10"
        ],
        "adapter": "builtin",
        "resources": "Configured LLM token budget; packages execute no arbitrary code.",
        "license_boundary": "BDA-authored Apache-2.0 packages; provenance is method reference.",
        "data_boundary": "Uses existing model/project policy; no new destinations.",
        "rollout_trigger": "Evaluate source accuracy and review time before expanding defaults.",
        "effort": "Bundled; scientific evaluation effort depends on task set.",
        "sources": [
          "https://github.com/agentskills/agentskills"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "scientific-methods",
        "state": "built_in",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "recorded",
            "message": "Implementation is bundled with BDA; deployment health and performance are not probed."
          }
        ],
        "blockers": [],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "scientific-models",
        "version": "1.0.0",
        "title": "Registered scientific models",
        "title_zh": "已注册科学模型",
        "description": "Assess exact plugin, site, checkpoint review and current runtime fingerprint.",
        "description_zh": "检查插件版本、站点配置、权重资格与运行指纹。",
        "function_ids": [
          "F12",
          "F14",
          "F15",
          "F16"
        ],
        "adapter": "model_registry",
        "resources": "Select declared CPU/GPU node; model-specific memory, wall time and input size must be measured.",
        "license_boundary": "Review code and exact weights separately; AF3/Protenix variants and PyRosetta dependencies require specific qualification.",
        "data_boundary": "Model inputs/checkpoints stay within reviewed project/site boundaries.",
        "rollout_trigger": "A named scientific task with baseline, checkpoint identity and a bounded trial budget.",
        "effort": "Planning estimate: 8–16 engineer-person-weeks for a shared GPU service; not a supplier quote.",
        "sources": [
          "https://github.com/jwohlwend/boltz",
          "https://github.com/google-deepmind/alphafold3",
          "https://github.com/bytedance/Protenix",
          "https://github.com/martinpacesa/BindCraft"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "scientific-models",
        "state": "not_installed",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "model_plugin",
            "status": "missing",
            "message": "Select a registered model plugin."
          },
          {
            "id": "compute_node",
            "status": "missing",
            "message": "Select a registered compute node for resource review."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "Select a registered model plugin.",
          "Select a registered compute node for resource review.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "local-inference",
        "version": "1.0.0",
        "title": "Local LLM inference",
        "title_zh": "本地 LLM 推理",
        "description": "Use the existing provider boundary; a served local model must be explicitly declared and tested.",
        "description_zh": "沿用模型服务边界，显式声明并测试自建推理服务。",
        "function_ids": [
          "F09",
          "F28"
        ],
        "adapter": "provider_registry",
        "resources": "GPU capacity, quantization, concurrency and context length benchmark; include standby/operations.",
        "license_boundary": "Serving code and model weights have independent terms.",
        "data_boundary": "Review prompts, traces, endpoint routing and retention; localhost-style names are not evidence of isolation.",
        "rollout_trigger": "API spending/privacy/latency justify operating a model service.",
        "effort": "Planning estimate: 4–8 engineer-person-weeks plus measured GPU and operations costs.",
        "sources": [
          "https://github.com/vllm-project/vllm"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "local-inference",
        "state": "not_installed",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "provider",
            "status": "missing",
            "message": "Select a registered local model provider."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "Select a registered local model provider.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "durable-pipelines",
        "version": "1.0.0",
        "title": "Nextflow / Temporal pipelines",
        "title_zh": "Nextflow / Temporal 管线",
        "description": "Future adapter for long-running scientific pipelines and cross-service recovery.",
        "description_zh": "未来的长期科学管线与跨服务恢复适配。",
        "function_ids": [
          "F12",
          "F13",
          "F26"
        ],
        "adapter": "planned",
        "resources": "Workflow service/worker capacity, scheduler integration and durable storage.",
        "license_boundary": "Review engine and bundled pipeline/container licenses separately.",
        "data_boundary": "Map external workflow IDs and lineage to existing project/workflow/artifact IDs.",
        "rollout_trigger": "Measured multi-day recovery complexity exceeds the existing worker model.",
        "effort": "Planning estimate: 12–24 engineer-person-weeks; integrate one bounded pipeline first.",
        "sources": [
          "https://github.com/nextflow-io/nextflow",
          "https://github.com/temporalio/temporal"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "durable-pipelines",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "multimodal-data",
        "version": "1.0.0",
        "title": "Multimodal data platform",
        "title_zh": "多模态数据平台",
        "description": "Future indexed data catalog for large sequence, image and assay collections.",
        "description_zh": "面向大规模序列、图像与实验数据的目录与索引。",
        "function_ids": [
          "F07",
          "F21",
          "F27"
        ],
        "adapter": "planned",
        "resources": "Storage/ingest bandwidth, indexing workers and backup/retention capacity.",
        "license_boundary": "Review datasets, schemas, annotation and infrastructure licenses.",
        "data_boundary": "Project ownership, provenance, consent/contract scope and retention must survive import.",
        "rollout_trigger": "Real multi-assay datasets exceed current artifact discovery/quality workflows.",
        "effort": "Planning estimate: 8–16 engineer-person-weeks plus data curation and storage.",
        "sources": [
          "https://github.com/laminlabs/lamindb"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "multimodal-data",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "robotic-assay",
        "version": "1.0.0",
        "title": "Robotic assay execution",
        "title_zh": "机器人实验执行",
        "description": "Future single-device, single-assay adapter with real site calibration and recovery.",
        "description_zh": "先验证单设备、单实验方法的标定、执行和恢复。",
        "function_ids": [
          "F23",
          "F24",
          "F26"
        ],
        "adapter": "planned",
        "resources": "Physical equipment, consumables, calibration, onsite operator and maintenance.",
        "license_boundary": "Review robot SDK, device/vendor contract and assay/IP terms.",
        "data_boundary": "Define sample identity, instrument traces, lab access and vendor data scope.",
        "rollout_trigger": "A stable repetitive assay and onsite owner justify hardware integration.",
        "effort": "Planning estimate: 12–30 engineer-person-weeks per initial assay; hardware and consumables require quotes.",
        "sources": [
          "https://github.com/PyLabRobot/pylabrobot",
          "https://github.com/Opentrons/opentrons"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "robotic-assay",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "physics-validation",
        "version": "1.0.0",
        "title": "Physics and multi-fidelity validation",
        "title_zh": "物理模拟与多精度验证",
        "description": "Future reproducible simulation service compared with simpler baselines.",
        "description_zh": "与简单基线对照的可重放模拟服务。",
        "function_ids": [
          "F15",
          "F16",
          "F17"
        ],
        "adapter": "planned",
        "resources": "CPU/GPU ensemble runs, simulation storage and domain expertise.",
        "license_boundary": "Force-field, parameterization and model/component terms may differ.",
        "data_boundary": "Freeze starting structures, force fields, seeds, environments and data ownership.",
        "rollout_trigger": "A decision repeatedly depends on effects that current empirical scores miss.",
        "effort": "Planning estimate: 12–24 engineer-person-weeks plus measured simulation cost.",
        "sources": [
          "https://github.com/openmm/openmm"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "physics-validation",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "model-finetuning",
        "version": "1.0.0",
        "title": "Domain model fine-tuning",
        "title_zh": "领域模型微调",
        "description": "Future training/evaluation pipeline with a protected holdout and rollback.",
        "description_zh": "带独立测试集与回滚的训练、评测流程。",
        "function_ids": [
          "F14",
          "F25",
          "F28"
        ],
        "adapter": "planned",
        "resources": "Curated data, distributed GPU time, evaluation labor and checkpoint storage.",
        "license_boundary": "Training data, base weights, derivatives and served outputs each need review.",
        "data_boundary": "Avoid cross-project leakage; record data eligibility and exact training snapshot.",
        "rollout_trigger": "Frozen-feature baselines plateau and a sufficient authorized dataset exists.",
        "effort": "Planning estimate: 20–40+ engineer-person-weeks; compute depends on pilot measurements.",
        "sources": [
          "https://github.com/huggingface/peft",
          "https://github.com/Biohub/esm"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "model-finetuning",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "foundation-pretraining",
        "version": "1.0.0",
        "title": "Foundation model pretraining",
        "title_zh": "基础模型预训练",
        "description": "Future feasibility program; no training adapter is shipped.",
        "description_zh": "先开展可行性研究，目前未提供训练适配器。",
        "function_ids": [
          "F14",
          "F25",
          "F31"
        ],
        "adapter": "planned",
        "resources": "Large licensed datasets, multi-node GPUs, training reliability and dedicated research team.",
        "license_boundary": "Dataset collection, base code, redistribution and resulting weights need separate terms.",
        "data_boundary": "Data eligibility, duplicates, contamination, provenance and deletion requirements must be designed first.",
        "rollout_trigger": "Unique defensible data and validated business/scientific need exceed existing models.",
        "effort": "Feasibility estimate: 4–8 engineer-person-weeks; total training cost deliberately unpriced until measured.",
        "sources": [
          "https://github.com/NVIDIA/Megatron-LM"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "foundation-pretraining",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "external-agents",
        "version": "1.0.0",
        "title": "External agent collaboration",
        "title_zh": "外部 Agent 协作",
        "description": "Future A2A adapter for an actual external collaborator.",
        "description_zh": "面向真实外部协作方的 A2A 适配。",
        "function_ids": [
          "F11",
          "F13",
          "F28"
        ],
        "adapter": "planned",
        "resources": "Identity federation, durable messaging, quotas and failure/replay handling.",
        "license_boundary": "Review protocol implementation and each remote service agreement.",
        "data_boundary": "Explicit delegated scopes, project boundaries, egress and audit; no transitive authority.",
        "rollout_trigger": "A named external team/service needs a durable collaborative task protocol.",
        "effort": "Planning estimate: 6–12 engineer-person-weeks plus partner integration.",
        "sources": [
          "https://github.com/a2aproject/A2A"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "external-agents",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "collaborative-canvas",
        "version": "1.0.0",
        "title": "Collaborative research canvas",
        "title_zh": "协作研究画布",
        "description": "Future shared editing tied to versioned research decisions.",
        "description_zh": "与版本化研发决策关联的协作编辑。",
        "function_ids": [
          "F03",
          "F29"
        ],
        "adapter": "planned",
        "resources": "WebSocket/presence service, concurrency, revision storage and offline conflict handling.",
        "license_boundary": "Some canvas libraries require production licenses; assess exact package/version.",
        "data_boundary": "Presence, edits and exported evidence must follow project access control.",
        "rollout_trigger": "Observed collaboration friction justifies shared editing beyond existing decision views.",
        "effort": "Planning estimate: 4–8 engineer-person-weeks plus chosen production license.",
        "sources": [
          "https://github.com/tldraw/tldraw",
          "https://github.com/yjs/yjs"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "collaborative-canvas",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    },
    {
      "manifest": {
        "id": "evaluation-observability",
        "version": "1.0.0",
        "title": "Scientific evaluation and traces",
        "title_zh": "科研评测与追踪扩展",
        "description": "Future cross-system benchmark/trace export beyond existing business audit.",
        "description_zh": "在已有业务审计基础上扩展跨系统评测和追踪。",
        "function_ids": [
          "F09",
          "F28",
          "F31"
        ],
        "adapter": "planned",
        "resources": "Trace/evaluation storage, redaction, benchmark maintenance and reviewer time.",
        "license_boundary": "Core/enterprise/hosted observability terms differ; review selected components.",
        "data_boundary": "Never export credentials or raw private project data by default; allowlist trace fields.",
        "rollout_trigger": "Evidence fidelity and cost regressions need a repeatable multi-provider comparison.",
        "effort": "Scope one evaluator first; estimate after representative dataset and retention requirements.",
        "sources": [
          "https://github.com/langfuse/langfuse",
          "https://github.com/promptfoo/promptfoo",
          "https://github.com/UKGovernmentBEIS/inspect_ai"
        ],
        "requirements": [
          {
            "id": "runtime",
            "title": "Executable adapter and recovery",
            "title_zh": "执行适配与恢复",
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof."
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits."
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope."
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria."
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately."
          }
        ]
      },
      "assessment": {
        "id": "evaluation-observability",
        "state": "planned",
        "ready_for_trial": false,
        "scientific_validation": "not_assessed",
        "checks": [
          {
            "id": "adapter",
            "status": "blocked",
            "message": "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it."
          },
          {
            "id": "license_review",
            "status": "missing",
            "message": "Supply a reviewed code/weights/dependency license reference."
          },
          {
            "id": "data_review",
            "status": "missing",
            "message": "Supply the data boundary and retention review reference."
          },
          {
            "id": "validation_plan",
            "status": "missing",
            "message": "Supply the scoped benchmark/acceptance plan reference."
          },
          {
            "id": "budget_review",
            "status": "missing",
            "message": "Supply the reviewed labor/compute/experiment budget reference."
          }
        ],
        "blockers": [
          "No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.",
          "Supply a reviewed code/weights/dependency license reference.",
          "Supply the data boundary and retention review reference.",
          "Supply the scoped benchmark/acceptance plan reference.",
          "Supply the reviewed labor/compute/experiment budget reference."
        ],
        "warnings": [
          "Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.",
          "Supplied review references are declarations, not independently verified documents or spending approvals."
        ],
        "selected_model": null
      }
    }
  ],
  "models": [],
  "compute_nodes": [],
  "providers": []
}
