# BDA v2 本地收口验收（2026-07-18）

## 结论

仓库默认运行面已完成 v2 收口，本地 PostgreSQL、Redis、MinIO、API、Celery workers、Beat、前端与 Nginx 均健康。活动契约只有 `/api/v2`；生产 readiness 保持 `false`，因为尚未提供真实 Kubernetes、远程 Docker mTLS、LSF 测试队列、生产 OIDC/LLM secrets、备份恢复与切换窗口证据。

## 自动化与契约

- Ruff 全绿；mypy 检查 145 个 Python 源文件通过。
- 后端 69 项测试通过，包括真实 PostgreSQL DAG/outbox 集成测试。
- 总覆盖率 86.18%；identity deps 100%、identity service 96%、compute service 98%、artifact service 97%、migration core 100%，满足整体 85% 和核心 95% 门禁。
- OpenAPI 包含 133 条路径；数据流矩阵覆盖 56 张表；所有写路由有权限元数据，API 路由不得直接执行 SQL。
- 前端 35 个测试文件、108 项测试通过；lint、TypeScript/Vite build、生成 SDK drift、普通 REST transport 边界和浏览器 vertical slice 通过。
- 活动代码扫描未发现 `/api/v1`、旧 submit/sync 路径、SQLite 生产配置、Docker socket 或手写普通 REST。

## 性能、SSE 与故障恢复

- k6：50 VU、60 秒、29,861 次请求，p95 137.84 ms，失败率 0.00%，满足 p95 < 500 ms。
- 压测曾发现 Nginx 上游短连接导致 ephemeral-port 502；增加动态 upstream zone 与 64 个 keepalive 后复验通过。
- 20 条并发 operation SSE 全部返回 200；数据库池 baseline/max/final 均为 0，overflow 为 0。修复点是 SSE 专用认证依赖在建立流前关闭请求 UoW。
- Redis 停止时 readiness 为 503，但 workflow submission 仍返回 202；事件保留在 transactional outbox，Redis 恢复后发布成功且 backlog 自动归零。
- MinIO 停止时 readiness 为 503；artifact complete 返回 `application/problem+json` 的 `upload_object_missing`，upload 状态可靠持久化为 failed，恢复后 readiness 转绿。

## 三次冻结快照迁移演练

冻结源为忽略版本控制的 `backups/v1-retirement/2026-07-17/`。演练 1 在干净数据库执行，演练 2 在同库重复执行，演练 3 在第二个干净数据库重建。

- 源表关键计数：7 projects、3 targets、204 artifacts、208 candidates、10 experiment results、208 research findings。
- 三次 source fingerprint 一致：`cfa10714de81cd7160325a50b37b33e049c9429ac47814f18722c15a9d1fec70`。
- 三次 1,447 个 ID 映射一致，digest 为 `1ffeed435ec3ec474b160dd2be7d7826cbd0a820736b8893604025683e39d538`。
- 三次 210 个文件 checksum 一致，digest 为 `842390959208736659e671230f479531b86b8b8e71d21cef2386c9938dfea467`；0 missing、0 rejection、全部源行可解释。
- 目标库含 214 artifacts：204 个源 artifacts、6 个 PD1 candidate structure/complex fixtures、4 个 script assets。
- 两个 sweet-protein targets 均绑定真实 target-structure artifact；PD1 三个候选绑定 3 个 structure 与 3 个 complex artifact。
- 10 条实验结果均绑定 candidate；200 个生成候选绑定 source job；建立 203 条 artifact lineage edges。
- 两个旧 Intelligence dossier 内嵌 target 被规范化为独立 Target，因此目标库共有 5 个 Target；不是虚构业务记录。
- `migration_runs` 持久化每次演练摘要；机器门禁 `check_migration_rehearsals.py` 通过。

## 数据库、镜像与安全

- Alembic `base → head → base → head` 通过，当前 head 为 `0008_target_artifact_fk`，autogenerate check 无漂移。
- pip-audit 与 npm audit 均为 0 已知漏洞。
- Trivy 对正式文件系统、后端镜像和前端镜像扫描为 0 HIGH/CRITICAL。
- Helm 6 个 Deployment 均采用 non-root、read-only root filesystem、RuntimeDefault seccomp、禁止提权并 drop ALL capabilities；`helm lint` 和 render 通过。
- 后端镜像不再包含本地 `.venv`，大小约 91 MB；API 以 `appuser` 运行，前端以 UID 101 运行。

## 管理员与最终本地运行面

- 管理员账号已创建并通过登录、`/auth/me`、HttpOnly refresh cookie rotation 验证，角色为 admin。
- 凭据只保存在被 Git 忽略且权限为 0600 的 `.env.admin.local`；报告和日志不记录密码。
- 默认 Compose 的 PostgreSQL、Redis、MinIO、API、四类 worker/Beat、前端和 Nginx 均健康；最终浏览器 vertical slice 通过。

## 历史项目运行库恢复（2026-07-18）

- 恢复前已将当前 PostgreSQL 保存为忽略版本控制的 `backups/v1-retirement/2026-07-17/pre-restore-runtime-20260718.dump`；恢复为只读源、幂等且保留已有 v2 管理员和性能验收项目。
- 当前运行库包含 8 个项目（7 个历史项目和 1 个既有性能项目）、5 个规范化 Target、214 个 artifact、208 个 candidate、10 个 experiment result、208 个 research finding、9 个 workflow run、3 个历史 job 和 203 条 lineage edge；迁移报告为 0 missing、0 rejection。
- sweet-protein 项目恢复 2 个可用 Target、206 个 artifact、200 个候选、2 个工作流和完整 research review。Monellin 绑定 PDB 2O9U（链 A/B），Brazzein 绑定 PDB 4HE7（链 A）；原 PDB、链、route、target type 与 legacy target ID 保存在 artifact lineage，项目 readiness 为 ready。
- 浏览器实测项目列表、sweet-protein 研究内容、候选列表和 Molstar 结构均可显示。MinIO 服务端 endpoint 与浏览器 presign endpoint 已分离；预签名请求不再携带 BDA Bearer Token，避免与 S3 签名冲突。

## 尚不可宣称完成的生产门禁

以下必须由生产环境资料和负责人提供后，在真实环境重新验收：Kubernetes namespace/Ingress/DNS/TLS、生产 PostgreSQL/Redis/MinIO、远程 Docker daemon mTLS、LSF SSH/queue、OIDC/LLM/external-source secret refs、OTLP/Prometheus 告警、PITR/MinIO 恢复、真实 Docker 与 LSF 输入到 artifact 闭环、维护窗口和切换/回滚签字。门禁未满足前 Helm 必须保持 `writesEnabled=false`。
