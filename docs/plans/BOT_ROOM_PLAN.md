> **规划资料，非当前功能清单。** 本文描述尚未实现的形态。当前行为见 [Bot-first 科研工作台](../BOT_FIRST_WORKSPACE.md)、[Copilot bot 名册](../COPILOT_BOT_ROSTER.md)与 [决策透明度](../DECISION_TRANSPARENCY.md)。

# 研究室：一个群聊入口、可见的交接、以及在结构上选位点

状态：规划（P0–P4 全部未实现；不得当作已有能力引用）

最后核验：2026-09-14（Asia/Shanghai；对照 `codex/bot-first-science-workspace` 合并点 `8007e022`，该点已合入六人名册、职责页、决策收件箱与按角色的权限门）

权威范围：本文只规定「人与 Bot 在哪一个界面里协作、Bot 之间的交接如何呈现、哪些判断需要停下来问人、以及如何在三维结构上选择位点并让它进入计算」。能力与权限边界仍以 [Copilot 服务与权限指南](../COPILOT_SERVICE_GUIDE.md) 为准；对外调用契约仍以 [MCP 能力面](../MCP_CAPABILITY_SURFACE.md) 为准；谁负责链条哪一段仍以 [Copilot bot 名册](../COPILOT_BOT_ROSTER.md) 为准。

数据来源：`backend_v2/app/copilot/{api,service,tasks,agent_loop,agent_runs,bots,handoffs,tools,registry,models,mcp,mcp_app}.py`、`backend_v2/app/{structures,intelligence,timeline}/`、`frontend/src/app/{Bots,BotDetail,Inbox}.tsx`、`frontend/src/features/copilot/`、`frontend/src/features/pdb-viewer/`、`backend_v2/alembic/versions/00{24,26,33}_*.py`、`qm-scripts/library/catalog.json`，均核对于 `8007e022`。外部参考：MCP Apps 扩展（2026-01-26）、MolViewSpec、BindCraft/BoltzGen 的 hotspot 输入形态。

替代关系：不取代任何活跃文档。本文是 [Bot-first 科研工作台](../BOT_FIRST_WORKSPACE.md)的下一组迭代（iteration 7 起）的规划；实施后各期行为写回该文档，本文对应阶段随之移入归档。

---

## 1. 问题陈述

到 `8007e022` 为止，Bot 这条线已经有六个真实存在的东西：

| 已有 | 位置 |
| --- | --- |
| 六人名册（conductor / researcher / planner / runner / analyst / auditor），能力只收窄不放宽 | `copilot/bots.py`，`GET /copilot/bots` |
| 交接是数据库行，claim 带 `{statement, evidence_ref, confidence}` | `copilot_handoffs`，`GET /copilot/projects/{id}/handoffs` |
| 每个 Bot 有职责页：职责、手上的任务、收发的交接、工作台链接、对话 | `/bots/:botId`（`app/BotDetail.tsx`） |
| 决策收件箱：需要补充信息、待审交付、待确认计算草稿、待审文献断言、无依据断言 | `/inbox`（`app/Inbox.tsx`），只读汇总，不新增端点 |
| 委派：`conductor` 可为另一个 operator 开子 run，子 run 用自己的 charter | `delegate_to_operator`，`copilot_agent_runs.parent_run_id` |
| 判断归属三态 `human / agent / agent_proposed_human_confirmed`，由服务层按写入者设置 | `project_timeline_entries.decided_by` |

缺的不是零件，是**这些零件没有一个共同的房间**。具体五条：

1. **没有群聊。** 对话（`/bots?view=chat`）、交接（`?view=handoffs`）、任务（`?view=tasks`）是三个页签。人要在三个页签之间自己拼时间线，才能回答"刚才发生了什么"。
2. **对话不记录是谁回的。** `copilot_messages` 没有 `bot` 列；`bot_hint` 只写在用户那一轮的 `context` 里（`tasks.py:99`）。所以一段包含多个 operator 的对话，事后无法按发言人复原——而这正是群聊的最低要求。
3. **派活要离开对话。** 指派任务在任务页签的 composer 里，对话里说"让方案设计去做"不会产生任何东西。
4. **决策没有独立形态。** 需要人拍板的事今天是从五个来源**推断**出来的（`Inbox.tsx` 里五个 `useQuery`），Bot 无法主动说"这里我需要你定一下"，也就无法附上选项和各自的依据。
5. **结构是单向的。** `StructureViewer` 有 `highlightResidues`，但 Mol* 的点选没有被订阅，人无法指着蛋白说"就这几个位点"；`intelligence_hotspots` 只能整条 accept/reject；而下游 RFdiffusion 的 `ppi.hotspot_res`、BindCraft 的 `target_hotspot_residues` **参数早就在插件目录里**（`0024_plugins_point_at_qm.py`、`0033_register_design_plugins.py`、`qm-scripts/library/catalog.json`），没有任何代码把确认过的位点喂进去。`TargetStructureOverlay` 里那句"没有已确认热点"是硬编码文本。

## 2. 目标形态

**一个项目一个研究室（Room）。** 打开 `/bots?project=…` 默认进入研究室：左侧是六人名册，中间是一条按时间排列的流，底部是一个输入框。人在里面说话、派活、看交接、拍板；职责页和任务页仍在，作为"某个人的桌子"和"某件事的详情"，不再是进入工作的唯一入口。

流里有且只有四类条目，**每一类都对应一条已经存在或本规划新增的数据库记录，没有一类是凭空生成的对白**：

| 条目 | 来源 | 是否打断人 |
| --- | --- | --- |
| **发言** | `copilot_messages`（新增 `bot` 列记录发言人） | 否 |
| **交接** | `copilot_handoffs`（已有），claim 逐条显示 confidence，`unsupported` 显著标出 | 否，但可审 |
| **任务事件** | `copilot_agent_runs` 的状态变化与交付（已有），含 `delegate_to_operator` 产生的子 run | 否 |
| **决策请求** | `copilot_decision_requests`（P2 新增），选项 + 各自依据 + 发起人 | **是，且只有它** |

这条分法是本规划唯一的新语义，且它是**减法**：它规定了什么**不该**出现在流里——模型的每一步推理、每一次工具调用、以及任何一句 Bot 之间的寒暄。工具调用折叠在发言下方（已有 `tool_calls`），展开可见，默认不占位。

**不生成 Bot 之间的对白。** Bot 之间真实存在的通信只有两种：`post_handoff` 写下的行，和 `delegate_to_operator` 开出的子 run。两者都渲染成群聊形态即可。让模型生成"总调度：方案设计你看一下"这类台词，会把可审计的记录换成看起来更热闹的假象，并且一旦上线就回不了头。

## 3. 分期

五期，每期单独可合、单独可回滚、单独有验收。P0 与 P1 不引入任何新的科学语义，先做是因为后面每一期的产物都要在这条流里被看见。

### P0 — 研究室与事件流（粗估 2–3 天）

**做什么**

- 迁移：`copilot_messages` 增加 `bot`（`String(80)`，可空）。写入点在 `tasks.py` 落助手消息处，取当轮解析出的 `active_bot.id`；空值表示未分化的 Copilot，不回填历史。
- 新端点 `GET /copilot/projects/{project_id}/room`：按时间倒序合流 messages / handoffs / agent-run 事件，游标分页，**只读**。不新建表，因此 `contracts/v2-flow-matrix.yaml` 无新行；`copilot_messages` 现有行的 producers/consumers 需要复核一次。
- 前端 `features/copilot/Room.tsx`：一条流 + 底部输入框。发言复用 `useCopilotChat`（**不允许出现第二个聊天实现**），交接卡片复用 `CopilotChain` 的 `HandoffCard`，任务卡片复用 `taskPresentation` 的 `deliveryLabel`。
- `/bots` 页签改为 **研究室 / 任务与交付 / 团队**；研究室为默认视图，原 `?view=chat` 与 `?view=handoffs` 重定向进研究室并锚定到对应条目。
- 实时：复用 `GET /copilot/conversations/{id}/stream`（已有 SSE）推进新发言；交接与任务事件沿用现有轮询节奏（`refetchInterval` 4s，仅在有活跃 run 时）。**不新增 SSE 端点**，一条流两种节奏是可接受的，掉线回落到轮询是既有约定（`lib/api/sse.ts` 的模块说明）。

**验收**

- 一段包含两个 operator 的对话，刷新后仍能按发言人复原。
- 一次 `post_handoff` 在研究室里以交接卡片出现，`unsupported` 的 claim 无需展开即可看到。
- 一个 `delegate_to_operator` 子 run 在流里挂在发起它的条目下，不单独占一行顶层。
- 只读角色（viewer）看得到全部条目，输入框禁用并说明原因（复用 `useCopilotReadOnly`）。

**门禁**：`export_openapi.py` + `npm run generate:api` 重跑；`frontend/scripts/browser-harness-core.mjs` 增加 `/room` 的 stub（否则 74 例浏览器矩阵变红）；`alembic upgrade → check → downgrade base` 往返。

### P1 — 在房间里派活（粗估 1–2 天）

**做什么**

- `@` 指名：输入框识别 `@研究员` / `@planner`，解析到 bot id 后作为该轮的 `bot` hint 发送。无 `@` 时沿用 `matchBot` 自动匹配（`bots/registry.ts`，平局返回 undefined 的行为保持不变）。
- 房间内派任务：一条发言旁的"交给 TA 办"动作，预填 `copilot_task_drafts`（owner = 被 `@` 的人，recipe 由 `task_services` 推出），**仍然跳到 composer 确认计划、写权限与预算**。本期不新增任何"一句话直接启动"的路径——启动一个会花钱的 run 必须经过它现在经过的那道审阅。
- 任务启动、状态变化与交付在房间里回帖，点击进入职责页的 `run=` 详情（URL 已是持久的）。

**验收**：`@` 一个不存在或已退役的 id 得到明确提示（服务端已有 `copilot_bot_retired`，前端在发送前解析）；`@` 一个 reviewer 或 director 不提供"交给 TA 办"（它们 `task_services` 为空）；派活后 composer 的 owner 预填正确且可改。

**门禁**：仅前端 + 既有端点，跑 vitest / build / lint / 浏览器矩阵。

### P2 — 决策请求（粗估 2–3 天）

**做什么**

- 新表 `copilot_decision_requests`：`project_id`、`run_id`（可空）、`asked_by`（bot id）、`question`、`options`（JSON 数组，每项 `{label, rationale, evidence_refs[]}`）、`recommended`（可空）、`status`（`open/answered/withdrawn`）、`answered_by`、`answered_at`、`answer`（选项 key 或自由文本）、`version`。附 `contracts/v2-flow-matrix.yaml` 新行。
- 新工具 `request_decision`（capability `chain-messaging`，`execution_mode="draft"`，`requires="session"`，`intent="internal"`，`audit=True`）。它**不能**自问自答，`answered_by` 只接受人。
- 何时该问，写成一条可复核的规则而不是一句叮嘱：**沿用 `autopilot/gates.py` 已在用的两条判据——是否不可逆、是价值问题还是经验问题。** 不新造第二套分类。charter 里写死：MSA 深度这类经验问题自己定；花预算、上台面、选热点这类价值问题必须问。
- 人回答后写 timeline，`decided_by=agent_proposed_human_confirmed`（该字段由服务层按写入者设置，本路径不例外）。
- `/inbox` 增加第六个来源"Bot 在等你的判断"，与现有五个来源同样独立加载、独立重试。

**验收**：一条 open 的决策请求同时出现在研究室与收件箱；回答后两处都变为已决并可追到 timeline 条目；未回答时发起它的 run 处于等待而不是继续；viewer 看得到但答不了。

**门禁**：flow matrix 新行；openapi + SDK 重生；迁移可逆；`copilot/` 覆盖率不得低于现状（本期新代码应高于总体）。

### P3 — 在结构上选位点（粗估 4–6 天，本规划的主体）

**现成可用的是两个标准，不是一个现成的 MCP。** 现有的分子可视化 MCP（ChatMol、PyMOL-MCP、MCPymol 一类）驱动的是本机桌面 PyMOL/ChimeraX 并回传截图：它们不在浏览器里、没有项目作用域与 RLS、选出来的残基落不进 `intelligence_hotspots`、也过不了写闸与 `If-Match`。接进来只会得到一张图。因此采用两个标准、自建三个工具：

- **MCP Apps 扩展**（`ui://` 资源 + `_meta.ui.resourceUri` 把工具绑到界面、沙箱 iframe、界面可回调 `tools/call`）。BDA 的 MCP 面已声明 `resources` 能力并实现了 `resources/read`，加 `ui://` 是延长而不是新建传输面。
- **MolViewSpec（.mvsj）**：Mol* 官方的声明式场景 JSON（选择、着色、标签、相机、注解）。**让 Bot 输出 MVS，而不是让它驱动 Mol* 的 API**——场景因此是可存、可 diff、可作为证据被引用的对象。

**做什么**

- 新 capability `structure-interaction`，三个工具注册进 `copilot/registry.py` 的同一个 `REGISTRY`（**不新建第二套工具定义**）：

  | 工具 | 模式 | 语义 |
  | --- | --- | --- |
  | `render_structure_view` | read | 返回 MVS 场景 + `ui://bda/structure-picker`；Bot 用它说"我说的是这个面、这几个残基" |
  | `propose_hotspot_set` | draft | 写一条 `pending` 的位点集合：残基、每个残基的理由、证据引用。**不确认** |
  | `request_residue_selection` | draft | 开一条决策请求（复用 P2 的表），界面回收人点选的残基，落成 `decided_by=human` 的位点集合 |

- 新表 `hotspot_sets` / `hotspot_set_residues`（或以 JSON 列存残基，二选一在实施时定，取决于是否需要按残基查询）：`project_id`、`target_id`、`structure_artifact_id`、`origin`（`agent/human/agent_proposed_human_confirmed`）、`residues`、`rationale`、`evidence_refs`、`status`。归属沿用 timeline 的三态语义，不新造词。
- 前端：`StructureViewer` 增加受控的 `onSelectionChange`（订阅 Mol* 的点选），只在 picker 模式下启用；`ui://bda/structure-picker` 作为房间内的内联控件，回传选择。
- 位点集合接入 `features/timeline/provenanceSources.ts` 的"只能选不能打字"名单——它正是平台自己拥有的对象。
- `planner` 的 charter 增补一句既有纪律的延伸：提出位点是测量加论证，**确认位点是人的动作**（与"不得 confirm/submit"同源）。

**验收**：Bot 能在房间里发出一个结构视图，人点三个残基并提交，产生一条 `origin=human` 的位点集合并附在项目上；Bot 提出的位点集合停在 `pending` 且无法自我确认；外部 MCP 客户端持有该项目 grant 时，`tools/list` 能看到三个工具中它被授予的部分（read 的那个无需绑定 run）。

**门禁**：flow matrix 新行；openapi + SDK；MCP 传输层测试覆盖 `ui://` 资源的 `resources/read`；浏览器矩阵新增 picker 用例（Mol* 用既有合成 PDB fixture，不引入外网依赖）。

### P4 — 让位点真的进入计算（粗估 2 天）

**做什么**：把已确认的位点集合接到插件参数——RFdiffusion 的 `ppi.hotspot_res`、BindCraft 的 `target_hotspot_residues`。参数来源打 `constrained` 徽章（`features/plugins/parameterOrigin.ts` 已有该档，且 `constrained` 优先于一切）。`TargetStructureOverlay` 的硬编码文案替换为真实数据。

**为什么放最后**：这是整条链上唯一真正改变产出的一步。前面四期全是呈现与记录，先把审计面建好，再让它影响一个会花 GPU 小时的作业。

**验收**：从房间里选定位点，到 workflow 节点参数里出现同一组残基且标记为受约束，中间无手工转抄；改动位点集合不会静默改写已提交的作业。

**门禁**：`check_plugin_cpu_declarations.py`、`check_cluster_claims.py` 照常；渲染出的 `#BSUB` 不因本期变化。

## 4. 明确不做

- **不生成 Bot 之间的对白。** 交接是行，行才是消息（§2）。
- **不把叙述层写进研究记录。** 工具调用与中间推理折叠可见，不进 timeline，不进 handoff。
- **不新增第二个聊天实现。** 房间复用 `useCopilotChat` 与 `CopilotChat` 的消息渲染。
- **不接桌面版 PyMOL/ChimeraX 的 MCP。** 理由见 P3 首段。
- **不让任何 Bot 确认自己的产物。** 位点、计算草稿、交付，确认动作一律是人的（与 `planner` 不得 confirm/submit、`archivist`→`analyst` 不得关闭目标同源）。
- **不为房间放宽 `Idempotency-Key` 与 `If-Match`。**
- **不在房间里开"一句话直接启动任务"的捷径。** 预算与写权限的审阅位置不变。

## 5. 已知边界与风险

- **归属只覆盖 timeline。** `decided_by` 尚未推广到 `campaign_decisions` 与 `research_findings`；P2 的决策答复写 timeline，因此在册，但位点集合的 `origin` 是本规划自建的第二处三态语义，**实施时应确认两者措辞一致**，否则半年后会出现两套读起来一样、含义不同的字段。
- **`copilot_messages.bot` 不回填。** 合并前的历史对话在房间里显示为未分化的 Copilot，这是诚实的呈现，不是缺陷。
- **一条流两种刷新节奏。** 发言走 SSE，交接与任务走轮询。在一次交接紧跟一句发言时，两者可能错序数秒。可接受，且比为它新增第二个流端点便宜；若实测刺眼，处理办法是按服务端时间戳排序而不是按到达顺序。
- **MCP Apps 是新扩展。** 宿主端支持度会变化；BDA 自家前端是第一个宿主，外部客户端拿不到界面时必须仍能拿到 `render_structure_view` 的 MVS 数据本身——**工具的返回值不得只有界面**。
- **位点集合一旦影响作业，就成了受管对象。** P4 之后修改它等于修改一个可能已被提交的输入，需要与 workflow 的版本约束对齐。

## 6. 分支与同步纪律

本栈的公共来源是 `bda-public/codex/bot-first-science-workspace`（合并点 `8007e022`），其上已有 #46–#51 六个合并。**实施分支从该分支或其合入后的公共 main 切出，不从私有 `origin/main` 切出**；软件改动必须先落在公共仓库，再按 `.bda-sync` 的流程回流。当前工作树的分支基于私有 main，实施前需要改基。

