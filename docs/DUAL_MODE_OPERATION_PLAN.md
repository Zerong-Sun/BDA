# 双模运行目标规划：自动化运行与人工查阅修改

状态：规划（未实现部分不得当作已有能力引用）

最后核验：2026-09-05（Asia/Shanghai；M1 落地后复核）

权威范围：BDA 工作台在「自动执行」与「人工查阅修改」两种模式上的目标形态、分期、验收条件与裁定。

数据来源：`backend_v2/app/{autopilot,workflows,compute,timeline,research,campaigns}` 的模型与任务代码，
`backend_v2/openapi.json` 与 `frontend/src/lib/api/generated/sdk.gen.ts` 的实际端点，
`frontend/src/App.tsx` 路由表，本地 `bda-*` 栈 2026-09-05 的实测状态，
以及 `private/legacy-overlay/backend_v2/scripts/` 下的种子脚本。

替代关系：不取代 `docs/AUTOPILOT_CAMPAIGNS.md`（它定义 Autopilot 的当前实现边界）。
本文在 M2 提出一处需要它同步修订的措辞。

---

## 1. 问题陈述

「工作台应该兼具自动化运行和手动运行查阅修改两种模式」这句话预设了一个共同的底座：
同一件事，可以自动跑，也可以人工看、人工改。

当前不是这样。当前是**三条互不相通的入口**：

| 入口 | 路径 | 产物落在哪 | 人能查阅 | 人能修改 |
|---|---|---|---|---|
| 人工 | Workflow 画布 → `workflow_runs` → `submissions` → `jobs` | 平台主干表 | 能 | 能 |
| 自动 | Autopilot draft → confirm → 不可变 campaign → `autopilot_stages` | Autopilot 私有表 | 只能看状态 | 不能 |
| **种子脚本** | `run_overlay.py backend_v2/scripts/seed_*.py --project-id <uuid>` | **直写主干表 ORM** | 能看结果 | **只能改 Python 再重跑** |

第三条路不是历史遗留，**它是今天科研记录的唯一来源**。
2026-09-05 把大麻素 C023–C037（含骨架筛选的 C029/C030）写进时间线走的就是它。

只要判据、STOP、单位错配这些内容只能通过「编辑一个私有仓库里的 Python 文件」进入平台：

- 「人工查阅修改」修改不到项目最重要的那部分；
- 「自动化运行」也无从读取它 —— 自动侧看不见一个它没参与生成的记录。

---

## 2. 现状盘点（2026-09-05 实测）

### 2.1 自动侧：协议层做完了，执行层没接上

`docs/AUTOPILOT_CAMPAIGNS.md` §4 的边界表准确。补三条代码级观察：

- `autopilot_stages` 有 `resource_type` / `resource_id` 两列，是**已经预留但没人写的产物指针**
  （`backend_v2/app/autopilot/models.py:132-134`）。这是自动侧通向主干的唯一接口。
- `execute_campaign` 的 docstring 写明它只做持久化交接并把首个 stage 置为 ready，
  「绝不从不完整的自然语言草稿里编造一次计算提交」。**这条克制是对的，不要动。**
- 因此自动侧的实际终点是 **first stage ready**，之后没有任何事发生。

现有端点：`POST /autopilot-drafts`、`/autopilot-drafts/{id}/confirm`、
`/autopilot-campaigns/{id}/start`、`/autopilot-campaigns/{id}/cancel`、`GET /autopilot-campaigns/{id}`。

### 2.2 人工侧：**后端齐了，前端缺写入路径**

这一节修正了本文初稿的一处误判。初稿把 M1 写成「把种子脚本那条路收进 API」，
核对 `openapi.json` 与生成 SDK 后确认：**API 早就在**。

| 能力 | 后端端点 | 生成 SDK | 前端客户端 | 前端 UI |
|---|---|---|---|---|
| 读时间线 | `GET /projects/{id}/timeline` | 有 | `listTimeline` / `listAllTimeline` | 有 |
| **建条目** | `POST /projects/{id}/timeline` | `postTimelineEntry…Post` | **无** | **无** |
| **改条目** | `PATCH /timeline/{id}` | `patchTimelineEntry…Patch` | **无** | **无** |
| **删条目** | `DELETE /timeline/{id}` | `deleteTimelineEntry…Delete` | **无** | **无** |
| 目标树 CRUD | `/projects/{id}/research-goals` 等 | 有 | `researchGoals.ts` 全套 | 有 |
| 条目挂目标 | `POST /research-goals/{id}/links` | 有 | `attachToResearchGoal` | **没挂到时间线** |

最后一行是可验证的：`AttachToGoalButton` 是**领域无关**的
（按 `(resource_type, resource_id)` 存储），已用在 `CandidateDetail`、`ProteinLibrary`、
`ValidationTable`、`JobStatusDrawer` 四处，**唯独没有用在时间线条目上**。
这正是大麻素项目 46 条记录全部渲染为 `unattached` 的直接原因。

**所以缺口比初稿估计的小得多，也具体得多**：缺的是
`frontend/src/lib/api/timeline.ts` 里的三个写函数、一个结构化编辑器、以及一颗按钮的挂载点。

### 2.3 第三条路的规模

| 度量 | 值 | 说明 |
|---|---|---|
| 大麻素决策覆盖 | 31/37 | 本次由 16/37 提升；C002/C009/C012/C013/C019/C020 仍缺 |
| 甜味蛋白决策覆盖 | 3/109 | 另有 D080–D099 共 20 个已声明为缺口 |
| 经 API 写入的记录 | 0 | 全部经种子脚本的 ORM 直写 |

甜味蛋白 3/109 不是疏忽，是这条路的**成本曲线**：每条记录都要手写一段 Python。

种子脚本还有一个次生问题：它绕过服务层直接构造 ORM 行、手动 `version += 1`，
因此**不产生审计记录**。UI 写入会产生，脚本写入不会 —— 同一张表上两种来源的可追溯性不等价。

### 2.4 一处已修复的漂移，和它留下的常设教训

`BDA_V2_SCHEMA_REVISION` 硬编码在六处（`config.py:83`、`docker-compose.yml`、
`backend_v2/Dockerfile`、Helm configmap、`ci.yml`、`staging.yml`），
0052/0053 落地后一处都没改，本次一并升到 `0053_decision_tree_drafts`。

症状具体：`/health/live` 返回 200，`/health/ready` 报 `schema_revision: mismatch`。
**容器起得来，对外服务门是红的**，三天没人发现。第 6 节把它写成一条常设门。

---

## 3. 三条不变量

所有阶段都必须保持这三条。它们是前两节问题的直接约束，不是偏好。

**I1. 一条执行主干。** 自动跑出来的东西落在与人工完全相同的表上 ——
`workflow_runs`、`jobs`、`candidates`、`project_timeline_entries` ——
而不是 Autopilot 私有的镜像表。`autopilot_stages.resource_id` **指向**它们，不复制它们。

> 违反的后果具体且已知：一旦自动侧有自己的候选表，
> 「人工把某个候选标为 rejected」就不会被自动侧的下一阶段看见，
> 两边各自收敛到不同结论，而没有任何一处报错。

**I2. 不可变的是协议，不是产物。** 冻结 spec 是为了让费用与权限可审计；
产物（候选、结果、判读）**必须可被人修正**，否则自动跑出的错误结论无法纠正。

**I3. 接管是显式状态转移。** 人接管一条自动 campaign 时必须写 ledger、改状态、UI 留痕。
不存在「悄悄编辑一条正在自动跑的东西」这种操作。

---

## 4. 目标态

**一条执行主干，两种驾驶方式，一个共同的介入点。**

```
                      ┌──────────────────────────────┐
   人工驾驶 ─────────▶│  workflow_runs / jobs /      │
   （Workflow 画布）   │  candidates /                │◀──── 自动驾驶
                      │  project_timeline_entries    │      （stage adapter）
                      └──────────────┬───────────────┘
                                     │
                            介入点：takeover
                        （显式状态转移 + ledger 留痕）
```

| 模式 | 谁发起 | 谁能改产物 | 协议可变吗 |
|---|---|---|---|
| 人工 | 用户在 UI | 用户 | 可变（版本化 + `If-Match`） |
| 自动 supervised | Autopilot campaign | 用户，经 takeover | 不可变 |
| 自动 plan_only | Autopilot campaign | —（不产生计算产物） | 不可变 |

种子脚本降级为**首次导入工具**，且改走服务层（见 M1）。

---

## 5. 分期

每期以「可验收的行为」结尾，不以「代码写完」结尾。

### M0 — 两种模式看同一份记录（已完成，2026-09-05）

- `0052` / `0053` 上线，时间线具备 `decision_ref` / `lane` / `alternatives`；
- 骨架筛选完整链条（C029 骨架级闸门、C030 序列级 STOP 与单位错配）入库；
- `schema_revision` pin 与迁移 head 对齐。

**验收（已达成）**：`/health/ready` 全绿；决策覆盖 16/37 → 31/37；
`check_decision_coverage.py` 通过、ratchet 抬到 31。

---

### M1 — 前端补上记录的写入路径（已完成，2026-09-05）

**差额**：后端与 SDK 齐备（§2.2），缺前端客户端、编辑器、挂载点。

**前端**

1. `frontend/src/lib/api/timeline.ts` 增 `createTimelineEntry` / `updateTimelineEntry` /
   `deleteTimelineEntry`，包装已生成的 SDK 函数；改与删发 `If-Match: W/"<version>"`，
   412 走「提示重载、绝不覆盖」。
2. 新增 `frontend/src/features/timeline/TimelineEntryEditor.tsx`，**结构化输入**而非自由文本：
   - `entry_type`（7 值）/ `outcome`（4 值）/ `lane`（4 值）/ `phase` / `decision_ref`；
   - `provenance`：八个允许键的具名输入，不允许自造第九个拼法；
   - `code_refs`：`path` + `role` 成对；
   - `alternatives`：`option` + `rejected_because`，**两项都必填**
     （无理由的备选是装饰，后端 `Alternative` 已强制，前端不要让用户走到 422 才知道）。
3. 客户端镜像 `check_lane_evidence`：`lane ∈ {wet, both}` 且 outcome 已定时，
   缺 `experiment_result_ids` / `protein_ids` 即禁止提交。
4. 编辑入口挂两处，共用同一编辑器：`ProjectTimeline` 的条目行、`DecisionTreeView` 的节点。
5. 在时间线条目行挂 `AttachToGoalButton`，`resource_type = "timeline_entry"` —— 一颗按钮，
   直接把 46 条 `unattached` 变成可挂载。

**后端**

6. 种子脚本改走 timeline 服务层而非 ORM 直写，使脚本写入与 UI 写入产生同样的审计记录
   （解决 §2.3 的可追溯性不等价，同时裁定第 8 节问题二）。

**验收**：把 C023–C037 从 `seed_cannabinoid_timeline.py` 删除后，
能在 UI 里重建出**逐字段相同**的 15 行（含 `alternatives` 的 20 条备选与全部 `code_refs`），
且 `check_decision_coverage.py` 仍报 31/37。

> 这条验收故意可证伪：如果编辑器只能写「标题 + 一段话」，它过不了。

**已验证的部分**：把库里真实的 C029 / C030 / C033 三行取出来，
经 `draftFromEntry` → `draftToBody` 往返后逐字段相等
（`alternatives`、`code_refs`、`provenance`、markdown 正文、UTC 时间戳全部不变）。
**未验证的部分**：需要登录会话的那半，即在浏览器里手动重建。
往返测试用的是真实数据，因此**没有留在公开仓库里**——公开测试固件只保留形状，
研究内容按 `docs/DATA_CATALOG.md` 的边界留在库里。

---

### M2 — stage adapter：自动侧接上主干（已完成，2026-09-05）

**差额**：`resource_type` / `resource_id` 已存在但无人写；`execute_campaign` 止于 first stage ready。

**后端**

1. 新增 `backend_v2/app/autopilot/adapters/`，定义 stage adapter 协议：
   `ensure_stage_resource(session, campaign, stage) -> (resource_type, resource_id)`，
   **幂等**，按 `stage.id` 派生确定性 key，恢复时先查外部状态再决定是否新建
   （与 Docker/LSF adapter 的 `ensure_submitted` 同一纪律）。
2. 第一个 adapter 产出 `workflow_run`：经 workflows 服务建 run，
   经 compute 服务走 `POST /workflow-runs/{id}/submissions`，
   `Idempotency-Key` 由 stage id 派生。**不新增第二条提交通道**——
   跨域写必须经另一个域的 service，不得直插外域 repository。
3. `execute_campaign` 对 ready stage 调 adapter，写 ledger 事件 `stage.resource_created`。
4. 若 adapter 需要落新表，必须同时进 `contracts/v2-flow-matrix.yaml`；
   当前设计不需要新表。

**前端**

5. Autopilot 页每个 stage 显示产物深链：`/workflow?run=<id>`、`/candidates`。

**文档**

6. 修订 `docs/AUTOPILOT_CAMPAIGNS.md` §2：现文把人工与自动的差别落在
   「研究者能否持续增加评价和决策」上，读起来像是自动 campaign 的产物也不可评价。
   明确「不可变」的宾语是 **frozen spec**，不是 campaign 产出的任何领域对象（I2）。
   同时更新 §4 边界表中 adapter 那一行。

**验收**：自动启动一条 supervised campaign，在 **Workflow 页**打开它跑出来的 run，
在 **Candidates 页**看到它产出的候选 —— 全程不访问 Autopilot 页。

**已达成的部分**：`compute` / `design` 阶段产出真实 `workflow_runs` 行，
Autopilot 页每个阶段直达 `/workflow?run=<id>`；重投与「worker 中途崩溃后 stage 指针丢失」
两种情况都只产生一条 run（测试清空 `resource_id` 后重跑，仍找回同一条）。
**未达成的部分**：候选物 —— 那要等 collect 阶段的 adapter，而 collect 的产物依赖真实计算完成。

---

### M3 — 接管与回填（部分完成，2026-09-05）

**目标**：人能改自动跑出来的东西，且改动对自动侧可见。

**数据模型**（新迁移）

1. `autopilot_campaigns` 增 `taken_over_at` / `taken_over_by`；
   `status` 增值 `manual_takeover`（现有 `ck_autopilot_autonomy` 约束不动，
   status 无 check 约束，但要在 service 层枚举收口）。

**后端**

2. `POST /autopilot-campaigns/{id}/takeover`，带 `If-Match`，幂等，写 ledger 事件 `campaign.takeover`。
3. 接管后自动推进停止；产物经各自领域 API 编辑（`PATCH /candidates/{id}` 等，已具备）。
4. 后续 stage 读**实时集合**而非启动时快照 —— 这是 I1 在读路径上的落点。

**前端**

5. Autopilot 页接管按钮 + 状态横幅；Workflow / Candidates 页对被接管 campaign 的产物显示来源标记。

**验收**：自动产出的候选被人工标为 rejected 后，下一阶段的输入集合确实少了那一条，
且 ledger 能读出是谁、何时、为何。

**已达成**：接管本身 —— 状态、时间、人、ledger（由用户署名）、幂等、已取消不可接管、
跨项目拒绝，以及「接管后 worker 不再推进」。
**未达成**：候选层面的回填闭环，与 M2 未达成的部分同因：还没有产出候选的 adapter。

---

### M4 — 无人值守闭环与预算实拨对账（部分完成，2026-09-05）

- 结果回写、候选漏斗、实验复盘的自动路径；
- 预算从 `reserved` 到 `committed` 的实拨对账；
- `AUTOPILOT_CAMPAIGNS.md` §6 列的完整验收：并发预留、超额拒绝、重复 idempotency key、
  取消级联、worker 重投、跨项目权限与 RLS、adapter 故障恢复。

**已达成**：预算 `reserved → committed` 实拨对账（`settle_reservation`）——
按预留封顶，超出部分作为 `unbilled_overrun_gpu_seconds` 记进 ledger 而不是抛异常；
重投幂等；已被取消释放的预留不再结算。
加上重复 idempotency key、超额拒绝、取消级联、adapter 故障恢复、跨项目权限，
`AUTOPILOT_CAMPAIGNS.md` §6 的清单已覆盖大半。

**随后补齐的两项**（`backend_v2/tests/test_autopilot_postgres.py`，需真实 PostgreSQL）：

- **并发预留**：八线程八连接争一个只装得下两份的预算，硬上限从未被突破。
  写它的过程纠正了我对防护结构的理解：预算锁与 campaign 版本乐观锁是两层，
  而同一 campaign 上的并发**通常由版本检查先拒绝**，不是预算锁。
- **worker 上下文 RLS**：这一项在动手验证时才发现根本没有可验证的东西 ——
  `0049` 给 autopilot 表加的 RLS 只认 `bda.user_id`，`0051` 给别的项目表补的
  `bda.worker_project_id` 分支从未覆盖到它们。缺陷方向与直觉相反：不是 worker 看得太多，
  而是**限定在自己项目里的 worker 看不见自己的 campaign**。`0055` 补上，测试两头都断言。

  这条也说明第 6 节那句「门在跑但什么也没检查」有个更难发现的变种：
  **门根本不存在，而文档描述它存在**。`AUTOPILOT_CAMPAIGNS.md` §5 一直写着 worker 必须
  限定在项目上下文中运行 —— 那句话在数据库里没有对应物，直到现在。

**仍未达成的一项**：在真实计算上跑通的端到端闭环。它需要集群，而集群登录按规则由所有者本人完成。

**只有这一项也通过之后**，才能把 Autopilot 描述为完整自动执行闭环。在此之前不得如此描述。

---

## 6. 门与验证矩阵

| 门 | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| OpenAPI + 前端 SDK 重生成，`git diff --exit-code` | ✓ | ✓ | ✓ | ✓ |
| 流程矩阵（新表必须声明） | — | ✓ | ✓ | ✓ |
| 决策覆盖 ratchet（只能升，升了要抬基线） | ✓ | — | — | — |
| 迁移可逆（`alembic check` → `downgrade base`） | — | — | ✓ | ✓ |
| 覆盖率阈值（总体 85%，指定模块 95%） | ✓ | ✓ | ✓ | ✓ |
| **schema pin 一致性（新增）** | ✓ | ✓ | ✓ | ✓ |
| 退役运行时 grep | ✓ | ✓ | ✓ | ✓ |

**新增门的定义**：`BDA_V2_SCHEMA_REVISION` 的六处硬编码必须等于 `alembic heads`。
写成脚本，不靠人记 —— §2.4 的漏改症状是 ready 门红而 live 门绿，人不会主动去看。

**M1 期间发现并修复的两处门缺陷**，都属于「门在跑但什么也没检查」这一类：

1. **决策覆盖门指向了不存在的路径**。CI 调用
   `check_decision_coverage.py contracts/decision-records.yaml`，而契约在
   `private/contracts/decision-records.yaml`。脚本对缺失文件的处理是打印
   「nothing to check」并 exit 0 —— 那是给公开仓库准备的正确行为，
   在私有仓库里却让这道 CLAUDE.md 称为「load-bearing」的门一直空转。已改指真实路径。
2. **时间线的写操作只有 create 记审计**。`update_entry` 与 `delete_entry` 都不写
   `audit_logs`。在 UI 还不能写记录时这只是不对称；M1 让人能改决策记录之后，
   它就是「谁改的、什么时候改的」查不到。两者现在都记，`actor` 是必填关键字参数
   而不是带默认值的可选项 —— 默认值会让下一个调用点悄悄丢掉这条线索。

本地验证：

```bash
backend_v2/.venv/bin/pytest backend_v2/tests/test_autopilot_formalization.py
```

```bash
npm --prefix frontend test
```

## 7. 明确不做

- 不改 `/api/v2`、`backend_v2`、`BDA_V2_*` 命名，不改版本号。
  仓库与已发布契约保持 **BDA v2 / 2.0.0**，内部重构标签不是产品版本。
- 不让 `plan_only` 启动计算。
- 不为自动侧建平行的候选 / 结果 / 时间线表（违反 I1）。
- 不把 Copilot 变成第四条执行入口。它编排领域服务，不拥有领域规则。
- 不在 M1 做「自动生成决策记录」。记录的价值在于人写下的判断依据，
  自动摘要会把这一层填成看起来完整的空话。

## 8. 已裁定（原「未决问题」）

**问题一：接管的粒度是 campaign 还是 stage？**
**裁定：M3 做 campaign 级。**
理由有二：预算的不变量（reservation / committed / ledger）本来就是 campaign 作用域的，
stage 级接管会造出一个权限混合的 campaign，自动路径可能推进过一个人正在编辑的 stage，
产生没有报错的竞态。代价是「为改一个阶段要接管整条」——可接受，
因为 supervised campaign 是唯一产生计算的类型，接管本就应该是显眼动作。
**会改变这个裁定的证据**：M3 上线后如果实测显示接管多数发生在长链条的末段，
且中途阶段仍需自动推进，那就值得为 stage 级重新评估。

**问题二：种子脚本在 M1 之后的归宿？**
**裁定：保留为导入器，但必须改走服务层。**
109 条甜味蛋白决策用 UI 逐条补不现实，脚本要留。
但「脚本写入与 UI 写入在权限与审计上等价」不能靠约定，
让两者走同一条服务层代码路径，等价性就是结构性的而不是承诺性的（M1 第 6 项）。

## 9. 已裁定：构建网络

**问题三：选路线 1 —— 给 Docker 构建配置宿主代理。** 依据是实测而不是偏好：
用 `http_proxy` / `https_proxy` 两个**小写** build arg 指向 `host.docker.internal:1082`，
`apt-get` 与 `npm ci` 都恢复正常，`docker compose build api-v2 frontend` 完整通过。
大写的那一对不够 —— apt 和 npm 读的是小写。

落地方式是 `docker-compose.yml` 里的 `BDA_BUILD_PROXY`，**默认空**，
所以 CI 与任何直连网络的机器行为完全不变；只有需要它的机器才设置：

```bash
BDA_BUILD_PROXY=http://host.docker.internal:1082 docker compose build
```

没有选路线 2（推本地 registry）是因为它把一次构建变成两台机器的协作，
而问题其实只是几个环境变量；没有选路线 3（脚本化覆盖层）是因为它验证不了
`requirements.lock` 与 `package-lock.json` 的变更，那正是构建应该验证的东西。

**M2 的前置因此解除**，覆盖层镜像的做法退役。

### 原文（问题三的记录）

**本地构建网络。**
本机 Docker 构建拿不到网络 —— VPN 的 TUN 把包管理源解析进 `198.18.0.0/15`，
`apt-get update` 与 `npm ci` 在构建阶段都失败。
2026-09-05 的绕过方式是宿主机构建 + 代码覆盖层镜像（`FROM <已构建镜像>` + `COPY`），
可用，**但不是交付形态**：它无法验证 `requirements.lock` 与 `package-lock.json` 的变更。

三条候选路线，按推荐顺序：

1. **给 Docker 构建配置宿主代理**（BuildKit 走 host 网络 + `HTTP_PROXY` build args）。
   改动最小，恢复的是正常构建路径。
2. **在能联网的环境构建并推到本地 registry**，本地只 pull。CI 已经在构建镜像，可复用。
3. 保持覆盖层方案但脚本化，并在文档里声明它**仅用于本地观察，不用于验收**。

M2 开工前需要选定一条。选 3 的话，M2 的验收必须移到 CI 或另一台机器上做。

## 10. 顺序与依赖

```
M0 (done) ──▶ M1 ──▶ M2 ──▶ M3 ──▶ M4
                      ▲
                      └── 问题三先解决
```

M1 与问题三无依赖关系，可以并行推进：M1 全部在前端与服务层，不需要重建镜像。
