# backend_v2/scripts — 脚本说明

这里放三类东西：CI 门禁脚本、需要真实环境才能跑的验证脚本，以及运维/数据订正脚本。判断标准是它们都不属于 `app/` 的运行时——API 与 worker 不导入这里的任何模块。

`mypy` 与 `ruff` 覆盖本目录（含 `archive/`），所以退役脚本也必须保持可通过类型检查。除特别说明外，所有脚本从仓库根目录以 `PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/<name>.py` 运行。

## 1. CI 门禁（改完代码请先在本地跑）

CI 逐条运行下列脚本，任一失败即阻断合并。它们校验的是"漂移"，不是逻辑 bug——多数红灯是某个再生成或登记步骤被跳过了。

| 脚本 | 把什么钉住 |
|---|---|
| `export_openapi.py` | 导出 `backend_v2/openapi.json`；CI 重新导出后比对，未再生成即失败。前端生成 SDK 也由它驱动 |
| `check_coverage.py` | 总覆盖率 85%，外加 identity、compute、artifacts、research 包与 migration 的 95% 门槛。阈值写在脚本里 |
| `check_flow_matrix.py` | `contracts/v2-flow-matrix.yaml` 必须覆盖每张表，并声明域、生产者、消费者、API 路径与 UI |
| `check_document_inventory.py` | 活跃 Markdown 的唯一 H1、五个元数据字段、无断链、可从 `docs/README.md` 到达；并校验外部数据索引 |
| `check_decision_coverage.py` | `DECISIONS.md` 的每条编号决策要么有时间线记录，要么在决策记录契约里被声明为缺口。契约位于 `private/contracts/decision-records.yaml`，公开仓库没有该目录时按"无可校验"通过 |
| `check_plugin_catalog_drift.py` | `qm-scripts/library/catalog.json` 与 `model_plugins` 注册表一致 |
| `check_plugin_cpu_declarations.py` | 插件声明 `cpus > 1` 时必须附 `cpus_evidence`，说明测量结果或上游线程开关 |
| `check_cluster_claims.py` | 作业脚本对集群的声明必须在运行时自证：声明不用 GPU 的阶段要在 `CUDA_VISIBLE_DEVICES` 存在时退出，`-n`、`span[ptile=]` 与线程数同源，暂存循环要比对文件计数。`--live <job-id>` 可向调度器核对运行中作业实际拿到什么 |

## 2. 上线前与运行时校验

| 脚本 | 用途 |
|---|---|
| `check_production_readiness.py` | 检查生产环境变量集合（kubeconfig、命名空间、镜像仓库、Ingress 主机、TLS secret 等）是否齐备 |
| `check_host_worker.py` | 宿主机 compute worker 的预检，也是 `run-host-worker.sh --check` 调用的那一支 |
| `check_migration_rehearsals.py` | 校验三次确定性迁移演练报告一致，可带 `--expect-verified` 断言条目数 |
| `validate_model_plugins.py` | 同步跑一遍全部模型插件的注册声明校验 |
| `record_plugin_runtime_validation.py` | 记录某个模型插件被观测到能正确运行——或不能。运行证据由此进入注册表 |
| `validate_qm_acceptance_outputs.py` | 对已验收的 2026-08-29 Qiming 快照做 fail-closed 完整性检查 |

## 3. 需要真实外部系统的端到端验证

不在 CI 里跑，需要活的数据库或集群会话。

| 脚本 | 需要什么 |
|---|---|
| `verify_dataflow_e2e.py` | 活数据库；检查输入绑定与节点间数据流 |
| `verify_lsf_e2e.py` | 真实 LSF 会话；经 `LSFAdapter` 提交一个作业并收集产物 |
| `check_lsf_roundtrip.py` | 真实 LSF 会话；走完提交、轮询、收集三步以证明适配器 |

集群会话由使用者在自己的终端里登录后复用，脚本不处理口令，也不自动重连。规则见 [集群操作规则](../../docs/QM_CLUSTER_OPERATION_RULES.md)。

### 宿主机 worker

`run-host-worker.sh` 在宿主机而不是容器里跑 `dispatch` / `poll` / `collect` 三个队列：到集群的路由是宿主机 VPN，容器的网络命名空间继承不到它；`research`、`copilot`、`maintenance` 仍然留在容器里。`--check` 只验证连通性后退出。它读同目录下的 `host-worker.env`，模板是 `host-worker.env.example`（该文件不进 Git 的实值版本）。

## 4. 运维与数据订正

| 脚本 | 用途 | 可重复执行 |
|---|---|---|
| `bootstrap_admin.py` | 创建第一个 v2 管理员（`--username` / `--password`） | 是 |
| `migrate_v1.py` | 把只读的 v1 SQLite 快照幂等迁入 v2（`--sqlite` 必填） | 是 |
| `backfill_candidate_metrics.py` | 把 `candidates.scores` 里的数值搬进可查询的 metric 行 | 是（有测试覆盖） |
| `backfill_review_references.py` | 为综述引用补抓元数据（PubMed、PDB、Crossref、DOI、文章页），`--apply` 才写库 | 是（有测试覆盖） |
| `backfill_workflow_node_plugin_bindings.py` | 把手工建的工作流节点绑定到注册表插件。已绑定的不动，解析不到的保持未绑定并如实报告，只有显式名单里的名字才变 `manual`。支持 `--dry-run` | 是；UI 手建节点会再次产生这种状态 |

`workflow_plugin_binding.py` 是上面那支脚本的共享辅助模块，不单独运行。

## 5. 研究侧工具

| 脚本 | 用途 |
|---|---|
| `build_af3_input.py` | 从 FASTA 生成 AlphaFold 3 的 `fold_input.json` |
| `score_foldability_precheck.py` | 折叠性预检评分：按 JSON spec 给出参考结构与预测目录，整复合物作为单一刚体叠合，同时报告逐链 RMSD，用固定判据给出 pass / topology_only / fail |

`_data_root.py` 解析授权外部研究数据的位置，遵循 `BDA_DATA_ROOT`。读外部研究数据的离线脚本必须经由它，不得硬编码用户目录。

## 6. `archive/`

跑完且不会再跑第二次的一次性脚本移到这里，保留出处而不留在活跃列表里。见 [archive/README.md](archive/README.md)。
