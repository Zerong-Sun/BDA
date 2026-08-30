# BDA Workbench 前端操作性与适用性重构规划

版本：v0.1
日期：2026-06-17
文档类型：前端 FRD / 交互架构规划
关联文档：`docs/PRD02_后端与工作流接入规划.md`
目标读者：前端、后端、算法、产品、项目负责人

## 1. 目标

当前前端已经具备四个核心页面、React Flow 工作流画布、Mol* 结构查看器、候选表、结果页、文件上传和基础 API 对接。下一阶段需要从“可演示的 PD-1 demo”升级为“可操作、可扩展、可接真实模型的设计工作台”。

本阶段前端目标：

- 让用户可以从项目、靶点、文件、模型、参数、任务、输出、候选和实验结果之间顺畅流转。
- 让 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、Mask RGN 等模型通过统一插件 schema 呈现，而不是在前端硬编码参数。
- 让工作流画布表达真实数据流：节点、端口、边、artifact、状态、日志、错误和重跑。
- 让文件上传与结果下载成为稳定的通用能力，而不是只服务 PDB demo。
- 让不同任务类型都能复用同一套交互：binder、nanocage、enzyme repair、redesign。
- 保留展示友好度，但优先服务真实研发操作。

## 2. 当前前端基础

已有能力：

- React + TypeScript + Vite。
- React Flow 工作流画布。
- TanStack Query 做 API 请求和缓存。
- Zod 做 API schema 校验。
- Zustand 做 UI 状态。
- Mol* 做 PDB/mmCIF 查看。
- `Experiments`、`Workflow`、`Candidates`、`Results` 四页闭环。
- `NodeBuilder` 能读取 `model-plugins` 和 `method-plugins`。
- `PDBFileUpload` 能上传结构文件。
- `WorkflowCanvas` 能添加节点、拖拽节点、保存 layout。

主要问题：

- NodeBuilder 仍偏卡片和 checkbox，没有根据 `parameter_schema_json` 动态渲染模型参数。
- 画布边只保存 source/target，没有保存端口、artifact 类型、数据兼容性。
- 文件上传只围绕 PDB/mmCIF，缺少 FASTA、CSV、JSON、ZIP 和通用 artifact browser。
- 节点详情不足，缺少输入、输出、参数、日志、job、artifact、重跑历史。
- 任务状态只在节点上显示，缺少统一 job drawer / log viewer。
- 候选表与结果页还没有与 artifact、workflow node、job 形成可追溯链接。
- 页面适合演示路径，但对真实项目的批量操作、专家参数、错误恢复还不够。

## 3. 产品方向

前端应从“四页展示”升级为“项目工作台”。

推荐核心对象：

- Project：项目空间。
- Target：靶点和约束。
- Artifact：文件和中间产物。
- Workflow：路线图。
- Node：模型或方法步骤。
- Job：一次实际运行。
- Candidate：可进入决策的候选。
- Experiment：湿实验数据和结论。
- Delivery：交付包。

用户操作主线：

1. 创建或打开项目。
2. 上传 target structure / sequence / constraints。
3. 选择 workflow template 或手动搭 DAG。
4. 选择模型插件，配置参数。
5. 连接节点端口，校验数据流。
6. 运行单节点或整条 workflow。
7. 查看日志、错误、输出文件和结构预览。
8. 将输出转为候选并排序。
9. 上传实验结果，生成 redesign constraints。
10. 下载交付包或进入下一轮 workflow。

## 4. 信息架构调整

主导航建议保留四个入口，但每页职责更清晰：

| 页面 | 新职责 |
|------|--------|
| Experiments | 项目入口、项目健康度、最近任务、下一步行动 |
| Workflow | target intake、artifact browser、DAG 画布、节点配置、任务运行 |
| Candidates | 候选筛选、结构检查、来源追踪、批量选择 |
| Results | 实验结果、redesign brief、交付包、轮次复盘 |

Workflow 页面建议采用三栏工作台：

- 左栏：Asset & Plugin Sidebar。
  - Artifacts。
  - Model plugins。
  - Workflow templates。
  - Saved parameter presets。

- 中间：Canvas。
  - DAG 节点。
  - typed ports。
  - edge validation。
  - status overlays。

- 右栏：Inspector。
  - 选中节点：参数、输入、输出、运行、日志。
  - 选中边：source port、target port、artifact type。
  - 选中 artifact：metadata、preview、download。
  - 选中空白：workflow summary 和 validate result。

这种布局比“顶部 NodeBuilder + 单画布”更适合真实操作，因为用户可以一边看数据资产，一边搭路线，一边编辑节点。

## 5. 推荐前端架构

### 5.1 分层

推荐保留当前 feature-based 目录，但明确分层：

```text
frontend/src/
  app/                 # 页面级路由和页面布局
  features/
    workflow/          # 画布、节点、边、inspector、templates
    artifacts/         # 上传、浏览、预览、下载
    plugins/           # plugin cards、schema form、parameter presets
    jobs/              # job status、logs、events、retry/cancel
    candidates/        # 候选表、详情、批量动作
    results/           # 实验结果和交付
    pdb-viewer/        # Mol* viewer
  lib/
    api/               # API client
    schemas/           # Zod schema
    queryKeys/         # TanStack Query key factory
    forms/             # schema-driven form utilities
    workflow/          # graph validation、port mapping
    store/             # UI state only
```

原则：

- Server state 全部交给 TanStack Query。
- Zustand 只存 UI state，例如当前项目、drawer 开关、选中节点、语言、toast。
- API response 全部经过 Zod schema。
- 插件参数表单由 schema 生成，不在组件中写死。
- React Flow 只负责交互和可视化，真实 graph 由后端保存。

### 5.2 Query Key 规范

建立 `queryKeys`：

```ts
queryKeys.project(projectId)
queryKeys.workflowRun(workflowRunId)
queryKeys.workflowGraph(workflowRunId)
queryKeys.artifacts(projectId)
queryKeys.artifact(artifactId)
queryKeys.plugins()
queryKeys.plugin(pluginId)
queryKeys.jobs(workflowRunId)
queryKeys.job(jobId)
queryKeys.jobLogs(jobId)
queryKeys.candidates(projectId)
queryKeys.results(projectId)
```

好处：

- 避免 invalidate key 分散。
- 方便轮询 running jobs。
- 方便节点运行后刷新 graph、jobs、artifacts、candidates。

### 5.3 类型与 Schema

前端需要和后端共享概念，但不直接共享 Python 类型。

新增 Zod schema：

- `ArtifactSchema`
- `ArtifactPreviewSchema`
- `PluginParameterSchema`
- `ModelPluginSchema`
- `WorkflowGraphSchema`
- `WorkflowEdgeSchema`
- `NodePortSchema`
- `JobSchema`
- `JobEventSchema`
- `RunValidationSchema`

所有页面优先使用 schema 推导的 TS 类型，减少手写 interface 漂移。

## 6. 关键体验改造

### 6.1 通用 Artifact Center

新增 `features/artifacts`。

能力：

- 上传 PDB/mmCIF/FASTA/CSV/JSON/ZIP。
- 展示 artifact list：类型、格式、来源、创建时间、大小、所属节点。
- 预览结构、FASTA、CSV 前 N 行、JSON。
- 下载单个 artifact。
- 批量下载选中 artifact。
- 将 artifact 拖到节点输入端口。

组件建议：

- `ArtifactUploadDropzone`
- `ArtifactBrowser`
- `ArtifactTypeBadge`
- `ArtifactPreviewPanel`
- `ArtifactDownloadButton`
- `ArtifactPicker`

上传体验：

- 拖拽上传。
- 上传前显示格式和大小校验。
- 上传后立即展示 metadata。
- 上传失败必须显示可读原因。

### 6.2 Schema-Driven Node Builder

`NodeBuilder` 从“模型卡 + 方法 checkbox”升级为“插件选择 + 参数 schema 表单”。

流程：

1. 获取 `model_plugins`。
2. 用户选择插件。
3. 前端读取 `parameter_schema_json.fields`。
4. 渲染 Basic / Advanced / Raw JSON 三层。
5. 用户选择输入 artifact 或从画布连线获得输入。
6. 保存节点。

组件建议：

- `PluginCatalog`
- `PluginCard`
- `PluginDetail`
- `ParameterSchemaForm`
- `ParameterField`
- `AdvancedParameterSection`
- `RawJsonParameterEditor`

参数控件映射：

| schema type | 控件 |
|-------------|------|
| `integer` | number input / stepper |
| `number` | slider + number input |
| `boolean` | toggle |
| `enum` | select / segmented control |
| `string` | text input |
| `artifact_ref` | artifact picker |
| `residue_selector` | Mol* residue selector |
| `json` | code editor |

必须显示：

- label。
- default。
- help。
- range。
- required。
- advanced。
- changed-from-default 标记。

### 6.3 Workflow Canvas 真实 DAG 化

当前画布只保存节点位置和简单边。下一阶段需要 typed DAG。

节点显示：

- 模型名和版本。
- 状态。
- 输入端口。
- 输出端口。
- 当前 job。
- 输出 artifact 数量。
- 关键 metrics。
- 错误提示。

边显示：

- source port。
- target port。
- artifact type。
- 是否兼容。
- 是否 feedback edge。

交互：

- 拖插件到画布创建节点。
- 从输出端口连到输入端口。
- 连线时即时校验 artifact type。
- 右键或快捷菜单删除节点/边。
- 保存 layout 和 graph。
- Validate workflow。
- Run selected node。
- Run ready nodes。
- Retry failed node。

节点状态颜色：

- `not_started`：灰。
- `queued`：蓝。
- `running`：青，带进度动画。
- `collecting_outputs`：紫。
- `completed`：绿。
- `failed`：红。
- `blocked`：黄。
- `requires_review`：橙。

### 6.4 Inspector 右侧面板

Inspector 是提高操作性的关键。

选中节点时显示 tabs：

- Overview：节点用途、插件版本、状态。
- Inputs：required/optional input ports、已连接 artifact。
- Parameters：schema form。
- Run：compute node、run button、validate result。
- Outputs：输出 artifacts。
- Logs：job logs 和 events。
- History：重跑记录。

选中 artifact 时显示：

- Metadata。
- Preview。
- Lineage。
- Used by。
- Download。

选中 workflow 空白时显示：

- Workflow summary。
- Validation errors。
- Ready nodes。
- Running jobs。
- Last outputs。

### 6.5 Job Center

新增全局或页面内 Job Center。

能力：

- 显示当前项目所有 jobs。
- 过滤 running / failed / completed。
- 查看 logs。
- cancel / retry。
- 跳转到对应节点。
- 下载输出。

前端轮询策略：

- 有 running job：每 2-5 秒轮询 job 和 logs。
- 没有 running job：不轮询或低频轮询。
- workflow graph 在 job 完成后 invalidate。

### 6.6 Candidate Traceability

Candidates 页面要从“候选表”升级为“候选决策中心”。

新增能力：

- 候选来源节点和 job。
- 输入 backbone / sequence / AF2 structure / Rosetta score 的 artifact links。
- 批量选择候选生成 FASTA/PDB zip。
- 对候选添加 decision：Order、Retest、Reserve、Reject。
- 标记失败原因并生成 redesign constraints。
- 在 Mol* 中展示 candidate 与 target 的 chain、interface residues、clash、hotspots。

候选详情建议 tabs：

- Summary。
- Structure。
- Sequence。
- Scores。
- Lineage。
- Decision。

### 6.7 Results 到 Redesign 闭环

Results 页面需要支持：

- 上传实验 CSV/XLSX。
- 字段映射：candidate_id、experiment_type、value、unit、pass/fail、failure_reason。
- 实验结果预览。
- 绑定候选。
- 生成 redesign brief。
- 生成 redesign constraints artifact。
- 一键创建下一轮 workflow。

这样 Results 不只是终点，而是下一轮设计入口。

## 7. 方法与技术选择

### 7.1 保留并强化

- React Flow：继续作为工作流画布。
- TanStack Query：继续作为 server state 管理。
- Zod：继续做运行时数据校验。
- Zustand：保留为轻量 UI store。
- Mol*：继续做结构查看。
- React Router：继续做页面路由。

### 7.2 建议新增

- React Hook Form：处理 schema-driven 参数表单。
- `@hookform/resolvers/zod`：把 Zod 和表单校验接起来。
- 轻量 code editor：用于 Raw JSON 参数，可选 Monaco 或 CodeMirror。
- 虚拟表格：候选和 artifact 很多时使用 TanStack Virtual。

### 7.3 不建议

- 不建议引入大型全局状态方案替代 TanStack Query。
- 不建议把所有 workflow 状态存在前端本地。
- 不建议为每个模型写独立参数组件，除非是非常特殊的 residue selector。
- 不建议前端直接拼命令行参数。

## 8. 页面级改造

### 8.1 Experiments

改造目标：从项目展示升级为项目操作入口。

新增：

- 最近运行任务。
- 失败任务提醒。
- 最近上传 artifact。
- 下一步行动按钮：Continue workflow、Review failed jobs、Upload results。
- 项目模板入口：Binder design、Scaffold redesign、Nanocage design、Enzyme repair。

保留：

- 项目概览。
- Copilot 简要建议。
- 中英文。

### 8.2 Workflow

改造目标：成为核心操作台。

新增：

- 左侧 Artifact / Plugin / Template sidebar。
- 中间 typed React Flow DAG。
- 右侧 Inspector。
- 顶部 Validate、Run ready、Stop、Export workflow。
- Job Center。

删除或弱化：

- 大块静态说明。
- 固定方法 checkbox。
- 仅为 demo 服务的节点文案。

### 8.3 Candidates

改造目标：从展示表格升级为筛选和决策。

新增：

- 多条件排序。
- 批量选择。
- artifact links。
- candidate lineage。
- 批量导出 FASTA/PDB/CSV。
- redesign action。

### 8.4 Results

改造目标：从结果展示升级为实验数据回流。

新增：

- 实验文件上传。
- CSV/XLSX 字段映射。
- 数据校验。
- 候选绑定。
- redesign constraints preview。
- 创建下一轮 workflow。

## 9. 组件规划

P0 新增组件：

- `ArtifactBrowser`
- `ArtifactUploadDropzone`
- `ArtifactPreviewPanel`
- `ArtifactPicker`
- `PluginCatalog`
- `ParameterSchemaForm`
- `WorkflowInspector`
- `NodePorts`
- `JobStatusDrawer`
- `JobLogViewer`
- `WorkflowValidatePanel`

P1 新增组件：

- `ResidueSelector`
- `WorkflowTemplatePicker`
- `ParameterPresetManager`
- `CandidateLineagePanel`
- `ExperimentColumnMapper`
- `RedesignBriefBuilder`

## 10. 前后端 API 对接

前端需要依赖以下 API：

- `GET /api/v1/model-plugins`
- `GET /api/v1/model-plugins/{id}`
- `POST /api/v1/artifacts/upload`
- `GET /api/v1/artifacts?project_id=...`
- `GET /api/v1/artifacts/{id}/preview`
- `GET /api/v1/artifacts/{id}/download`
- `GET /api/v1/workflow-runs/{id}/graph`
- `PATCH /api/v1/workflow-runs/{id}/graph`
- `POST /api/v1/workflow-runs/{id}/validate`
- `POST /api/v1/workflow-runs/{id}/nodes/{node_id}/run`
- `POST /api/v1/workflow-runs/{id}/run`
- `GET /api/v1/workflow-runs/{id}/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/jobs/{id}/logs`
- `POST /api/v1/jobs/{id}/cancel`
- `POST /api/v1/jobs/{id}/retry`

短期兼容：

- 继续支持现有 `/targets/upload-pdb`，但前端新入口优先走通用 artifact API。
- 继续支持现有 `/workflow-runs/{id}/layout`，但新 graph API 就绪后迁移。

## 11. 实施路线

### Milestone 1：前端数据契约

交付：

- 新增 artifact、plugin parameter、workflow graph、job 的 Zod schema。
- 建立 query key factory。
- 整理 API client。

验收：

- 所有新增 API response 都有 schema 校验。
- workflow、artifact、job 的 invalidate 逻辑清晰。

### Milestone 2：Artifact Center

交付：

- 通用上传组件。
- artifact list。
- artifact preview。
- artifact picker。

验收：

- PDB/mmCIF/FASTA/CSV/JSON 可以上传和预览。
- 节点输入可以选择 artifact。

### Milestone 3：Schema-Driven Node Builder

交付：

- Plugin catalog。
- ParameterSchemaForm。
- Basic / Advanced / Raw JSON。
- 参数 diff 和校验错误显示。

验收：

- RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、Mask RGN 参数不硬编码也能显示。

### Milestone 4：Workflow Inspector 与 Typed DAG

交付：

- 右侧 Inspector。
- 节点 ports。
- typed edges。
- workflow validate panel。

验收：

- 用户能看清每个节点缺什么输入、输出什么 artifact。
- 错误连线会被明确提示。

### Milestone 5：Job Center

交付：

- job list。
- log viewer。
- run / cancel / retry。
- running job polling。

验收：

- 用户运行节点后能看到状态、日志、输出和错误原因。

### Milestone 6：Candidates 与 Results 闭环

交付：

- Candidate lineage。
- 批量导出。
- 实验上传字段映射。
- redesign constraints preview。
- 创建下一轮 workflow。

验收：

- 用户可以从实验失败原因生成下一轮工作流输入。

## 12. 验收标准

可操作性：

- 用户不看代码也能上传数据、选模型、调参数、连接节点、运行节点、看日志、下载结果。
- 用户知道每个节点为什么不能运行：缺输入、参数错误、资源不可用、上游失败。
- 用户可以从任何输出 artifact 回到来源节点和 job。

适用性：

- 新增一个模型插件后，前端无需新增专用页面即可显示参数和创建节点。
- binder、nanocage、enzyme repair 可以复用同一套 artifact、workflow、job、candidate 组件。
- 本地 demo、Docker、云端 worker 的差异不暴露给普通用户。

可靠性：

- API 错误有明确提示。
- 长任务不会阻塞界面。
- 刷新页面后 workflow 状态仍然可恢复。
- 下载和上传失败可以重试。

## 13. 推荐近期行动

1. 先把 `Workflow` 页面改成左侧资源栏、中间画布、右侧 Inspector 的布局骨架。
2. 新建 `features/artifacts`，把 PDB 上传扩展成通用 artifact 上传/浏览。
3. 新建 `ParameterSchemaForm`，让 NodeBuilder 从 plugin schema 渲染参数。
4. 给 React Flow 节点增加 input/output ports，为后端 DAG 做准备。
5. 新建 JobStatusDrawer 和 JobLogViewer，把运行状态从节点 badge 扩展为可调试界面。
6. 再改 Candidates 和 Results，使候选、实验结果、redesign constraints 能追溯到 artifact 和 workflow。
