# Autopilot 协议与实现边界

状态：活跃

最后核验：2026-09-05（Asia/Shanghai；stage adapter 与人工接管落地后复核）

权威范围：当前公开 BDA 的 Autopilot 数据模型、API、用户流程与已知边界。

数据来源：当前 Autopilot schema、service、task、API、前端页面与自动化测试。

替代关系：取代归档原型中与当前迁移链、预算模型和执行状态不一致的说明。

## 1. 设计问题

长时科研流程不能把自然语言 prompt 直接等同于可执行协议。Prompt 可能缺少预算、阶段、输入和终止条件，而一次计算提交可能持续数小时；如果协议、费用和中间状态只保存在浏览器或 worker 内存中，页面刷新、任务重试或进程故障就可能造成重复提交和不可审计的费用。

Autopilot 因此不负责“猜测并立即运行”。它先把需求保存为 draft，再由用户审查和确认，最后以不可变 campaign 承接异步执行。这个顺序把语言理解与资源提交分离，使权限、并发控制、预算和取消都能在数据库事务中验证。

## 2. 与人工 campaign 的关系

人工 `campaigns` 保存设计—实验—复盘流程；`autopilot_campaigns` 保存冻结协议和自动执行状态。两者保持不同模型，因为人工轮次允许研究者持续增加评价和决策，而已经确认的自动协议必须保持不可变。

**"不可变"的宾语是 frozen spec，不是 campaign 产出的任何领域对象。** 这一句在 stage adapter 落地后必须说清楚：预算与权限校验建立在 spec 不变之上，所以 spec 冻结；而 stage 产出的 workflow run、job、候选物都落在与人工完全相同的主干表上，**必须可以被人修正**——一条自动跑出来的错误结论如果改不了，平台就只是在更快地累积错误。改产物的授权通过 §3.5 的人工接管显式移交，不是靠绕过状态机。

确认 Autopilot draft 时可以提供 `manual_campaign_id`。该外键只允许连接同一项目的人工 campaign，用于记录人工设计如何交接到自动协议；它不会合并两个状态机，也不会把人工 campaign 的权限或预算隐式授予 Autopilot。

## 3. 用户流程

### 3.1 创建 draft

`POST /api/v2/autopilot-drafts` 接受且只接受以下一种输入：

- `prompt`：至少 10 个字符的自然语言需求；或
- `structured_brief`：调用方已经构造的结构化需求。

服务器保存原始输入、规范化 spec、项目和创建者。响应的 `ETag` 标识 draft 版本。

### 3.2 确认 campaign

`POST /api/v2/autopilot-drafts/{draft_id}/confirm` 必须携带 `If-Match`。版本不一致返回 `412`，避免用户确认已经被其他请求修改的预览。

确认请求声明：

- campaign 名称；
- `supervised` 或 `plan_only` 自主级别；
- 监督式 campaign 的显式 GPU/金额硬预算；
- 可选的同项目人工 campaign handoff。

确认后，prompt 和 spec 被复制到不可变 campaign。`plan_only` 可以不设计算预算，但不能启动计算；平台不存在默认 400 GPU 小时额度。

### 3.3 启动与预算预留

`POST /api/v2/autopilot-campaigns/{campaign_id}/start` 接受 idempotency key 和本次申请的 GPU 秒数/金额。事务在加锁的预算行上计算 `reserved + committed + requested`，超过任一硬上限即返回 `409`。相同 key 和相同参数返回原 operation；相同 key 被不同预算复用时返回冲突。

成功启动返回 `202` 和 operation ID。当前 worker 会验证 reservation、记录受限 service principal 的 ledger 事件，并把第一个 pending stage 转为 `ready`。

### 3.4 人工接管

`POST /api/v2/autopilot-campaigns/{campaign_id}/takeover` 必须携带 `If-Match`，把 campaign 置为 `manual_takeover`，记录 `taken_over_at` / `taken_over_by`，并写一条**由用户而非 service principal 署名**的 ledger 事件。

三点同时成立：自动推进停止（`execute_campaign` 见到 `manual_takeover` 直接返回，与见到 `cancelled` 一样）；谁、何时留在行上；协议仍然冻结。接管是**幂等**的——重复调用返回同一条记录，不写第二次移交，因为两条移交记录会让"谁在负责"这个问题重新变得无法回答。

已取消的 campaign 不能接管（409）：没有东西可接。

### 3.5 取消与恢复

`POST /api/v2/autopilot-campaigns/{campaign_id}/cancel` 是幂等操作。同步事务把活动 stage 标记为 cancelled，并对运行中的 operation、research generation 和 job 发出 cancel request；异步对账任务随后释放尚未 committed 的预算 reservation。

Ledger 只接受真实用户或受限 service principal 两类 writer。重复的 execute/cancel delivery 通过 operation、reservation 和 ledger 标识去重，避免恢复任务重复扣费或重复推进阶段。

## 4. 当前已实现范围

| 能力 | 状态 | 证据位置 |
| --- | --- | --- |
| prompt/structured brief draft | 已实现 | `backend_v2/app/autopilot/schemas.py`、`service.py` |
| ETag 确认与不可变 campaign | 已实现 | `api.py`、`service.py` |
| 类型化预算与事务性 reservation | 已实现 | `models.py`、`service.py` |
| 异步 operation 与 append-only ledger | 已实现 | `service.py`、`tasks.py` |
| 幂等取消和预算释放 | 已实现 | `service.py`、`tasks.py` |
| Prompt-first 前端和结构化预览 | 已实现 | `frontend/src/app/Autopilot.tsx` |
| workflow_run stage adapter | 已实现 | `backend_v2/app/autopilot/adapters.py`；`compute` / `design` 阶段产出真实 `workflow_runs` 行，幂等键写在 `legacy_id` |
| stage 产物指针与前端深链 | 已实现 | `autopilot_stages.resource_type` / `resource_id`；Autopilot 页每个阶段直达 Workflow 页 |
| 人工接管（`manual_takeover`） | 已实现 | 迁移 `0054`、`service.take_over_campaign`、`POST …/takeover` |
| 预算 reserved → committed 实拨对账 | 已实现 | `tasks.settle_reservation`；按预留封顶，超出部分记为 `unbilled_overrun_gpu_seconds` |
| research / collect / review stage adapter | 尚未实现 | 这些阶段的产物依赖真实计算完成后的回写，不能凭 spec 生成 |
| 自动结果回写、候选漏斗和实验复盘 | 尚未实现 | 需要上一行的 adapter、领域事件与新界面 |
| 完整无人值守闭环 | 尚未达成 | 见 §6：真实 adapter 的故障恢复已有测试，但端到端闭环未在真实计算上跑通 |

## 5. 操作约束

- 用户必须先选择项目；后端项目权限是唯一安全边界。
- 监督式 campaign 未声明预算时不得确认，`plan_only` 不得启动计算。
- worker 必须在 operation 的项目上下文中运行，不能使用无项目边界的应用账号。
- 不应根据归档分支、原型截图或旧 README 推断当前功能；只有当前 release 的 API、迁移、测试和本文档共同定义实现范围。
- 生产写入保持关闭，直到真实计算、身份、TLS、备份恢复、告警和回滚演练完成签字。

## 6. 验证

Autopilot 的最小回归集为：

```bash
backend_v2/.venv/bin/pytest backend_v2/tests/test_autopilot_formalization.py
npm --prefix frontend test
```

完整验收还应覆盖并发预算预留、超额拒绝、重复 idempotency key、取消级联、worker 重投、跨项目权限与 RLS，以及真实 stage adapter 的故障恢复。

其中**已覆盖**：重复 idempotency key、超额拒绝、取消级联、settle 的重投幂等、预留超支的封顶与记账、adapter 在 worker 中途崩溃后的复用（清空 stage 指针后仍找回同一条 run）、跨项目接管拒绝。

并发预留与 worker 上下文 RLS 需要真实 PostgreSQL，单独放在
`backend_v2/tests/test_autopilot_postgres.py`，按 `BDA_V2_RUN_DB_TESTS=1` 开启：

```bash
BDA_V2_RUN_DB_TESTS=1 BDA_V2_DATABASE_URL=... \
  backend_v2/.venv/bin/pytest backend_v2/tests/test_autopilot_postgres.py
```

**并发预留**：八个线程、各自独立连接，争一个只装得下两份的预算。写这个测试时才看清防护是两层的，
且触发顺序与预期相反 —— `_reserve_budget` 的 `SELECT … FOR UPDATE` 先把算术串行化，
但随后 `campaign.version` 的乐观锁只放行一个事务，其余抛 `StaleDataError` 回滚（预留一并回滚）。
**同一 campaign 上的并发，通常是版本检查而不是预算锁在拒绝。** 两者都是真实拒绝，
不变量成立：硬上限从未被突破，回滚的事务不留预留行。

**worker 上下文 RLS**：`0055_autopilot_worker_rls`。`0049` 建表时已经加了 RLS，
但表达式只认 `bda.user_id`；`0051` 后来给其余项目表加的 `bda.worker_project_id` 分支没有覆盖到这里。
留下的缺陷与"泄露"相反：**一个按 §5 要求限定在自己项目里的 worker，看不见它被派去执行的那个 campaign**。
在 stage adapter 让 worker 真的去读 campaign 之前，这一点不会显现。已补齐，并两头都断言：
限定到别的项目什么也看不到，限定到自己的项目恰好看到自己那一条。

**仍未覆盖**：在真实计算上跑通的端到端闭环。**这一项没通过之前，不得把 Autopilot 描述为完整自动执行闭环。**
