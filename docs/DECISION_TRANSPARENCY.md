# 决策透明度：哪些判断被记录、由谁作出、谁必须放行

状态：活跃

最后核验：2026-09-12（Asia/Shanghai；本轮七条规则全部落地并实跑门禁）

权威范围：本文只规定「一个判断如何被归属、证据如何被引用、哪些步骤必须由人放行、一次批准可以承载多少」。MCP 能力面见 [MCP 能力面](MCP_CAPABILITY_SURFACE.md)；Autopilot 的执行与预算模型见 [Autopilot 协议与实现边界](AUTOPILOT_CAMPAIGNS.md)；Copilot 自身的能力边界见 [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md)。

数据来源：`backend_v2/app/{timeline,autopilot,core}/`、`frontend/src/features/{timeline,plugins,jobs,results}/`、`backend_v2/tests/test_{project_timeline,review_budget,autopilot_stage_gates,autopilot_formalization}.py`。

替代关系：不取代任何现有文档。

---

## 1. 设计问题

平台越来越多的工作由 agent 完成，而记录层对此**一无所知**。三个具体缺口：

- 一条判断是研究者推理出来的、模型起草而人接受的、还是模型自己决定的，在表里**长得一模一样**。因此「agent 定的参数和我定的，哪种更好」这个问题无法从数据回答——它需要归属在当时就被写下来。
- 证据字段可用但没人填。`project_timeline_entries` 建表时就有六个 provenance 键；两个种子脚本合起来填过 `job_ids` **一次**，49 条进了 `external_refs` 且都是 LSF 作业号**字符串**，`artifact_ids` / `candidate_ids` / `workflow_run_ids` 全生命周期为空。
- 中断点是 campaign 级的一个二档开关。supervised 要么问每一步（评审人开始不读就批），要么什么都不问。两者都不是监督。

## 2. 七条规则

| # | 规则 | 机制所在 |
| --- | --- | --- |
| 1 | 一条判断记录**谁的判断**，且归属不由写入方声明 | `timeline.service.create_entry(decided_by=…)` |
| 2 | Autopilot 确认落成决策节点，冻结 spec 作为可寻址依据 | `autopilot.service._record_confirmation_decision` |
| 3 | 一次批准可以承载多少，集中声明 | `core/review.py` |
| 4 | 平台自己拥有的对象**只能选，不能打字** | `frontend/.../provenanceSources.ts` |
| 5 | 每个参数值说明它**来自哪里** | `frontend/.../parameterOrigin.ts` |
| 6 | 哪些阶段必须由人放行，按**步骤做什么**决定 | `autopilot/gates.py` |
| 7 | 决策卡出现在**事件现场**，证据已预填 | `frontend/.../RecordDecisionButton.tsx` |

### 2.1 归属：`decided_by`

`human` / `agent` / `agent_proposed_human_confirmed` / `unspecified`。

**由服务层从写入者身份设置，`TimelineEntryCreate` 与 `TimelineEntryUpdate` 上都没有这个字段。**
能设置它的调用方也能把 agent 的工作盖上 "human"，那时比较的就是标签而不是作者——与「D 编号只由编排者分配」、「ledger 只接受单一写者」是同一条纪律。两个测试盯着这个字段的**缺席**。

`agent_proposed_human_confirmed` 单独成一档，不并入任何一侧：模型起草、人逐条接受产生的东西，既不是人推理出来的判断，也不是没人复核的判断，而**它正是被委托的工作产生的主要形态**。合并掉它就毁掉了唯一值得做的比较。

默认 `unspecified` 而非 `human`：回填等于把猜测写成记录（种子历史里有在集群上、脚本参与下作出的判断）。列表端点因此可以按 `decided_by` 过滤——这才让问题可问。

### 2.2 评审预算

`core/review.py` 把「一次批准可以承载多少」集中声明，原因写一次：**读不完整个列表的评审人会停止评审、开始接受**。

这不是存储上限。`Field(max_length=…)` 防的是荒谬的载荷；评审预算更小，理由是人的注意力，即使数据存得下也约束。

落地时发现的缺口：**Autopilot 的 stages 原本无上限**。frozen spec 从 prompt 规范化而来，confirm 一次接受全部阶段，没有任何东西阻止模型提出四十个阶段。现在在建 draft 时就拒（过长的 spec 不会成为待确认的东西），confirm 时再查一次（那才是批准动作）。

`research_generations` 的导入**在册豁免**：它要求 `validation.valid` 为真，且要求调用方回传预览时的 checksum，因此被批准的东西是被钉住的——这是决策树 bootstrap 没有的防线；而它的数量上限绑在已发布的包格式上。一个测试断言这两条防线仍然存在，豁免的理由一旦腐蚀就会失败。

### 2.3 证据只能选

平台拥有的对象由**选择器**回答，没有可以打字的框。这是机制而不是便利：校验可以被粘贴绕过，不存在的控件不能。

三类，分法本身是诚实的部分：

- **可选**——jobs / candidates / artifacts / workflow runs / findings / experiment results / 构建体，都已有项目级列表。
- **可填但校验为 UUID**——`autopilot_campaign_ids` 没有列表接口，且它的行由 confirm 服务写入而非手打。
- **自由文本**——只有 `external_refs`。它存在的目的正是平台**不拥有**的东西（LSF 作业号是它的由来），在这里要求 UUID 是错的。它是唯一的例外，也正因为有它，规则在别处才能严格。

已引用但不在当前列表里的 id **仍然显示**。一条记录可能引用了已被过滤或删除的行，下一次保存时静默丢掉它等于悄悄改写记录。

### 2.4 参数来源

`default` / `recommended` / `edited` / `constrained`，只显示后三者——每个未改动字段都挂徽章会淹没真正携带信息的那几个。

`constrained` 胜过一切，包括恰好等于默认值的被锁定值：**改变读者该怎么做的事实是「它被锁定了」**，不是它碰巧与默认值相同。这个来源是真实的而非脚手架：插件声明的 `resources.cpus` 驱动 `-n`、`span[ptile]` 与工具自己被告知的线程数，`compute/scripts.declared_cpus` 存在的目的就是让三者不能不一致；一个放任线程参数单独漂移的表单，正在生产本项目视为**违规**而非通知的那种不一致，而且看起来和任何一个可编辑数字没有区别。

`recommended` 作为入口接好但未接数据源：route plan 已经算出每个模块的 `default_parameters`，但那条路今天到不了画布，凭空造一个来源等于给一个无事实支撑的声明挂徽章。

### 2.5 阶段放行

`autopilot/gates.py` 按**步骤做什么**声明层级，两个人真正能回答的属性：**是否可逆**，以及**是价值问题还是经验问题**。MSA 搜索多深是经验问题，agent 大概更强；是否动用预算、材料是否上台，都不是——它们属于承担后果的人。

层级在 confirm 时**冻结到 stage 行上**：后来重新分类一个 stage key，不得静默重新打开一个别人在旧分类下确认过的 campaign。

**未识别的 stage key 被扣留。** 没人分类过的阶段就是没人想过的阶段，在它上面猜"安全"是让门失去意义的方式。

**今天刻意不扣留 `compute`**，并作为决定而非疏漏记录在此：它的 adapter 产出的 `workflow_runs` 行停在 draft，平台没有任何从 Autopilot 阶段走到提交的路径。现在扣留它会拦住一个什么都不花的步骤，并且在门真正守住任何东西之前，就教会人们径直点过它。层级现在就声明，为的是**某个阶段开始提交的那天，改这里一个词就能扣留它**，而不是靠谁注意到问题出现了。`submit` / `wetlab` / `bench` / `express` / `assay` / `order` 同样提前分类——门必须先于能力存在，否则第一个湿实验阶段是不设门上线的。

放行按阶段、带 `If-Match`、由人在 ledger 上署名并附扣留理由、且**幂等**：两条放行记录会让"谁放的"无法回答，而那是这条记录唯一存在的理由。放行一个从未被扣留的阶段会被拒——在没人被要求批准的东西上签名，会让放行日志声称比实际发生更多的复核。

### 2.6 决策卡在事件现场

设计原理研究四十年的结论换个说法就是：**需要额外一个动作才能捕获的 rationale 不会被捕获**。所以动作移到 id 已经在手的地方：一个已终止的作业、一条已测量的 assay，各自带一个"记一条决策"，打开编辑器时证据已引用。

只在**已终止**的作业上提供。对还在飞的运行作判断是计划，因为被判断的东西还能变；`isSettledJob` 读 `TERMINAL_JOB_STATUSES` 而不是重复它。`failed` 计入：否定结论是本项目最贵的资产，也最容易不被记录。

**预填的只有平台知道的事实**，标题、结论与被否分支留空，且有测试盯着。预填一个判断等于把模型的意见放在人的签名之下，而这条记录存在的目的恰恰是说清一个判断是谁的。

## 3. 本轮实跑门禁

| 检查 | 结果 |
| --- | --- |
| `ruff` / `mypy`（250 文件） | 通过 |
| `pytest backend_v2/tests` | 通过 |
| `npm --prefix frontend test` / `run build` | 通过 |
| `check_flow_matrix.py` | 通过，78 表 / 190 路径 |
| `check_document_inventory.py` | 通过 |
| `check_plugin_cpu_declarations.py` / `check_cluster_claims.py` / `check_decision_coverage.py` | 通过 |
| `alembic upgrade head` → `check` → `downgrade base` | 一次性数据库上往返通过 |
| OpenAPI 与生成 SDK | 重新生成后无漂移 |
| `check_coverage.py` | **未达 85%**：本机 82.05%，HEAD 基线 81.78% |

覆盖率差额在本机是既有状态。本轮新增模块自身为 `core/review.py` 100% / `copilot/citations.py` 100% / `mcp_app.py` 95.6% / `autopilot/gates.py` 91.7% / `mcp.py` 86.4%，全部高于总体，因此是把总数抬上去的。

## 4. 已知边界

- **`recommended` 参数来源没有数据源。** route plan 算出的 `default_parameters` 到不了画布；接通它需要一条从 route plan 到 NodeBuilder 的路径，那是独立的改动。
- **`compute` 未扣留是一个会过期的决定。** 它成立的前提是「没有阶段会提交」。这个前提一旦变化，`gates.STAGE_TIERS` 里的一个词必须同时变化，而目前没有任何机械检查会提醒这件事——检查它需要先有提交路径。
- **归属只覆盖 timeline。** `campaign_decisions`、`research_findings` 的审阅状态等其他判断载体没有 `decided_by`。先做 timeline 是因为它是决策树的载体；推广前应当先确认其他表的判断是否同样存在"模型起草、人接受"这一形态。
