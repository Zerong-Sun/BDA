# BDA Workbench 前端设计说明

版本：v1.0  
日期：2026-06-06  
对应目录：`/Users/zero/project/BDA/frontend`  
对应 PRD：`/Users/zero/Desktop/bigo bio/BDA/PRD01_完整产品需求文档.md`  
文档类型：前端设计说明 / Frontend Requirement & Design Document  

## 1. 前端定位

`BDA/frontend` 当前是 BDA Workbench 的 React 演示前端（由 `nolab` 静态 demo 迁移而来）。它不是营销页，也不考虑移动 App、小程序或原生客户端，而是一个面向浏览器的蛋白质设计工作台原型，用四个页面展示完整闭环：

- Experiments：项目入口和智能协作助手。
- Workflow：自动路线、模型节点、计算资源和 Copilot。
- Candidates：候选表、筛选规则、候选详情和下一步决策。
- Results：实验读数、结论、第二轮设计 brief 和交付包。

第一版前端应服务一个清晰目标：用本地静态 Web 页面讲清楚 PD-1 binder 项目如何从靶标输入、模型路线、候选筛选、BLI/SEC 实验结果，到下一轮 redesign 约束形成闭环。核心浏览场景是桌面浏览器和大屏平板浏览器。

当前代码中仍有 RBD / SARS-CoV-2 / BLI-SPR / RBDBinder 的旧口径。后续优化必须统一为 PD-1 binder、BLI、PD1Binder 命名体系。

## 2. 设计原则

### 2.1 工作台优先

BDA 的前端应该像科研和工程团队每天会使用的 workbench，而不是产品官网。页面首屏必须出现可操作数据、项目状态、工作流节点或候选表，不做大面积品牌宣传和空泛介绍。

### 2.2 闭环叙事

每个页面都要回答闭环中的一个问题：

- Experiments：现在有哪些项目，哪个项目正在推进，下一步是什么？
- Workflow：这个设计任务经过哪些模型和筛选步骤，每步状态如何？
- Candidates：哪些候选值得实验，为什么？
- Results：实验结果说明了什么，下一轮设计应该怎么改？

### 2.3 决策可读

所有图表、卡片、表格和说明文字都要服务决策。避免只展示漂亮结构图而不说明候选为什么被选中、为什么被淘汰、下一步应该做什么。

### 2.4 静态可演示，动态可扩展

第一版可以是静态网页，但页面结构要按真实系统设计：模型卡、方法参数、计算节点、候选字段、实验 readout 都应能在后续从 JSON 或 API 配置中读取。

### 2.5 克制的专业视觉

当前暗色工作台方向是合适的，但要避免过度发光、过度渐变和过于娱乐化。BDA 应呈现“高密度、可信、可扫描”的科学工程工具气质。

## 3. 当前前端结构

当前文件：

- `index.html`：四个页面和所有静态 DOM。
- `styles.css`：暗色主题、布局、卡片、工作流画布、表格、Web 浏览器自适应样式。
- `app.js`：路由切换、候选表渲染、候选详情、节点添加、Copilot 静态回复、中英文切换、导出数据。

当前关键模块：

- 顶部导航：`Experiments`、`Workflow`、`Candidates`、`Results`。
- 语言切换：`languageToggle`。
- Copilot hero：`assistant-hero`、`agent-workspace`。
- 工作流画布：`map-panel`、`node`、`edges`。
- 节点添加器：`nodeBuilder`、`model-option`、`method-toggle`。
- 候选表：`candidateRows`、`candidateSearch`、`candidateStatusFilter`。
- 候选详情：`detail-panel`。
- 结果导出：`exportResults`、`preparePackage`。

当前实现方式适合快速 demo，但后续需要拆分数据与视图，把候选数据、项目数据、workflow 节点、翻译文案从 `app.js` 中抽成独立配置。

## 4. 信息架构

### 4.1 一级导航

顶部导航保持四个主入口：

- Experiments
- Workflow
- Candidates
- Results

第一版不增加独立 Admin 页面。服务器、计算节点、模型插件、LLM provider 的入口可以先在 Workflow 的 Add node / Compute access 中做静态展示，后续再拆成后台配置页。

### 4.2 推荐演示路径

标准演示路径：

1. Experiments：打开 PD-1 binder 项目，看到闭环摘要和下一步建议。
2. Workflow：展示 RFdiffusion → ProteinMPNN → AF2 → Rosetta → BDA filters → Wet-lab validation。
3. Candidates：查看候选表，选择 PD1Binder_c4361，解释为什么作为 anchor。
4. Results：展示 9/48 BLI 阳性、0.6 nM BLI Kd、SEC aggregation 作为主要 QC loss，并生成第二轮约束。

每个页面都应该能独立看懂，但连续浏览时形成完整故事。

## 5. 页面设计

## 5.1 Experiments 页面

页面目标：作为项目入口，快速展示 BDA 的闭环能力、当前项目状态和下一步行动。

当前结构：

- Page head：标题 `BDA Experiments` 和 `New experiment`。
- Copilot hero：AI Beagle Copilot 的身份、三个动作按钮、示例对话。
- Agent workspace：Plan route、Adjust workflow、Interpret lab results 三个面板。
- Overview cards：Active project、Binding positives、Compute access、Next action。
- Experiment cards：binder、nanocage、enzyme 三个项目卡。

设计优化：

- 当前 binder 项目必须改为 PD-1 binder，不再出现 SARS-CoV-2 RBD。
- `Project_test_0423` 建议改为 `PD1_binder_0423` 或 `PD1Binder_validation_0423`。
- Overview 中 `Binding positives` 改为 `9/48 BLI-positive candidates`。
- Copilot hero 中保留“把 design brief 转为 traceable loop”的定位，但第一版标注为静态/规则化演示。
- 项目卡主图应优先使用 PD-1 binder 相关结构图；如果暂时没有，可保留 `bam001.png`，但 alt 和文案必须改为 PD-1。

布局要求：

- 桌面 Web：Copilot hero 三列布局，overview 四列，项目三列。
- 大屏平板 Web：Copilot hero 两列，overview 两列，项目两列。
- 手机浏览器不是核心场景，只保证页面可打开和基础内容可读，不针对手机重做工作流体验。

关键交互：

- `New experiment` 进入 Workflow。
- `Plan route` 展示 PD-1 route proposal。
- `Adjust workflow` 展示可开发性阈值和节点调整建议。
- `Interpret lab results` 展示 BLI、SEC、下一轮约束。

## 5.2 Workflow 页面

页面目标：展示蛋白设计路线和模型节点，让用户理解每一步做什么、依赖什么输入、产出什么结果。

当前结构：

- Toolbar：New route、Add node、Start workflow、Copilot panel。
- Route intake：target protein 输入和文件上传。
- Node builder：模型卡、方法控制、计算资源、预览卡片。
- Workflow map：静态 DAG 节点和 SVG 边。
- Copilot panel：静态对话和快捷问题。

目标 workflow：

```text
Target protein
  ↓
Structure preparation
  ↓
RFdiffusion backbone generation
  ↓
ProteinMPNN sequence design
  ↓
AlphaFold2 complex prediction
  ↓
Rosetta relax / interface scoring
  ↓
BDA filters
  ↓
Wet-lab validation
  ↘ feedback redesign constraints
```

当前优化点：

- `AlphaFold3` 模型卡改为 `AlphaFold2`，因为第一批接入是 AF2。
- `OpenMM MD` 在第一批中不是核心节点，可暂时移到 optional methods 或后续插件。
- 节点文案从 RBD 改成 PD-1。
- 计算资源区保留 CPU/GPU 两类：CPU worker 支持 structure preparation、Rosetta、score merge；GPU worker 支持 RFdiffusion、ProteinMPNN GPU、AF2。
- `Start workflow` 在静态 demo 中不应假装提交真实任务，应显示 `Demo mode: compute not connected`。

Node builder 设计：

- 左侧：Model cards。
- 中间：Method controls。
- 右侧：Compute access 和 Preview card。

第一批模型卡：

- RFdiffusion：Backbone generation，GPU。
- ProteinMPNN：Sequence design，GPU preferred / CPU fallback。
- AlphaFold2：Complex prediction，GPU。
- Rosetta：Relax & interface scoring，CPU。
- BDA filters：Selection layer，CPU。
- Wet-lab validation：Experiment queue，manual / data entry。

方法控制：

- Interface score。
- Diversity cap。
- Expression risk。
- Aggregation penalty。
- Hydrophobic patch penalty。
- Auto report。

专家模式后续可增加：

- RFdiffusion contig map。
- ProteinMPNN temperature。
- AF2 recycles、database preset。
- Rosetta score function、relax repeats、interface chain definition。

## 5.3 Candidates 页面

页面目标：把大量模型输出转为实验决策列表。

当前结构：

- Summary strip：Generated、Designed、Folded、Simulated、Ordered。
- Compute status strip。
- Search、status filter、priority only。
- Candidate table。
- Selection rules 和 Copilot note。
- Candidate detail panel。

目标字段：

- Candidate。
- Family。
- Interface。
- Pred Kd 或 Predicted binding score。
- pLDDT。
- interface pAE。
- Rosetta interface energy。
- Clash count。
- Buried SASA。
- Solubility。
- Expression risk。
- Status。
- Decision。

第一版静态字段可以保留当前表格，但建议将 `Pred Kd` 标为预测值或临时指标，避免与 BLI 实测 Kd 混淆。

候选详情设计：

- 顶部结构图。
- 候选 ID。
- 一段自然语言解释。
- 四个核心 score bar：Interface、Confidence、Solubility、Rosetta / MD stability。
- Next action。
- 后续增加：sequence、designed residues、fixed residues、artifact links。

候选状态：

- Validated。
- QC risk。
- Retest。
- Reserve。
- Not tested。
- Ordered。
- Rejected。

决策状态：

- Anchor。
- Order。
- Retest。
- Reserve。
- Hold。
- Reject。

当前优化点：

- 候选 ID 从 `RBDBinder_*` 改成 `PD1Binder_*`。
- 所有 `BLI/SPR` 改为 `BLI`。
- `c4361` 可以保留作为候选编号，但完整 ID 改为 `PD1Binder_c4361`。
- 增加 `Rosetta` 相关列或详情指标，匹配第一批模型接入范围。

## 5.4 Results 页面

页面目标：把实验结果和计算证据变成可汇报的结论与下一轮设计 brief。

当前结构：

- Metric cards：Binding positives、Best Kd、Main QC loss、Decision。
- Interpretation band。
- Delivery package。
- Validation readouts table。
- Round-two design brief。
- Client package。

优化目标：

- `Client package` 改为 `Internal package` 或 `Delivery package`。
- `BLI / SPR` 改为 `BLI`。
- Best Kd 写为 `0.6 nM, BLI`，并在说明中注明 buffer、温度、重复数和拟合方式待补齐。
- Interpretation 中强调：第一版展示的是 PD-1 binder 预计算闭环，不是实时模型运行。
- Round-two design brief 保留：preserve c4361 epitope footprint、increase scaffold diversity、reduce exposed hydrophobic area。

结果页必须避免：

- 把 0.6 nM 写成无来源的泛化能力。
- 把 BLI 说成 BLI/SPR 混合验证。
- 把静态 demo 说成实时运行结果。

## 6. 视觉系统

### 6.1 色彩

当前色彩变量：

- 背景：`#050608`、`#07090d`。
- 面板：`#101216`、`#171a20`、`#20242d`。
- 边线：`#2c323d`。
- 文本：`#f5f7fb`。
- 次级文本：`#9aa4b2`。
- 强调色：cyan `#39d2d8`、green `#28d17c`、amber `#f7b84b`、blue `#35a2ff`。

设计建议：

- 保持暗色专业工作台。
- cyan 用于导航、eyebrow、科技提示。
- green 用于成功、validated、ready。
- amber 用于 review、queued、risk。
- red 只用于失败和严重错误，避免频繁使用。
- 不新增大面积紫色渐变，避免视觉上变成泛 AI dashboard。

### 6.2 字体与字号

当前使用系统 sans-serif，适合静态原型。长期建议：

- 正文：Inter / system-ui。
- 数字：使用 tabular numbers，便于表格和指标对齐。
- H1：页面标题，30-54px。
- H2：卡片标题，16-20px。
- 表格和工具栏：12-14px。

注意：

- 工具页不要使用过大的 hero 字号。
- 表格、节点、卡片中的文字必须优先可扫描。
- 避免负 letter-spacing。

### 6.3 形状与间距

当前圆角 `8px` 合适。建议：

- 卡片、按钮、面板统一 6-8px 圆角。
- 工具类 icon button 固定 38px。
- 面板间距 12-18px。
- 页面 padding 桌面 Web 24px，大屏平板 Web 16-20px。

### 6.4 图标

继续使用 lucide：

- `wand-sparkles`：generation。
- `dna`：sequence design。
- `scan-search`：fold prediction。
- `activity`：simulation / scoring。
- `filter`：selection。
- `flask-conical`：wet-lab。
- `server-off`：compute unavailable。
- `package-check`：delivery package。

图标按钮必须保留 `title` 或 tooltip，避免用户猜含义。

## 7. 组件设计

### 7.1 Topbar

职责：

- 品牌。
- 主导航。
- 系统状态。
- 语言切换。

优化：

- 小宽度浏览器下导航可横向滚动。
- `Auto route enabled` 在静态 demo 中可改为 `Demo mode` 或 `Static demo`。
- 如果计算未接入，顶部状态不应显示 live 绿色点，可改为 amber 或 neutral。

### 7.2 Metric Card

用于 overview、summary、results。

结构：

- label。
- value。
- supporting text。

要求：

- value 使用大号数字。
- supporting text 解释数据来源。
- 如果是实验指标，需要标注方法，例如 BLI。

### 7.3 Workflow Node

结构：

- icon + node name。
- body：节点目的。
- footer：状态或进度。

状态：

- source。
- running。
- completed。
- failed。
- blocked。
- review。

后续节点详情：

- input artifacts。
- output artifacts。
- model version。
- parameter summary。
- compute node。
- logs。
- rerun button。

### 7.4 Model Option

结构：

- icon。
- model name。
- model role。
- resource badge，CPU/GPU/optional。

后续应由 `model-plugins.json` 或 API 返回。

### 7.5 Candidate Table

要求：

- 支持搜索。
- 支持状态筛选。
- 支持 priority only。
- 点击行更新详情。
- 后续支持列配置、排序、分页或虚拟滚动。

静态第一版候选数少，可以保持普通 table。后续真实数据必须引入 TanStack Table 或等价方案。

### 7.6 Detail Panel

职责：

- 解释当前选中候选。
- 给出 score 和 next action。

优化：

- 结构图区域需要固定高度，避免图片尺寸导致布局跳动。
- 分数条需要附带阈值解释。
- 增加 evidence chips：`BLI positive`、`SEC risk`、`Rosetta pass` 等。

### 7.7 Copilot Panel

第一版定位：

- 静态/规则化 Copilot，不接真实 LLM。
- 用于演示 BDA 如何解释候选和生成下一轮约束。

交互：

- quick actions 触发预设回复。
- 输入框可保留，但输出来自本地规则。
- 不允许生成新的实验事实。

后续接 LLM 后：

- 回复必须绑定项目数据。
- 高风险动作需要确认。
- 结构化输出优先。

## 8. 交互设计

### 8.1 路由

当前通过 hash route 切换页面，适合静态 demo。

后续 React/Next.js 中对应：

- `/experiments`
- `/workflow`
- `/candidates`
- `/results`

静态版本应保留 hash，便于本地文件打开。

### 8.2 节点添加

当前流程：

1. 点击 Add node。
2. 打开 node builder。
3. 选择 model option。
4. 勾选 method controls。
5. 预览节点。
6. Add card to workflow。

优化：

- 添加节点后应保留参数摘要。
- 如果 compute unavailable，节点仍可添加，但状态为 `blocked` 或 `not connected`。
- 第一批节点应按 RFdiffusion、ProteinMPNN、AF2、Rosetta、BDA filters、Wet-lab 排列。

### 8.3 候选选择

当前流程：

1. 搜索或筛选候选。
2. 点击候选行。
3. 右侧详情更新。

优化：

- 选中行需要更明显的左边框或背景。
- `Priority only` 应切换按钮 active 状态。
- 空结果时展示 reset filters。

### 8.4 导出

当前 `Export data` 可导出 JSON。

第一版静态 demo：

- `Export CSV` 导出候选 CSV。
- `Export data` 导出 demo JSON。
- `Prepare package` 显示 toast：Delivery package queued / Demo package prepared。

后续真实系统：

- 导出走异步任务。
- 提供 ZIP 下载。
- 导出记录进入 audit log。

### 8.5 中英文

当前 `applyLanguage()` 通过遍历 DOM 文本替换。短期可用，但长期风险较高。

优化：

- 第一版静态 demo 可继续使用现方案。
- 后续应改为 keyed i18n，例如 `data-i18n-key` 或 React i18n。
- 所有动态候选解释需要从数据层同时提供中文/英文，避免自动替换漏文案。

## 9. 数据设计

第一版建议把静态数据抽成 JSON：

- `data/projects.json`
- `data/workflow.json`
- `data/candidates.json`
- `data/results.json`
- `data/translations.json`

### 9.1 Candidate 数据结构

建议：

```json
{
  "candidate_id": "PD1Binder_c4361",
  "family": "F2",
  "interface_score": 94,
  "predicted_binding": "0.6 nM",
  "measured_kd": "0.6 nM",
  "measured_kd_method": "BLI",
  "plddt": 92,
  "interface_pae": null,
  "rosetta_interface_energy": null,
  "md_drift": "1.8 A",
  "expression_risk": "High",
  "status": "Validated",
  "decision": "Anchor",
  "next_action": "Order motif-preserving variants with scaffold diversity cap: max 6 designs per family."
}
```

注意：

- `predicted_binding` 和 `measured_kd` 必须分开。
- BLI 的 buffer、温度、重复数和拟合方式目前为待补齐字段。
- `rosetta_interface_energy` 第一版若无数据可为空，但列和字段可预留。

### 9.2 Workflow 数据结构

建议：

```json
{
  "workflow_id": "pd1_binder_demo",
  "mode": "static_demo",
  "nodes": [
    {
      "node_id": "target",
      "type": "input",
      "title": "Target protein",
      "status": "completed",
      "resource": "local"
    },
    {
      "node_id": "rfdiffusion",
      "type": "model",
      "model": "RFdiffusion",
      "status": "demo",
      "resource": "gpu"
    }
  ],
  "edges": [
    ["target", "rfdiffusion"]
  ]
}
```

## 10. Web 端自适应设计

桌面 Web：

- 顶部导航固定。
- Workflow 画布 + Copilot panel 双栏。
- Candidates 使用表格 + 详情 panel。
- Results 使用 metric grid + readout table。

大屏平板 Web：

- Workflow Copilot panel 可折叠。
- Candidates 详情 panel 下移。
- 卡片从四列变两列。

小宽度浏览器：

- 导航横向滚动。
- 表格允许横向滚动。
- Workflow 画布可以保留横向滚动，后续如有需要再改为纵向 step list。
- 详情面板变成普通 section，不悬浮。
- 手机浏览器不作为第一版核心验收场景。

重要约束：

- 不允许文字溢出按钮或卡片。
- 工作流节点不可互相遮挡。
- 结构图和表格不能挤压到不可读。

## 11. 当前问题与优化清单

P0 必改：

- 全站 RBD / SARS-CoV-2 / ACE2-facing epitope 改为 PD-1 binder。
- `RBDBinder_*` 改为 `PD1Binder_*`。
- `BLI/SPR` 改为 `BLI`，0.6 nM 明确来自 BLI。
- `AlphaFold3` 改为 `AlphaFold2`。
- `OpenMM MD` 从第一批核心节点中移除或标为 optional。
- `Client package` 改为 `Internal package` 或 `Delivery package`。
- 顶部状态从 `Auto route enabled` 改为 `Static demo` 或 `Demo mode`。

P1 优化：

- 静态数据抽 JSON。
- 候选表增加 Rosetta 相关预留字段。
- Workflow 节点增加 CPU/GPU resource badge。
- Add node 面板区分 model cards 和 method cards。
- 结构图区域固定高度，减少布局跳动。
- 导出候选 CSV 真实可用。

P2 优化：

- 引入 React / TypeScript / Vite 或 Next.js。
- 引入 keyed i18n。
- 用 React Flow 替代静态 SVG workflow。
- 用 TanStack Table 替代原生 table。
- 接入 Mol* 或 3Dmol.js。
- 接入本地 API gateway、CPU worker、GPU worker。

## 12. 后续组件拆分建议

如果从静态页面升级为 React，建议组件拆分：

- `AppShell`
- `Topbar`
- `PageHeader`
- `MetricCard`
- `ExperimentCard`
- `CopilotHero`
- `CopilotPanel`
- `AgentActionTabs`
- `RouteIntake`
- `NodeBuilder`
- `WorkflowCanvas`
- `WorkflowNode`
- `ComputeStatusPanel`
- `CandidateTable`
- `CandidateDetail`
- `SelectionRules`
- `ResultsMetrics`
- `ValidationReadoutsTable`
- `DeliveryPackagePanel`
- `Toast`

领域 hook：

- `useDemoProject`
- `useWorkflow`
- `useCandidates`
- `useCandidateFilters`
- `useCopilotDemo`
- `useExportData`

## 13. 验收标准

第一版前端验收：

- 打开本地 `index.html` 即可浏览，无需后端。
- 四个页面可通过顶部导航切换。
- 全站文案统一为 PD-1 binder demo。
- 候选表可搜索、筛选、点击更新详情。
- Workflow 展示 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、BDA filters、Wet-lab validation。
- Results 明确 9/48 BLI 阳性、0.6 nM BLI Kd、SEC aggregation 主要 QC loss。
- Copilot 明确为静态/规则化演示，不编造新实验事实。
- 中文/英文切换后主要文案可读，布局不破。
- 桌面浏览器和大屏平板浏览器下无明显重叠、溢出或不可读；小宽度浏览器只保证基础可访问。

## 14. 设计总结

BDA 前端的核心不是炫技，而是让复杂蛋白设计流程变得可理解、可操作、可追踪。`nolab` 当前已经有很好的工作台雏形：项目入口、Copilot、工作流画布、候选表、结果页都已成形。下一步优化的关键是统一 PD-1 demo 口径、把 RFdiffusion / ProteinMPNN / AF2 / Rosetta 的模型路线讲清楚、把候选和实验数据从硬编码中解放出来，并让每个页面都坚定服务一个问题：这个设计为什么值得继续推进？
