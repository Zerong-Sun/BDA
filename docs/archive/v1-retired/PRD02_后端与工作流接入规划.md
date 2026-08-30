# BDA Workbench 后端与工作流接入规划

版本：v0.1
日期：2026-06-17
文档类型：后端 PRD / 技术产品规划
适用阶段：Phase 2，真实模型接入、云端计算、文件上传下载与前后端联调
目标读者：后端、前端、算法、计算平台、项目负责人

## 1. 背景与目标

BDA 当前已经具备前端工作流画布、候选展示、结果交付、FastAPI 后端、数据库、模型插件表、任务表、Docker compute adapter 和 RFdiffusion / ProteinMPNN / AlphaFold2 / Rosetta 的容器脚手架。下一阶段的核心不是再做一个单模型网页，而是把多个模型和内部 Mask RGN 统一接入为一个可组合、可追踪、可闭环的设计平台。

本阶段目标：

- 建立统一数据端口，让 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、Mask RGN 只通过标准 artifact contract 交换数据。
- 建立模型插件规范，把每个模型的输入、输出、参数、资源需求、命令模板、版本和注释沉淀到数据库。
- 支持可重排工作流 DAG，例如 RFdiffusion → ProteinMPNN → AlphaFold2 → Rosetta，也支持 ProteinMPNN → RFdiffusion → ProteinMPNN → AlphaFold2 → Rosetta 这类迭代路线。
- 支持闭环回流，把预测、评分、湿实验、失败原因转成下一轮节点输入或约束。
- 补齐前端文件上传、结果下载、日志查看、节点参数编辑和任务状态轮询 API。
- 保留云端服务器 / HPC / GPU Worker 接口，允许本地 demo、Docker、远端 HTTP worker、SSH/Slurm 等模式逐步接入。

## 2. 非目标

- 不在第一轮内重写所有模型源码。
- 不要求所有重 GPU 任务在本地实时完成。
- 不要求一次性支持所有 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta 参数，但必须设计可扩展参数 schema。
- 不把工作流固定成单一路线；后端必须支持 DAG，而不是只支持线性链。
- 不把前端上传的文件直接作为任意 shell 参数使用；所有文件都必须先进入 artifact store 并通过白名单 schema 引用。

## 3. 当前基础

仓库已有能力：

- API：FastAPI，主要接口位于 `/api/v1`。
- 存储：本地 artifacts 目录，后续可切 MinIO。
- 数据库：`projects`、`targets`、`design_tasks`、`workflow_runs`、`workflow_node_runs`、`candidates`、`model_plugins`、`method_plugins`、`server_connections`、`compute_nodes`、`jobs`。
- 计算：`DemoComputeAdapter` 和 `LocalDockerAdapter`。
- 文件：已有 PDB/mmCIF 上传、候选结构下载、项目 delivery zip 下载。
- 模型脚手架：`docker/models/rfdiffusion`、`proteinmpnn`、`alphafold2`、`rosetta`。
- 内部模型：`maskrgnn_clean` 已在仓库内，但还没有被注册为平台插件。

主要缺口：

- `workflow_chain.py` 目前偏线性继承，不能表达任意 DAG 和反馈边。
- job 提交时还没有把 input artifacts mount 到容器，也没有稳定收集 `/output/manifest.json`。
- `model_plugins.parameter_schema_json` 已存在，但还没有形成前端可渲染的字段规范。
- 文件对象缺少统一 artifact 表与 lineage，难以追踪某个 PDB/FASTA/CSV 从哪个节点产生。
- 前端对上传、参数、节点运行、日志、结果文件的 API 契约需要稳定下来。

## 4. 总体架构

推荐采用五层设计：

1. API Gateway：FastAPI 负责权限、项目、文件、工作流、任务、插件和下载。
2. Workflow Orchestrator：根据 DAG、节点状态、输入输出 contract 决定哪些节点可以运行。
3. Plugin Registry：保存每个模型/方法的 schema、默认参数、资源要求、命令模板、镜像/API endpoint。
4. Compute Adapter：屏蔽本地 Docker、远端 Docker、HTTP Worker、SSH/Slurm、Kubernetes 等执行环境。
5. Artifact Store：统一管理上传文件、中间产物、最终交付包、manifest、日志和 lineage。

核心原则：

- 节点之间不直接传路径，传 artifact id。
- 模型容器不依赖 BDA 数据库，只读取 `/input/manifest.json`，写出 `/output/manifest.json`。
- 前端不理解各模型的内部文件路径，只理解 plugin schema、node parameters、artifact list 和 job status。
- 工作流边定义“哪个输出端口连接到哪个输入端口”，后端负责校验兼容性。

## 5. 统一 Artifact Contract

所有输入输出统一为 Artifact 对象。

建议新增 `artifacts` 表：

| 字段 | 说明 |
|------|------|
| `artifact_id` | 全局唯一 ID，例如 `art_...` |
| `project_id` | 所属项目 |
| `workflow_run_id` | 可为空，上传 target 时可能还没有 workflow |
| `node_run_id` | 产生该 artifact 的节点，可为空 |
| `artifact_type` | `structure`、`sequence`、`alignment`、`score_table`、`constraints`、`manifest`、`log`、`report`、`experiment_result` |
| `format` | `pdb`、`mmcif`、`fasta`、`a3m`、`json`、`csv`、`zip` |
| `storage_uri` | `local://...` 或 `s3://...` |
| `display_name` | 前端展示名 |
| `size_bytes` | 文件大小 |
| `checksum` | sha256，用于去重和审计 |
| `metadata_json` | chain、residue_count、model、score columns 等 |
| `created_by` | 上传者或系统 |
| `created_at` | 创建时间 |

Artifact 类型建议：

| 类型 | 常见格式 | 用途 |
|------|----------|------|
| `target_structure` | PDB/mmCIF | 靶点结构 |
| `cleaned_structure` | PDB/mmCIF | 清洗后的靶点 |
| `contig_map` | JSON/TXT | RFdiffusion 约束 |
| `backbone_set` | PDB/mmCIF/ZIP | RFdiffusion 输出骨架 |
| `sequence_set` | FASTA/CSV | ProteinMPNN 或 Mask RGN 输出序列 |
| `predicted_structure` | PDB/mmCIF | AlphaFold2 输出结构 |
| `complex_structure` | PDB/mmCIF | 复合物结构 |
| `score_table` | CSV/JSON | Rosetta、BDA filter、实验评分 |
| `experiment_table` | CSV/XLSX/JSON | 湿实验读数 |
| `delivery_package` | ZIP | 最终交付 |

容器输入 manifest 示例：

```json
{
  "job_id": "job_xxx",
  "project_id": "proj_pd1_0423",
  "node_run_id": "node_xxx",
  "inputs": {
    "target_structure": {
      "artifact_id": "art_target_001",
      "path": "/input/target.pdb",
      "format": "pdb",
      "metadata": {
        "chains": ["A"],
        "epitope_residues": ["A:56", "A:57"]
      }
    }
  },
  "parameters": {
    "num_designs": 100,
    "temperature": 0.1
  }
}
```

容器输出 manifest 示例：

```json
{
  "status": "completed",
  "outputs": {
    "sequence_set": [
      {
        "path": "/output/designed.fasta",
        "format": "fasta",
        "metadata": {
          "count": 100,
          "source_model": "ProteinMPNN"
        }
      }
    ],
    "score_table": [
      {
        "path": "/output/scores.csv",
        "format": "csv"
      }
    ]
  },
  "metrics": {
    "best_score": -12.4,
    "num_candidates": 100
  }
}
```

## 6. 插件规范

每个模型插件都需要一份 manifest，写入 `model_plugins`。同一模型不同版本或不同运行方式作为不同插件版本。

插件字段：

- `model_plugin_id`：例如 `plugin_rfdiffusion_1_1_container`。
- `model_name`：例如 `RFdiffusion`。
- `model_type`：`backbone_generation`、`sequence_design`、`structure_prediction`、`scoring`、`internal_model`。
- `version`：代码或镜像版本。
- `input_schema_json`：输入端口定义。
- `output_schema_json`：输出端口定义。
- `parameter_schema_json`：前端可渲染参数。
- `artifact_schema_json`：文件格式、数量、大小、可预览性。
- `resource_requirement_json`：GPU、CPU、内存、显存、预计运行时间。
- `container_image` / `api_endpoint`：本地容器或远端服务。
- `command_template`：容器内启动命令。
- `citation` / `license`：后续交付和审计需要。

参数 schema 统一格式：

```json
{
  "fields": [
    {
      "key": "num_designs",
      "label": "Number of designs",
      "type": "integer",
      "default": 100,
      "min": 1,
      "max": 10000,
      "help": "生成候选数量。数量越大，运行时间和存储占用越高。",
      "advanced": false
    },
    {
      "key": "temperature",
      "label": "Sampling temperature",
      "type": "number",
      "default": 0.1,
      "min": 0,
      "max": 2,
      "help": "采样随机性。较高值增加多样性，也可能增加低质量候选。",
      "advanced": true
    }
  ]
}
```

前端根据 `type` 渲染控件：

- `integer` / `number`：输入框或 slider。
- `boolean`：toggle。
- `enum`：select 或 segmented control。
- `string`：文本输入。
- `residue_selector`：结构查看器联动选择残基。
- `artifact_ref`：文件选择器。
- `json`：专家模式 JSON 编辑器。

## 7. 第一批插件接口

### 7.1 RFdiffusion

角色：骨架生成 / binder backbone sampling。

输入：

- `target_structure`：PDB/mmCIF。
- `contig_map`：contig 约束。
- `hotspot_residues`：结合热点残基。
- `design_constraints`：binder length、chain、对称性、fixed residues。

输出：

- `backbone_set`：生成的 backbone PDB 集合。
- `score_table`：采样元数据和模型分数。
- `run_manifest`：输出文件索引。

关键参数：

- `num_designs`
- `contig_map`
- `hotspot_residues`
- `binder_length_min`
- `binder_length_max`
- `diffusion_steps`
- `noise_scale_ca`
- `noise_scale_frame`
- `symmetry`
- `random_seed`

### 7.2 ProteinMPNN

角色：给 backbone 设计序列。

输入：

- `backbone_set` 或 `structure`
- `fixed_positions`
- `omit_aas`
- `chain_selection`
- `bias_json`

输出：

- `sequence_set`：FASTA。
- `score_table`：sequence log probability、recovery、per-residue scores。

关键参数：

- `num_seq_per_target`
- `sampling_temperature`
- `backbone_noise`
- `omit_aas`
- `fixed_positions`
- `designed_chains`
- `random_seed`

### 7.3 AlphaFold2

角色：结构预测 / complex confidence。

输入：

- `sequence_set`
- `target_structure` 或 target sequence
- `pairing_config`
- `msa_mode`

输出：

- `predicted_structure`
- `complex_structure`
- `score_table`：pLDDT、pTM、ipTM、PAE、interface pAE。
- `pae_matrix`：JSON/NPY。

关键参数：

- `model_preset`
- `num_recycles`
- `msa_mode`
- `template_mode`
- `pairing_strategy`
- `max_template_date`
- `random_seed`

### 7.4 Rosetta

角色：relax、interface scoring、ddG、clash、buried SASA。

输入：

- `predicted_structure` 或 `complex_structure`
- `score_config`
- `relax_constraints`

输出：

- `relaxed_structure`
- `score_table`
- `interface_metrics`

关键参数：

- `protocol`
- `nstruct`
- `relax_rounds`
- `score_function`
- `interface_chains`
- `ddg_repeats`
- `constraint_weight`

### 7.5 Mask RGN

角色：内部 sequence / graph diffusion 模型，第一阶段作为实验性插件接入。

输入：

- `structure` 或 `backbone_set`
- `mask_positions`
- `task_config`

输出：

- `sequence_set`
- `score_table`
- `embedding` 或中间特征，可选。

关键参数：

- `checkpoint_path`
- `num_samples`
- `mask_ratio`
- `temperature`
- `fixed_positions`
- `random_seed`

接入策略：

- 先封装 `maskrgnn_clean/inference.py` 为标准 runner。
- 将配置文件路径和 checkpoint 路径放入 plugin resource/env，不让前端直接传任意本地路径。
- 输出必须写 `/output/manifest.json`，FASTA 和 CSV 作为 artifact 注册。

## 8. 工作流 DAG 与闭环

工作流必须从线性链升级为 DAG。

建议新增或规范化：

- `workflow_edges` 表：保存 `source_node_run_id`、`source_port`、`target_node_run_id`、`target_port`、`edge_type`。
- `edge_type`：`data`、`control`、`feedback`、`review_gate`。
- 节点可运行条件：所有 required input ports 都有 artifact；依赖节点状态为 completed；人工 review gate 通过。
- 节点重跑策略：修改参数后生成新 job，保留旧 artifact 和 lineage，不覆盖历史结果。

典型路线：

1. Target upload → Clean target → RFdiffusion → ProteinMPNN → AlphaFold2 → Rosetta → BDA filter → Delivery。
2. Target upload → ProteinMPNN redesign → AlphaFold2 → Rosetta。
3. RFdiffusion → ProteinMPNN → AlphaFold2 → failed candidates → constraints → RFdiffusion round 2。
4. Mask RGN → AlphaFold2 → Rosetta → wet-lab feedback → Mask RGN round 2。

闭环对象：

- 成功信号：high pLDDT、low interface PAE、good Rosetta score、BLI positive、SEC monomeric。
- 失败信号：不表达、聚集、不结合、非特异、预测结构差、clash 高。
- 回流形式：`redesign_constraints` artifact，连接到下一轮 RFdiffusion / ProteinMPNN / Mask RGN。

## 9. 后端 API 规划

### 9.1 文件与 Artifact

- `POST /api/v1/artifacts/upload`
  - 上传结构、FASTA、CSV、JSON、ZIP。
  - 参数：`project_id`、`artifact_type`、`display_name`、`metadata_json`。
  - 返回：artifact 对象、preview/download URL。

- `GET /api/v1/artifacts/{artifact_id}`
  - 返回 artifact 元数据。

- `GET /api/v1/artifacts/{artifact_id}/download`
  - 下载原始文件。

- `GET /api/v1/artifacts/{artifact_id}/preview`
  - 返回可预览文本、结构 metadata、表头和前 N 行。

- `POST /api/v1/artifacts/batch-download`
  - 多文件打包下载。

现有 `/targets/upload-pdb` 可以保留为快捷接口，但内部应调用 artifact service。

### 9.2 插件

- `GET /api/v1/model-plugins`
- `GET /api/v1/model-plugins/{plugin_id}`
- `POST /api/v1/model-plugins/{plugin_id}/validate-schema`
- `POST /api/v1/model-plugins/register`
  - admin 使用，读取 manifest JSON 并写数据库。

前端 NodeBuilder 只依赖 plugin schema，不硬编码模型参数。

### 9.3 工作流

- `POST /api/v1/projects/{project_id}/workflow-runs`
- `GET /api/v1/workflow-runs/{workflow_run_id}`
- `GET /api/v1/workflow-runs/{workflow_run_id}/graph`
  - 返回 nodes、edges、artifacts、jobs。

- `PATCH /api/v1/workflow-runs/{workflow_run_id}/graph`
  - 保存前端画布布局和连线。

- `POST /api/v1/workflow-runs/{workflow_run_id}/nodes`
- `PATCH /api/v1/workflow-runs/{workflow_run_id}/nodes/{node_run_id}`
- `DELETE /api/v1/workflow-runs/{workflow_run_id}/nodes/{node_run_id}`

- `POST /api/v1/workflow-runs/{workflow_run_id}/validate`
  - 校验 DAG、端口兼容、参数合法、资源是否可用。

- `POST /api/v1/workflow-runs/{workflow_run_id}/run`
  - 运行全部 ready 节点。

- `POST /api/v1/workflow-runs/{workflow_run_id}/nodes/{node_run_id}/run`
  - 只运行某个节点。

### 9.4 Jobs

- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/logs`
- `GET /api/v1/jobs/{job_id}/events`
- `POST /api/v1/jobs/{job_id}/cancel`
- `POST /api/v1/jobs/{job_id}/retry`

任务状态：

- `queued`
- `staging`
- `running`
- `collecting_outputs`
- `completed`
- `failed`
- `cancelled`
- `blocked`
- `requires_review`

### 9.5 云端服务器与计算节点

已有：

- `GET /api/v1/servers`
- `GET /api/v1/compute-nodes`
- `POST /api/v1/compute-nodes/{id}/health-check`

建议补充：

- `POST /api/v1/servers`
- `PATCH /api/v1/servers/{server_id}`
- `POST /api/v1/servers/{server_id}/test-connection`
- `GET /api/v1/compute-nodes/{compute_node_id}/queue`
- `POST /api/v1/compute-nodes/{compute_node_id}/drain`

云端服务器接口形态：

- HTTP Worker：BDA 后端提交 job spec，worker 拉取 artifacts，运行模型，上传 manifest。
- SSH/Slurm：BDA 后端生成 job bundle，通过 SSH 上传并 `sbatch`，轮询 Slurm 状态。
- Remote Docker：远程 Docker host 运行容器。
- Kubernetes：后续作为 P2。

## 10. 数据库调整建议

P0 必做：

- 新增 `artifacts` 表。
- 新增 `workflow_edges` 表。
- 在 `jobs` 中增加 `parameters_json`、`input_manifest_artifact_id`、`output_manifest_artifact_id`。
- 在 `workflow_node_runs` 中保留 `input_files_json` / `output_files_json` 兼容旧数据，但新逻辑使用 artifact ids。

P1 建议：

- 新增 `artifact_lineage` 表，记录 artifact 从哪些父 artifact 和 job 产生。
- 新增 `plugin_versions` 或保留 `model_plugin_id + version` 的唯一约束。
- 新增 `job_events` 的标准事件类型：`submitted`、`staged`、`started`、`log`、`artifact_created`、`completed`、`failed`。

P2 建议：

- 数据集 registry。
- Benchmark registry。
- 参数 preset 表。
- Workflow template 表。

## 11. 计算执行规范

每个 job 的运行流程：

1. 后端校验节点参数和输入 artifact。
2. 创建 job，状态为 `queued`。
3. Artifact store 准备 job workspace。
4. 写入 `/input/manifest.json`。
5. Compute adapter 提交任务。
6. Worker 运行模型。
7. Worker 将输出写入 `/output`，必须包含 `/output/manifest.json`。
8. 后端轮询状态，进入 `collecting_outputs`。
9. 后端解析 output manifest，注册 artifacts、metrics、candidate records。
10. 更新 node、job、workflow 状态。
11. Orchestrator 检查下游 ready 节点。

容器挂载建议：

- `/input`：只读输入。
- `/output`：输出目录。
- `/work`：临时工作目录，可选。

环境变量：

- `BDA_JOB_ID`
- `BDA_INPUT_MANIFEST=/input/manifest.json`
- `BDA_OUTPUT_DIR=/output`
- `BDA_GPU=1`
- `BDA_PROJECT_ID`

## 12. 前端对接规划

### 12.1 文件上传

前端上传流程：

1. 用户选择 PDB/mmCIF/FASTA/CSV/JSON/ZIP。
2. 前端调用 `POST /artifacts/upload`。
3. 后端返回 artifact metadata。
4. 前端把 artifact 绑定到 target、node input 或实验结果。
5. 结构文件使用 preview URL 给 Mol*；表格文件显示前 N 行预览。

前端需要展示：

- 文件名、类型、大小、上传状态。
- 解析出的 chain、residue_count、sequence_count、table columns。
- 错误原因：格式不支持、文件太大、解析失败、权限不足。

### 12.2 节点参数

NodeBuilder 流程：

1. 拉取 `GET /model-plugins`。
2. 用户选择插件。
3. 前端根据 `parameter_schema_json.fields` 渲染表单。
4. 用户选择输入 artifact 或从上游端口连线。
5. 保存节点参数到 `workflow_node_runs.parameters_json`。
6. 运行前调用 `/workflow-runs/{id}/validate`。

参数分层：

- Basic：常用、安全、有默认值。
- Advanced：专家参数，默认折叠。
- Raw JSON：只给 admin 或 expert mode。

### 12.3 数据下载

下载入口：

- 单个 artifact 下载。
- 节点输出 zip。
- 候选 FASTA/PDB 批量下载。
- 项目 delivery package 下载。
- workflow run 全量导出，包括 graph、parameters、metrics、manifest。

### 12.4 任务状态与日志

前端轮询：

- workflow graph：5-10 秒。
- running job logs：2-5 秒。
- completed job：停止轮询。

展示：

- 节点状态 badge。
- job id、compute node、启动时间、耗时。
- stdout/stderr tail。
- 输出 artifacts 列表。
- 失败原因和 retry 按钮。

## 13. 实施路线

### Milestone 0：文档与接口冻结

交付：

- 本文档评审通过。
- Artifact contract、plugin manifest、job manifest 示例确定。
- 前端和后端确认 API 命名。

验收：

- 能用一个 mock plugin 描述输入、参数、输出，并由前端渲染参数表单。

### Milestone 1：Artifact 中心

交付：

- `artifacts` 表与 migration。
- 通用 `/artifacts/upload`、download、preview、batch-download。
- 现有 `/targets/upload-pdb` 内部改为 artifact。
- 文件 checksum、大小限制、格式白名单。

验收：

- 上传 PDB/mmCIF/FASTA/CSV，前端可拿到 metadata 和下载链接。
- 上传 target 后可以作为工作流节点输入。

### Milestone 2：插件注册与参数 schema

交付：

- 插件 manifest 格式。
- `register_plugins.py` 注册 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、Mask RGN。
- 前端 NodeBuilder 使用 `parameter_schema_json` 动态渲染。

验收：

- 不改前端代码即可增加一个 mock plugin 并显示参数表单。
- 每个参数有 label、default、help、advanced。

### Milestone 3：DAG 工作流与节点运行

交付：

- `workflow_edges` 表。
- `/workflow-runs/{id}/graph` read/write。
- DAG validate。
- 单节点 run。
- ready-node 调度。

验收：

- 可以创建 RFdiffusion → ProteinMPNN → AlphaFold2 → Rosetta。
- 可以创建反馈边并保存。
- 参数变化后重跑节点不会覆盖旧 artifact。

### Milestone 4：容器执行与 manifest 收集

交付：

- Docker adapter mount `/input`、`/output`。
- 写 input manifest。
- 收集 output manifest。
- 注册输出 artifacts。
- 日志和 job events。

验收：

- 四个 stub model 可以真实跑通并产生 artifacts。
- 前端能看到任务状态、日志、输出文件。

### Milestone 5：真实模型最小接入

交付顺序：

1. ProteinMPNN：通常输入输出最清晰，优先打通。
2. Rosetta scoring：用于快速验证结构评分。
3. RFdiffusion：接入 contig/hotspot 参数。
4. AlphaFold2：根据资源情况接本地或远端服务。
5. Mask RGN：作为内部 experimental plugin。

验收：

- 至少一条真实路线能从输入 artifact 生成输出 artifact。
- 每个模型失败时给出可读 error_message。
- 所有模型参数和版本进入 job record。

### Milestone 6：云端服务器

交付：

- HTTP Worker adapter。
- server credential_ref 机制。
- health check。
- 远端 artifact pull/push。

验收：

- 后端可以把 job 提交到云端 worker。
- 本地前端无需知道远端路径，只通过 BDA API 看状态和下载结果。

## 14. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 各模型输入输出差异大 | 工作流难组合 | 用 artifact type + port schema 统一，不让节点互相知道内部路径 |
| 参数过多 | 前端复杂、用户难用 | Basic / Advanced / Raw JSON 分层 |
| GPU 任务运行慢 | 前端等待差 | 异步 job + 日志 + artifact 增量显示 |
| 云端路径暴露 | 安全风险 | 前端只看 artifact id 和 download URL |
| 重跑覆盖历史结果 | 复现失败 | artifact immutable，重跑生成新 job 和新 artifacts |
| 模型 license/citation 混乱 | 交付风险 | plugin registry 强制记录 license/citation |
| 失败日志不可读 | 调试成本高 | runner 捕获异常并写 structured error manifest |

## 15. 成功标准

第一阶段成功标准：

- 用户能上传 target structure，并在 workflow 节点里选择它作为输入。
- 用户能在前端选择 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、Mask RGN，并看到可编辑参数和注释。
- 用户能自由连接节点，后端能校验端口兼容性。
- 用户能运行单个节点，看到 job 状态、日志和输出 artifacts。
- 用户能下载节点输出、候选文件和项目交付包。
- 后端能保留云端计算接口，不把实现锁死在本地 Docker。
- 一条 demo 闭环路线可以跑通：上传 target → 运行 stub/真实模型 → 注册输出 → 下游节点消费 → 评分 → 下载。

## 16. 推荐近期行动

优先级从高到低：

1. 先做 `artifacts` 表和通用 artifact API。
2. 再做插件 manifest 和参数 schema，更新 RFdiffusion / ProteinMPNN / AlphaFold2 / Rosetta / Mask RGN 注册数据。
3. 把 workflow 从线性继承升级到 edges + ports。
4. 修 Docker adapter，让容器真正读取 `/input/manifest.json` 并输出 `/output/manifest.json`。
5. 前端 NodeBuilder 改为从 plugin schema 渲染参数。
6. 文件上传统一到 artifact API，结构预览和表格预览共用同一套 metadata。
7. 最后接云端 HTTP worker，保留 SSH/Slurm 为下一阶段。
