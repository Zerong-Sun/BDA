# BDA Workbench v2

BDA Workbench 是面向蛋白与生物材料设计的可追溯研发工作台。当前唯一活动后端为 `backend_v2/`，唯一 API 契约为 `/api/v2`；业务数据使用 PostgreSQL，任务由 Redis/Celery 调度，权威文件存入 MinIO，前端为 React + TypeScript。

本公开仓库是 BDA 软件的唯一真源。私有 `BDA-demo` 只跟随明确的 BDA
release/tag，并额外保存私有研究数据与部署配置；软件变更从本仓库经单向同步
PR 进入 demo，禁止在 demo 中形成软件分叉。

## PD1 演示包

公开仓库只内置 `pd1-demo-v1`：一个 PD1 项目、12 条公开来源文献元数据、
4 条证据关系，以及三个虚构候选对应的 6 个带 checksum 的 `DEMO` PDB 文件。
全部候选 ID、指标和结构都是预计算合成演示内容，不代表真实模型运行、实验结果、
医疗结论或科研结论。详见[数据卡](examples/migration-fixtures/pd1/DATA_CARD.md)。

## 主要能力

- 组织、项目、多 target 与主目标管理
- 带 ETag 并发控制的工作流编辑、不可变运行快照和异步提交
- 远程 Docker/LSF 计算适配器、transactional outbox、任务状态机、取消与重试
- 两阶段直传、checksum、artifact lineage、候选、实验结果与异步交付包
- Campaign、文献 claim/evidence/relation、Target Intelligence、知识库、Registry 与 Copilot
- 本地/OIDC 身份、组织与项目授权、事务审计、Problem Details、cursor、SSE、指标与链路追踪

## 快速启动

复制 `.env.example` 为 `.env`，替换所有密钥和密码，然后执行：

```bash
docker compose up --build
```

访问 `http://localhost:8080`。健康检查为 `/api/v2/health/live` 与 `/api/v2/health/ready`，MinIO 控制台仅绑定本机 `9003` 端口。

生产 Helm 默认 `BDA_V2_WRITES_ENABLED=false`。数据库/对象存储备份、迁移对账、真实 Docker/LSF 闭环、OIDC/LLM Secret、性能、监控和回滚负责人未全部验收前，不得开启生产写入。

当前 alpha 只承诺可复现 staging 基线，不宣称真实 Kubernetes、LSF、OIDC、
TLS、PITR、告警和恢复验收已经完成。

## 开发检查

```bash
backend_v2/.venv/bin/ruff check backend_v2
backend_v2/.venv/bin/mypy --config-file backend_v2/pyproject.toml backend_v2/app backend_v2/scripts
backend_v2/.venv/bin/pytest backend_v2/tests
npm --prefix frontend test
npm --prefix frontend run build
```

详细说明：

- [后端 v2 说明](docs/BACKEND_V2.md)
- [前端 v2 说明](docs/FRONTEND_V2.md)
- [v2 本地验收证据](docs/V2_LOCAL_ACCEPTANCE.md)
- [后端目录说明](backend_v2/README.md)
- [前端目录说明](frontend/README.md)

历史运行说明仅保存在 `docs/archive/`，用于迁移考古，不可作为部署手册。

## 许可证

软件采用 [Apache-2.0](LICENSE)；PD1 演示数据单独采用
[CC BY 4.0](DATA_LICENSE.md)。贡献和公开数据变更必须遵守
[CONTRIBUTING.md](CONTRIBUTING.md) 与 [DATA_POLICY.md](DATA_POLICY.md)。
