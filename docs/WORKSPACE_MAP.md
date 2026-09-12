# BDA 工作区结构说明

状态：活跃

最后核验：2026-09-12（Asia/Shanghai；逐目录核验目录分工、权威文档与门禁映射）

权威范围：公开仓库各部分的职责边界、权威文档入口、对应的 CI 门禁，以及新增内容与退役内容的落点。各部分内部的设计细节以其专属文档为准。

数据来源：仓库内版本化代码、配置、`.github/workflows/ci.yml` 与本文列明的文件。

替代关系：不取代根目录 `README.md` 的平台总览，也不取代 [文档索引](README.md)；本文只回答"这块是什么、归谁管、改完之后哪道门禁会响"。

## 1. 顶层目录

| 路径 | 是什么 | 权威文档 | 改动后会响的门禁 |
|---|---|---|---|
| `backend_v2/` | 生产后端：FastAPI 应用、Celery worker、SQLAlchemy 模型、Alembic 迁移、运维脚本、镜像与 Helm chart | [后端 v2 说明](BACKEND_V2.md) | ruff、mypy、pytest + 覆盖率、alembic check/downgrade、OpenAPI 漂移 |
| `frontend/` | React 19 + Vite 前端，唯一的 Web 界面 | [前端 v2 说明](FRONTEND_V2.md) | eslint、vitest、tsc + vite build、bundle 体积、生成类型漂移、传输边界 grep |
| `qm-scripts/` | Qiming 集群（IBM Spectrum LSF）作业库与插件运行手册 | [集群操作规则](QM_CLUSTER_OPERATION_RULES.md)、[插件接口](PLUGIN_INTERFACE.md) | 插件目录漂移、CPU 槽位声明、集群声明校验 |
| `contracts/` | 跨层契约。当前只有 `v2-flow-matrix.yaml`：每张表的域、生产者、消费者、API 路径与 UI 落点 | 本文 §5 | 数据流矩阵校验 |
| `docs/` | 公开文档树。活跃文档必须可从 `docs/README.md` 到达 | [文档索引](README.md) | 文档清单与链接校验 |
| `examples/` | 公开可分发的示例数据。当前只有 PD1 迁移夹具 | [PD1 数据卡](../examples/migration-fixtures/pd1/DATA_CARD.md) | 公开数据门禁（`scripts/check_public_data.py`） |
| `monitoring/` | Prometheus 抓取配置、告警规则与 Grafana 预置面板 | [后端 v2 说明 §10](BACKEND_V2.md) | 无专属门禁 |
| `nginx/` | 本地 compose 栈的反向代理与前端静态站点配置 | 本文 §6 | 已退役运行时契约 grep |
| `scripts/` | 仓库级（非后端）脚本。当前只有 `check_public_data.py` | 本文 §5 | 公开数据门禁工作流 |
| `tools/` | 辅助工具收纳区，判据是"平台不依赖它也能跑"；当前无独立脚本 | [tools/README.md](../tools/README.md) | 无 |
| `.github/` | CI、CodeQL、公开数据门禁、staging 发布工作流与 Dependabot | 本文 §5 | 工作流自身 |
| `docker-compose*.yml` | 本地栈（主栈 / dev 覆盖 / host worker 覆盖） | 根 `README.md` §7 | `test_compose_startup_contract.py`、已退役运行时契约 grep |

私有研究数据、模型权重、数据库导出与运行归档不在本仓库，见 [数据目录](DATA_CATALOG.md) 与 `DATA_POLICY.md`。

## 2. `backend_v2/` 内部分工

| 子目录 | 职责 |
|---|---|
| `app/` | 22 个领域包，每个遵循 `api.py` / `service.py` / `repository.py` / `models.py` + `schemas.py` 四文件约定 |
| `app/core/` | 配置、数据库、Celery、problem+json 错误、限流等跨域基础设施，本身不是领域 |
| `app/migration/` | v1 迁移原语，不挂载路由 |
| `alembic/` | 迁移脚本；元数据来自 `app/all_models.py` |
| `scripts/` | 运维、门禁与一次性脚本，见 [脚本说明](../backend_v2/scripts/README.md) |
| `tests/` | pytest；没有 `conftest.py`，用例自建夹具 |
| `helm/`、`deploy/`、`Dockerfile` | 部署面：chart、PostgreSQL 角色 SQL、运行镜像 |
| `plugin_manifests/` | 随镜像发布的插件清单目录，由 `BDA_V2_PLUGIN_MANIFEST_DIR` 指向、经注册表 API 列出；测试要求它们校验和固定且不含站点专有信息 |
| `docs/` | 后端近身文档：[architecture](../backend_v2/docs/architecture.md)、[operations](../backend_v2/docs/operations.md)、[testing](../backend_v2/docs/testing.md)。它们不在 `docs/` 门禁范围内，入口在 `backend_v2/README.md` |

### 注册一个新领域

`app/module_registry.py` 里的 `MODULES` 是领域的登记处。`all_models.py`（Alembic 读元数据）、`main.py`（挂载路由）与 `core/celery_app.py`（`imports=TASK_MODULES`）都从它读取，所以新增领域只改这一处，外加在 `contracts/v2-flow-matrix.yaml` 为新表补一行。

唯一的例外是 `main.py` 末尾直接挂载的 `/mcp` 子应用：它不是 `APIRouter`，`routers()` 也只接受 `APIRouter`；而且它整个表面只有一个 `POST /mcp`，路径前缀式的生产写入门禁无法逐工具判断，所以写入检查由 `copilot.mcp._authorize_write` 在知道执行模式的地方重建。签发与吊销 grant 的 REST 路由仍是普通 copilot 路由，照常走注册表。理由写在 `main.py` 那段注释里。

`ModuleDescriptor` 的 `permission_actions` 与 `metric_prefixes` 目前**没有任何读取方**，是声明性清单；真正生效的是 `api.py` 上的 `x-permission` 声明与指标的实际命名。改这两个字段不会改变运行时行为。

## 3. `frontend/` 内部分工

| 子目录 | 职责 |
|---|---|
| `src/app/` | 路由级页面（Workflow、Candidates、Results、Research、Autopilot、Timeline、Lab、Experiments、Guide、FAQ、Login） |
| `src/features/` | 按功能域组织的组件与 hook；页面组合它们 |
| `src/components/ui/` | shadcn 注册表基元 |
| `src/components/reui/` | ReUI 注册表基元（Frame、Data Grid、Filters、Stepper、Timeline、Badge、Alert、Autocomplete、Sortable、Icon Tile/Stack） |
| `src/components/examples/` | ReUI 官方 worked example，作为改造参照保留 |
| `src/lib/` | API 客户端、生成 SDK、Zod 边界校验、i18n、主题 |
| `src/vendor/` | 仅 CJS 包的 ESM 垫片，由 `vite.config.ts` 的 `resolve.alias` 指向 |
| `src/test/` | 跨切面测试，含迁移审计 |
| `scripts/` | 构建体积检查与浏览器纵切冒烟 |

### 看起来没人引用但不能删的前端文件

`src/test/reuiMigrationAudit.test.ts` 是 2026-07 那次 shadcn/ReUI 迁移留下的**活契约**。它断言下列文件必须存在：`components.json` 指定的 registry 与 style、`@/*` 路径别名、一组 ReUI 基元、七个 worked example（`components/examples/c-*.tsx`）、一组 UI 控件及其大小写文件名，并断言已废弃适配层的缺席。删除其中任何一个，测试会失败——这是设计意图，不是漏网。判断某个前端文件能否删除，先读那份测试，不要只看 import 图。

`src/components/reui/data-grid/` 下的 `data-grid-column-filter`、`data-grid-column-visibility`、`data-grid-table-dnd`、`data-grid-table-dnd-rows`、`data-grid-table-virtual` 当前没有引用方，它们是随 Data Grid 一起装入的上游注册表文件，按整套保留，便于重新运行注册表 CLI 时不产生差异。

`src/lib/api/generated/` 由 `npm run generate:api` 从 `backend_v2/openapi.json` 生成，不手改。

## 4. `qm-scripts/`

`library/` 是作业定义库：`qm_job.py` 提供 `params` / `validate` / `render` 三个子命令，作业以 JSON 配置描述，不手写批处理脚本；`catalog.json` 与后端 `model_plugins` 注册表必须一致，由插件目录漂移门禁校验。`plugins/` 下每个模型一份运行手册，由 `generate_docs.py` 从 `registry.json` 生成。

集群是 LSF，用 `bsub` 而不是 `sbatch`；登录节点只做查看、轻量暂存、传输与提交。`-n`、`span[ptile=]` 与工具线程数必须同源同值，声明不需要 GPU 的阶段必须在运行时自证。完整规则见 [集群操作规则](QM_CLUSTER_OPERATION_RULES.md)。

## 5. 契约面与门禁

这些文件本身就是契约，改动会被 CI 对比：

| 文件 | 由什么生成 / 校验 | 门禁脚本 |
|---|---|---|
| `backend_v2/openapi.json` | `backend_v2/scripts/export_openapi.py` | CI 重新导出后 `git diff --exit-code` |
| `frontend/src/lib/api/generated/` | `npm --prefix frontend run generate:api` | 同上 |
| `contracts/v2-flow-matrix.yaml` | 手工维护，新表必须补行 | `check_flow_matrix.py` |
| `qm-scripts/library/catalog.json` | `build_catalog.py` | `check_plugin_catalog_drift.py` |
| `qm-scripts/plugins/*/README.md` | `generate_docs.py` | 插件文档测试 |
| `docs/**/*.md` | 手工维护 | `check_document_inventory.py` |
| 作业脚本中的集群声明 | 手工维护 | `check_cluster_claims.py` |
| 插件槽位声明 | 手工维护 | `check_plugin_cpu_declarations.py` |

CI 还有两道 grep，扫描范围是**运行时代码与部署配置**，不含 `docs/`：

- 已退役的运行时契约——`/api/v1`、`submit-to-compute`、`/jobs/.*/sync`、`experiment-results/upload`、`copilot/literature` 在 `frontend/src`、`backend_v2/app`、`docker-compose.yml`、`nginx/`、`backend_v2/helm` 中命中即失败；`docker.sock` 与 `sqlite:///` 在后四者中命中即失败。
- 前端传输边界——`frontend/src` 里禁止出现 `apiRequest`，裸 `fetch(` 只允许出现在白名单文件（transport、SSE、预签名对象传输、结构 URL 加载与测试）中。

每道门禁都有可本地运行的脚本或命令，见 `CLAUDE.md` 与 [脚本说明](../backend_v2/scripts/README.md)。

## 6. 本地栈

`docker-compose.yml` 起 PostgreSQL、PgBouncer、Redis、MinIO、API、三类 worker、Beat、前端与 nginx。`docker-compose.dev.yml` 与 `docker-compose.host-worker.yml` 是覆盖层，单独读主文件会得到与实际运行不符的结论——以容器上的 `config_files` 标签为准。端口与健康检查见根 `README.md` §7。

## 7. 文档在哪儿写

- **面向使用者、需要被检索到的**：写进 `docs/`，并在 [docs/README.md](README.md) 加索引项。活跃文档必须有唯一 H1 和五个元数据字段（状态、最后核验、权威范围、数据来源、替代关系），且不能有断链——否则文档清单门禁失败。
- **贴着代码、给改这块代码的人看的**：写成该目录下的 `README.md`（如 `backend_v2/scripts/README.md`、`tools/README.md`），并从上一级 README 链过去。
- **面向 agent 的仓库操作约定**：写进根 `CLAUDE.md`。
- **研究记录、运行证据、私有数据清单**：不写进本仓库，见 [数据目录](DATA_CATALOG.md)。

## 8. 退役的东西放哪儿

| 类型 | 去向 |
|---|---|
| 已完成的计划、设计、评审文档 | `docs/archive/<时间>-<主题>/`，附 README 说明为什么退役、当前以什么为准，见 [归档索引](archive/README.md) |
| 已经跑完、不会再跑第二次的一次性脚本 | `backend_v2/scripts/archive/`，在 [脚本说明](../backend_v2/scripts/README.md) 记明它做过什么 |
| 没有引用方的代码 | 直接删除，并在 [归档索引](archive/README.md) 登记路径与恢复命令；Git 历史是它的归档 |
| 含私有路径或研究运行的历史文档 | 只保留在私有恢复库，不在公开树重建 |
