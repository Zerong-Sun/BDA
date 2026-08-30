# Autopilot 协议与实现边界

状态：活跃

最后核验：2026-08-30（Asia/Shanghai）

权威范围：当前公开 BDA 的 Autopilot 数据模型、API、用户流程与已知边界。

数据来源：当前 Autopilot schema、service、task、API、前端页面与自动化测试。

替代关系：取代归档原型中与当前迁移链、预算模型和执行状态不一致的说明。

## 1. 设计问题

长时科研流程不能把自然语言 prompt 直接等同于可执行协议。Prompt 可能缺少预算、阶段、输入和终止条件，而一次计算提交可能持续数小时；如果协议、费用和中间状态只保存在浏览器或 worker 内存中，页面刷新、任务重试或进程故障就可能造成重复提交和不可审计的费用。

Autopilot 因此不负责“猜测并立即运行”。它先把需求保存为 draft，再由用户审查和确认，最后以不可变 campaign 承接异步执行。这个顺序把语言理解与资源提交分离，使权限、并发控制、预算和取消都能在数据库事务中验证。

## 2. 与人工 campaign 的关系

人工 `campaigns` 保存设计—实验—复盘流程；`autopilot_campaigns` 保存冻结协议和自动执行状态。两者保持不同模型，因为人工轮次允许研究者持续增加评价和决策，而已经确认的自动协议必须保持不可变。

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

### 3.4 取消与恢复

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
| 具体 research/compute stage adapter | 尚未完整实现 | 当前 execute task 只完成 durable handoff 和首阶段 ready |
| 自动结果回写、候选漏斗和实验复盘 | 尚未实现 | 需要 stage adapter、领域事件与新界面 |

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

完整验收还应覆盖并发预算预留、超额拒绝、重复 idempotency key、取消级联、worker 重投、跨项目权限与 RLS，以及真实 stage adapter 的故障恢复。后四项在接入具体执行 adapter 后必须通过，才能把 Autopilot 描述为完整自动执行闭环。
