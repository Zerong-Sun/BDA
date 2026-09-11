# MCP 能力面：把既有工具注册表暴露给外部 agent

状态：活跃 / §6 四步全部已实现

最后核验：2026-09-11（Asia/Shanghai；本轮实现四步并实跑全部门禁）

权威范围：本文只规定「BDA 以 MCP 协议对外暴露哪些能力、凭什么授权、挂在哪里」。Copilot 自身的能力边界仍以 [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md) 为准；Autopilot 的执行与预算模型仍以 [Autopilot 协议与实现边界](AUTOPILOT_CAMPAIGNS.md) 为准。

数据来源：`backend_v2/app/copilot/{registry,tools,capabilities,actions,agent_loop,tasks,mcp,mcp_app}.py`、`backend_v2/app/main.py`、`backend_v2/app/module_registry.py`、`backend_v2/app/identity/deps.py`、`backend_v2/app/autopilot/models.py`、`backend_v2/openapi.json`、`backend_v2/tests/test_copilot_mcp{,_transport}.py`。

替代关系：不取代任何现有文档。本文是 [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md) 的传输层补充，其冻结的禁止事项在 MCP 上原样生效。

---

## 1. 设计问题：不要包 REST

把 `/api/v2` 包成 MCP 工具是第一个会想到的做法，它有三个具体的、可量化的问题：

- **体量**：当前 `openapi.json` 是 185 条 path / **251 个 operation** / 4.3 MB。一个工具清单塞进模型上下文就已经越界，而 MCP 客户端要在每轮对话里带着它。
- **粒度错配**：REST 端点的粒度是**资源**（`GET /candidates`、`PATCH /candidates/{id}`），agent 需要的粒度是**任务**（"这个项目的候选物里哪些通过了折叠门"）。前者要 agent 自己拼装三四次调用，每次都可能拼错。
- **控制面丢失**：251 个 operation 中只有 121 个带 `x-permission`。REST 层的授权是 HTTP 依赖注入，它保护的是"能不能调这个端点"，回答不了"这次调用是不是用户要的"。

同时，**能力面已经存在**：`backend_v2/app/copilot/registry.py` 的 `ToolSpec` 把 schema、capability、execution_mode、handler、audit、citation 声明在同一个对象上，`REGISTRY.execute` 是唯一的 dispatch 点。当前注册 **28 个工具 / 11 个 capability**，按执行模式分为 read 18 / draft 7 / queue 3。

## 2. 结论

**MCP server 是 `copilot.registry.REGISTRY` 的第二个传输面，不是第二套工具定义。**

`registry.py` 的模块 docstring 自陈了这个模块存在的原因：一个工具曾经散在三处（模型 schema、capability 映射、`if name == ...` 分发链），加一个要改三处，漏掉第三处不会报错——工具要么不可达，要么可达但跳过了 capability 检查。**为 MCP 另写一套工具定义就是加上第四处。**

因此 MCP 层只负责三件事，一件不多：

1. 把 `ToolSpec.schema()` 翻译成 MCP 的 `tools/list` 响应；
2. 把 MCP 的 `tools/call` 翻译成 `REGISTRY.execute(tool_id, context, arguments, granted=…)`；
3. 构造那个 `ToolContext`——这是全部实质工作所在，见 §3。

## 3. 四个必须解决的问题

### 3.1 意图门：`request_text` 从哪里来

写工具的保险丝是 `actions.CopilotActions.request_allows()`：它在**用户自己的原话**里找领域词 + 动词，并排除建议语气与否定从句。当前两个调用点分别传入：

- `copilot/tasks.py:111` — `request_text=source.content`，即用户的聊天消息；
- `copilot/agent_loop.py:179` — `request_text=run.goal`，即用户创建 agent run 时写下的目标。

**MCP 客户端没有"用户原话"。** 它发来的 `arguments` 是对端模型生成的，把它当作 `request_text` 等于让模型给自己开门——这条保险丝会当场失效，而且不会报错。

规则（本方案唯一的新增语义，且是减法）：

- **MCP 会话必须绑定到一个已存在的 `copilot_agent_runs` 行。** `request_text = run.goal`，与 `agent_loop.py:179` 完全一致，不引入第三种意图来源。
- **未绑定 run 的 MCP 会话只暴露 `execution_mode == "read"` 的 18 个工具**，`tools/list` 里根本不出现另外 10 个。不可见优于可见而拒绝：后者会让对端模型反复重试并把失败当作可以绕过的障碍。
- `requires="session"` 的 5 个 draft 工具（`wetlab-authoring` 三个、`research-trace-authoring` 一个、`promote_candidate_to_bench`）**不经过 `actions` 服务，因而没有意图门**。在 MCP 上它们必须按 `execution_mode` 归入"需要 run 绑定"一档，否则会成为整条链上唯一没有用户授权的写路径。

### 3.2 身份与凭证

MCP 客户端不是浏览器：拿不到 HttpOnly refresh cookie，也不应当持有用户的长期 access token。

`autopilot_service_principals`（`name` / `enabled` / `allowed_actions`）已经是"受限非人类写者"的正确形状，并且 `autopilot_ledger` 用 `ck_autopilot_ledger_one_writer` 约束强制"要么是人、要么是 service principal，不能都是"。照这个形状做，但**不要复用 autopilot 域的表**——它的 `allowed_actions` 语义绑定在 campaign 执行上。

方案：在 `copilot` 域新增 `copilot_mcp_sessions`，一行即一次授权：

| 列 | 含义 |
| --- | --- |
| `project_id` | 作用域项目。不可为空——没有项目上下文的工具调用会跨项目查询 |
| `agent_run_id` | 绑定的 run，可空（可空即 §3.1 的只读会话） |
| `issued_by` | 签发的**人**。FK 到 `users` |
| `granted_capabilities` | capability 子集，必须是 `copilot_configs.enabled_skills` 的子集 |
| `token_hash` | 照 `refresh_sessions.token_hash` 的做法存哈希，不存明文 |
| `expires_at` / `revoked_at` | 与 run 同生命周期；run 终止即失效 |

**凭证由用户在 UI 上显式签发，不由 API 自动发放。** 这样"谁授权的、给哪个项目、能干什么、什么时候到期"四个问题都有行可查，与 ledger 的 one-writer 约束是同一种设计。

### 3.3 挂载点与写闸

**不要把 MCP 挂进 `/api/v2`。** `main.py` 的 `production_write_gate` 中间件按 path 前缀与 HTTP 方法判断：MCP 的一切都是 `POST /mcp`，在写闸眼里是一个方法、一条路径。挂进去会得到两个错误结果之一——要么整个 MCP 面在 `writes_enabled=false` 时全挂（读也不能用），要么被豁免掉从而**绕过生产写闸**。后者是真实的安全洞。

方案：独立挂载点 + 在 dispatch 内部显式重建写闸。

```
app.mount("/mcp", mcp_app)          # 同进程，复用 SessionFactory / DomainError handler
```

dispatch 里：`settings.writes_enabled` 为 false 时，`spec.execution_mode != "read"` 一律返回 `writes_disabled`（503），错误体沿用 `core/problem.py` 的 `DomainError`，与 REST 面同码同型。

**实现陷阱**：`module_registry.routers()` 对每个 `router_modules` 断言 `isinstance(router, APIRouter)`，否则 `raise RuntimeError`。MCP 子应用不是 `APIRouter`，所以它**不能**通过 `MODULES` 注册。签发/吊销 session 的那几个 REST 端点走 `copilot` 现有 router；MCP 子应用本身在 `main.py` 显式 `mount`。

### 3.4 RLS 与项目作用域

`identity/deps.py:_resolve_user` 在解析用户后调用 `set_request_rls_context(session, user_id=…, is_global_admin=…)`。MCP 的**每一次** `tools/call` 必须走同一条路径——用 `copilot_mcp_sessions.issued_by` 解析出的用户设置 RLS 上下文，而不是用一个服务账号绕过它。

`ToolContext.project_id` 必须从 session 行取，**不接受调用方在 `arguments` 里传项目 ID**。`tools.py:_project_of` 已经在 `project_id is None` 时抛错，但它防不住"传了一个别的项目的 ID"。

## 4. 暴露什么

| 会话形态 | `tools/list` 内容 | 授权依据 |
| --- | --- | --- |
| 只读会话（无 run 绑定） | 18 个 `read` 工具 ∩ `granted_capabilities` | 用户签发 + 项目成员资格 |
| 绑定 run 的会话 | 上述 + 7 个 `draft` + 3 个 `queue`，仍 ∩ `granted_capabilities` | 追加 `run.goal` 的意图门 |

`granted_capabilities` 取交集而非并集：`copilot_configs.enabled_skills` 是项目对 copilot 的授权上限，MCP 会话不得超过它。一个项目关掉了 `wetlab-authoring`，MCP 就拿不到它——不需要第二处开关。

## 5. 明确不做

- **不暴露 251 个 REST operation。** §1。
- **不新建第二套工具定义。** §2。
- **不暴露 `spawn_subagent`。** 它的递归深度上限由 `copilot_agent_runs` 维护；MCP 客户端本身已经是一层编排者，再给它生成子 agent 的能力会让深度计数失去意义。
- **不给文件系统、shell、凭证或数据库访问。** [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md) 已冻结此条，MCP 面不是重新讨论它的地方。
- **不绕过 compute 的 draft → confirm → submit。** `create_compute_draft` 是 `draft` 模式；确认与提交仍然只有人能做。
- **不为 MCP 放宽 `Idempotency-Key` 与 `If-Match`。** 对端重试比人频繁得多，这两个头在 MCP 上比在浏览器上更需要，而不是更不需要。

## 6. 实施顺序与落地形态

四步，每步单独可合并、单独可回滚，全部已实现。

| 步 | 内容 | 状态 |
| --- | --- | --- |
| 1 | `copilot_mcp_sessions` 表 + migration `0056` + 签发/吊销端点 + 流矩阵条目 | **已做** |
| 2 | MCP 子应用：`tools/list` 由 `REGISTRY` 派生；只读会话；写闸重建 | **已做** |
| 3 | run 绑定 + 意图门接入（`request_text = run.goal`） | **已做** |
| 4 | UI：签发、查看、吊销；审计里显示 MCP 来源 | **已做** |

### 6.1 已实现部分的具体形态

- **表**：`copilot_mcp_sessions`（migration `0056_copilot_mcp_sessions`）。`project_id` 非空、
  `agent_run_id` 可空（可空即只读会话）、`issued_by` 指向**人**、`granted_capabilities`、
  `token_hash`（SHA-256，照 `refresh_sessions` 的做法）、`expires_at` / `revoked_at`、
  `last_used_at` / `call_count`。RLS 用 `0048_project_rls._project_expression` 的**同一条**表达式
  （含 worker 分支），不是一条相似的表达式。upgrade / downgrade 已在一次性数据库上实跑往返。
- **派生而非声明**：`mcp.available_tools` 依次按 grant 能力 ∩ 项目 `enabled_skills`、
  live run 的 `allowed_tools`、以及意图门收敛，最后按 **tool id 在 `REGISTRY.all()` 上取**——
  与 `agent_loop._schemas` 同一语义。不可调用的工具**不出现在 `tools/list` 里**：
  列出来再拒绝会训练对端模型重试，而能重试的拒绝读起来像障碍不像边界。
- **意图门**：`mcp._intent_filtered` 用 `request_text=run.goal` 构造 `CopilotActionService`，
  对 `research_agent.WRITE_TOOL_NAMES` 的五个工具调 `request_allows`。其余写工具（wetlab / research-trace 四个）
  `request_allows` 不认识，因此仅由 run 绑定把关——这也是「无 run 即无任何写工具」这条规则的由来。
- **写闸**：`mcp._authorize_write` 做两件事——`settings.writes_enabled` 的 cutover 闸，
  以及**每次调用重新校验签发人的项目角色**（`require_project_permission(..., "write")`）。
  后者堵的是「签发后被降级为 viewer，token 却继续能写到过期」。
- **挂载**：`main.py` 用 `app.add_route("/mcp", …)` 与 `"/mcp/"` 两条，不用 `app.mount`——
  mount 会把 `POST /mcp` 答成 307 到 `/mcp/`，而重定向时丢 body 或 Authorization 的客户端
  会表现成认证 bug 而不是路由问题。MCP 不进 OpenAPI，因此不进流矩阵的路径校验。
- **协议子集**：`initialize` / `ping` / `tools/list` / `tools/call`，外加对通知（无 `id`）回 202。
  prompts、resources、sampling **未实现且不声明**。没有引入 MCP SDK 依赖：这个子集是几百行 JSON-RPC，
  而代价会是在一个安全面的请求路径上增加一个运行时依赖，代码仍然要读。
- **审计**：写工具在 `actions._once` 的行之外，另记一条 `copilot.mcp.<tool>`，
  `entity_type="copilot_mcp_session"`。前者记的是**授权依据**（run），后者记的是**谁握着 token**——
  事故是从后一个问题开始查的。读不记：注册表已有的规则是「一条读一行会把真正重要的写埋掉」。
- **UI**：copilot 抽屉的第三个面。token 只显示一次并明说不可找回；每行的工具数与写工具数
  是**服务器此刻的判断**而非签发时的存量，因此绑定 run 结束后该行直接显示「只读」。

### 6.2 防止它自己腐化的那一个测试

`test_copilot_mcp.py::test_listing_never_leaves_the_registry` 断言列出的每个工具都能在
`REGISTRY` 里查到，且 `inputSchema` **就是** `ToolSpec.parameters` 这个对象本身。
它防的是有人为 MCP 手写一份工具定义——那会工作，并且会成为工具被声明的第四处。
与 `check_decision_coverage.py` 在决策树里的角色相同。

`test_unbound_session_lists_no_write_tool` 是第二条：钉住整个模块存在的理由。

## 7. 门禁清单与本轮实跑结果

| 检查 | 结果 |
| --- | --- |
| `ruff check backend_v2` | 通过 |
| `mypy`（CI 方式，无 `--config-file`） | 通过，247 个文件 |
| `pytest backend_v2/tests` | 通过（835 用例，新增 37） |
| `export_openapi.py` 后 `git diff` | 无漂移（已重新导出，189 条路径） |
| `npm run generate:api` 后 `git diff` | 无漂移（已重新生成） |
| `check_flow_matrix.py` | 通过，78 张表 / 189 条路径 |
| `check_document_inventory.py` | 通过 |
| `alembic check` | 无模型/迁移漂移 |
| `alembic upgrade head` → `downgrade base` | 在一次性数据库上往返通过；RLS policy 实际创建 |
| 退役路径 grep | 通过 |
| 前端传输边界（未新增 `fetch(`） | 通过 |
| REUI 审计 | 通过（能力用 `Checkbox`、mandate 用 `Select`，不用原生控件） |
| `npm --prefix frontend test` | 通过，112 文件 / 565 用例 |
| `npm --prefix frontend run build` | 通过，entry 461.3 KiB |
| `check_coverage.py` | **未达 85%**，见下 |

**覆盖率说明。** 本机实测（含 `BDA_V2_RUN_DB_TESTS=1`，在一次性数据库上跑）：
HEAD 基线 **81.78%**，本次改动后 **81.86%**。新增两个模块自身为
`mcp.py` 89.9% / `mcp_app.py` 94.7%，高于总体，因此**是把总数抬上去的**。
85% 的差额在本机是既有状态，不是本次引入；在能复现 CI 环境的机器上需要单独核对。

## 8. 已知边界

- **`citation` 在协议边界上会丢。** 28 个工具的 `ToolSpec.citation` 规定了结果如何变成引用，
  而 MCP 协议本身没有引用概念，`tools/call` 的结果是文本内容块。因此**经 MCP 产生的结论，
  其可审计性弱于经 BDA 自己的 chat 产生的结论**——这与决策树准入规则第二条（依据必须是
  仓库内可寻址的对象）直接相关，不是实现细节。当前的处置是：MCP 的写工具全部落在
  pending-review 形态上，且每次写都留下 `copilot.mcp.<tool>` 审计行；把引用带过协议边界
  需要另一个决定。
- **对端客户端的提示词注入不在防护范围内。** 能约束的只有能力交集、run 绑定、意图门、
  写闸与每次调用的角色复核；一个被注入的对端模型仍然可以在其授权范围内做出错误但合法的调用。
  这与给一个人类账号授权的风险同型，不同的是频率。
- **一个 grant 借用 run 的目标作为授权依据，但并不驱动那个 run。** 内部 worker 循环与外部
  MCP 客户端可以同时对一个 live run 存在。`requires="agent_run"` 的工具因此完全不暴露
  （见 §5），所以外部客户端不能挂起或分叉那个 run；但两者都能在同一项目上写，
  而 run 的 transcript 只会记下内部循环做的事。
