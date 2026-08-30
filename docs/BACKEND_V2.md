# BDA 后端 v2 说明

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；当前平台与科研总状态以 docs/refactor/CURRENT_STATE_2026-08-29.md 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

## 1. 运行边界

v2 是 FastAPI 模块化单体。API、通用 worker、research worker、copilot worker 与 Beat 分进程部署。PostgreSQL 是唯一业务数据库，Redis 只承载 Celery，MinIO 是权威制品存储；API 容器本地目录不属于业务数据面。

所有接口位于 `/api/v2`。成功响应直接返回类型化资源或 cursor page；错误使用 `application/problem+json`，字段固定为 `type/title/status/detail/instance/error_code/trace_id`，校验错误附加 `errors`。

## 2. 模块边界

`app/` 按 identity、projects、targets、workflows、compute、artifacts、candidates、experiments、campaigns、research、knowledge、literature、intelligence、registry、delivery、copilot、audit 与 platform 划分。路由负责协议与依赖注入，service 负责规则，repository 负责持久化，model/schema 分别表示数据库与外部契约。

跨域写入通过 service 或 outbox 事件完成。Copilot 只编排领域服务；compute 不直接访问 Campaign repository。请求使用短生命周期 SQLAlchemy session，SSE 建立前完成授权并释放连接。

## 3. 数据与并发

- UUID 主键、UTC 时间、`version` 乐观锁；旧数据保留唯一 `legacy_id`。
- 写接口通过 `If-Match: W/"<version>"` 防止覆盖；缺少条件返回 428，版本冲突返回 412。
- 列表使用不透明 cursor，不提供 offset/total 兼容层。
- 项目软删除并保留 30 天，物理清理由 maintenance queue 执行。
- 审计记录与业务写入同事务保存 actor、组织、项目、动作、实体、trace、结果和时间。

## 4. 身份与授权

本地账号和标准 OIDC discovery/authorization-code/PKCE 最终映射到统一用户。Access JWT 默认 15 分钟；Refresh Token 默认 30 天、哈希保存且每次刷新轮换，浏览器只通过 Secure/HttpOnly/SameSite Cookie 发送。

角色为 admin、researcher、viewer，并叠加组织成员和项目成员关系。所有命令路由声明 `x-permission` 并通过统一 dependency 校验；viewer 不能上传、编辑、提交、取消或推进审核。

## 5. 工作流与计算

提交 `POST /workflow-runs/{id}/submissions` 必须提供 `Idempotency-Key`。API 只创建 submission、job、attempt 与 outbox，返回 202；Redis 暂不可用不导致计算请求丢失。

状态机为：

```text
pending -> dispatching -> queued -> running -> collecting -> succeeded
                                                \-> failed
                         \--------------------------> cancelled
```

publisher 用 `FOR UPDATE SKIP LOCKED` 发布任务。队列为 `dispatch`、`poll`、`collect`、`maintenance`、`research`、`copilot`，Beat 扫描到期任务。Docker/LSF adapter 均实现 `ensure_submitted/status/cancel/collect`，以 job UUID 派生确定性名称和 staging key，恢复时先查询外部状态，避免重复提交。

统一运行协议包含输入 manifest、参数、预签名 GET、输出 manifest 与预签名 PUT。`collect()` 拒绝路径穿越，校验 schema、大小和 SHA-256，并在同一事务创建 artifacts、lineage、候选、实验结果与完成事件。

生产 Docker 仅允许远程 mTLS daemon；禁止挂载宿主机 socket。LSF 使用 SSH credential ref、确定性 job name/目录与脚本 checksum，wrapper 仅能向受限 MinIO key 上传。

## 6. Artifact 协议

浏览器流程：

1. `POST /artifact-uploads` 创建 session。
2. 客户端计算 SHA-256，并按 required headers 直传预签名 URL。
3. `POST /artifact-uploads/{id}/complete` 提交 checksum。
4. 服务校验大小、checksum 与 PDB/mmCIF/FASTA/JSON/CSV/XLSX/ZIP/PDF 格式，提升到最终对象并创建 artifact。

Artifact 状态为 uploading、available、failed、deleted。reconciliation 检查超时 staging、孤儿对象、缺失对象、共享 checksum 引用和软删除项目。

## 7. 高级领域

- Project 支持多个 target，`primary_target_id` 只是主目标指针。
- Campaign 包含 campaign/round/evaluation/decision，任务完成事件经 outbox 推进评估。
- Literature 包含 document/chunk/claim/evidence/relation/subscription；摄取和关系检测由 research queue 执行。
- Intelligence 包含 run/report/evidence/hotspot/design route；审核使用 ETag，apply-route 创建普通工作流，export 生成 artifact。
- Registry 管理 server、compute node、model/method plugin、参数目录、script asset 和 LLM provider；数据库只存 `credential_ref`。
- Copilot 提供 chat/messages/SSE/config/skills/route plan/interpretation，外部调用在 copilot queue 执行。
- Compute draft 确认后创建普通 job；配体查询无副作用，导入必须生成项目 artifact。

## 8. 配置与启动门禁

配置前缀为 `BDA_V2_`。MinIO 使用 `MINIO_ENDPOINT` 进行服务端对象 I/O，使用 `MINIO_PUBLIC_ENDPOINT` 为浏览器直传和下载生成不可改写 host 的预签名 URL。生产至少要验证 PostgreSQL、Redis、这两个 MinIO endpoint、JWT/refresh 密钥、OIDC、LLM provider、远程 Docker mTLS 或 LSF SSH/queue、外部科研源、OTLP/Prometheus 与写入开关。生产环境发现默认密钥、SQLite、demo compute、Docker socket、缺失 provider 或不安全 TLS 时必须拒绝启动。

本地示例见仓库根目录的 `.env.example`（唯一一份）。Helm 默认 `writesEnabled: "false"`。

## 9. 迁移与切换

`scripts/migrate_v1.py` 是只读、幂等 ETL，按 identity/registry → projects/targets → research/workflows/jobs → artifacts/candidates/results → campaign/literature/intelligence/audit 迁移。ID 使用 UUIDv5；终态 job 不生成 outbox。允许文件根必须显式传入，根目录外路径进入拒绝清单，所有文件重新计算 SHA-256。每次演练把 source fingerprint、表计数、checksum digest、ID-map digest 与拒绝摘要写入 `migration_runs`；`scripts/check_migration_rehearsals.py` 要求三份报告完全一致。

仓库退役前快照保存在忽略版本控制的 `backups/v1-retirement/`，包含 SQLite/WAL、artifacts、deliverables、配置和 SHA256SUMS。生产切换仍要求三次真实快照演练、零未解释记录、零外键错误、可迁移文件 checksum 100%、备份恢复、Docker/LSF 闭环和维护窗口审批。

v2 开启写入前可恢复固定 v1 镜像与只读快照；开启后不回写旧系统，只使用 PostgreSQL PITR、MinIO versioning 与备份恢复。

## 10. 监控与故障处理

健康端点为 `/health/live` 和 `/health/ready`。结构化日志携带 trace ID 并传播 W3C Trace Context。关键指标包括数据库池、outbox backlog、Celery retry、状态停留时长、Docker/LSF 错误、MinIO 校验失败和迁移进度。

- Redis 中断：提交仍落库；恢复后 publisher 清空 backlog。
- external ID 丢失：adapter 用确定性名称查询，禁止盲目重交。
- MinIO 中断/checksum 错误：job 保持 collecting/failed 并记录分类，不能标记 succeeded。
- worker 崩溃/重复 outbox：幂等 task 与状态机处理重放。
- 取消竞态：以终态和外部查询结果收敛，记录人工 retry attempt。

## 11. 开发与验收

```bash
ruff check backend_v2
mypy --config-file backend_v2/pyproject.toml backend_v2/app backend_v2/scripts
pytest backend_v2/tests --cov=backend_v2/app --cov-report=json:backend_v2/coverage.json
python backend_v2/scripts/check_coverage.py backend_v2/coverage.json
alembic -c backend_v2/alembic.ini upgrade head
alembic -c backend_v2/alembic.ini check
```

本地 PostgreSQL/Redis/MinIO、50 并发 API、20 SSE、故障恢复、三次快照迁移、依赖审计和容器扫描结果见 `docs/V2_LOCAL_ACCEPTANCE.md`。生产验收仍需在实际 Kubernetes、远程 Docker daemon 与 LSF 测试队列重跑闭环，并验证监控告警、PITR/MinIO 恢复和维护窗口。缺少这些环境证据时只能声明“仓库默认切换完成”，不能声明“生产已切流”。
