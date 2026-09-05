# BDA v2 本地 staging 验收

状态：活跃

最后核验：2026-08-31（Asia/Shanghai）

权威范围：公开 alpha 候选版本的本地自动化、迁移、公开数据和运行时验收。

数据来源：当前公开分支的代码、CI 配置、测试输出、PD1 manifest 与本地容器健康检查。

替代关系：取代包含私有项目行数、研究结果、用户路径或旧迁移 head 的历史验收记录。

## 1. 验收问题

本验收回答的是：公开仓库能否在不依赖私有研究数据的条件下完成构建、测试、数据库迁移和 PD1 演示。它不回答真实蛋白模型是否有效，也不把本地 Docker 环境等同于生产 Kubernetes、LSF 或身份基础设施。

## 2. 自动化结果

本轮 alpha 候选在相同代码 HEAD 上取得以下结果：

| 检查 | 结果 | 判定 |
| --- | ---: | --- |
| 后端 pytest（含 PostgreSQL） | 710 passed | 通过 |
| 后端总覆盖率 | 85.25% | 通过 85% 门禁 |
| 研究包分支覆盖率 | 96.57% | 通过 95% 门禁 |
| 前端单元测试 | 451 passed | 通过 |
| 浏览器纵向矩阵 | 112/112 | 通过 |
| Ruff、Mypy、OpenAPI drift | 0 error | 通过 |
| npm audit、pip-audit、Trivy | 0 vulnerability/secret/misconfiguration finding | 通过 |
| Helm lint、文档清单、公开数据门 | 0 error | 通过 |

这些数字用于固定当前候选版本的回归基线；后续增删测试时，应同时记录测试语义和覆盖范围，不能只追求数量不下降。

## 3. 数据库迁移

本轮验收时迁移链从 base 单线前进至 `0051_worker_project_rls`。此后 `0052_decision_tree_fields` 与 `0053_decision_tree_drafts` 于 2026-09-02 落地，head 已是 `0053_decision_tree_drafts`；下列五项是对 0051 head 做的，**尚未在 0053 上重跑**，本文不代为宣称。本轮在独立的临时 PostgreSQL 17 实例中实际完成：

1. 空 PostgreSQL 执行 `base → head`；
2. 执行 `head → base → head` round trip；
3. 运行 `alembic check`，确认 ORM metadata 与迁移无漂移；
4. 启用 PostgreSQL 测试，验证项目权限、RLS 和 worker 项目上下文拒绝越权访问；
5. 在 head schema 上检查插件目录与数据库部署记录一致。

从正式 demo 基线 `0045_foldseek_threads` 恢复克隆并升级到 head 仍属于下一阶段 staging 数据库任务，本轮没有迁移或改写现有 demo 数据库。

生产恢复不依赖线上 downgrade。正式迁移前必须创建 PostgreSQL custom-format 备份和 MinIO version manifest；失败时回滚应用并从备份恢复。

## 4. 公开 PD1 数据

公开数据门确认仓库只有一个研究包 `pd1-demo-v1`，且该包只包含一个 PD1 项目。12 条文献元数据、4 条证据关系和 4 个公开结构引用形成闭合引用；3 个虚构候选的 6 个 `DEMO` PDB fixture 与 manifest SHA-256 一致。

测试不会从外部私有数据根补充 PD1 内容。缺少任何私有数据副本时，公开数据门、后端测试和前端演示仍必须可运行。

## 5. 本地运行面

Docker Compose 启动 PostgreSQL、Redis、MinIO、API、Celery worker、Beat、前端和 Nginx。验收要求：

- `/api/v2/health/live` 返回存活；
- `/api/v2/health/ready` 检查数据库 revision、Redis、MinIO 和必要 worker heartbeat；
- worker build revision 与 schema revision 和 API 一致；
- writes-disabled staging 下，写请求按契约拒绝，读取与健康检查保持可用；
- Redis 或 MinIO 不可用时 readiness 转为失败，服务恢复后重新就绪。

当前 demo 运行面保持 `BDA_V2_WRITES_ENABLED=false`。该状态是安全门禁，不应为了通过 smoke test 而临时绕过。

## 6. 尚未完成的生产验收

以下证据不属于公开 alpha 的已完成范围：真实 Kubernetes namespace/Ingress/DNS/TLS、生产 OIDC 与 secret refs、真实 LSF 队列端到端提交、PostgreSQL PITR、MinIO version restore、生产告警、故障注入和回滚签字。

上述项目全部完成前，production deploy job 与写入开关必须保持关闭；文档和界面也不得使用“production-ready”或等价表述。
