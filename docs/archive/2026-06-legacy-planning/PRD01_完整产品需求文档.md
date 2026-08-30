# BDA Workbench 完整产品需求文档

版本：v1.0  
日期：2026-06-06  
产品名称：BDA Workbench / Biomaterial Design Automation Platform  
第一版核心模型：RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta；XPNN 作为后续模型插件预留，不进入第一版范围  
文档类型：产品需求文档 PRD  
适用阶段：前端 MVP 完善、后端与算法接入、长期平台架构规划  
目标读者：创始团队、产品、前端、后端、算法、结构生物学、湿实验、项目管理、投资人展示支持团队

## 1. 产品摘要

BDA 是一个面向蛋白质设计与生物材料设计的可视化自动化工作台。用户从靶标蛋白、设计目标和实验约束出发，通过平台规划设计路线、展示或调用 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta 等模型模块，生成候选骨架、序列和结构，完成结构与可开发性筛选，选择候选进入湿实验，并把 BLI、SEC、表达、纯化等实验结果回流为下一轮设计约束。第一版前端部署为本地静态网页，以预计算的 PD-1 binder 项目作为 demo；工程架构需要预留后续接入本地服务器、CPU/GPU 计算节点和真实模型运行端口。

一句话定义：

BDA 把蛋白质设计从零散脚本、模型和文件夹，转化为一个可追踪、可解释、可交付、可迭代的 AI 蛋白工程闭环。

当前前端 MVP 已形成四个核心视图：

- Experiments：项目与实验入口，展示 PD-1 binder、蛋白笼、酶修复等项目。
- Workflow：自动路线与工作流画布，支持模型卡片、计算状态、Copilot 对话。
- Candidates：候选物筛选层，支持候选表、状态筛选、优先级筛选、候选解释。
- Results：闭环证据与交付，展示实验读数、结论、第二轮设计 brief 和交付包。

长期目标是成为蛋白质工程领域的 EDA 式平台：不仅生成候选，更沉淀模型、参数、结构、候选、实验和反馈数据资产。

## 2. 背景与机会

蛋白质设计任务已经具备一批强大的模型和工具。第一批接入优先围绕 RFdiffusion、ProteinMPNN、AlphaFold2 和 Rosetta 搭建 binder design 闭环，后续再扩展 Boltz、Chai、OpenMM 和内部模型。但真实研发流程仍然高度碎片化。

主要痛点：

- 流程碎片化：靶点准备、骨架生成、序列设计、结构预测、评分、实验记录分散在不同脚本和文件格式中。
- 决策链断裂：计算结果多为 PDB、FASTA、CSV，实验人员难以直接判断哪些候选应该合成，为什么合成。
- 模型黑箱化：用户难以理解模型基于哪些残基、约束、界面或概率偏好做出设计。
- Benchmark 表达不足：平台中接入的任何模型或方法都需要通过可追溯图表、数据集、baseline 和案例证明。
- 实验结果难回流：KD、kon、koff、表达、SEC、失败原因若不能绑定候选和模型版本，就无法支持下一轮 redesign。
- 项目协作不足：计算团队、湿实验团队、PI 和评审对象使用不同语言理解同一个项目，信息传递成本高。

BDA 的机会在于把“模型能力”包装成“工程流程能力”和“组织协作能力”，让 AI 蛋白设计真正进入可复现、可管理、可交付的产品形态。

## 3. 产品定位

BDA 不是单一模型网页封装，也不是一次性 Demo。BDA 是面向蛋白质设计和生物材料设计的自动化工作台。

产品定位分为三层：

- 模型层：第一批接入 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta，采用 model-agnostic 的模型插件架构，后续可兼容 XPNN、Boltz、Chai、OpenMM 等模块。
- 流程层：把 target intake、task definition、generation、fold prediction、MD、scoring、candidate selection、wet-lab validation、feedback redesign 串成标准化 workflow。
- 决策层：通过结构视图、候选表、评分解释、Copilot、实验 readout 和交付包，把复杂计算结果转化为实验和项目决策。

## 4. 目标用户

### 4.1 计算蛋白设计研究者

关心模型路线、参数、输入输出文件、日志、模型版本、评分指标和 benchmark。需要专家模式、可复现记录、节点重跑、参数导出和模型插件接口。

### 4.2 湿实验研究者

关心候选物是否值得合成、表达是否可行、是否聚集、亲和力如何、下一步实验是什么。需要清晰候选排序、实验队列、FASTA/PDB 导出、失败原因录入和实验结果可视化。

### 4.3 PI / 项目负责人

关心项目是否推进、投入产出比、实验命中率、最佳候选、下一轮策略。需要项目总览、漏斗图、结果解读、benchmark 摘要和交付报告。

### 4.4 外部展示对象 / 评审 / 投资人

关心 BDA 解决了什么问题、案例是否可信、实验结果是否闭环、平台是否具备长期接入模型和计算节点的能力。需要展示模式、隐藏内部路径、保留核心证据和叙事。

## 5. 产品目标与非目标

### 5.1 P0 目标

- 支持用户创建项目、定义 target、启动或展示一条标准 binder workflow。
- 支持 PD-1 binder 案例完整展示：输入、路线、生成、筛选、实验验证、第二轮约束、交付包。
- 第一版前端部署环境为本地静态网页，使用预计算数据；同时预留后续接入 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta 的服务器端口和计算节点接口。
- 支持候选表筛选、候选详情解释、优先级判断和 CSV/JSON 导出。
- 支持 AI Beagle Copilot 的静态/规则化演示，用于解释候选、调整 workflow、生成下一轮设计建议；第一版不接真实 LLM。
- 支持计算资源状态展示，包括 HPC/GPU 不可用时的降级提示。
- 支持中英文界面切换，满足内部研发和外部展示。

### 5.2 P1 目标

- 接入真实后端 API，替换静态数据。
- 接入结构预测、评分、MD、实验数据上传。
- 支持 workflow node 详情、日志、参数和结果文件。
- 支持交付包生成，包括 FASTA、PDB、评分表、报告和第二轮约束。

### 5.3 P2 目标

- 支持多项目、多团队、多模型版本、权限隔离。
- 支持 active learning 和自动 redesign。
- 支持模型注册中心、benchmark registry、数据版本管理和审计日志。

### 5.4 非目标

- MVP 不要求现场实时完成 GPU 重任务，可以使用预计算任务和异步状态。
- 第一版前端不强依赖真实服务器、计算节点、LLM 或 XPNN；但工程设计必须预留 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta 的真实接入接口。
- MVP 不要求覆盖所有蛋白设计任务，优先 binder、multimer、scaffold redesign。
- MVP 不要求完全自动生成实验 protocol，但必须支持实验交付包和实验结果回流。
- MVP 不做泛聊天机器人，Copilot 必须服务于 BDA 的任务定义、路线调整、候选解释和结果回流。
- 第一版不需要外部客户账号、外部 reviewer 独立登录、水印或客户空间。

## 6. 核心使用场景

### 6.1 PD-1 Binder 闭环案例

用户输入 PD-1 靶标结构和指定结合界面，定义 binder design 任务。平台展示预计算路线：target definition → backbone generation → sequence design → fold prediction → MD stability → BDA filters → wet-lab validation。候选经过界面评分、pLDDT、interface pAE、MD drift、solubility、aggregation risk、expression risk 筛选后，48 个进入实验。实验结果显示 9/48 BLI 阳性，最佳 Kd 为 0.6 nM，候选为 PD1Binder_c4361。该 Kd 来自 BLI；具体 buffer、温度、重复数和拟合方式待补齐。平台建议第二轮保留 c4361 epitope footprint，增加 scaffold diversity，并惩罚暴露疏水面积。

### 6.2 多聚体 / 蛋白笼设计

用户定义蛋白笼或多聚体装配目标，输入对称性、chain number、装配几何和 assay 条件。平台生成多聚体兼容序列，预测装配结构，评估界面、对称性偏差、稳定性和可表达性，输出候选和实验建议。

### 6.3 酶 scaffold 修复

用户上传已有酶 scaffold 和实验失败信息，例如低活性、低溶解性或热稳定性不足。平台建议 partial sequence redesign 或 scaffold stabilization 路线，固定活性位点，优化表面残基和稳定性，输出 mutation proposal。

### 6.4 失败候选 Redesign

用户录入实验失败原因，如不表达、聚集、不结合、结合弱或非特异结合。平台将失败原因转化为下一轮约束，例如提高 solubility gate、惩罚 hydrophobic patch、固定已验证界面接触、增加 negative design。

## 7. 信息架构

一级模块：

- Dashboard / Experiments
- Project Overview
- Target Intake
- Task Definition
- Model Route Selection
- Workflow Canvas
- AI Beagle Copilot
- Candidate Analysis
- Protein Structure Viewer
- Benchmark Dashboard
- Experiment Validation
- Feedback Redesign
- Results & Delivery
- Data & Model Registry
- Connections & Compute
- Plugin Registry
- LLM Provider Settings
- Admin & Permissions

当前前端 MVP 合并为四个主导航：

- Experiments：承载 Dashboard、Project Overview、Copilot route summary。
- Workflow：承载 Target Intake、Model Route Selection、Workflow Canvas、Copilot。
- Candidates：承载 Candidate Analysis、Selection Rules、Candidate Detail。
- Results：承载 Experiment Validation、Feedback Redesign、Delivery Package。

长期后台管理区需要增加三个配置入口：

- Connections & Compute：管理服务器、HPC、GPU、云计算节点、健康检查、队列和资源状态。
- Plugin Registry：管理模型插件和方法插件，包括 RFdiffusion、ProteinMPNN、Fold prediction、MD、评分器、实验解析器和报告生成器；XPNN 只作为后续可选插件预留。
- LLM Provider Settings：管理 Copilot 可用的大模型供应商、模型名、密钥引用、结构化输出能力和数据发送策略。

## 8. 页面级需求

### 8.1 Experiments 页面

页面目标：让用户快速理解 BDA 当前项目状态、核心案例和下一步操作。

必须展示：

- 顶部导航：Experiments、Workflow、Candidates、Results。
- 产品名称：BDA Workbench。
- 状态条：自动路线状态、计算资源状态或系统状态。
- 语言切换：中文 / EN。
- AI Beagle Copilot hero：说明 Copilot 能把设计 brief 转化为闭环流程。
- Copilot 快捷动作：Plan route、Adjust workflow、Interpret lab results。
- 项目 overview cards：活跃项目、结合阳性、计算资源、下一步行动。
- 项目卡片：Project_test_0423、Nanocage_delivery_0518、Enzyme_repair_0507。

关键交互：

- 点击 New experiment 进入 Workflow。
- 点击项目 Open 进入对应 workflow。
- 点击 Copilot 动作切换对应视图：路线规划、约束调整、实验解读。
- 中英文切换不应破坏布局。

验收标准：

- 用户在 30 秒内能看懂 BDA 是一个设计-验证-反馈闭环平台。
- PD-1 binder 案例的数字和叙事在 Experiments、Candidates、Results 中保持一致。
- 桌面浏览器和大屏平板浏览器下项目卡、Copilot、overview cards 不重叠。

### 8.2 Workflow 页面

页面目标：用流程画布表达一条可追踪的蛋白设计路线，并允许用户添加模型节点或自动规划路线。

必须展示：

- Toolbar：New route、Add node、Start workflow、Copilot panel toggle。
- New route 面板：target protein 输入、文件上传、示例约束、Auto route。
- Node builder：模型卡片、方法控制、计算资源状态、预览卡片。
- Workflow canvas：节点、连线、反馈边、运行状态。
- Copilot panel：对候选选择、workflow 调整、第二轮设计进行对话。

默认 PD-1 workflow 节点：

- Target protein：PD-1 靶标结构、指定结合界面、BLI 和 SEC 约束。
- Task requirements：设计带表达和可开发性约束的 PD-1 binders。
- Backbone generation：采样 binder backbones。
- Sequence design：序列设计，保留 scaffold diversity。
- Fold prediction：评估 complex confidence、interface pAE、clash。
- MD stability：评估 interface drift 和 exposed hydrophobic area。
- BDA filters：按 interface、fold confidence、solubility、aggregation、expression risk 排序。
- Wet-lab validation：表达、纯化、BLI、SEC、thermal shift。

节点状态：

- Not started
- Queued
- Running
- Completed
- Failed
- Skipped
- Requires review

关键交互：

- New route：用户输入 target 或上传 PDB/mmCIF/FASTA，生成空白路线草稿。
- Add node：选择模型卡片和方法控制，添加到画布。
- Start workflow：检查计算资源；资源不可用时显示明确失败状态，不假装运行成功。
- Copilot：回答候选选择、评分解释、下一步模型、第二轮约束。

验收标准：

- 空白路线、已有路线和计算不可用状态都有明确 UI。
- 用户能理解每个节点的输入、目的、输出和当前进度。
- 节点新增后不遮挡主要 workflow。

### 8.3 Candidate 页面

页面目标：帮助用户从大量候选中选择最值得实验验证和下一轮优化的候选。

必须展示：

- 漏斗摘要：Generated、Designed、Folded、Simulated、Ordered。
- 计算资源状态：HPC/GPU/CPU 当前可用性。
- 搜索框：按 candidate 或 family 搜索。
- 状态筛选：All、Validated、Retest、Reserve。
- Priority only：只看 Anchor、Order、Retest 或 validated candidates。
- Candidate table。
- Selection rules。
- Copilot note。
- Candidate detail panel。

Candidate table 字段：

- Candidate
- Family
- Interface
- Pred Kd
- pLDDT
- MD drift
- Expression
- Status
- Decision

候选详情字段：

- 结构图或 3D viewer。
- 候选说明。
- Interface score。
- Stability / pLDDT。
- Solubility。
- MD stability。
- Next action。

筛选规则：

- Interface score 位于 top decile，且 epitope 无严重 clash。
- Complex pLDDT > 82，interface pAE 可接受。
- MD interface drift < 3.2 A。
- Expression risk 为 medium 或更好。

验收标准：

- 点击候选行后详情面板同步更新。
- 筛选为空时显示 empty state。
- 导出 CSV 包含当前完整候选字段。
- 候选排序理由必须能解释“为什么进入实验”或“为什么暂缓”。

### 8.4 Results 页面

页面目标：把计算和实验结果转化为项目结论、第二轮设计 brief 和内部交付包。

必须展示：

- Binding positives：9/48 BLI-positive candidates，18.8%。
- Best Kd：0.6 nM，候选 PD1Binder_c4361；该 Kd 来自 BLI，buffer、温度、重复数和拟合方式待补齐。
- Main QC loss：SEC aggregation。
- Decision：Round 2。
- Interpretation：说明主要改进方向不是盲目提高 affinity，而是在合成前加强 developability control。
- Delivery package 清单。
- Validation readouts 表格。
- Round-two design brief。
- Internal package 清单。

Validation readouts 字段：

- Step
- Pass
- Signal
- Implication

默认 readouts：

- Expression screen：42/48，F2/F5 families express reliably。
- Purification：36/48，low-yield failures cluster in F1。
- BLI：9/48，best measured Kd: 0.6 nM；buffer、温度、重复数和拟合方式待补齐。
- SEC / aggregation：34/48，exposed hydrophobic patches explain most QC loss。

关键交互：

- Export data：导出 JSON 数据包。
- Prepare package：进入交付包生成队列。

验收标准：

- 结果页所有数字与候选表一致。
- 所有强结论都绑定数据来源、检测方法和比较对象。
- 交付包内容能直接服务实验团队、内部汇报和后续研发沟通。

### 8.5 AI Beagle Copilot

页面目标：作为 BDA 的任务协作层，帮助用户把自然语言需求转化为路线、筛选逻辑和下一轮约束。

核心能力：

- Route planning：根据 target、design objective、assay constraints 生成 workflow 草案。
- Workflow adjustment：根据用户偏好或失败原因调整节点和阈值。
- Candidate interpretation：解释候选排名、风险和推荐实验。
- Lab result interpretation：把实验结果转化为下一轮 redesign constraints。
- Delivery summary：生成内部汇报或展示对象可读的路线依据和结果摘要。

Copilot 不应做：

- 不应脱离项目数据泛泛聊天。
- 不应编造不存在的实验结果。
- 不应在缺失数据时给出确定性结论。
- 不应绕过权限显示内部模型路径、checkpoint 或敏感文件。

MVP 响应模板：

- 第二轮设计：推荐 64 variants，40 个 c4361 footprint-preserving designs，24 个 scaffold-diverse designs。
- 可开发性：提高 solubility gate 到 88，加入 exposed hydrophobic area penalty，expression risk 保持 medium 或更好。
- 评分解释：综合 interface geometry、complex pLDDT、interface pAE、MD drift、solubility、aggregation risk、expression risk。
- 下一模型：若已有 fold prediction，优先加 MD；若已有 MD 和 developability readout，优先加 BDA filters。

### 8.6 Connections & Plugin Registry 后台配置页

页面目标：为接入真实服务器、计算节点、LLM、模型和方法预留可操作入口，避免未来每接一个模型都需要改前端代码。

Connections & Compute 必须支持：

- 新增服务器连接：本地服务器、实验室内网、HPC 登录节点、云端 API、外部模型服务。
- 配置认证方式：API key、OAuth、SSH key、service account。
- 查看 health check：在线、离线、鉴权失败、队列阻塞、资源维护。
- 新增计算节点：CPU、GPU、HPC queue、Kubernetes worker、cloud instance。
- 配置 scheduler：local、Slurm、PBS、Kubernetes、Celery、Temporal、cloud batch。
- 查看节点资源：GPU 型号、GPU 数、CPU 数、内存、队列名、容器运行时、当前任务。

Plugin Registry 必须支持：

- 新增模型插件：填写模型类型、版本、输入 schema、输出 schema、参数 schema、资源需求、运行命令或 API endpoint。
- 新增方法插件：填写方法类型、适用节点、适用模型输出、参数 schema、输出指标。
- 插件验证：schema validate、test run、artifact check。
- 插件状态：draft、active、deprecated、blocked。
- 插件版本管理：同一模型多个版本可以并存，历史 workflow 固定旧版本，新 workflow 默认使用 active 版本。

LLM Provider Settings 必须支持：

- 配置 OpenAI-compatible API、本地模型、私有 endpoint 或云厂商模型。
- 设置 model name、base URL、密钥引用、上下文长度、是否支持 tool calling 和 JSON schema。
- 设置数据策略：是否允许发送序列、结构、实验结果、项目名、内部文件路径。
- 设置用途范围：route planning、candidate explanation、result interpretation、report generation。
- 执行 health check 和结构化输出测试。

验收标准：

- 管理员可以在不改代码的情况下新增一个模型插件，并让 Workflow 的 Add node 面板出现对应模型卡。
- 管理员可以新增一个评分方法，并让 Candidate ranking 或 BDA filters 节点启用该方法。
- 管理员可以新增一个计算节点，并让 Workflow run 提交到该节点。
- 管理员可以切换 Copilot 使用的 LLM provider，同时保留同一套 Copilot 产品能力。
- 外部展示模式下，Connections、Plugin Registry 和 LLM Provider Settings 默认不可见。

## 8.7 第一批模型接入需求

第一批真实模型接入范围：

- RFdiffusion：负责 binder backbone generation。
- ProteinMPNN：负责 backbone-conditioned sequence design。
- AlphaFold2：负责 target-binder complex structure prediction 和 pLDDT / pAE / interface pAE 解析。
- Rosetta：负责 relax、interface analysis、interface energy、clash、shape complementarity 等评分。

第一批不接入 XPNN。XPNN 只作为后续 ModelPlugin 预留，不影响当前数据流和 UI 设计。

### 8.7.1 标准数据流

标准 PD-1 binder 设计数据流：

1. Target intake  
   输入 PD-1 PDB/mmCIF、target chain、binding site residues、optional fixed residues。

2. Structure preparation  
   脚本清洗结构，输出 cleaned target PDB、chain map、residue map、missing residue report、ligand/water removal report。

3. RFdiffusion input builder  
   根据 target chain、hotspot residues、binder length、contig map、number of designs 生成 RFdiffusion 配置。

4. RFdiffusion run  
   输出 backbone PDB、trajectory metadata、run log、seed、contig 和设计约束。

5. RFdiffusion output normalizer  
   统一 backbone 文件命名、chain ID、residue numbering、candidate_id、parent_run_id。

6. ProteinMPNN input builder  
   将 backbone PDB 转换为 ProteinMPNN 输入，生成 fixed positions、designed chains、omit amino acids、temperature、num seq per target 等参数文件。

7. ProteinMPNN run  
   输出 FASTA、sequence score、sampling metadata。

8. Sequence-to-complex builder  
   将 ProteinMPNN sequence 回填到 backbone，生成 candidate complex PDB 和 AF2 输入 FASTA。

9. AlphaFold2 run  
   对 target-binder complex 进行结构预测，输出 ranked PDB、pLDDT、PAE、ranking_debug、result pickle/json。

10. AF2 output parser  
   解析 pLDDT、interface pAE、ipTM 或替代 complex confidence、chain confidence、model rank。

11. Rosetta relax / interface analysis  
   对 AF2 top complex 进行 relax、interface analyzer、clash check、interface energy、buried SASA、shape complementarity、hydrogen bond、salt bridge 等计算。

12. Score merge  
   合并 RFdiffusion、ProteinMPNN、AF2、Rosetta、developability filters 结果，输出候选总表。

13. Candidate ranking  
   根据界面质量、结构置信度、Rosetta 能量、可开发性、多样性和实验约束生成 rank、decision、next action。

14. Delivery package  
   输出 FASTA、PDB/mmCIF、score table、参数文件、run manifest、候选推荐理由。

### 8.7.2 数据对齐脚本

必须准备一组中间数据对齐脚本，保证不同模型之间文件、链、残基编号和候选 ID 一致。

脚本清单：

- `prepare_target.py`：清洗 PDB/mmCIF，统一 chain、删除水分子、可选删除 ligand，输出 target metadata。
- `build_rfdiffusion_config.py`：根据界面参数生成 contig map、hotspot 参数和 RFdiffusion run config。
- `normalize_backbones.py`：规范 RFdiffusion 输出，统一 candidate_id、chain ID、residue numbering。
- `build_mpnn_inputs.py`：生成 ProteinMPNN JSONL、fixed positions、designed chain 配置。
- `thread_mpnn_sequences.py`：将 ProteinMPNN 序列回填到 backbone，输出候选结构和 FASTA。
- `build_af2_inputs.py`：生成 AlphaFold2 complex FASTA、chain break、job manifest。
- `parse_af2_outputs.py`：解析 ranked models、pLDDT、PAE、interface pAE、model confidence。
- `run_rosetta_interface.py`：封装 Rosetta relax、InterfaceAnalyzer、clash 和界面评分。
- `merge_scores.py`：合并所有模型和方法输出，生成候选宽表和 score provenance。
- `validate_artifacts.py`：校验文件存在、hash、schema、候选数量、chain map 一致性。

所有脚本必须遵守：

- 输入和输出用 JSON schema 描述。
- 每一步生成 `manifest.json`，记录输入文件、输出文件、hash、参数、模型版本、脚本版本和运行时间。
- 不用临时文件名作为候选 ID，候选 ID 必须由 project、workflow、node、rank 或 seed 规则生成。
- 中间 PDB 的 chain ID 和 residue numbering 必须可追溯到原始 target。
- 所有脚本支持 dry-run 和 validate-only 模式，便于前端在启动任务前检查参数。

### 8.7.3 界面可调参数

需要把“可以调整的需求部分”抽成界面控件，避免用户直接改配置文件。

Target / task 参数：

- Target chain。
- Binding site / hotspot residues。
- Residues to exclude。
- Fixed target residues。
- Binder length range。
- Number of designs。
- Diversity requirement。
- Output top N。

RFdiffusion 参数：

- Contig map。
- Hotspot residues。
- Number of trajectories。
- Diffusion steps。
- Binder length。
- Symmetry / oligomer setting，第一版可先隐藏，后续开放。
- Random seed。
- Scaffold constraint，后续开放。

ProteinMPNN 参数：

- Designed chain。
- Fixed positions。
- Number of sequences per backbone。
- Sampling temperature。
- Omit amino acids。
- Tied positions，后续开放。
- Soluble / expression-friendly residue preference，作为 BDA filter 参数，不直接改 ProteinMPNN 核心。

AlphaFold2 参数：

- Database preset，full_dbs 或 reduced_dbs。
- Model preset，monomer、multimer。
- Number of recycles。
- Number of predictions per model。
- Use templates。
- Max template date。
- GPU node selection。

Rosetta 参数：

- Relax on/off。
- Number of relax repeats。
- InterfaceAnalyzer on/off。
- Score function。
- Interface chain definition。
- Clash threshold。
- Interface energy threshold。
- Buried SASA threshold。

Ranking / filtering 参数：

- pLDDT threshold。
- interface pAE threshold。
- Rosetta interface energy threshold。
- clash count threshold。
- buried SASA threshold。
- hydrophobic patch penalty。
- solubility score threshold。
- family diversity cap。
- maximum candidates per scaffold family。

界面要求：

- 普通模式只展示任务目标、hotspot、设计数量、binder 长度、top N 和核心阈值。
- 专家模式展示 RFdiffusion、ProteinMPNN、AF2、Rosetta 的完整参数。
- 所有参数变更必须保存为 workflow config，并进入 run manifest。
- 参数控件需要显示默认值、推荐范围、风险提示和是否影响 GPU/CPU 资源。

### 8.7.4 CPU/GPU 端口预留

第一版前端为本地静态网页，但后续接真实计算时需要预留本地服务端口和 worker 类型。

推荐本地端口规划：

- `localhost:8100`：BDA API gateway，统一项目、workflow、candidate API。
- `localhost:8110`：CPU worker API，用于 PDB 清洗、数据对齐、Rosetta、score merge、report generation。
- `localhost:8120`：GPU worker API，用于 RFdiffusion、ProteinMPNN GPU 模式、AlphaFold2。
- `localhost:8130`：artifact/file service，用于上传、下载、manifest、签名 URL。
- `localhost:8140`：job event service，用于 polling、SSE 或 WebSocket 推送任务状态。
- `localhost:8150`：plugin registry service，用于模型和方法插件配置。

CPU worker 必须支持：

- structure preparation。
- data alignment scripts。
- Rosetta relax/interface scoring。
- score merge。
- CSV/JSON/PDF/ZIP export。

GPU worker 必须支持：

- RFdiffusion。
- ProteinMPNN，大批量时优先 GPU，小批量可 CPU fallback。
- AlphaFold2。

端口设计要求：

- 前端不直接调用单个模型端口，只调用 BDA API gateway。
- API gateway 根据 workflow node 和 resource requirement 分发到 CPU 或 GPU worker。
- 每个 worker 暴露 `/health`、`/capabilities`、`/jobs`、`/jobs/{id}`、`/logs/{id}`。
- 端口可通过环境变量覆盖，例如 `BDA_GPU_WORKER_URL`。
- 本地静态 demo 中这些端口可以不可用，但 UI 需要显示 “not connected / demo mode”。

### 8.7.5 计算资源与存储准备

最小开发配置，适合本地 demo、脚本联调、小规模测试：

- CPU：16 cores。
- RAM：64 GB。
- GPU：1 张 NVIDIA GPU，建议 24 GB VRAM，最低不低于 16 GB VRAM。
- 系统盘：1 TB SSD。
- 数据盘：4 TB SSD 或 NVMe，主要用于 AlphaFold2 数据库、模型权重、中间文件和结果。
- 适用任务：小 target、小批量 RFdiffusion、ProteinMPNN、少量 AF2 预测、Rosetta 评分。

推荐工作站配置，适合 PD-1 binder 项目的真实小批量运行：

- CPU：32 cores。
- RAM：128 GB。
- GPU：1-2 张 NVIDIA GPU，每张 48 GB VRAM；如果预算允许，优先 80 GB VRAM。
- 系统盘：1-2 TB NVMe。
- 数据盘：8 TB NVMe/SSD。
- 归档盘：8-16 TB HDD/NAS。
- 适用任务：数百到数千 backbone/sequence 的分批运行，AF2 complex prediction，Rosetta 批量评分。

团队级配置，适合多人和多项目并发：

- CPU：64+ cores。
- RAM：256 GB。
- GPU：2-4 张 NVIDIA GPU，48-80 GB VRAM。
- 高速本地 scratch：8-16 TB NVMe。
- 共享数据盘：16-32 TB NAS 或对象存储。
- 备份盘：与项目数据同量级，至少保留关键 artifact 和数据库配置。
- 适用任务：多 workflow 并行、benchmark、参数扫描、批量候选筛选。

存储估算：

- AlphaFold2 full genetic databases：预留 3 TB，建议放 SSD/NVMe；如果只做小规模测试，可用 reduced_dbs 降低空间占用。
- RFdiffusion / ProteinMPNN / AF2 / Rosetta 容器、conda 环境、模型权重：预留 300-500 GB。
- 单个 PD-1 binder workflow 中间文件：小规模 demo 预留 50-200 GB；数百条轨迹和 AF2/Rosetta 结果建议预留 500 GB-2 TB。
- 结果归档：每个项目建议预留 0.5-2 TB，取决于是否保存所有 AF2 result pickle、trajectory 和 Rosetta silent 文件。

硬件判断原则：

- AF2 通常是最吃显存和数据库存储的步骤，GPU VRAM 和数据库 SSD 是主要瓶颈。
- RFdiffusion 和 ProteinMPNN 可以先小批量跑通，再扩大 trajectories 和 sequences。
- Rosetta 多数流程更偏 CPU，可通过多核并行和任务拆分扩展。
- 如果预算只能优先买一类资源，优先保证 GPU VRAM、AlphaFold2 数据库 SSD、scratch 空间。

## 9. 核心数据对象

### 9.1 Project

- project_id
- project_name
- project_type
- target_id
- owner_id
- status
- current_stage
- created_at
- updated_at
- tags

### 9.2 Target

- target_id
- name
- source_type
- pdb_id
- chain_ids
- sequence
- structure_file_path
- cleaned_structure_file_path
- epitope_residues
- metadata_json

### 9.3 DesignTask

- task_id
- project_id
- task_type
- objective
- constraints_json
- model_route_json
- status
- created_by

### 9.4 WorkflowRun

- workflow_run_id
- task_id
- status
- start_time
- end_time
- compute_resource
- summary_metrics_json
- output_directory

### 9.5 WorkflowNodeRun

- node_run_id
- workflow_run_id
- node_type
- node_name
- status
- model_name
- model_version
- input_files_json
- output_files_json
- parameters_json
- metrics_json
- logs
- error_message

### 9.6 Candidate

- candidate_id
- project_id
- task_id
- workflow_run_id
- family
- sequence
- structure_file_path
- complex_file_path
- interface_score
- pred_kd
- plddt
- interface_pae
- md_drift
- solubility_score
- aggregation_risk
- expression_risk
- status
- decision
- next_action

### 9.7 ExperimentResult

- result_id
- experiment_batch_id
- candidate_id
- experiment_type
- pass_status
- value
- unit
- raw_file
- processed_file
- conclusion
- failure_reason

### 9.8 DeliveryPackage

- package_id
- project_id
- candidate_ids
- report_file
- fasta_file
- structure_bundle
- score_table
- experiment_summary
- redesign_constraints
- created_at

### 9.9 ServerConnection

- server_id
- server_name
- server_type，本地服务器、实验室内网、HPC 登录节点、云服务、外部 API。
- base_url
- auth_type，API key、OAuth、SSH key、service account、none。
- credential_ref，不在数据库明文保存密钥，只保存密钥引用。
- network_status
- health_check_endpoint
- last_health_check_at
- capabilities_json
- owner_id
- enabled

### 9.10 ComputeNode

- compute_node_id
- server_id
- node_name
- node_type，CPU、GPU、HPC queue、Kubernetes worker、cloud instance。
- scheduler_type，local、Slurm、PBS、Kubernetes、Celery、Temporal、cloud batch。
- queue_name
- gpu_type
- gpu_count
- cpu_count
- memory_gb
- storage_path
- container_runtime，Docker、Singularity、Apptainer、none。
- status，available、busy、unavailable、blocked、maintenance。
- current_jobs_json
- resource_limits_json
- last_seen_at

### 9.11 ModelPlugin

- model_plugin_id
- model_name
- model_type，backbone_generation、sequence_generation、fold_prediction、scoring、md_simulation、llm、report_generation。
- provider，internal、open_source、commercial、customer_provided。
- version
- description
- input_schema_json
- output_schema_json
- parameter_schema_json
- artifact_schema_json
- supported_task_types
- supported_file_types
- resource_requirement_json
- default_compute_node_id
- container_image
- command_template
- api_endpoint
- license
- citation
- status，draft、active、deprecated、blocked。

### 9.12 MethodPlugin

- method_plugin_id
- method_name
- method_type，filter、ranking、normalization、metric_calculation、visualization、experiment_parser、redesign_strategy。
- description
- input_schema_json
- output_schema_json
- parameter_schema_json
- compatible_model_types
- compatible_workflow_nodes
- default_parameters_json
- version
- owner_id
- status

### 9.13 LLMProvider

- llm_provider_id
- provider_name
- provider_type，OpenAI-compatible、local_model、private_endpoint、cloud_vendor。
- base_url
- model_names
- auth_type
- credential_ref
- tool_calling_supported
- json_schema_supported
- max_context_tokens
- default_temperature
- allowed_scopes，route_planning、candidate_explanation、result_interpretation、report_generation。
- data_policy，是否允许发送结构文件、序列、实验数据、内部路径。
- status

## 10. API 草案

### Project

- `GET /projects`
- `POST /projects`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}`

### Target

- `POST /targets/upload`
- `POST /targets/from-pdb`
- `GET /targets/{target_id}`
- `POST /targets/{target_id}/clean`
- `GET /targets/{target_id}/preview`

### Workflow

- `POST /design-tasks`
- `POST /design-tasks/{task_id}/route`
- `POST /design-tasks/{task_id}/run`
- `GET /workflow-runs/{workflow_run_id}`
- `GET /workflow-runs/{workflow_run_id}/nodes`
- `GET /workflow-runs/{workflow_run_id}/logs`
- `POST /workflow-runs/{workflow_run_id}/resume-from-node`

### Candidate

- `GET /projects/{project_id}/candidates`
- `GET /candidates/{candidate_id}`
- `PATCH /candidates/{candidate_id}`
- `POST /candidates/filter`
- `POST /candidates/export`

### Experiment

- `POST /experiment-batches`
- `POST /experiment-results`
- `GET /projects/{project_id}/experiment-results`
- `PATCH /experiment-results/{result_id}`

### Copilot

- `POST /copilot/route-plan`
- `POST /copilot/workflow-adjustment`
- `POST /copilot/candidate-explanation`
- `POST /copilot/result-interpretation`
- `POST /copilot/delivery-summary`

### Delivery

- `POST /delivery-packages`
- `GET /delivery-packages/{package_id}`
- `GET /delivery-packages/{package_id}/download`

### Server Connection

- `GET /servers`
- `POST /servers`
- `GET /servers/{server_id}`
- `PATCH /servers/{server_id}`
- `POST /servers/{server_id}/health-check`
- `GET /servers/{server_id}/capabilities`

### Compute Node

- `GET /compute-nodes`
- `POST /compute-nodes`
- `GET /compute-nodes/{compute_node_id}`
- `PATCH /compute-nodes/{compute_node_id}`
- `POST /compute-nodes/{compute_node_id}/health-check`
- `GET /compute-nodes/{compute_node_id}/jobs`
- `POST /workflow-runs/{workflow_run_id}/submit-to-compute`
- `POST /workflow-node-runs/{node_run_id}/submit-to-compute`
- `POST /jobs/{job_id}/cancel`

### Model Plugin

- `GET /model-plugins`
- `POST /model-plugins`
- `GET /model-plugins/{model_plugin_id}`
- `PATCH /model-plugins/{model_plugin_id}`
- `POST /model-plugins/{model_plugin_id}/validate-schema`
- `POST /model-plugins/{model_plugin_id}/test-run`
- `POST /model-plugins/{model_plugin_id}/activate`
- `POST /model-plugins/{model_plugin_id}/deprecate`

### Method Plugin

- `GET /method-plugins`
- `POST /method-plugins`
- `GET /method-plugins/{method_plugin_id}`
- `PATCH /method-plugins/{method_plugin_id}`
- `POST /method-plugins/{method_plugin_id}/validate-schema`
- `POST /method-plugins/{method_plugin_id}/test-run`

### LLM Provider

- `GET /llm-providers`
- `POST /llm-providers`
- `GET /llm-providers/{llm_provider_id}`
- `PATCH /llm-providers/{llm_provider_id}`
- `POST /llm-providers/{llm_provider_id}/health-check`
- `POST /llm/chat`
- `POST /llm/structured-output`

## 11. 前端技术需求

建议技术栈：

- Next.js / React / TypeScript。
- React Flow 或 xyflow 用于 workflow canvas。
- Mol* 或 3Dmol.js 用于结构可视化。
- TanStack Table 用于大规模候选表。
- ECharts 或 Plotly 用于 benchmark 和实验图表。
- Zustand 或 Redux Toolkit 用于状态管理。
- i18n 方案支持中英文。

### 11.1 前端分层架构

前端采用“业务页面 + 领域模块 + 基础组件 + API SDK”的分层方式，避免页面直接拼接后端数据和模型逻辑。

推荐目录结构：

- `app/` 或 `pages/`：路由页面，包括 Experiments、Workflow、Candidates、Results、Admin。
- `features/projects/`：项目、实验列表、项目总览。
- `features/workflow/`：workflow canvas、node builder、route intake、node detail。
- `features/candidates/`：候选表、候选详情、筛选器、ranking 配置。
- `features/results/`：实验结果、交付包、redesign brief。
- `features/copilot/`：Copilot panel、prompt composer、structured response renderer。
- `features/admin-connections/`：服务器、计算节点、LLM provider、插件管理。
- `components/ui/`：按钮、表格、弹窗、toast、tooltip、segmented control 等基础 UI。
- `components/bio/`：结构 viewer、序列 viewer、contact map、score chart。
- `lib/api/`：类型安全 API client，统一处理认证、错误码、重试、分页。
- `lib/schemas/`：共享 JSON schema、Zod schema 或 TypeScript 类型。
- `lib/state/`：全局状态、缓存、用户偏好、语言设置。

前端数据流：

- 服务端数据通过 API client 进入 React Query / SWR 缓存层。
- 页面组件只消费领域 hook，例如 `useProjectCandidates`、`useWorkflowRun`、`useComputeNodes`。
- 长耗时任务状态通过 polling 或 WebSocket / Server-Sent Events 更新。
- 大文件、结构文件、报告文件不进入全局状态，只保存 URL、hash、metadata。
- 用户草稿，例如 workflow draft、筛选条件、Copilot 输入，可短期保存在 local storage，但提交后以后端为准。

### 11.2 前端稳定性要求

- 所有 API 调用必须有 loading、empty、error、retry 四种状态。
- Workflow、Candidates、Results 页面必须支持后端暂时不可用时展示最后一次缓存数据，并明确标注数据时间。
- Candidate table 必须支持分页或虚拟滚动，不能一次性渲染 10 万行。
- 结构 viewer 必须按需加载结构文件，加载失败时展示静态缩略图和下载入口。
- Copilot 调用失败时，不影响 workflow 和候选表的核心操作。
- Export / Prepare package 这类动作必须使用异步任务，不在前端等待长连接完成。
- 中英文切换必须基于稳定 key，不应通过遍历 DOM 文本替换作为长期方案。
- 前端错误需要上报到日志系统，至少包含 route、user_id、project_id、error_code、trace_id。

### 11.3 前端扩展性要求

- Add node 面板中的模型卡片必须来自 `GET /model-plugins`，不能写死。
- Method controls 必须来自 `GET /method-plugins`，并按节点类型过滤。
- Compute access 必须来自 `GET /compute-nodes`，并显示真实状态、队列和资源。
- Copilot 可用能力必须来自 `GET /llm-providers` 和权限策略。
- Candidate table 字段需要支持后端配置列 schema，以便新评分方法增加指标列。
- Results 页面中的 readout 表格需要支持实验类型扩展，例如 ELISA、cell assay、thermal shift、assembly assay。
- 前端所有插件 UI 都应先渲染通用 schema form，复杂模型再逐步提供专用表单。

前端体验原则：

- BDA 是工作台，不是营销页。首屏应展示项目、工作流和可操作数据。
- 工具型界面要紧凑、清晰、可扫描，避免过度装饰。
- 图标按钮优先使用 lucide icons，并提供 title 或 tooltip。
- 关键数据要跨页面一致，避免同一案例在不同页面出现冲突数字。
- 结构图、候选表、实验 readout 必须服务决策，不做纯视觉展示。
- 计算不可用、无候选、无实验结果、导出失败等状态必须有明确反馈。

## 12. 后端与计算架构建议

### 12.1 总体后端架构

后端采用模块化单体优先、服务边界清晰的架构。MVP 阶段不急于拆成大量微服务，但代码和数据边界必须按未来服务化设计。

核心模块：

- API Gateway / Web API：统一认证、权限、请求校验、trace id、错误格式。
- Project Service：项目、target、task、成员、权限。
- Workflow Service：workflow template、workflow run、node run、状态机、节点依赖。
- Candidate Service：候选物、评分、筛选、排序、导出。
- Experiment Service：实验批次、实验结果、原始文件、失败原因。
- Plugin Registry：模型插件、方法插件、schema、版本、状态。
- Compute Orchestrator：计算节点、任务提交、队列状态、日志、artifact sync。
- File Service：结构文件、FASTA、CSV、报告、实验原始文件和签名下载。
- Copilot Service：LLM provider、prompt template、结构化输出、审计记录。
- Report Service：交付包、PDF/ZIP、内部报告和展示包。
- Audit Service：关键操作日志、权限变更、导出记录、Copilot 建议确认。

推荐基础设施：

- FastAPI。
- PostgreSQL。
- Redis。
- Celery / Temporal 用于异步任务。
- S3 / MinIO 用于结构文件、FASTA、报告、实验原始文件。
- MLflow 或内部 registry 记录模型版本和任务结果。
- Connection manager 统一管理服务器、HPC、云端 API、模型服务和 LLM endpoint。
- Secret manager 统一保存 API key、SSH key、service account，不允许在项目数据表中保存明文密钥。

### 12.2 后端服务边界

MVP 可以部署为一个 FastAPI 应用，但内部必须保持以下边界：

- API layer 只做请求校验和权限判断，不写业务流程。
- Domain service 处理项目、workflow、候选、实验等业务规则。
- Repository layer 负责数据库读写。
- Adapter layer 负责外部系统连接，例如 HPC、S3、LLM、模型 API。
- Worker layer 负责异步任务、导出、模型运行、文件解析。

稳定性原则：

- 外部模型、HPC、LLM、对象存储都视为不稳定依赖，必须通过 adapter 隔离。
- adapter 必须有超时、重试、熔断、错误码映射和健康检查。
- 核心业务表不依赖外部服务实时返回，外部失败只影响对应 node 或 job。
- 所有异步任务必须幂等，同一个 `idempotency_key` 重试不能产生重复候选或重复实验结果。

### 12.3 Workflow 架构

- MVP 可使用轻量 executor。
- 长期支持 Nextflow / Snakemake。
- 每个节点定义标准 input_schema、output_schema、parameter_schema。
- Workflow node 不直接硬编码某个模型，而是引用 ModelPlugin 或 MethodPlugin。
- Workflow run 必须记录插件版本、schema 版本、参数、输入输出 hash 和计算节点。
- Workflow 状态机必须明确：draft、validated、queued、running、paused、completed、failed、cancelled、archived。
- Node run 状态机必须明确：not_started、ready、queued、running、completed、failed、skipped、blocked、requires_review。
- 节点依赖必须由 DAG 描述，禁止用前端连线作为唯一真实来源。
- 支持从失败节点重跑、从指定节点 resume、复制历史 workflow 生成新任务。
- 节点输出 artifact 必须有 manifest，记录文件名、类型、路径、hash、大小、生成节点和 schema 版本。
- 长任务进度不通过同步 HTTP 返回，而是通过 job status、event stream 或 polling 返回。

### 12.4 计算架构

- 本地 GPU 服务器。
- HPC 集群。
- 云 GPU。
- 任务队列与资源监控。
- 资源不可用时，前端显示 queued、blocked 或 compute unavailable。
- 计算节点通过 ComputeNode 抽象接入，避免前端绑定具体机器名。
- 支持 Slurm、PBS、Kubernetes、Celery、Temporal、local executor 的适配层。
- 支持同一 workflow 的不同节点提交到不同计算资源，例如结构预测走云 GPU，轻量评分走本地 CPU，报告生成走普通后端队列。
- 每个 compute adapter 需要实现 submit、status、logs、cancel、artifact sync 五类能力。
- 计算任务提交前必须进行 resource validation，例如 GPU 数、显存、容器运行时、输入文件是否存在。
- 计算任务必须有 heartbeat；超过阈值未更新时标记为 stale，并进入人工检查或自动恢复流程。
- 支持计算节点维护模式，维护中的节点不接受新任务，但历史日志仍可查看。
- 支持任务优先级和队列策略，例如 demo 高优先级、批量 benchmark 低优先级。
- 支持 artifact sync：计算节点输出先落本地 scratch，再同步到对象存储并写入 manifest。

### 12.5 模型插件架构

- RFdiffusion。
- ProteinMPNN。
- AlphaFold2。
- Rosetta / interface scorer。
- XPNN，后续可选插件，第一版不接入。
- AlphaFold3 / Boltz / Chai，后续可选插件。
- OpenMM，后续可选插件。
- Developability scorer。
- Experiment parser。
- Report generator。
- 新模型必须通过 ModelPlugin 注册，不应直接写死在前端或 workflow 代码中。
- 模型插件必须声明输入、输出、参数、资源需求、运行方式、版本和 license。
- 同一模型允许存在多个版本，workflow 必须可固定到某个版本运行。
- 已废弃模型不能用于新任务，但历史 workflow 仍可查看和复现。
- 模型插件运行方式支持三类：container command、remote HTTP API、Python SDK adapter。
- 模型插件必须通过 schema validation 才能进入 active 状态。
- 模型插件输出必须写入标准 artifact manifest，不能只返回自由文本日志。
- 模型插件可以提供前端 form schema，让 Add node 面板自动生成参数表单。
- 模型插件必须声明失败类型，例如 input_invalid、resource_unavailable、runtime_error、output_parse_failed、license_blocked。

### 12.6 方法插件架构

- Affinity score。
- Diversity cap。
- Expression risk。
- Aggregation penalty。
- Interface contact recovery。
- Hydrophobic patch penalty。
- SEC risk classifier。
- Redesign strategy generator。
- 新方法作为 MethodPlugin 接入，可被 workflow node、candidate ranking、Copilot 和 report generator 调用。
- 方法插件需要声明适用节点、适用模型输出、参数 schema 和输出指标。
- 方法插件优先设计为轻量、可组合、可复用的 scoring 或 transformation 单元。
- 方法插件必须支持批量输入，避免候选表逐行调用导致性能崩溃。
- 方法插件输出的指标必须带单位、方向和解释，例如越大越好、越小越好、阈值建议。
- Candidate ranking 必须支持多方法加权，且保存权重配置。

### 12.7 LLM 与 Copilot 架构

- Copilot 不绑定单一 LLM 供应商，必须通过 LLMProvider 抽象调用。
- 支持 OpenAI-compatible API、本地大模型、私有 endpoint、云厂商模型。
- LLM 调用必须声明用途 scope，例如 route_planning、candidate_explanation、result_interpretation、report_generation。
- 对每个 LLM provider 设置数据发送策略，明确是否允许发送序列、结构文件、实验数据、内部路径和敏感项目信息。
- 关键任务优先使用结构化输出 JSON schema，避免 Copilot 生成无法解析的自由文本。
- Copilot 建议必须保存 prompt、输入摘要、模型名、模型版本、输出、用户确认状态，便于审计。
- Copilot Service 必须将上下文组装、LLM 调用、工具调用、结果验证分开。
- Copilot 只能通过受控工具访问 BDA 数据，不能直接读取任意文件路径。
- 高风险动作，例如提交 workflow、修改阈值、导出交付包，必须用户确认后执行。
- LLM 输出必须经过 schema validation 和 policy check，失败时返回“需要人工确认”。
- Copilot 的推荐不能直接覆盖实验事实；所有实验数据以 Experiment Service 为准。

### 12.8 数据库与文件架构

PostgreSQL：

- 保存项目、target、task、workflow、candidate、score、experiment、plugin、connection、audit 等结构化数据。
- 关键表使用 UUID 主键，避免跨环境迁移冲突。
- 高频查询字段建立索引，例如 project_id、workflow_run_id、candidate_id、status、created_at。
- JSONB 用于保存可扩展 schema，但核心筛选字段需要提升为独立列，避免查询性能不可控。
- 大规模 candidate score 可拆分为宽表加 JSONB，或按 score_type 建辅助表。

对象存储：

- 保存 PDB/mmCIF、FASTA、CSV、JSON manifest、图片、PDF、ZIP、实验原始文件。
- 所有 artifact 必须记录 hash、size、content_type、created_by_node、schema_version。
- 下载使用短期签名 URL，外部 reviewer 不直接看到内部存储路径。

缓存：

- Redis 缓存 session、任务状态、短期查询结果和事件队列。
- 候选表和 benchmark 图表可以做项目级缓存，但实验结果更新后必须失效。

### 12.9 稳定性与可观测性

错误处理：

- 所有 API 返回统一错误结构：error_code、message、details、trace_id、retryable。
- 前端展示用户可理解的错误，日志保留工程细节。
- 模型、计算、LLM、文件解析错误必须映射为标准错误码。

重试与降级：

- 可重试错误包括网络超时、队列暂时不可用、对象存储短暂失败。
- 不可重试错误包括 schema invalid、权限不足、输入文件损坏、license blocked。
- 计算节点不可用时，workflow 可以保持 queued 或 blocked，用户可切换节点。
- LLM 不可用时，Copilot 降级为模板化建议和手动操作，不阻断主流程。
- 结构 viewer 不可用时，提供结构文件下载、静态缩略图和表格指标。

可观测性：

- 每个请求、workflow run、node run、job、LLM call 都必须有 trace_id。
- 后端记录结构化日志，至少包含 user_id、project_id、workflow_run_id、node_run_id、plugin_id。
- 指标监控包括 API latency、error rate、job queue length、job success rate、artifact sync failure、LLM latency、plugin failure rate。
- 关键事件写入 audit log，例如删除项目、修改插件、导出交付包、切换 LLM provider。

备份与恢复：

- PostgreSQL 每日备份，重要环境支持 point-in-time recovery。
- 对象存储开启版本保留或定期快照。
- 插件配置、workflow template、LLM provider 配置需要可导出和迁移。
- 失败恢复时优先保证数据一致性，再恢复任务执行。

### 12.10 安全性与权限架构

- 认证支持本地账号、企业 SSO 或 OAuth，MVP 可先使用本地账号。
- 权限采用 RBAC，长期可扩展到项目级 ABAC。
- 外部 reviewer 默认无下载权限、无插件配置权限、无内部日志权限。
- Secret manager 保存密钥引用，业务数据库不保存明文密钥。
- 所有导出操作记录 audit log。
- LLM data policy 必须按项目和 provider 生效，敏感项目默认禁止发送序列、结构和实验原始数据到外部 LLM。
- 文件下载必须经过权限校验和签名 URL。

### 12.11 扩展性验收标准

- 新增一个模型时，只需要注册 ModelPlugin、配置运行 endpoint 或 command、绑定计算资源，不需要改动候选表和 workflow 核心数据结构。
- 新增一个评分方法时，只需要注册 MethodPlugin，并在 workflow node 或 ranking 配置中启用，不需要重写候选筛选页面。
- 新增一个 LLM provider 时，只需要配置 LLMProvider 和数据策略，Copilot 的产品能力不随供应商变化。
- 新增一个计算节点时，只需要注册 ComputeNode 并通过 health-check，workflow 即可选择该节点提交任务。
- 所有插件运行失败必须返回标准错误码、日志路径和可重试建议。
- 插件 schema 变更必须保留版本，历史 workflow 不因新 schema 发布而失效。

## 13. 权限与展示模式

角色：

- Admin
- Project Owner
- Computational Scientist
- Experimental Scientist
- Viewer

展示模式要求：

- 使用预计算项目。
- 隐藏内部文件路径、checkpoint hash、敏感参数和未公开实验数据。
- 保留 workflow、候选、结构、benchmark、实验验证和交付包叙事。
- 支持一键演示路径：Experiments → Workflow → Candidates → Results。
- 支持中英文切换。
- 第一版不需要外部客户账号、外部 reviewer 独立登录、项目水印或客户空间。

## 14. 成功指标

产品指标：

- 新用户能否在无工程师协助下理解 PD-1 binder 案例。
- 用户能否从候选表中选出实验优先级。
- 用户是否愿意把实验结果录回平台。
- 用户是否能把 Results 页面直接用于内部汇报。

技术指标：

- 页面首屏加载时间。
- 候选表筛选响应时间。
- workflow 节点状态同步成功率。
- 结构 viewer 加载成功率。
- 导出成功率。
- 任务失败后的恢复率。
- API P95 latency。
- 异步任务成功率。
- 插件 schema validation 通过率。
- 计算节点 health-check 成功率。
- Artifact sync 成功率。
- LLM structured output validation 通过率。
- 关键操作 audit log 完整率。
- 单个外部依赖失败时核心页面可用率。

科学指标：

- 计算筛选通过率。
- 实验命中率。
- 预测评分与 KD / SEC / expression 的相关性。
- feedback redesign 后的命中率或 QC 改善。
- 当前 demo 模型路线相对 baseline 的任务表现；XPNN 指标后续另行定义。

## 15. MVP 里程碑

### M0：当前静态前端整理

- 统一中英文文案。
- 统一案例数字。
- 补齐空状态、错误状态、导出状态。
- 将静态候选数据抽离为 JSON。
- 明确 PD-1 binder demo 数据来源和免责声明。
- 明确第一版为本地静态网页部署，不依赖后端、服务器、计算节点、LLM 或 XPNN。

### M1：交互型前端 MVP

- 候选表支持真实导出。
- New route 表单生成本地 workflow JSON。
- Node builder 生成可持久化 workflow draft。
- Results 导出 JSON / ZIP 模拟包。
- Copilot 响应绑定当前项目状态。

### M2：后端 API 接入

- Project / Target / Workflow / Candidate / Experiment API。
- 文件上传和结构预览。
- 任务状态轮询。
- 候选数据分页和筛选。
- 实验结果录入。
- 统一错误码、trace_id、API 日志和 audit log。
- 对象存储 artifact manifest。

### M3：RFdiffusion / ProteinMPNN / AF2 / Rosetta 接入

- RFdiffusion backbone generation 插件接入。
- ProteinMPNN sequence design 插件接入。
- AlphaFold2 complex prediction 插件接入。
- Rosetta relax/interface scoring 插件接入。
- 中间数据对齐脚本完成：target preparation、RFdiffusion config、MPNN input、AF2 input、Rosetta score merge。
- CPU worker 和 GPU worker 端口打通。
- 模型版本记录。
- 输出候选解析。
- Fold prediction 和 scoring 节点接入。
- 交付包自动生成。
- ModelPlugin / MethodPlugin registry。
- ComputeNode registry 和 health check。
- 至少一个 container command 插件和一个 remote API 插件完成 test run。
- XPNN 作为后续可选模型插件，不作为 M3 默认交付项。

### M4：闭环与展示版

- Feedback redesign 任务生成。
- Benchmark dashboard。
- 内部展示模式。
- 权限和审计基础版。
- LLMProvider settings 和 Copilot 结构化输出。
- 计算节点失败、LLM 失败、结构文件加载失败的降级方案。

## 16. 关键风险与应对

风险：第一版过早绑定某个模型，导致静态 demo 变成模型能力承诺。  
应对：第一版不绑定 XPNN 或任何实时模型能力，只展示 PD-1 binder 预计算闭环；模型插件和 XPNN 接入留到后续版本。

风险：Demo 数字被误读为完整临床或产业验证。  
应对：所有实验结果必须绑定检测方法、条件、样本数、候选 ID 和数据来源。

风险：工作流视觉化但不能真正复现。  
应对：每个节点必须记录 input hash、参数、模型版本、容器版本、seed、输出文件。

风险：候选排序只看亲和力，忽略可开发性。  
应对：默认综合 interface、pLDDT、interface pAE、MD drift、solubility、aggregation、expression。

风险：Copilot 生成不可信建议。  
应对：Copilot 只基于项目数据、候选数据和实验结果回答；缺失数据时必须说明不确定性。

风险：平台过早变成模型陈列柜。  
应对：所有模型插件必须服务于标准 workflow 和候选决策。

## 17. 已确认边界与待确认问题

已确认边界：

- XPNN 第一版先不用管，只保留后续模型插件接口。
- 第一版部署环境是本地静态网页。
- 当前 demo 改为 PD-1 binder 项目。
- 0.6 nM Kd 来自 BLI。
- 第一版不需要外部客户账号。
- 第一版不需要项目水印。

待确认问题：

- PD-1 binder 案例中 0.6 nM BLI Kd 的 buffer、温度、重复数和拟合方式。
- 9/48 BLI 阳性和 34/48 SEC 通过是否来自同一批候选。
- 当前 compute unavailable 是否只是演示状态，还是后续需要接入启明 HPC 状态。
- PD-1 binder demo 的候选命名、结构图和前端静态数据是否需要同步从 RBD 文案改为 PD-1。
- 第一批真实运行使用 AF2 full_dbs 还是 reduced_dbs。
- GPU 采购优先 24 GB、48 GB 还是 80 GB VRAM。
- Rosetta 使用官方二进制、Conda 包、源码编译还是容器镜像。
- RFdiffusion、ProteinMPNN、AF2、Rosetta 是否统一用 Docker/Apptainer 容器部署。

## 18. 产品叙事

BDA 的核心不是“又接了几个模型”，而是把蛋白设计从手工工具链变成工程系统。第一版先用本地静态网页展示 PD-1 binder 的预计算闭环：从 target 到 workflow，从 candidate 到 wet-lab，从 failure reason 到 redesign constraints。对计算团队，它提供未来可复现流程的产品框架；对实验团队，它提供候选决策和实验反馈的工作台雏形；对项目负责人和评审对象，它证明 Bigo Bio 不只是有模型设想，而是有把模型、候选、结构、实验和反馈组织成长期数据资产的平台能力。
