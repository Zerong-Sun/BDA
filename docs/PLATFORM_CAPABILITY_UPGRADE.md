# 全平台能力升级与接入账本

状态：活跃

最后核验：2026-10-11（本地开发与集成范围；外部硬件、商业服务及科研有效性另行验收）

权威范围：本轮跨模块实现、兼容性、开源借鉴方式及全部功能组的后续接入条件。

数据来源：版本化代码、领域文档、回归测试和表中官方开源仓库。成本是规划量级，不是供应商报价。

替代关系：承接既有 2.6 候选版；不把调研清单、模型登记或绿色软件测试当作完整商业发布与真实实验验收。

## 本轮实现

平台继续采用模块化单体、类型化领域接口和持久任务。科研方法包负责“如何做”，工具权限负责“允许做什么”，实际证据、实验审核和决策记录分别保存。没有用另一套 Agent 框架重写可用的执行系统，也没有把外部工具目录全部加载到模型上下文。

1. **论据工作台**：明确论点 ID，保存原文、论文观点、项目解释、支持/反驳关系和定位；源文本变化后提醒并阻止沿用过期复核；支持 CSL-JSON 和 Web Annotation 导出。
2. **研究决策中心**：将假说、备选路线、成功标准、证伪标准、下一次决策及真实论据放在一起；保留并发修改版本及时间线记录。
3. **科研 Skill**：8 个原创方法包，兼容 Agent Skills 文件格式；锁定版本、内容校验和、输入/输出契约及本轮工具证据。选中包不增加执行授权。
4. **项目学习**：新增顺序敏感特征、可替换的预测/校准/推荐接口，训练集内预处理、分组留出与泄漏诊断、成本和多样性推荐。新模型先进入 shadow，再经明确晋升。
5. **实验分析**：BLI、AKTA、酶活提供诊断和限制；新增结果先待审核，只有接受后才映射为候选实测指标，学习层校验对应审核来源。
6. **结构比较**：保留作者编号配对，新增显式序列对齐；报告双侧覆盖与对应关系，多解拒绝静默选取。没有把该算法命名为 US-align 或 TM-align。
7. **真实交付**：冻结记录与源文件，验证 SHA-256，生成有实际内容的 RO-Crate 1.1 ZIP；修复“最新交付”排序。
8. **扩展与模型资格**：独立 `/extensions` 展示已内置、待配置和规划方案，检查现有登记、权重用途复核与运行指纹；明确受限资格可阻止工作流提交。
9. **知识检索**：将搜索移入项目隔离的数据库查询，先过滤后分页；保留来源并显示未知审核状态，不再只检索前 200/500 条记录。

这些升级使用现有依赖或本地原创实现。实际新增、可复用的机制包括标准方法包、Biopython 对齐、SciPy 诊断和开放格式导出；没有安装 LangGraph、PydanticAI、Docling、ESM、BayBE、Temporal 等外部运行时。

## 31 个功能组的落实方式

“本轮实现”指代码变化；“保留并回归”指既有功能继续使用，不宣称重写；“后续接入”意味着执行适配或部署验收尚未提供。

| ID | 功能 | 本轮处理与下一步 |
| --- | --- | --- |
| F01 | 身份、组织、项目权限 | 保留并回归；新写入口复用权限和项目边界。企业 SSO 可接 [Keycloak](https://github.com/keycloak/keycloak)，需真实身份源与迁移演练。 |
| F02 | 靶点和背景 | 保留现有检索；方法包要求来源和证据局限。[ToolUniverse](https://github.com/mims-harvard/ToolUniverse) 精选适配仍需实体映射、配额和来源测试。 |
| F03 | 路线和假说 | 本轮实现决策合同与决策中心，保留否决路线和原始时间线。 |
| F04 | 题录和引用 | 本轮 CSL-JSON 导出；[Zotero](https://github.com/zotero/zotero) 双向同步、去重冲突处理后续接入。 |
| F05 | 原文和论据 | 本轮论点身份、人工页/节/图定位、源漂移与 Web Annotation；[Docling](https://github.com/docling-project/docling)/[GROBID](https://github.com/grobidOrg/grobid) 坐标解析尚未安装。 |
| F06 | 综述和筛选 | 方法包约束检索范围及反证；[PaperQA](https://github.com/Future-House/paper-qa)、[ASReview](https://github.com/asreview/asreview) 需标注集和漏检评测后接入。 |
| F07 | 知识和记忆 | 本轮完整项目范围的关键词分页检索；[pgvector](https://github.com/pgvector/pgvector) 和时序知识图谱需检索基准、更新/删除一致性。 |
| F08 | 情报和专利 | 本轮确保引用原件变化在情报上下文中可见；保留官方检索边界。专利族、法律状态覆盖仍不能等同 FTO。 |
| F09 | Bot 和持久执行 | 本轮类型化方法输出、证据调用核验；保留当前持久执行。[PydanticAI](https://github.com/pydantic/pydantic-ai) 或 [LangGraph](https://github.com/langchain-ai/langgraph) 只在对照验收后替换具体子流程。 |
| F10 | 科研 Skill | 本轮 8 个版本化方法包及 UI 选择、运行快照；格式参考 [Agent Skills](https://github.com/agentskills/agentskills)，未复制混合许可第三方正文。 |
| F11 | MCP 与互通 | 保留协议子集与权限表；完整 [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) 互操作测试和 A2A 后续接入。 |
| F12 | 工作流 | 本轮增加模型资格预检；[Nextflow](https://github.com/nextflow-io/nextflow) 科学管线可先包装单个插件，禁止双重提交与重试。 |
| F13 | 计算与恢复 | 保留 outbox、Celery、Docker/LSF 合同并回归。真实故障注入、跨日恢复和 [Temporal](https://github.com/temporalio/temporal) 是独立验收项。 |
| F14 | 模型插件 | 本轮确切代码/权重/用途复核、失效状态与登记检查；不把配置文件当作真实主机观测。 |
| F15 | 蛋白设计 | 保留已有模型声明和独立插件；[BoltzGen](https://github.com/HannesStark/boltzgen)、[Foundry](https://github.com/RosettaCommons/foundry) 已列资源与资格条件，未启动计算。 |
| F16 | 结构预测 | 本轮统一资格门控；AF3/Chai/Boltz 等各权重和任务适用性仍需单独评测，不因共享接口互相替代。 |
| F17 | 结构和界面 | 本轮新增 Biopython 序列对应与报告；[US-align](https://github.com/pylelab/USalign)、[ProLIF](https://github.com/chemosim-lab/ProLIF) 执行和基准仍需后续接入。 |
| F18 | 序列和构建体 | 保留序列、保守性、密码子功能并回归；[DNA Chisel](https://github.com/Edinburgh-Genome-Foundry/DnaChisel) 多重合成约束需真实供应商规则。 |
| F19 | 配体 | 保留导入与目录；[RDKit](https://github.com/rdkit/rdkit) 标准化需版本固定、盐/立体化学政策和原结构留存，尚未安装。 |
| F20 | 候选和轮次 | 本轮成本/多样性选择与可解释排除原因；保留候选谱系与实验事实分离。 |
| F21 | 实验与质控 | 本轮审核和学习来源约束；批次效应、重复类型与检测限仍需各 assay 的真实 SOP 和验证数据。 |
| F22 | BLI/AKTA/酶活 | 本轮残差、参数可辨识性和数据条件诊断；拟合成功不自动成为合格测量。 |
| F23 | ELN/LIMS | 保留轻量记录；[eLabFTW](https://github.com/elabftw/elabftw) 库存、条码与团队签核接入列为后续方案。 |
| F24 | 机器人和外包 | 扩展中心列出 [PyLabRobot](https://github.com/PyLabRobot/pylabrobot)、Opentrons/外包条件；无新设备执行或下单适配。 |
| F25 | 学习和不确定性 | 本轮可替换接口与泄漏诊断；当前特征为 461 维人工描述符，非 ESM。[ESM](https://github.com/evolutionaryscale/esm)、[BoTorch](https://github.com/meta-pytorch/botorch)、[MAPIE](https://github.com/scikit-learn-contrib/MAPIE) 必须用项目留出与前瞻对照证明增益。 |
| F26 | Autopilot 和预算 | 保留预算预留、取消与阶段状态；方法包不会放大 Autopilot 权限；机器人与真实多阶段反馈尚未闭环。 |
| F27 | 制品和交付 | 本轮实数据 ZIP、校验与 RO-Crate；[OpenLineage](https://github.com/OpenLineage/OpenLineage)/MLflow 为后续跨系统接口。 |
| F28 | 评测和运维 | 本轮扩展契约、负例与全栈回归；[OTel](https://github.com/open-telemetry/opentelemetry-python)、Langfuse/Inspect 成本与科学正确性评测服务另行部署。 |
| F29 | 前端和呈现 | 本轮决策中心、方法库、质控、学习评测和扩展中心，沿用 React/Mol*/React Flow；新增浏览器页面覆盖。 |
| F30 | 专家报告 | 本轮可追溯研究交付；[marimo](https://github.com/marimo-team/marimo)/Quarto 可重放分析需独立沙箱、依赖锁与资源限额。 |
| F31 | LAAS 价值 | 本轮将论据、决策、审核、学习和交付衔接；完整计费、合同/SLA、客户上线与实验收益证明仍是独立产品工作。 |

## 高成本方案的取舍

扩展中心保存每项方案的资源、数据、许可、预算复核和触发条件。优先在真实需求出现时小规模对照：模型表示层在现有特征不足时试验 ESM；样本与批次规模足够时比较 BayBE/BoTorch；跨日任务出现可量化恢复问题时再迁移持久引擎。机器人、云实验室、企业身份、可重放 notebook、向量/图检索、大规模科学模型分别验收，不要求一次性购买整个技术栈。

工程预算应拆成适配开发、算力/存储、外部 API、运维、许可及真实实验六部分。扩展中心的工期与资源区间是规划假设，具体费用需要选定供应商、目标吞吐和实验规模之后估算；当前没有运行价格测试或购买服务。

## 发布、兼容与回滚

- Schema 从 `0073_learning_lifecycle` 升至 `0074_research_decision_contract`，只新增研究目标 JSON 合同列。先备份再迁移；降级会删除该新增内容，因此优先回滚应用并保留扩展列。
- 旧学习数据集、旧算法及原作者编号结构配对保持可读；新数据集特征和推荐策略记录版本，不重写旧结论。
- 实验审核从新分析结果开始严格执行。历史未审核数据保持明确状态，不批量补造人工接受记录。
- 新模型资格属于可选但有约束力的登记：缺记录的旧插件提示警告；已经声明但不合格、过期或用途不符的记录阻止提交。
- 应用、worker 与 OpenAPI/SDK 必须一起升级；旧 worker 不会自动加载新交付或诊断代码。
- 本轮不调整 `/api/v2` 和包身份，不发布未经真实实验验收的 GA，也不将研究模型表现写成客户收益承诺。

## 本轮软件验证

| 验证 | 结果 |
| --- | --- |
| 后端完整测试，含隔离 PostgreSQL | 2,505 通过、7 跳过；总体语句覆盖率 89.91%，关键模块覆盖门禁通过 |
| 研究包分支覆盖 | 60 项通过，104/104 分支，100% |
| 前端完整测试 | 169 文件、1,055 项通过；随后修复选择框初始显示 ID，新增回归并通过 31 项相关复验 |
| 桌面浏览器矩阵 | 86 个用例；83 个首轮通过，修复测试契约后其余 3 个定向复验通过 |
| 静态与契约 | Ruff、mypy、ESLint（4 个既有 TanStack 编译器警告）、TypeScript、构建体积门禁通过；OpenAPI/SDK 可逐字节再生成 |
| 数据与文档 | 90 张表 / 253 条路径数据流检查通过；插件目录、CPU 声明与文档入口检查通过 |
| 并发与来源 | 交付双连接 QC 撤回、有效 RLS/角色继承、未提交数据拒绝、原件哈希变更和跨项目引用均有回归 |
| 数据迁移 | 隔离 PostgreSQL 完成降至 base、升级至 0074 及 Alembic 差异检查；本地运行库先备份，再升级至 0074，未对运行库执行降级 |
| 本地运行 | API、worker、scheduler 和 beat 已更新；健康检查、方法目录、扩展目录、研究目标、知识检索和学习列表均返回成功 |
| 真实模型链路 | 现有 DeepSeek 配置通过结构化输出、证据复制、路线选择和工具调用四项检查；合成演示项目完成一次只读方法包任务，输出通过契约与实际工具引用校验，证据不足时保留 partial |

7 个跳过项分别为专用 Bot 并发测试 1 项、私有决策合同 1 项、单独启用的 scheduler 角色权限测试 3 项、未配置容器镜像的 gate 执行测试 2 项。没有把这些条件性测试计为通过。集群脚本检查因当前无 LSF stage 跳过真实生成器验证；本轮不探测远端主机。未重建容器或重跑远端 CI / 安全扫描，依赖锁文件未变化。

真实模型验收限制为 4 轮、180 秒和项目内只读调用；实际运行 3 轮，未写入科研记录、启动计算或运行实验。当前模型未配置可信计价，费用状态为 unavailable；不能将展示值 0 解读为免费。带金额上限的首次验收请求在模型调用前被现有计价门禁阻止，随后使用轮数和时限约束完成检查。该检查仅验证运行和结构化交付，不证明科学判断正确。

各模块操作说明见[文档索引](README.md)。软件测试、真实部署与科研有效性分别记录；上述通过不证明新方法提升药物研发成功率。
