# Copilot 服务、入口与接口指南

状态：活跃

最后核验：2026-09-07（Asia/Shanghai；对照当前工作树代码与 OpenAPI）

权威范围：BDA v2 的 Copilot 服务种类、前端入口、工具权限、HTTP 接口、模型配置与实现边界。平台整体成熟度见 [README](../README.md)。

数据来源：[能力目录](../backend_v2/app/copilot/capabilities.py)、[工具注册](../backend_v2/app/copilot/tools.py)、[API](../backend_v2/app/copilot/api.py)、[OpenAPI](../backend_v2/openapi.json) 和本文链接的前端组件。

替代关系：取代旧 Copilot 能力规划、DeepSeek 配置说明和验证报告作为当前操作依据；旧版本见[归档索引](archive/README.md)。研究包协议单独见[研究包指南](RESEARCH_PACKAGES.md)。

## 1. 定位与默认入口

Copilot 是围绕研究目标推进工作的项目助手。默认入口是同一工作区中的目标输入、任务计划、进度和交付物；简单问题进入对话，连续工作先展示可修改的服务类型及授权范围。Research 的调研入口复用同一工作区。系统的文本分类只是可修改的建议，不决定权限。

用户侧提供五类服务：**明确研究目标、调研与比较证据、制定实验方案、跟进执行与处理异常、解读结果与设计下一轮**。13 类能力是开发者的权限分组，29 个工具是执行接口，不要求用户理解这些内部分类。

启动前检查任务计划；外部检索和保存笔记分别勾选授权，未勾选只读取现有资料。运行时按步骤收窄工具范围。任务卡持续展示实际步骤、来源、交付内容、缺口和下一步，原始轮次默认折叠。项目首页可进入助手或直接继续专业页面。

任务书交付物可以编辑后应用为项目 prompt，保存时携带项目版本和修改原因。停止的任务可以保存为 `pending_review` 标签的计划记录，再进入项目决策树关联目标和编辑；该动作不批准科学结论。补充信息可继续原任务，可保留或缩小写入授权，费用额度不变，最多增加 12 轮，总上限 200。

Autopilot 保留高级“按批准方案运行”入口和独立的方案确认、计算预算协议。Copilot 任务与 campaign 尚未共用完整执行状态机，当前不开放完整无人值守闭环。

### 按任务查找专业入口

Copilot 提供项目内的问答、证据检索、研究草案、实验工具调用和多步后台任务。部分 AI 功能嵌在项目页、Research 和 Workflow 中，使用独立领域接口，并不经过聊天接口。

| 你要做的事 | 从哪里使用 | 实际结果与下一步 |
| --- | --- | --- |
| 了解项目、解释候选或已有实验结果 | 顶部 Copilot → 询问或解释；各页面的上下文 Copilot 按钮 | 返回带实体引用的回答。不会自动改变评分、审核结论或实验记录。 |
| 起草项目任务书（prompt） | 新建项目对话框；项目页任务书卡片 | 后台生成可编辑草案；用户创建项目或保存修改后才成为项目任务书。也可以完全手写。 |
| 做连续文献调研 | Research → 文献与证据 → AI 辅助文献调研 | 启动持久化任务，检索、等待、读取可获取内容、保存待审核笔记；在任务记录中检查产物。 |
| 发起一次文献检索、靶标分析或资料缺口修复 | 聊天明确提出操作，或对应 Research 操作按钮 | 返回检索/分析/修复任务 ID 和 pending 状态；完成情况读资源或 operation。 |
| 保存研究笔记 | 聊天明确要求“保存为待审核笔记”；或回答上的保存入口 | 新建待审核知识记录。保存不等于通过科学审核。 |
| 选择计算路线 | Copilot → 制定实验方案；Workflow 中的路线规划 | 助手读取模板目录并交付待审核方案；Workflow 页面比较后创建工作流。两者都不提交计算。旧 CopilotActions 组件保留兼容实现，默认抽屉不再展示其直接建图按钮。 |
| 从任务书建立目标和决策树 | 决策记录/时间线的空记录引导 | 起草目标与分支，用户逐项编辑、删除，再导入正式记录。 |
| 查蛋白库、计算浓度或稀释方案 | 聊天调用实验工具；或 Lab 页面 | 查询和计算不写实验结果。无需项目和模型的直接计算入口是顶部工具箱。 |
| 将候选纳入实验、分析仪器文件、关联研究目标 | Lab/Candidates/结果页面；也有受限 Copilot tools | 部分动作会写入蛋白库、实验结果或目标关联，必须明确请求并满足权限。文件分析需要已上传的同项目 artifact。 |
| 处理需等待的多步任务 | Copilot → 我的任务与交付物 | 服务端保存轮次、工具调用、成本与等待状态。可离开页面后返回；停止任务使用取消入口。 |
| 看执行脚本并运行 | Workflow → 提交工作流 → 预览 → 确认；或计算草案确认面板 | 这是用户控制的执行接口，确认后 worker 才可能创建/提交真实作业。聊天没有提交工具。 |

入口实现：[Copilot 抽屉](../frontend/src/components/ui/CopilotDrawer.tsx)、[Research](../frontend/src/app/Research.tsx)、[Workflow](../frontend/src/app/Workflow.tsx)、[任务书](../frontend/src/features/projects/ProjectChooser.tsx)、[决策树引导](../frontend/src/features/timeline/DecisionTreeBootstrap.tsx)。完整用户路径见[平台使用指南](GUIDED_PLATFORM_WORKFLOW.md)。

## 2. 聊天、后台任务和页面 AI 的区别

| 类型 | 执行方式 | 适用范围 | 成功的含义 |
| --- | --- | --- | --- |
| 普通聊天 | `POST /api/v2/copilot/chat` 返回 202，worker 处理，消息列表/SSE 返回回答 | 一次咨询、有限工具调用、排队请求；每轮工具预算最多 6 次 | 回答已保存。排队动作仍可能未完成；开发环境无模型时只返回明确标注的工作区计数提示。 |
| 后台任务（agent run） | 返回 202；多轮状态、等待和成本持久化 | 连续研究、等待领域任务或已存在的计算作业；允许时可创建一级子任务 | 执行状态与交付状态分开。模型结束回复不能直接证明目标达成；平台检查所选服务的必需交付章节、步骤与引用记录，再显示交付物待审核、部分完成、受阻、需补充或需审核。 |
| 页面 AI 辅助 | 任务书/决策树草案走各自后台接口；路线推荐与模型测试在当前请求中调用模型 | 起草可编辑材料、选模板、测试连接 | 草案或推荐准备好，后续保存、审核、应用、提交仍是分别发生的动作。 |
| 确定性平台服务 | 计算器、仪器拟合、模板构图、状态查询、导入校验、作业脚本渲染 | 已声明的数据处理和执行规则 | 对应计算或业务操作完成；本身不是 LLM 推理或科研审核。 |

后台任务可以恢复等待中的**平台任务**；它并不是对任意网站、shell 或任意 HTTP 请求的自动重试代理。agent run 的 `skills` 缩小项目允许的能力集，不能扩大权限。Research 的专用调研入口使用 literature 配方，其能力上限为 `project-read`、`research-read`、`knowledge-authoring`、`literature-search`，其中写工具还须在计划中单独授权。

## 3. 服务边界与权限

- 查询以当前用户和项目为边界，实体 ID 仍由服务端复核。前端页面上下文和所选记录只提供定位信息，不授予权限。
- 普通聊天的写工具须匹配明确的正向请求；新后台任务使用服务端保存的 `authorized_writes`。后者是明确授权的工具清单，不能超出项目能力或服务配方；补充消息和子任务不能扩大该清单。所有工具在同一注册入口校验参数和写权限，调用未提供的工具会被拒绝。
- 模型工具名是服务端函数名，不是 HTTP URL。模型通过白名单调用领域服务，不直接拿到数据库、shell、文件系统或密钥。
- 模型可以创建计算**草案**，没有确认计算、提交作业、取消作业、批准科学证据、删除项目的普通聊天工具。HTTP 中存在这些接口，不代表模型获得调用能力。
- `draft` 不能一概理解为“不写数据库”：知识草案会落库，`wetlab-authoring` 的分析会记录结果，`research-trace-authoring` 会建立关联。具体副作用见能力表。
- 普通聊天的 `skill` 只接受规范能力 ID；配置和 agent run 的 `skills` 支持兼容别名。`research` 是较宽的历史能力集合，包含计算草案及实验写入；它不等于专用文献调研入口的四项权限。
- `enabled_skills=[]` 现在明确表示禁用全部工具；未提供配置时才继承默认能力。迁移 `0056` 将旧空列表转换成显式 `research`，保留原部署语义。保存模型设置不会把已禁用的权限重新打开。后台每轮都会收窄已被项目撤回的权限。完整项目权限矩阵仍主要通过配置 API 管理。

### 可直接使用的请求示例

- 只读：“解释这条候选记录的评分，引用已有结果；缺失的指标请列出来，不新增记录。”
- 检索：“请检索当前项目的文献，并读取可获取的正文或摘要；请保存带引用的待审核笔记。”多步请求优先用后台任务。
- 实验计算：“用 A280=1、消光系数 10000、分子量 12000 Da、光程 1 cm 计算浓度。”数值和单位必须明确。
- 计算草案：“请为已有工作流准备 LSF 计算草案，列出输入、资源和待确认项。”接下来由用户在确认面板检查。

## 4. 模型配置：用户需要做什么

**已有平台模型**：选项目 → Copilot → 模型设置，查看当前模型及“继承平台配置/项目配置”，再测试连接。普通用户无需输入 API Key。

**开发环境的项目 BYOK**：展开高级模型设置，填写服务地址、模型名和 API Key 后保存。服务端将密钥写入 `BDA_V2_LLM_LOCAL_SECRET_DIR` 下的受限文件，数据库保存 `file:` 引用；不是仅存在进程内存。持久化依赖该目录的部署与备份配置。

**生产环境**：浏览器禁止提交长期原始密钥。管理员注册 provider，通过环境变量或挂载文件提供 `env:` / `file:` 凭据引用，并确保 API 和相关 worker 都能解析。当前适配器不直接调用任意 secret-manager SDK；密钥管理系统需把凭据注入为可读环境变量或文件。

统一选择顺序为：支持显式模型选择的请求中指定的有效模型 → 项目绑定模型 → 唯一共享默认模型。显式选择失效不会悄悄切换模型；其他项目的 BYOK 不参与共享默认选择。未创建的项目没有项目级配置，任务书生成使用可用的共享默认模型。

共享默认的具体规则：

1. 设置 `BDA_V2_LLM_DEFAULT_PROVIDER_REF` 时，按注册 provider 的 `credential_ref` 筛选，须唯一。
2. 没设置该值时，优先选择唯一 `config.platform_default=true` 的共享启用模型。
3. 无默认标记时，仅在恰好一个共享启用模型的情况下继承；多个候选视为未配置明确默认。

当前 wire 协议为 OpenAI-compatible **Chat Completions**，并使用 Bearer 凭据。服务地址会追加 `/chat/completions`（已经以此结尾则保持）；需要 `/v1` 的提供方应在 base URL 中包含 `/v1`。工具型任务还要求模型支持 function/tool calls；仅“连接测试通过”不能证明工具调用、引用或结构化输出可靠。

管理员使用 `/api/v2/registry/llm-providers` 注册模型，示意请求如下。占位地址和名称需按实际服务替换；不在请求中放原始 Key。

```json
{
  "name": "Platform research model",
  "provider_type": "openai_compatible",
  "endpoint": "https://provider.example.invalid/v1",
  "model": "<model-id>",
  "credential_ref": "env:BDA_RESEARCH_MODEL_KEY",
  "config": { "platform_default": true },
  "enabled": true
}
```

配置实现：[模型选择](../backend_v2/app/copilot/provider_selection.py)、[凭据及模型请求](../backend_v2/app/copilot/provider.py)、[项目配置服务](../backend_v2/app/copilot/service.py)、[注册 schema](../backend_v2/app/registry/schemas.py)。

### 按任务检查模型

`GET …/task-readiness` 读取当前模型的检查结果；`POST …/config/assessments` 发起两次模型请求，检查结构化任务书字段、固定证据值及来源、已知可用路线选择、function call 参数四项。测试工具不会执行领域操作。结果仅是协议样例检查，不是科学能力或真实外部流程验收。

检查记录保存在项目配置的服务端保留字段 `task_qualification`，普通配置更新不能伪造它；记录绑定 provider 身份、版本、配置与模型，7 天有效。模型改变后自动失效，任务等待后恢复也会复核。五类引导服务按所需检查开放；没有通过仍可使用专业页面手动操作和普通问答。高级 `custom` API 任务保持兼容，不会因此获得“已验证”的交付标签。

管理员可在 provider `config.bda_pricing` 填写 `input_usd_per_million`、`output_usd_per_million`，并设置输出 token 上限。设置费用额度的后台任务在每次模型请求前按输入字节、输出上限和最多重试次数保守预留；没有价格则在调用前停止，不能把未知成本显示为免费。未限定输出时，有价格的提供方默认 `max_tokens=2048`。费用是平台估算，不能替代服务商账单或服务商侧的硬限额；不含另行批准的集群计算费用。

## 5. 异步结果与故障恢复

| 看到的状态/错误 | 应如何理解和处理 |
| --- | --- |
| HTTP 202 / pending / running | 请求已接受或正在执行。保留 operation、draft、search 或 agent run ID，按对应资源查询，不重复创建同一任务。 |
| 草案 ready | 草案可供检查；任务书、目标树和研究派生内容仍需各自保存/导入。 |
| agent run awaiting_tasks | 在等待已登记的任务，服务端在结果到达后唤醒。用户无需保持网页打开。 |
| agent run succeeded | 仅表示 runner 正常结束；界面以 `outcome.status` 展示交付状态。旧记录没有可验证的 outcome 时显示需审核。 |
| outcome completed | 配方步骤及所引用的成功工具记录通过结构检查；交付物待审核，不表示科研结论已经成立。 |
| outcome partial / blocked / needs_input / review_required | 显示剩余步骤或原因；补充信息可继续原任务，并可撤回写入授权；新增授权须另建计划。没有结构化交付、捏造工具引用或任意开放目标不能自动标成 completed。 |
| 无可用模型 / credential_unavailable | 确认唯一默认或项目绑定、provider 启用状态，以及执行进程能否读取凭据。 |
| 无效 JSON / 无效证据 ID / 不适用路线 | 不接受自动推荐；修正输入、选择模板或更换已验证模型后重试。 |
| 中文检索转换失败 | 配置有效模型，或改用英文检索词。零检索结果只说明该次查询未找到记录。 |
| 403 / capability disabled | 检查用户权限和项目能力配置；前端提示词不能绕过。 |
| 412 | 资源已变化，重新读取版本、检查内容后再操作。 |
| 503 / 长时间 pending | 检查写入开关、凭据、API、outbox publisher 及 research/copilot worker。 |

聊天 SSE 输出 `message` / `done` 事件并支持 `after_message_id`。聊天历史与后台任务轮次的真源是数据库；后台任务取消接口使用当前 `If-Match`，取消/级联范围按返回结果核对。

## 6. 已实现与仍需验收的边界

- `POST /api/v2/copilot/interpretations` 当前做的是记录摘要/计数，没有调用模型。聊天对结果的解释才可能使用 LLM。
- `POST /api/v2/copilot/route-plans` 的 `use_model` 默认是 `false`。前端路线规划传 `true`，模型只在现有目录内选择；直接调用 API 而省略该字段得到的是模板规则建议。
- “生成相似研究”是基于来源项目资料的派生与可选外部检索，不应当作已完成独立、全面的文献综述。导入成功也不等于科学审核通过。
- 决策树草案基于项目任务书生成，用户确认导入后形成目标/记录；不能据此宣称实验已执行。
- 聊天与后台任务共用科学事实、引用和操作边界的基础政策。后台 literature / interpretation 的结构化交付还经过带真实工具记录的自动科学复核，复核不可用时降为需审核；这些自动检查不能代替人工评审。
- 聊天和后台任务从同一工具注册表生成 schema；所有写操作统一检查权限，普通聊天的实验写工具使用当前请求的授权，后台任务使用已批准范围。阶段检查验证记录是否存在，无法证明任意自然语言科研目标完全满足。
- 强模型、弱模型都须分别验证工具选择、结构化输出、证据引用、失败恢复和不越过提交边界。连接成功、模拟测试通过、过去某次运行记录，都不代表当前客户环境的全流程已经验收。
- Copilot 后台任务与 Autopilot campaign 是不同服务。后者的预算协议、人工接管、stage adapter 和未完成闭环见 [Autopilot 当前边界](AUTOPILOT_CAMPAIGNS.md)。

## 7. 开发者：能力与模型工具清单

下表按 `capabilities.py` 的授权分组列出 13 类服务、29 个不同工具。部分读工具在多个能力中共享；实际参数、执行上下文及权限以工具注册和领域服务为准。`GET /api/v2/copilot/skills` 返回能力元数据，不是完整工具参数 schema。

| 能力 ID | 模型工具名 | 服务及副作用 |
| --- | --- | --- |
| `project-read` | `list_project_targets`, `list_project_candidates`, `list_experiment_results`, `get_workflow_status`, `get_compute_status` | 读靶标、候选、实验、工作流及计算状态；不修改。 |
| `research-read` | `research_overview`, `search_research`, `get_research_items`, `get_dataset_slice`, `get_reference`, `get_reference_content`, `list_research_goals` | 读研究实体、数据集、目标和已保存的论文内容；搜索工作区不等于外部检索。 |
| `result-interpretation` | `list_project_candidates`, `list_experiment_results` | 复用候选/实验读取工具供模型解释；不写评分或测量值。 |
| `knowledge-authoring` | `search_project_knowledge`, `create_knowledge_draft` | 搜索知识；明确请求后新建待审核知识草案。 |
| `literature-search` | `start_literature_search` | 排队 Europe PMC 检索和摄取；返回可追踪的异步资源。 |
| `target-intelligence` | `start_target_intelligence` | 对同项目的精确 operational Target 排队分析。 |
| `research-gap-repair` | `resolve_research_gaps` | 对精确 Research target 修复可获取资料，科学性缺口仍保留。 |
| `workflow-planning` | `get_workflow_status`, `plan_workflow_route` | 查询工作流，读取确定性模板目录供模型比较；创建与提交仍走用户页面/API。 |
| `wetlab-read` | `list_proteins`, `compute_concentration`, `plan_dilution_series` | 读蛋白库；做浓度和稀释计算，无实验记录写入。 |
| `wetlab-authoring` | `promote_candidate_to_bench`, `analyse_bli_run`, `analyse_akta_run`, `analyse_enzyme_plate` | 明确请求后提升候选为实验构建体，或分析已上传 artifact 并记录实验结果。 |
| `research-trace-authoring` | `attach_to_research_goal` | 明确请求后将已有结果、候选、构建体等关联研究目标。 |
| `agent-orchestration` | `await_compute_job`, `spawn_subagent` | 仅后台 agent run：等待已存在作业、创建受父任务权限和深度限制的子任务。不是提交计算工具。 |
| `compute-drafting` | `get_compute_status`, `create_compute_draft` | 读计算状态，创建待确认计算草案；不确认、不提交。 |

## 8. 开发者：HTTP 接口地图

以下均为 `/api/v2` 的完整路径。写接口的命令权限及字段以 [OpenAPI](../backend_v2/openapi.json) 为准；前端通过[生成 SDK](../frontend/src/lib/api/generated/sdk.gen.ts)调用。后台 worker 通过领域 service 执行工具，不是模拟用户逐个点击这些接口。

### 8.1 Copilot 自有接口（完整清单）

| 方法与接口 | 提供的服务 | 返回/执行位置 |
| --- | --- | --- |
| `GET /api/v2/copilot/task-services` | 五类服务、能力上限、写工具及步骤目录 | 200，同步，只读 |
| `GET /api/v2/copilot/projects/{project_id}/task-readiness` | 当前模型的有效检查记录和可用服务 | 200，同步，只读 |
| `POST /api/v2/copilot/projects/{project_id}/config/assessments` | 两次模型调用，运行四项协议检查 | 200，服务端保存与模型指纹绑定的检查结果 |
| `POST /api/v2/copilot/agent-runs/{run_id}/continuations` | 创建者补充要求并继续停止的根任务 | 202，须 If-Match；不扩大写入或费用范围 |
| `POST /api/v2/copilot/agent-runs/{run_id}/decision-records` | 用户把交付内容保存为待审核计划记录 | 200，须 If-Match；同一交付重复保存复用记录 |
| `GET /api/v2/copilot/skills` | 查询能力元数据 | 200，同步，只读 |
| `POST /api/v2/copilot/chat` | 创建/继续对话并发送消息 | 202，含 conversation、message、operation；copilot worker |
| `GET /api/v2/copilot/projects/{project_id}/conversations` | 项目对话列表 | 200，cursor 分页 |
| `GET /api/v2/copilot/conversations/{conversation_id}` | 对话详情 | 200 |
| `GET /api/v2/copilot/conversations/{conversation_id}/messages` | 权威消息记录、引用及工具结果 | 200，cursor 分页 |
| `GET /api/v2/copilot/conversations/{conversation_id}/stream` | 消息更新流 | 200，SSE，`message`/`done` |
| `GET /api/v2/copilot/projects/{project_id}/config` | 项目配置与有效模型信息 | 200，ETag；无专属记录时返回版本 0 的继承视图，不写数据库 |
| `PUT /api/v2/copilot/projects/{project_id}/config` | 保存模型绑定、偏好和能力集 | 200；修改已有记录须 If-Match |
| `POST /api/v2/copilot/projects/{project_id}/config/tests` | 调用当前有效模型测试连接 | 200，connected/reason；当前请求同步调用模型 |
| `POST /api/v2/copilot/route-plans` | 返回模板选项，按 use_model 决定是否请模型推荐 | 200，同步；不创建工作流 |
| `POST /api/v2/copilot/interpretations` | 汇总记录中的候选/结果信息 | 200，同步，当前不调用 LLM |
| `POST /api/v2/copilot/agent-runs` | 创建持久化多步任务 | 202，run + operation_id；copilot worker |
| `GET /api/v2/copilot/projects/{project_id}/agent-runs` | 项目任务列表 | 200，cursor 分页 |
| `GET /api/v2/copilot/agent-runs/{run_id}` | 任务状态、预算与成本 | 200，ETag |
| `GET /api/v2/copilot/agent-runs/{run_id}/turns` | 读取模型/工具轮次 | 200，cursor 分页 |
| `POST /api/v2/copilot/agent-runs/{run_id}/cancellations` | 用户取消后台任务 | 200，须 If-Match；返回取消结果，不是普通聊天工具 |

聊天请求主要字段：`project_id`、`message`、可选 `conversation_id`、`skill`、`context`。`context` 支持 `route`、`research_tab`、`selected_entity_ids`、`language`；顶层 `intent=review_section` 用于章节辅助。

后台任务主要字段：`project_id`、`goal`、`service_kind`、`authorized_writes`，可选 `skills`、`max_turns`、`max_cost_usd_cents`。默认配方 UI 和 API 为 24 轮，旧专家面板为 12 轮；金额单位为美分。服务端生成并保存 `task_contract`，客户端不能提交完成判据。响应 `outcome` 包含步骤、交付内容、缺口、来源操作和产物入口；`status` 保留执行状态兼容。

### 8.2 嵌在页面中的 AI 和研究交接

| 方法与接口 | 所属领域 / 使用位置 | 结果和后续动作 |
| --- | --- | --- |
| `POST /api/v2/projects/prompt-drafts` | Projects，新建/完善任务书 | 202；organization_id、name、project_type、summary、language，可选已有 project_id；后台生成 |
| `GET /api/v2/projects/prompt-drafts/{draft_id}` | Projects | 读 pending/ready/failed；草案权限按创建者及组织/项目规则复核 |
| `POST /api/v2/projects` | Projects | 用户把最终 prompt 保存为新项目；不是模型工具 |
| `PATCH /api/v2/projects/{project_id}` | Projects | 更新任务书；有旧任务书时修改须说明 prompt_change_reason，并带 If-Match |
| `POST /api/v2/projects/{project_id}/decision-tree-drafts` | Research，空记录引导 | 202；从已有任务书起草目标树 |
| `GET /api/v2/decision-tree-drafts/{draft_id}` | Research | 读取生成状态和可编辑 proposal |
| `POST /api/v2/projects/{project_id}/decision-tree` | Research | 201；用户确认后导入目标与分支记录 |
| `POST /api/v2/projects/{project_id}/literature/searches` | Literature，检索 | 202；检索/摄取任务 |
| `GET /api/v2/literature/searches/{search_run_id}` | Literature | 读取结果计数、完成状态或错误 |
| `GET /api/v2/literature/documents/{document_id}/chunks` | Literature | 读取保存的正文/摘要片段 |
| `GET /api/v2/literature/documents/{document_id}/retrieval-traces` | Literature | 检查检索来源、校验值及状态 |
| `POST /api/v2/projects/{project_id}/research-generations` | Research，生成相似研究 | 202；来源项目派生草案及可选外部证据 |
| `GET /api/v2/research-generations/{generation_id}` | Research | 读草案、校验信息和 checksum |
| `POST /api/v2/research-generations/{generation_id}/import` | Research | 201；带 checksum 确认导入，不代表审核通过 |
| `POST /api/v2/copilot-research-imports/validate` | Research，结构化回答导入 | 校验结构化研究结果，无模型推理 |
| `POST /api/v2/copilot-research-imports` | Research | 201；用户导入符合 schema 的结构化结果 |
| `GET /api/v2/operations/{operation_id}` | Platform | 统一跟踪异步操作 |
| `GET /api/v2/operations/{operation_id}/events` | Platform | 读取操作进度事件流 |

领域数据的其余 CRUD、审核、订阅接口见 OpenAPI；它们的存在不增加 Copilot 工具权限。

### 8.3 用户控制的执行与配置交接

| 方法与接口 | 谁调用 / 用途 |
| --- | --- |
| `POST /api/v2/projects/{project_id}/workflow-runs` | UI 把选定方案创建为普通工作流草案；无 `/copilot/apply-route` 接口 |
| `GET /api/v2/workflow-runs/{workflow_id}/preflight` | UI 读取输入、插件及运行证明检查 |
| `POST /api/v2/workflow-nodes/{node_id}/script-previews` | UI 读取确定性脚本和输入 manifest；不提交 |
| `POST /api/v2/workflow-runs/{workflow_id}/submissions` | 用户确认后提交；Idempotency-Key，当前 UI 传 workflow_version |
| `POST /api/v2/compute-drafts` | 有权限的客户端创建计算草案 |
| `GET /api/v2/compute-drafts` | 列出项目计算草案 |
| `GET /api/v2/compute-drafts/{draft_id}` | 用户审查草案 |
| `POST /api/v2/compute-drafts/{draft_id}/confirm` | 用户确认，202 后由后台处理；不能通过普通聊天确认 |
| `GET /api/v2/registry/llm-providers` | 查看注册模型 |
| `POST /api/v2/registry/llm-providers` | 管理员注册模型和凭据引用 |
| `GET /api/v2/registry/llm-providers/{provider_id}` | 读取模型配置 |
| `PATCH /api/v2/registry/llm-providers/{provider_id}` | 管理员更新注册模型，按 ETag 防止覆盖 |

代码位置：[Projects](../backend_v2/app/projects/api.py)、[Research](../backend_v2/app/research/api.py)、[Literature](../backend_v2/app/literature/api.py)、[Compute](../backend_v2/app/compute/api.py)、[Workflows](../backend_v2/app/workflows/api.py)、[Registry](../backend_v2/app/registry/api.py)。

## 9. 维护与交付检查

改入口、工具或 API 后，同时更新本文的任务表、能力表、接口表。接口和 schema 变化还须重新生成 OpenAPI/SDK。不要把已注册工具、前端按钮、后台 worker 和真实外部执行视为同一层能力。

最小核对范围：能力白名单与否定请求、项目隔离、配置继承、任务状态与恢复、无效模型输出、引用来源、草案到确认的权限边界。对应测试在 `test_copilot_capabilities.py`、`test_copilot_actions.py`、`test_copilot_registry.py`、`test_copilot_agent_runs.py`、`test_copilot_agent_loop.py`、`test_guided_platform.py`、`test_copilot_task_contracts.py`，前端入口测试在 `frontend/src/features/copilot/`、`frontend/src/app/researchPage.test.tsx`。

部署本次代码前须执行迁移 `0056_copilot_task_contracts`，然后同步更新 API 与 worker。迁移已在隔离 PostgreSQL 数据库验证升级、模型一致性和降级，没有修改现有运行数据库。

交付目标为桌面网页版，Copilot 的交互设计与验收以桌面浏览器为准，手机端不在当前开发与交付范围内。本次验证覆盖自动化测试、构建和中英文桌面浏览器流程，没有调用真实模型、外部检索或客户集群。真实部署验收按[平台验收清单](GUIDED_PLATFORM_WORKFLOW.md#客户部署验收)记录模型、环境、时间、输出和失败场景。历史验证报告只证明当时的环境，不能替代本次交付验收。
