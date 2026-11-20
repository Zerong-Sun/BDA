// Static manifests with no configured external services.
export const EXTENSION_CATALOG = {
  "version": "1.0",
  "manifest_checksum_sha256": "76c24c461d8f358644b5dc3fed76bbfa77a89efe00f9cf57d7ed4dcdad73eca2",
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "沿用 PostgreSQL、Redis、任务进程与制品存储；按实测负载配置容量。",
        "license_boundary_zh": "遵循 BDA 及依赖许可；可选供应商另行审核。",
        "data_boundary_zh": "沿用项目和制品的数据边界。",
        "rollout_trigger_zh": "作为所有扩展的基础，需验证实际环境的故障恢复。",
        "effort_zh": "已内置；部署验收仍按具体站点开展。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "使用已配置的模型令牌预算；方法包不执行任意代码。",
        "license_boundary_zh": "BDA 编写的方法包采用 Apache-2.0；来源记录用于方法参考。",
        "data_boundary_zh": "沿用现有模型与项目策略，不增加出站目的地。",
        "rollout_trigger_zh": "扩展默认方法前，先评估来源准确性和复核耗时。",
        "effort_zh": "已内置；科学评测工作量取决于任务集合。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "选择已声明的 CPU/GPU 节点；逐模型实测内存、运行时长与输入规模。",
        "license_boundary_zh": "代码与具体权重分别审核；AF3/Protenix 变体及 PyRosetta 依赖需要专门资格审核。",
        "data_boundary_zh": "模型输入与权重保留在已审核的项目和站点边界内。",
        "rollout_trigger_zh": "明确科学任务、基线、权重身份和有上限的试验预算。",
        "effort_zh": "规划估算：共享 GPU 服务需 8–16 工程人周；不是供应商报价。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "评测 GPU 容量、量化、并发与上下文长度，并计入待机及运维。",
        "license_boundary_zh": "推理服务代码与模型权重具有独立许可条款。",
        "data_boundary_zh": "审核提示词、追踪记录、端点路由和保留策略；本地主机名称不证明数据隔离。",
        "rollout_trigger_zh": "API 开销、隐私或延迟需求足以支持自建模型服务。",
        "effort_zh": "规划估算：4–8 工程人周，另加实测 GPU 和运维成本。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "工作流服务与任务进程容量、调度器集成及持久存储。",
        "license_boundary_zh": "分别审核引擎和配套管线、容器的许可。",
        "data_boundary_zh": "将外部工作流标识和谱系映射至现有项目、工作流及制品标识。",
        "rollout_trigger_zh": "实测的多日任务恢复复杂度已超出现有任务进程模型。",
        "effort_zh": "规划估算：12–24 工程人周；先接入一条范围明确的管线。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "存储与导入带宽、索引任务进程，以及备份和数据保留容量。",
        "license_boundary_zh": "审核数据集、数据结构、标注与基础设施许可。",
        "data_boundary_zh": "导入后仍须保留项目归属、来源、同意或合同范围及保留规则。",
        "rollout_trigger_zh": "真实多测定数据已超出现有制品检索和质量工作流的能力。",
        "effort_zh": "规划估算：8–16 工程人周，另加数据整理和存储成本。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "实体设备、耗材、校准、现场操作人员与维护。",
        "license_boundary_zh": "审核机器人 SDK、设备供应商合同及测定和知识产权条款。",
        "data_boundary_zh": "明确样本身份、仪器记录、实验室访问权限和供应商数据范围。",
        "rollout_trigger_zh": "稳定重复的测定流程和现场负责人足以支持硬件集成。",
        "effort_zh": "规划估算：首个测定需 12–30 工程人周；硬件和耗材需另行报价。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "CPU/GPU 多次模拟、模拟数据存储与领域专业知识。",
        "license_boundary_zh": "力场、参数化方法及模型组件的许可可能不同。",
        "data_boundary_zh": "冻结初始结构、力场、随机种子、环境和数据归属。",
        "rollout_trigger_zh": "决策反复依赖现有经验评分无法反映的效应。",
        "effort_zh": "规划估算：12–24 工程人周，另加实测模拟成本。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "整理后的数据、分布式 GPU 时间、评测人员与权重存储。",
        "license_boundary_zh": "训练数据、基础权重、衍生模型及服务输出均须分别审核。",
        "data_boundary_zh": "防止跨项目泄漏；记录数据使用资格和精确训练快照。",
        "rollout_trigger_zh": "冻结特征基线已达到瓶颈，且有足量已授权数据。",
        "effort_zh": "规划估算：20–40+ 工程人周；计算成本由试点测量确定。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "大规模许可数据、多节点 GPU、可靠训练系统和专职研究团队。",
        "license_boundary_zh": "数据收集、基础代码、再分发和训练后权重须分别约定条款。",
        "data_boundary_zh": "先设计数据使用资格、去重、污染检查、来源及删除要求。",
        "rollout_trigger_zh": "独有且可持续的数据和已验证的业务、科学需求超出现有模型能力。",
        "effort_zh": "可行性估算：4–8 工程人周；训练总成本待测量后估算。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "联合身份、持久消息、配额及失败和重放处理。",
        "license_boundary_zh": "审核协议实现和每个远程服务协议。",
        "data_boundary_zh": "显式限定委托权限、项目边界、出站和审计；权限不得传递扩张。",
        "rollout_trigger_zh": "明确的外部团队或服务需要持久协作任务协议。",
        "effort_zh": "规划估算：6–12 工程人周，另加合作方集成工作。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "WebSocket 与在线状态服务、并发、版本存储和离线冲突处理。",
        "license_boundary_zh": "部分画布库需要生产许可；审核具体软件包与版本。",
        "data_boundary_zh": "在线状态、编辑与证据导出均须遵循项目访问控制。",
        "rollout_trigger_zh": "已观察到的协作困难，足以支持在现有决策视图之外增加共同编辑。",
        "effort_zh": "规划估算：4–8 工程人周，另加所选生产许可费用。"
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
            "boundary": "Implementation plus scoped failure/restart tests; configuration alone is not deployment proof.",
            "boundary_zh": "需要可执行适配及限定范围的故障、重启测试；仅有配置不证明部署可用。"
          },
          {
            "id": "license",
            "title": "Code, weights and dependency terms",
            "title_zh": "代码、权重及依赖许可",
            "boundary": "Review exact version/checkpoint and intended use, including commercial limits.",
            "boundary_zh": "审核具体版本、权重与预期用途，包括商业使用限制。"
          },
          {
            "id": "data",
            "title": "Data isolation and egress",
            "title_zh": "数据隔离与出站",
            "boundary": "Define project isolation, retention, destinations and approved data scope.",
            "boundary_zh": "明确项目隔离、数据保留、目的地和获准使用的数据范围。"
          },
          {
            "id": "validation",
            "title": "Acceptance evidence",
            "title_zh": "验收证据",
            "boundary": "Frozen benchmark with baseline, failure cases and task-specific acceptance criteria.",
            "boundary_zh": "使用固定基准、对照、失败案例及任务专属验收标准。"
          },
          {
            "id": "budget",
            "title": "Resource and operating budget",
            "title_zh": "资源与运行预算",
            "boundary": "Estimate engineering, compute, licenses, experiments and ongoing operations separately.",
            "boundary_zh": "分别估算工程、计算、许可、实验及持续运维成本。"
          }
        ],
        "resources_zh": "追踪与评测存储、脱敏、基准维护及复核人员时间。",
        "license_boundary_zh": "核心版、企业版和托管服务条款不同；审核选定组件。",
        "data_boundary_zh": "默认不得导出凭据或原始私有项目数据；仅允许明确批准的追踪字段。",
        "rollout_trigger_zh": "证据准确性和成本退化需要可重复的多供应商比较。",
        "effort_zh": "先限定一个评测器；确定代表性数据集和保留要求后再估算。"
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
