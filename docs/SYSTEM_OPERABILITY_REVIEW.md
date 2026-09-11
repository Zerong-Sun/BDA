# System operability review

状态：活跃

最后核验：2026-09-11（合并后的代码、本机 Docker 栈与数据库实测）

权威范围：BDA v2 现有可操作性、内置 API 与内置大语言模型的能力边界、从想法到集群的端到端自动化差距；不代表生产部署状态。

数据来源：仓库内版本化代码与测试、本机 `bda-*` Docker 栈、其 PostgreSQL 实例的运行记录、真实 Chromium 验收脚本。无私有研究数据。

替代关系：补充 [Workflow connections and gates](WORKFLOW_GATES.md) 与 [Autopilot protocol and implementation boundary](AUTOPILOT_CAMPAIGNS.md)，说明两者之间尚未接合的部分。

## 结论

一句话：**记录、审查与门控这一半已经相当完整；从想法到集群的无人值守那一半还没有接通。**

把「提出一个想法 → 中间几个人工确认点 → 其余全自动完成」拆成六步，现状是：

| 步骤 | 现状 | 依据 |
| --- | --- | --- |
| 1. 表达目标、生成调研 | **可用**。Copilot 可检索文献、目标情报、项目知识，产出待审草稿 | `copilot/capabilities.py`；literature / intelligence / research 队列 |
| 2. 由目标推荐路线 | **可用但需人工确认**。`planRoute` 给出路线选项，`applyRoutePlan` 落成节点 | `copilot/route_catalog.py`、`Workflow.tsx` 路线规划面板 |
| 3. 连线与门控 | **本次补齐**。端口级连线、逐次结果门控、仅次序连线 | `workflows/connections.py`、`workflows/gate_engine.py` |
| 4. 提交到集群 | **机制齐全，里程极少**。见下文 | 数据库中历史作业总数：**2**，均为 LSF，最近一次 2026-07-05 |
| 5. 结果回收与筛选 | **可用**。collect 校验 SHA-256/大小/schema，门控按条件、排序、Top N 或人工放行 | `compute/adapters.py`、`gate_runtime.py` |
| 6. 无人值守串起全程 | **未实现**。Autopilot 只到「建出一个草稿 workflow run，等人打开」 | `autopilot/adapters.py` 的模块注释写明这是刻意的边界 |

所以今晚这个问题的答案是：**目前做不到全自动，缺口集中在第 4 步和第 6 步，而且第 4 步的缺口主要不是代码问题。**

## 内置 API 能做到什么

FastAPI 模块化单体，194 条 `/api/v2` 路径，79 张表，全部进了数据流矩阵。能力覆盖项目、目标、工作流、计算、制品、候选、实验、活动、研究、知识、时间线、文献、情报、注册表、交付、Copilot、Autopilot、湿实验、配体、审计与平台自检。

值得强调的是它**不做**什么，因为这些克制是它可信的原因：

- 提交计算的接口只写 submission/job/attempt/outbox 四张表就返回 202，不在请求里调用任何计算后端。Redis 挂掉不会丢作业。
- 所有写操作要 `If-Match`，缺头 428、过期 412。列表只有不透明游标，没有 offset/total。
- 制品上传是浏览器直传 MinIO 的两段式，API 从不接收 multipart 文件体。
- 生产启动时如果发现默认密钥、SQLite、演示计算后端、挂载的 docker.sock、缺 LLM 提供方或不安全 TLS，直接拒绝启动。

## 内置大语言模型能做到什么

配置上是 OpenAI 兼容端点 + 按项目 BYOK，另有一个规则式的演示提供方作为无凭据时的回退。凭据只以 `env:` / `file:` 引用形式存放，不入库。

能力按 `copilot/capabilities.py` 分成 read / draft / queue 三档，并且**没有任何一档可以直接提交计算**：

- **read**：项目数据、研究证据、结果解读、湿实验库与台面计算。
- **draft**：知识草稿、湿实验构建体登记、仪器文件解析、研究轨迹挂接、**计算草稿**（`create_compute_draft`，显式标注 `requires_confirmation`）。
- **queue**：文献检索、目标情报、研究缺口修复——都要用户明确请求。

除聊天外还有持久化的 agent run：`agent_loop.py` 支持工具调用循环、`await_compute_job` 挂起等待作业落定、`spawn_subagent` 派生子任务。这是「无人值守」真正的骨架，已经存在。

**它的天花板是刻意设的**：路线应用、计算提交、门控放行都要人确认。要做到用户设想的自动化，需要的不是更强的模型，而是把这些确认点改成可授权的策略，并为每一步留下可审计的记录。

## 第 4 步的真实障碍：集群登录

`BDA_V2_LSF_SSH_KEY_PATH` 为空，`BDA_V2_LSF_SSH_HOST=qm`。按 `docs/QM_CLUSTER_OPERATION_RULES.md`，启明的登录方式是**用户在自己的终端里手动输入密码**，代理只能复用用户已确认的会话；不得自动登录、自动重连或后台探活。

这条规则和「连上集群之后它就能全部自己完成」直接冲突。这不是缺一段代码，是一个需要用户决定的取舍：

- 要么在集群侧配置一把长期可用的密钥或代理会话，由平台持有；
- 要么接受集群提交始终是一个人工确认点——每一轮由人把渲染好的作业推上去。

`ssh_transport.py` 两种传输都已实现（密钥 `BatchMode=yes`，以及为不提供 publickey 的站点准备的 paramiko PTY 通道），所以哪条路都是配置问题，不是开发问题。

另外，本机栈当前 `BDA_V2_SCHEDULER_DISPATCH_PAUSED=true`，所以 `/health/ready` 报 `unavailable`——这是刻意暂停，不是故障。

## 第 6 步：Autopilot 的边界

`autopilot/adapters.py` 的模块注释把边界写得很清楚，而且理由是对的：

> 适配器刻意**不**凭空造出一个计算提交。一份没有指明路线的冻结规格只会得到一个 `draft` 运行和一个说明此事的阶段；人打开 Workflow 页面把它做完。从一句话猜出一条路线，就是把 GPU 小时花在没人问过的问题上。

目前 `ADAPTERS` 只注册了 `compute` 和 `design` 两个阶段键，都指向同一个「建一个 workflow run」的适配器。草稿、确认、预算预留与取消都是主线能力；研究/计算的分阶段适配器与完整闭环不是。数据库里 Autopilot 活动与草稿数均为 **0**，这条路径至今没有真实使用。

## 里程：值得正视的一点

平台自身的计算通路历史上只跑过 **2 个作业**。同期真正的集群工作（AF3、jackhmmer 等）走的是手写 LSF 脚本。

这说明：门控、绑定、清单、回收这些机制在测试里是绿的，但在真实作业上的暴露极少。在把更多自动化压到这条通路上之前，先用一条完整的真实路线跑通一次，比再加功能更有价值。

## 本次修复

见 [Workflow connections and gates](WORKFLOW_GATES.md) 与 [Workflow gate validation and repairs](WORKFLOW_GATES_REVIEW.md) 的既有清单。本轮在其之上补了四项：

| 编号 | 问题 | 修复 |
| --- | --- | --- |
| O01 | 卡片按声明端口渲染连接点后，没有端口的旧连线在画布上直接消失——连同唯一能配置门控的徽章。真实路线上 6 条边只画出 2 条 | 每张卡片常驻一对「仅次序」连接点，无端口连线锚在其上 |
| O02 | 两个没有兼容端口的节点在界面上**无法连接**：对话框只说「没有兼容端口」，连接按钮一直禁用。服务端一直接受 `dependency` 连线，但没有任何界面能产生它 | 拖动空心连接点即建立仅次序连线；连接对话框也把它列为一个正式选项 |
| O03 | 画布自带一个与所在栅格行无关的高度，底部留白，图被压到更小的缩放；只读横幅与图例浮层互相压字 | 画布填满所在列；横幅与图例改为图上方的常规行，不再浮在路线上 |
| O04 | 预检结果整列铺开，九节点路线常有二十行，把画布推到一屏以下 | 默认显示前 4 条并给出「N 项阻断 · M 项提示」计数，可展开 |

节点卡片另外把「必填但未连接」的输入端口标红，因为这是路线拒绝提交最常见的单一原因。

## 复现

```sh
backend_v2/.venv/bin/pytest backend_v2/tests
npm --prefix frontend test
npm --prefix frontend run test:workflow-ux
npm --prefix frontend run test:browser
```

2026-09-11 结果：后端 **908 passed**；前端 **576 passed**；工作流浏览器验收 **10/10 步**；浏览器矩阵 **148/148**。Ruff、mypy、OpenAPI、数据流矩阵、插件槽位、集群声明与文档清单门均通过。
