# BDA 接口与模型卡片扩展开发指南

本文面向后续开发和联调，说明当前 PDA/BDA 平台的主要接口、接口用途、修改入口，以及如何添加新的模型、新的 workflow 卡片和新的运行脚本。

## 1. 总体链路

当前主流程是：

1. 前端选择项目，创建或读取 `workflow_run`。
2. 前端从后端读取 `model_plugins` 和 `method_plugins`，渲染 Add node 面板。
3. 用户添加节点后，前端调用后端创建 `workflow_node_run`。
4. 用户连线或拖动节点后，前端把节点位置和 edge 写回后端 graph。
5. 用户上传文件后，后端注册为 `artifact`。
6. 用户启动 workflow 后，后端按节点创建 job，准备 `/input/manifest.json`。
7. compute adapter 运行模型脚本，模型脚本写 `/output/manifest.json`。
8. 后端收集输出 manifest，把模型产物注册为新的 artifacts，并更新节点/job 状态。
9. 前端轮询 graph/jobs/artifacts，刷新画布、日志和下载入口。

核心原则：前端不要硬编码模型参数；模型输入、输出、参数、资源要求都优先由后端 `model_plugins` schema 驱动。

## 2. 主要接口索引

所有接口默认挂在 `/api/v1` 下。

### 2.1 项目与 workflow

| 接口 | 用途 | 前端调用 | 后端文件 |
|---|---|---|---|
| `GET /projects` | 项目列表 | `frontend/src/lib/api/projects.ts` | `backend/app/routers/core.py` |
| `GET /projects/{project_id}/overview` | 项目首页 overview | `projects.ts` | `core.py` |
| `GET /projects/{project_id}/workflow-runs/latest` | 当前项目最新 workflow run | `projects.ts` | `core.py` |
| `POST /projects/{project_id}/workflow-runs` | 创建 workflow run | `frontend/src/lib/api/workflow.ts` | `backend/app/routers/workflow_mgmt.py` |
| `GET /workflow-runs/{workflow_run_id}` | workflow run 详情 | `workflow.ts` / `projects.ts` | `core.py` |
| `GET /workflow-runs/{workflow_run_id}/nodes` | 节点列表 | `workflow.ts` | `core.py` |
| `POST /workflow-runs/{workflow_run_id}/nodes` | 新增节点 | `workflow.ts` | `workflow_mgmt.py` |
| `PATCH /workflow-runs/{workflow_run_id}/nodes/{node_run_id}` | 修改节点参数/状态/位置 | `workflow.ts` | `workflow_mgmt.py` |
| `DELETE /workflow-runs/{workflow_run_id}/nodes/{node_run_id}` | 删除节点 | `workflow.ts` | `workflow_mgmt.py` |

### 2.2 Graph、连线与校验

| 接口 | 用途 | 前端调用 | 后端文件 |
|---|---|---|---|
| `GET /workflow-runs/{workflow_run_id}/graph` | 一次返回 run、nodes、edges、artifacts、jobs | `getWorkflowGraph` | `workflow_mgmt.py` |
| `PATCH /workflow-runs/{workflow_run_id}/graph` | 保存节点位置和连线 | `saveWorkflowLayout` | `workflow_mgmt.py` |
| `PATCH /workflow-runs/{workflow_run_id}/layout` | 旧版 layout 保存接口，保留兼容 | 旧逻辑 | `workflow_mgmt.py` |
| `POST /workflow-runs/{workflow_run_id}/validate` | 校验 edge 是否成 DAG、端口是否匹配 | `validateWorkflowRun` | `workflow_mgmt.py` + `services/workflow_graph.py` |

Graph edge 关键字段：

```json
{
  "source_node_run_id": "node_rf",
  "source_port": "backbone_set",
  "target_node_run_id": "node_mpnn",
  "target_port": "backbone_set",
  "edge_type": "data"
}
```

端口名来自 `model_plugins.input_schema_json.ports` 和 `model_plugins.output_schema_json.ports`。如果新增模型，一定要把端口写清楚，否则 graph validate 会报 `unknown_source_port`、`unknown_target_port` 或 `incompatible_ports`。

### 2.3 Artifact 上传、预览、下载

| 接口 | 用途 | 前端调用 | 后端文件 |
|---|---|---|---|
| `POST /artifacts/upload` | 通用文件上传，适合 fasta/csv/json/zip 等 | `frontend/src/lib/api/artifacts.ts` | `backend/app/routers/files.py` |
| `POST /targets/upload-pdb` | 结构文件上传，同时解析 PDB/mmCIF metadata | `uploadArtifact` 对结构文件走这里 | `files.py` |
| `GET /projects/{project_id}/artifacts` | 项目 artifact 列表 | `listProjectArtifacts` | `files.py` |
| `GET /artifacts/{artifact_id}` | artifact 详情 | 可新增前端调用 | `files.py` |
| `GET /artifacts/{artifact_id}/preview` | 文本/结构预览 | `ArtifactBrowser` / `WorkflowInspector` 使用 URL | `files.py` |
| `GET /artifacts/{artifact_id}/download` | 单文件下载 | `ArtifactBrowser` / `WorkflowInspector` 使用 URL | `files.py` |
| `POST /artifacts/batch-download` | 批量打包 zip 下载 | 可新增前端调用 | `files.py` |

数据表和仓库：

- 表结构：`backend/db/schema.sql` 的 `artifacts`
- Repository：`backend/app/repositories/artifacts.py`
- Artifact 推断和 hash：`backend/app/services/artifacts.py`
- 本地/MinIO 存储抽象：`backend/app/services/artifact_store.py`

### 2.4 插件 registry

| 接口 | 用途 | 前端调用 | 后端文件 |
|---|---|---|---|
| `GET /model-plugins` | 模型插件列表，驱动模型卡片 | `listModelPlugins` | `backend/app/routers/registry.py` |
| `GET /model-plugins/{model_plugin_id}` | 单个模型插件详情 | 可新增前端调用 | `registry.py` |
| `POST /model-plugins/{model_plugin_id}/validate-schema` | 检查插件 schema 是否完整 | `validateModelPlugin` | `registry.py` |
| `GET /method-plugins` | 方法插件列表，驱动 method controls | `listMethodPlugins` | `registry.py` |
| `GET /method-plugins/{method_plugin_id}` | 方法插件详情 | 可新增前端调用 | `registry.py` |
| `POST /method-plugins` | 前端快速创建 method plugin | `createMethodPlugin` | `registry.py` |
| `GET /compute-nodes` | 计算节点列表 | `listComputeNodes` | `registry.py` |
| `GET /servers` | 服务器连接列表 | `listServers` | `registry.py` |

默认模型插件定义在：

- `backend/app/plugins/defaults.py`

数据库初始化时注册默认插件：

- `backend/scripts/init_db.py`
- `backend/scripts/register_plugins.py`

### 2.5 Job 与 compute

| 接口 | 用途 | 前端调用 | 后端文件 |
|---|---|---|---|
| `POST /workflow-runs/{workflow_run_id}/submit-to-compute` | 提交 workflow run 到计算后端 | `submitWorkflowRun` | `backend/app/routers/compute.py` |
| `GET /workflow-runs/{workflow_run_id}/jobs` | workflow job 列表 | `listWorkflowJobs` | `backend/app/routers/jobs.py` |
| `GET /jobs/{job_id}` | job 详情 | `getJob` | `jobs.py` |
| `GET /jobs/{job_id}/logs` | job 日志 | `JobStatusDrawer` / `WorkflowInspector` | `jobs.py` |

核心后端文件：

- `backend/app/services/job_service.py`
- `backend/app/compute/adapter.py`
- `backend/app/compute/factory.py`
- `backend/app/celery_app.py`

运行模式：

- `BDA_COMPUTE_MODE=demo`：不真实运行，只做占位。
- `BDA_COMPUTE_MODE=local`：本地调用 `docker/models/*/run.py` stub runner，适合开发调试。
- `BDA_COMPUTE_MODE=docker`：通过 Docker adapter 执行模型镜像。

### 2.6 Copilot

| 接口 | 用途 | 前端调用 | 后端文件 |
|---|---|---|---|
| `GET /copilot/config` | 查看 LLM 配置，不返回完整 key | `getCopilotConfig` | `backend/app/routers/copilot.py` |
| `PUT /copilot/config` | 管理员更新 LLM base/model/key | `updateCopilotConfig` | `copilot.py` |
| `POST /copilot/chat` | 同步聊天 | `sendCopilotMessage` | `copilot.py` |
| `POST /copilot/chat/stream` | SSE 流式聊天 | `streamCopilotMessage` | `copilot.py` |
| `GET /copilot/knowledge` | 可编程生物材料知识库检索 | `listCopilotKnowledge` | `copilot.py` |
| `POST /copilot/route-plan` | 规则/LLM 路线建议 | `planRoute` | `copilot.py` |
| `POST /copilot/candidate-explanation` | 候选解释 | `explainCandidate` | `copilot.py` |
| `POST /copilot/result-interpretation` | 实验结果解释 | `interpretResults` | `copilot.py` |

本地接 DeepSeek 这类 OpenAI-compatible provider 时，不要把 key 提交进仓库。启动后端时用环境变量：

```bash
BDA_COMPUTE_MODE=local \
LLM_API_BASE=https://api.deepseek.com \
LLM_MODEL=deepseek-v4-pro \
LLM_API_KEY='your-local-key' \
./.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8100
```

## 3. 前端文件与后端接口对应关系

| 前端文件 | 负责内容 |
|---|---|
| `frontend/src/lib/api/client.ts` | API base、鉴权 token、统一错误处理 |
| `frontend/src/lib/api/projects.ts` | project 和 latest workflow run |
| `frontend/src/lib/api/workflow.ts` | workflow nodes、graph、validate、submit |
| `frontend/src/lib/api/artifacts.ts` | 上传和 artifact 列表 |
| `frontend/src/lib/api/registry.ts` | model/method/compute/server registry |
| `frontend/src/lib/api/jobs.ts` | jobs 和 logs |
| `frontend/src/lib/api/copilot.ts` | Copilot config/chat/knowledge |
| `frontend/src/lib/schemas/*.ts` | Zod schema，负责解析后端返回 |
| `frontend/src/app/Workflow.tsx` | workflow 页面数据编排 |
| `frontend/src/features/workflow/NodeBuilder.tsx` | Add node 面板、模型卡、method controls、参数表单 |
| `frontend/src/features/workflow/WorkflowCanvas.tsx` | React Flow 画布、拖拽、连线、保存 graph |
| `frontend/src/features/workflow/workflowMapper.ts` | 后端 node/edge 转 React Flow node/edge |
| `frontend/src/features/workflow/WorkflowInspector.tsx` | 节点/job/artifact 检查面板 |
| `frontend/src/features/workflow/WorkflowResourceSidebar.tsx` | 左侧 artifact 和插件信息 |
| `frontend/src/features/plugins/ParameterSchemaForm.tsx` | 根据 `parameter_schema_json` 渲染参数 |

修改接口返回字段时，通常要同步改三处：

1. 后端 router/repository/service。
2. 前端 `lib/schemas/*.ts`。
3. 前端 `lib/api/*.ts` 或使用该数据的 feature 组件。

## 4. 如何修改现有接口

### 4.1 修改后端返回字段

步骤：

1. 找到 router，例如 workflow graph 在 `backend/app/routers/workflow_mgmt.py`。
2. 如果数据来自数据库，修改 repository，例如 `backend/app/repositories/catalog.py`。
3. 如果字段是 JSON，确认 `backend/app/repositories/base.py` 的 `JSON_COLUMNS` 包含该列名，否则前端可能收到字符串。
4. 修改或新增测试：
   - API 行为：`backend/tests/test_api.py`
   - workflow graph：`backend/tests/test_workflow.py`
   - compute/job manifest：`backend/tests/test_compute_e2e.py`、`backend/tests/test_job_manifest.py`
5. 前端同步更新 Zod schema，例如 `frontend/src/lib/schemas/workflow.ts`。

### 4.2 修改前端调用方式

步骤：

1. 在 `frontend/src/lib/api/*.ts` 修改请求路径、method、body。
2. 在 `frontend/src/lib/schemas/*.ts` 修改返回 schema。
3. 在页面或 feature 组件里更新 query key 和 invalidate 逻辑。
4. 如果涉及 workflow graph，重点检查：
   - `Workflow.tsx`
   - `WorkflowCanvas.tsx`
   - `workflowMapper.ts`
   - `WorkflowInspector.tsx`

### 4.3 修改参数表单

模型参数从 `model_plugins.parameter_schema_json.fields` 生成。

字段示例：

```json
{
  "key": "num_designs",
  "label": "Number of designs",
  "type": "integer",
  "default": 100,
  "help": "Number of backbones to sample.",
  "minimum": 1,
  "maximum": 100000,
  "advanced": false
}
```

修改入口：

- 默认参数定义：`backend/app/plugins/defaults.py`
- 前端字段转换：`frontend/src/lib/forms/parameterSchema.ts`
- 前端表单渲染：`frontend/src/features/plugins/ParameterSchemaForm.tsx`

如果新增字段类型，例如 `file_select`、`multi_select`、`range_pair`，要同步改 `parameterSchema.ts` 和 `ParameterSchemaForm.tsx`。

## 5. 如何添加新的模型

下面以新增 `ESMFold` 为例，实际模型名可替换。

### 5.1 增加后端 model plugin

编辑 `backend/app/plugins/defaults.py`，在 `DEFAULT_MODEL_PLUGINS` 里新增一项：

```python
{
    "model_plugin_id": "plugin_esmfold",
    "model_name": "ESMFold",
    "model_type": "fold_prediction",
    "provider": "open_source",
    "version": "1.0.0",
    "description": "Fast single-sequence structure prediction.",
    "input_schema_json": {
        "ports": [
            _port("sequence_set", ["sequence_set"], help="FASTA sequences.")
        ]
    },
    "output_schema_json": {
        "ports": [
            _port("predicted_structure", ["predicted_structure"], many=True),
            _port("score_table", ["score_table"], required=False)
        ]
    },
    "parameter_schema_json": {
        "fields": [
            _field("chunk_size", "Chunk size", "integer", 128, "Memory/performance tradeoff.", minimum=16),
            _field("random_seed", "Random seed", "integer", 0, "Zero means auto.", advanced=True, minimum=0)
        ]
    },
    "artifact_schema_json": {
        "outputs": [
            {"type": "predicted_structure", "formats": ["pdb", "mmcif"]},
            {"type": "score_table", "formats": ["json", "csv"]}
        ]
    },
    "supported_task_types": ["binder_design", "scaffold_redesign"],
    "supported_file_types": ["fasta"],
    "resource_requirement_json": {"gpu_count": 1, "min_vram_gb": 16, "cpu_count": 4, "memory_gb": 16},
    "default_compute_node_id": "compute_gpu_local",
    "container_image": "bda/esmfold:1.0.0",
    "command_template": "python run.py",
    "api_endpoint": None,
    "license": "upstream dependent",
    "citation": "ESMFold citation TBD",
    "status": "active",
}
```

注意：

- `model_plugin_id` 必须稳定，不要随便改，否则已有 workflow node 的 `model_plugin_id` 会失效。
- `model_name` 会被前端用来判断卡片标题、icon 和节点类型。
- `model_type` 应尽量落在已有类型：`backbone_generation`、`sequence_generation`、`fold_prediction`、`scoring`、`selection`、`experiment`。如果新增类型，要同步前端映射。
- `input_schema_json.ports[].artifact_types` 和上游输出的 artifact_type 要能交集匹配。
- `output_schema_json.ports[].name` 会成为 edge 的 `source_port`。

### 5.2 注册到数据库

开发环境重新初始化：

```bash
./.venv/bin/python backend/scripts/init_db.py
```

或只注册插件：

```bash
./.venv/bin/python backend/scripts/register_plugins.py
```

如果线上已有数据库，应做 migration/upsert，不要直接删库。

### 5.3 增加模型 runner

本地 stub runner 位置：

```text
docker/models/{model_key}/run.py
```

例如：

```text
docker/models/esmfold/run.py
```

runner 输入：

```text
/input/manifest.json
```

manifest 关键字段：

```json
{
  "job_id": "job_xxx",
  "project_id": "proj_xxx",
  "workflow_run_id": "run_xxx",
  "node_run_id": "node_xxx",
  "plugin_id": "plugin_esmfold",
  "model_name": "ESMFold",
  "inputs": [
    {
      "port": "sequence_set",
      "artifact_id": "art_xxx",
      "path": "/input/art_xxx_input.fasta",
      "format": "fasta",
      "artifact_type": "sequence_set"
    }
  ],
  "parameters": {
    "chunk_size": 128
  }
}
```

runner 输出：

```text
/output/manifest.json
```

输出 manifest 示例：

```json
{
  "outputs": {
    "predicted_structure": [
      {
        "path": "predicted.pdb",
        "artifact_type": "predicted_structure",
        "format": "pdb",
        "display_name": "ESMFold predicted structure",
        "metadata": {"source": "esmfold"}
      }
    ],
    "score_table": [
      {
        "path": "confidence.json",
        "artifact_type": "score_table",
        "format": "json"
      }
    ]
  },
  "metrics": {
    "folded": 1,
    "mean_plddt": 82.4
  }
}
```

后端收集输出的代码在 `backend/app/services/job_service.py` 的 `collect_job_outputs`。只要 runner 按上面的 manifest 写文件，后端会自动注册 artifacts、更新 job 和 node。

### 5.4 让 compute adapter 找到 runner

本地模式查找逻辑在 `backend/app/compute/factory.py`。如果新增模型名和目录名不能自动匹配，需要在 local runner 映射里增加：

```python
"ESMFold": REPO_ROOT / "docker" / "models" / "esmfold" / "run.py"
```

Docker 模式则要保证：

- `container_image` 正确。
- `command_template` 正确。
- Docker image 内部读取 `/input/manifest.json`，写 `/output/manifest.json`。

### 5.5 前端显示新模型卡片

通常不需要手动加前端卡片。`NodeBuilder` 会读取 `GET /model-plugins` 并把每个 plugin 映射成卡片。

但如果新模型需要更准确的 icon、nodeType、resource，需要改：

- `frontend/src/features/workflow/NodeBuilder.tsx`

当前映射逻辑根据 `plugin.model_name` 识别 RFdiffusion、ProteinMPNN、AlphaFold2，其他默认落到 `scoring`。新增模型时建议添加明确映射：

```ts
nodeType:
  plugin.model_name === 'ESMFold'
    ? 'fold_prediction'
    : ...
```

icon 映射也在同文件：

```ts
const PLUGIN_ICON: Record<string, string> = {
  RFdiffusion: 'wand-sparkles',
  ProteinMPNN: 'dna',
  AlphaFold2: 'scan-search',
  Rosetta: 'activity',
  ESMFold: 'scan-search',
}
```

如果只是 demo fallback 卡片，也可以改：

- `frontend/src/features/workflow/workflowTypes.ts`

但真实接后端后，应优先依赖 `model_plugins`，不要只改 fallback。

### 5.6 前端 graph 节点显示

后端节点转画布节点在：

- `frontend/src/features/workflow/workflowMapper.ts`

如果新增 `node_type`，要在 `NODE_META` 增加：

```ts
fold_prediction: { icon: 'scan-search', resource: 'gpu', column: 3 }
```

如果是全新类型，例如 `property_prediction`：

```ts
property_prediction: { icon: 'activity', resource: 'gpu', column: 4 }
```

否则节点仍能显示，但会 fallback 成 local/database 样式。

### 5.7 增加测试

建议至少补：

- `backend/tests/test_api.py`：确认 `GET /model-plugins` 返回新模型。
- `backend/tests/test_workflow.py`：确认新模型端口和 graph validate 可用。
- `backend/tests/test_compute_e2e.py`：本地 mode 下新模型 runner 能输出 artifacts。
- `frontend/src/features/workflow/workflowMapper.test.ts`：如果新增 node_type，确认前端状态和显示映射。

## 6. 如何添加新的 method plugin

Method plugin 是方法/筛选/参数策略，不一定等于模型。它用于 NodeBuilder 的 method controls，并会写入 node 的 `parameters_json.method_refs`。

### 6.1 后端默认 method

当前默认 method seed 在 `backend/db/seed_demo.sql` 或数据库 seed 逻辑中。若要稳定内置某个 method，可在 seed 中增加记录。

### 6.2 前端临时创建 method

`NodeBuilder` 已支持调用：

```http
POST /api/v1/method-plugins
```

payload：

```json
{
  "method_name": "Interface energy gate",
  "method_type": "scoring_filter",
  "description": "Reject designs above a Rosetta interface energy cutoff.",
  "compatible_model_types": ["Rosetta"],
  "compatible_workflow_nodes": ["scoring"],
  "default_parameters_json": {"interface_delta_g_max": -8.0},
  "status": "active"
}
```

如果要让 method 真正影响 runner，需要在模型 runner 或 job preparation 中读取：

```json
{
  "parameters": {
    "method_refs": [
      {
        "method_plugin_id": "method_xxx",
        "method_name": "Interface energy gate",
        "method_type": "scoring_filter",
        "default_parameters_json": {"interface_delta_g_max": -8.0}
      }
    ]
  }
}
```

## 7. 如何添加新的前端卡片

这里的“卡片”有三类，改法不同。

### 7.1 新模型卡片

优先新增后端 `model_plugin`，前端会自动出现卡片。只在需要 icon/nodeType 特化时改：

- `frontend/src/features/workflow/NodeBuilder.tsx`
- `frontend/src/features/workflow/workflowMapper.ts`

### 7.2 新 workflow demo fallback 卡片

如果后端 registry 不可用时也想显示 demo 卡片，改：

- `frontend/src/features/workflow/workflowTypes.ts`

新增 `nodeTemplates` 项：

```ts
esmfold: {
  id: 'esmfold',
  icon: 'scan-search',
  title: 'ESMFold prediction',
  body: 'Fast single-sequence structure prediction',
  resource: 'gpu',
  nodeType: 'fold_prediction',
  modelName: 'ESMFold',
  modelVersion: '1.0.0',
  pluginId: 'plugin_esmfold',
}
```

### 7.3 新 dashboard/feature 卡片

例如新增 artifact summary、compute card、Copilot knowledge card：

1. 在对应 feature 下建组件，例如 `frontend/src/features/workflow/MyCard.tsx`。
2. 在页面装配文件引用，例如 `frontend/src/app/Workflow.tsx`。
3. 如果需要 API，先在 `frontend/src/lib/api/*.ts` 增加函数。
4. 如果需要解析返回，先在 `frontend/src/lib/schemas/*.ts` 增加 Zod schema。
5. 文案如果要中英双语，改：
   - `frontend/src/lib/i18n/types.ts`
   - `frontend/src/lib/i18n/en.ts`
   - `frontend/src/lib/i18n/zh.ts`

## 8. 常见修改任务速查

### 8.1 新增 artifact 类型

改动点：

- 后端识别：`backend/app/services/artifacts.py`
- 前端上传推断：`frontend/src/lib/api/artifacts.ts`
- 模型 plugin 端口：`backend/app/plugins/defaults.py`
- 输出 manifest 中的 `artifact_type`
- 必要时更新 preview/download：`backend/app/routers/files.py`

### 8.2 修改模型输出文件

改动点：

- runner：`docker/models/{model}/run.py`
- 输出 manifest：`outputs.{port}`、`artifact_type`、`format`
- 后端收集逻辑如需新格式：`backend/app/services/job_service.py`
- 前端显示如需新预览：`ArtifactBrowser`、`WorkflowInspector`

### 8.3 修改节点状态

后端状态来源：

- `workflow_node_runs.status`
- `jobs.status`
- `job_service.submit_workflow_run`
- `job_service.collect_job_outputs`

前端状态映射：

- `frontend/src/features/workflow/workflowMapper.ts` 的 `mapStatus`

如果新增状态，例如 `waiting_for_review`，要同时改后端写入、前端 union 类型和映射。

### 8.4 修改 layout 或 edge 行为

后端：

- 表：`workflow_edges`
- repository：`backend/app/repositories/catalog.py`
- graph router：`backend/app/routers/workflow_mgmt.py`
- graph validate：`backend/app/services/workflow_graph.py`

前端：

- `WorkflowCanvas.tsx` 保存 edge `source_port`、`target_port`
- `workflowMapper.ts` 从后端 edge 转 React Flow edge
- `WorkflowNode.tsx` 的 Handle id。目前默认是 `input` 和 `output`。

### 8.5 修改 Copilot provider

本地环境变量：

```bash
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
LLM_API_KEY=...
```

代码入口：

- 配置：`backend/app/settings.py`
- 后端 config API：`backend/app/routers/copilot.py`
- LLM client：`backend/app/copilot/service.py`
- 前端 API：`frontend/src/lib/api/copilot.ts`
- 前端技能列表：`frontend/src/features/copilot/skills/registry.ts`

不要把真实 key 写入 `.env.example`、README、测试或源码。

## 9. 开发与验证命令

### 9.1 初始化数据库

```bash
./.venv/bin/python backend/scripts/init_db.py
```

### 9.2 本地运行

后端：

```bash
BDA_COMPUTE_MODE=local ./.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8100
```

前端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 9.3 测试

后端：

```bash
./.venv/bin/python -m pytest backend/tests -q
```

前端：

```bash
cd frontend
npm test -- --run
npm run build
```

### 9.4 最小手动联调

1. 打开 `http://127.0.0.1:5173`。
2. 登录 `admin / admin123`。
3. 进入 Workflow。
4. 选择项目并创建 workflow run。
5. 上传 PDB 或 FASTA。
6. Add node，选择模型卡，确认参数表单来自 schema。
7. 拖动/连线节点，刷新后确认 layout/edge 仍存在。
8. Start workflow。
9. 检查 job 状态、logs、输出 artifacts。
10. 点击 preview/download，确认可访问。

## 10. 合并前检查清单

新增模型或卡片合并前，至少确认：

- `GET /model-plugins` 能看到新模型。
- 新模型的 `input_schema_json.ports` 和上游 output artifact type 能匹配。
- 新模型的 `output_schema_json.ports` 和 runner manifest port 一致。
- `POST /workflow-runs/{id}/validate` 不报端口错误。
- `BDA_COMPUTE_MODE=local` 下 runner 能产生 `/output/manifest.json`。
- 后端能注册输出 artifacts。
- 前端 Add node 能显示模型卡和参数。
- 画布刷新后节点、edge 不丢。
- `npm run build`、`npm test -- --run`、`pytest backend/tests -q` 通过。
