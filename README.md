# BDA Workbench

> **BDA Workbench** is an open, traceable workspace for computational protein-design research. The public alpha combines project evidence, workflow specifications, asynchronous operations, artifacts, experiments, and reviewable AI assistance in one versioned system. Its bundled `pd1-demo-v1` dataset is synthetic demonstration material; the current release is a reproducible staging baseline rather than a production deployment or a source of scientific conclusions.

BDA Workbench 面向计算蛋白设计中“证据、设计、计算、实验和决策分散在不同工具里”的问题。分散的记录使研究者难以回答三个基本问题：某个候选为何产生、它由哪些输入和软件版本生成，以及后续结论能否被独立复核。

现有工作流工具通常擅长编排节点，却不能同时保存文献证据、项目权限、人工决策和实验反馈；通用对话助手能够生成建议，却往往缺少项目边界、预算约束和可恢复的执行状态。因此，仅增加一个流程编辑器或聊天入口，不能建立可审计的研发闭环。

BDA 将项目作为权限与追溯边界，把研究证据、版本化工作流、异步计算、制品谱系、候选和实验记录放入同一模块化单体。平台使用 PostgreSQL 保存业务事实，使用 MinIO 保存计算制品，使用 Redis/Celery 传递异步工作；Copilot 与 Autopilot 只能通过受限、可审计的服务接口参与这一过程。

当前公开 alpha 已通过后端、前端、浏览器、迁移和公开数据检查，并提供可重复导入的 PD1 演示包。该验证证明的是软件基线可测试、演示数据可追溯和关键状态约束可执行，不证明真实模型性能、实验有效性或生产基础设施已经验收。

## 1. 系统边界

本文使用以下术语：**研究工作区（Research workspace）**保存可追溯的研究实体与证据；**工作流（workflow）**描述版本化计算图；**制品（artifact）**是带校验和与谱系的文件输出；**人工 campaign**记录设计—实验—复盘轮次；**Autopilot campaign**是经用户确认后冻结的自动执行协议。人工 campaign 与 Autopilot campaign 通过显式关联交接，但不是同一个数据模型。

平台当前遵循三项边界：

- PostgreSQL 是组织、项目、权限、状态、预算和谱系等业务数据的真源。
- MinIO 是结构、模型输出、报告和交付包等计算制品的真源。
- Git 保存软件、不可变清单、小型公开演示数据和可审查文档，不保存私有研究运行包。

公开 `BDA` 仓库是软件真源。私有 `BDA-demo` 只能跟随明确的 BDA release tag，并在允许目录中增加私有研究数据和部署配置；软件变更通过受保护的单向同步 PR 进入 demo，不从 demo 反向发布。

## 2. 研究流程

平台把一次研发活动组织为可检查的状态转换，而不是一段无法复现的对话：

```text
研究问题与约束
      │
      ▼
证据、目标与项目上下文 ──► 工作流草案 ──► 人工确认与异步计算
      │                                      │
      │                                      ▼
      └────────────────────────────── 制品、候选与谱系
                                             │
                                             ▼
                                   实验记录、评价与下一轮决策
```

这条路径的重点不是自动化程度，而是每次写入都有项目权限、执行身份、输入版本和审计记录。研究者可以从候选或实验结果反查工作流快照与制品，也可以在工作流启动前审查节点参数、资源需求和目标计算环境。

### 2.1 建立项目与研究上下文

1. 创建组织和项目，并为项目指定一个或多个 target。
2. 在 Research workspace 中登记文献元数据、证据、数据集和研究目标；**判断**挂在研究目标树上显示为决策树，每个节点带结论、证据条数、被否掉的分支与完整决策正文；计划、方法与结果在同一份记录的时间线视图里按阶段读。两处是同一份数据的两种读法，不是两份记录。
3. 通过 Registry 选择已经注册的模型插件、方法插件、计算节点与提供商。

### 2.2 设计与执行工作流

1. 创建工作流图并连接类型兼容的输入、输出端口。
2. 运行 preflight；系统检查图结构、插件契约、制品输入和计算目标。
3. 提交后生成不可变运行快照。任务通过 transactional outbox 进入 Celery 队列，并由 Docker 或 LSF 适配器执行。
4. 输出写入 MinIO，校验和、运行谱系和状态写入 PostgreSQL。

### 2.3 记录候选与实验反馈

候选、实验结果和交付包都属于项目域对象。实验数据不覆盖计算结果，而是以新的记录连接候选、构建体、测量条件和制品，使模型预测与实验观察可以分别审查。

Lab 工作台提供蛋白构建体管理、浓度与稀释计算，以及 BLI、AKTA 和酶活动力学分析。它用于把必要的实验反馈接回项目谱系，不承担完整 LIMS/ELN 的职责。

## 3. Copilot 与 Autopilot

Copilot 是受项目上下文和工具白名单限制的研究协作层。它可以读取项目、研究证据、候选、工作流和实验结果，也可以在用户明确请求时创建待确认操作。长时任务使用持久化 agent run：对话轮次、工具调用、预算和等待中的计算均保存在服务器，浏览器不是会话真源。

Autopilot 用于冻结协议后的自动执行交接，其当前交互顺序为：

1. 输入自然语言需求或结构化 brief，生成版本化 draft/spec。
2. 预览目标、阶段和约束，并明确填写 campaign 名称与硬预算。
3. 使用 ETag/`If-Match` 确认 draft，生成不可变 campaign。
4. 启动时事务性预留预算并返回异步 operation ID。
5. 取消时幂等地级联到阶段、operation、research generation 和计算 job，再由 worker 对账未提交预算。

当前 worker 能够可靠地完成预算预留、执行交接、首阶段就绪和取消对账；具体 research/compute 阶段仍需要版本化 stage adapter。因而，本 alpha **尚不提供从任意自然语言需求到真实多阶段计算、结果回写和实验复盘的无人值守闭环**。执行地图、候选漏斗和自动迭代控制台属于后续界面与适配器工作，不应从归档设计稿推断为已发布功能。详见 [Autopilot 协议与边界](docs/AUTOPILOT_CAMPAIGNS.md)。

## 4. 当前能力与成熟度

| 领域 | 当前状态 | 可验证边界 |
| --- | --- | --- |
| 组织、项目、target 与角色权限 | 已实现 | 写路由声明权限；项目域受拒绝优先权限约束 |
| Research、文献关系与研究包目录 | 已实现 | 私有包通过 manifest、checksum 与对象 URI 注册 |
| 干实验决策树与项目时间轴 | 已实现 | 一份记录三种读法：树视图（目标树 + 挂在其下的判断、被否分支、未绑定证据标记）、时间线视图（按阶段的完整流）、未决视图（当前活跃的分支点）。Research workspace 与项目时间轴渲染同一棵树 |
| 工作流、插件端口与运行快照 | 已实现 | ETag 并发控制；提交后快照不可变 |
| Docker/LSF 异步计算与制品谱系 | 已实现，真实集群待验收 | 本地与测试适配器可验证；真实 LSF 闭环不在公开 alpha 的验收范围内 |
| Copilot 持久化 agent run | 已实现 | 支持受限工具、长任务挂起/恢复、一级子任务和成本上限 |
| Autopilot 冻结协议与预算控制 | 已实现 | draft、确认、预算预留、operation、审计与取消对账可测试 |
| Autopilot 完整多阶段执行闭环 | 部分实现 | stage adapter、结果回写、可视执行地图和自动复盘尚未完成 |
| 生产部署 | 未开放 | production deploy 与写入必须在真实基础设施和恢复演练签字后启用 |

界面中的 viewer 只读提示用于帮助用户理解权限，不构成安全边界；后端授权、数据库行级安全策略和 worker 项目上下文才决定数据能否被访问或修改。

## 5. PD1 演示包

公开仓库只包含 `pd1-demo-v1`。该包由一个 PD1 项目、12 条公开来源的文献元数据、4 条证据关系、4 个公开结构引用和 6 个 `DEMO` PDB fixture 组成；6 个 fixture 对应 3 个虚构候选，并具有固定 SHA-256 校验和。

公开文献元数据与结构引用用于演示来源关系。候选 ID、候选指标和 `DEMO` PDB 内容均为预计算合成材料，不是本仓库运行模型所得，也不代表实验结果、医疗建议或科研结论。数据来源、字段语义、许可和校验和见 [PD1 数据卡](examples/migration-fixtures/pd1/DATA_CARD.md)。

## 6. 架构

```text
React + TypeScript
        │ /api/v2
        ▼
FastAPI 模块化单体 ─────► PostgreSQL
        │                    业务事实、权限、状态、预算、谱系
        ├───────────────► Redis / Celery
        │                    outbox、队列、worker heartbeat
        └───────────────► MinIO
                             版本化计算制品与校验和
```

该架构保持一个部署边界，但通过 module descriptor 注册模型、路由、Celery task、权限和指标，避免把领域拆成过早的微服务。`/api/v2` 是唯一活动 API；包含私有路径和旧研究运行的 v1 迁移档案只保存在私有恢复库，不随公开发行版发布。

## 7. 本地启动

要求：Docker Engine、Docker Compose v2，以及可用于本地开发的空闲端口。

```bash
cp .env.example .env
# 替换 .env 中的全部示例密钥和密码
docker compose up --build
```

启动后可访问：

- Web：`http://localhost:8080`
- liveness：`http://localhost:8080/api/v2/health/live`
- readiness：`http://localhost:8080/api/v2/health/ready`
- MinIO 控制台：`http://localhost:9003`（仅本机绑定）

`.env.example` 面向本地开发；生产 Helm 的 `BDA_V2_WRITES_ENABLED` 默认值为 `false`。真实 Kubernetes、LSF、OIDC、TLS、PostgreSQL 持续时间点恢复（PITR）、MinIO 恢复、告警和回滚演练全部验收前，不应开启生产写入。

## 8. 验证与复现

代码变更至少应运行以下检查：

```bash
backend_v2/.venv/bin/ruff check backend_v2
backend_v2/.venv/bin/mypy --config-file backend_v2/pyproject.toml backend_v2/app backend_v2/scripts
backend_v2/.venv/bin/pytest backend_v2/tests
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:browser
python scripts/check_public_data.py
```

迁移验收包括空库 upgrade、全量 downgrade/upgrade round trip，以及从公开 demo 基线克隆升级；恢复策略使用迁移前备份和应用回滚，不依赖危险的线上 downgrade。更完整的命令、依赖和预期结果见 [本地验收](docs/V2_LOCAL_ACCEPTANCE.md)与[发布及恢复说明](docs/STAGING_RELEASE_AND_RECOVERY.md)。

## 9. 文档、贡献与引用

- [文档索引](docs/README.md)
- [后端说明](docs/BACKEND_V2.md)
- [前端说明](docs/FRONTEND_V2.md)
- [插件接口](docs/PLUGIN_INTERFACE.md)
- [安全政策](SECURITY.md)
- [贡献指南](CONTRIBUTING.md)
- [公开数据政策](DATA_POLICY.md)

引用本软件时，请同时记录 BDA release tag、Git commit、PD1 package version 和所用插件 manifest checksum；这些信息比仅记录网页访问日期更能确定实际执行环境。软件采用 [Apache License 2.0](LICENSE)，PD1 演示数据单独采用 [CC BY 4.0](DATA_LICENSE.md)。
