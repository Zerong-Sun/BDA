# 可核验的研究交付包

状态：活跃

最后核验：2026-10-11（实现与单元测试；不代表外部存储部署验收）

权威范围：Results 页交付 ZIP 的内容、冻结语义与完整性边界。

数据来源：[交付内核](../backend_v2/app/delivery/bundle.py)、[异步任务](../backend_v2/app/delivery/tasks.py)、[回归测试](../backend_v2/tests/test_delivery_bundle.py)。

替代关系：取代原先仅含清单的交付实现；不取代数据库备份和研究包导入协议。

## 创建与读取

Results 页的“创建研究交付包”在项目写权限下明确发起。页面默认选择当前项目全部候选，并包含实验结果；API 可限制候选 UUID。创建时冻结业务记录及源文件的版本、大小和 SHA-256，任务在现有 outbox/Celery 流程中执行。页面显示 pending、available 或 failed，待处理时轮询，失败显示原因；读取最新包按创建时间排序。

PostgreSQL 冻结使用独立的 `REPEATABLE READ READ ONLY` 事务，复制调用方当前数据库角色、`search_path` 以及请求/worker 的 RLS 上下文。候选、测量和审核状态来自同一数据库快照，只包含已提交数据；并发 QC 撤销不会造成旧测量和新拒绝状态混杂。外层包写入事务不会被自动提交、回滚或 flush。普通调用若有待提交对象、已写入或已加行锁的事务，会收到 `delivery_uncommitted_changes`，应先提交项目改动，再通过独立请求创建交付。

唯一内部例外是旧版待执行包：worker 只锁定包记录、尚未写项目数据时，可显式启用 `allow_locked_transaction`，仍只读取已提交项目记录。此参数不是公开 API；调用方不得先写项目数据。SQLite 单元测试使用传入事务，不代表 PostgreSQL 并发保证。真实双连接 QC 交错、RLS 身份/角色继承、外层事务保留和旧包重试由 `test_delivery_postgres.py` 覆盖。

## ZIP 内容

| 文件 | 内容 |
| --- | --- |
| `candidates.json` | 选定候选的标识、版本、分数、属性和结构引用 |
| `candidate-metrics.json` | 指标值、单位、方法、evidence_kind 和作业/实验来源 |
| `experiment-results.json` | 选定范围内实验记录、原始文件引用、结果元数据和版本 |
| `artifacts/<uuid>/<filename>` | 候选结构及所选实验结果引用的实际源文件 |
| `manifest.json` | 冻结时间、记录数、选项、各数据文件 SHA-256 和限制 |
| `ro-crate-metadata.json` | 按 RO-Crate 1.1 表达数据包和文件关系的 JSON-LD |

指标原有的预测/实测类型继续保留，导出不会将其升级为科学结论。选择不导出实验记录时，候选指标仍按其 evidence_kind 导出，不会偷偷改写为预测。引用文件均验证数据库记录和实际字节；任一文件消失、变化或校验失败，任务失败，不发布缺文件的成功包。

## 边界与恢复

- 每类记录最多 10,000 条，总未压缩内容最多 100 MiB；超出时缩小选择。当前构建使用内存，适合有界项目交付，大规模流式导出是后续工作。
- 仅收集上述已引用文件，不声称导出所有项目资料、模型权重、完整数据库或可重放计算环境。
- 不导出存储 object key、凭据或预签名 URL。文件命名清洗且前置 UUID，防止路径穿越与重名覆盖。
- 用户自填属性仍属于项目数据；拥有导出权限不意味着源文献或其他第三方数据具有再分发许可。清单明确不授予再分发许可。
- 同一包的源字节经过完整校验后才标记 available；派生制品保存来源血缘。重试不会把半成品标记成功。旧版已排队、尚无冻结快照的任务在首次新版构建时冻结，并以该时间为准。
- 可重复构建固定 ZIP 时间戳和文件内容，清单保存冻结时间；不对所有外部解压器、RO-Crate 验证器或长期归档格式作未经测试的兼容承诺。

格式依据：[RO-Crate 1.1 root entity](https://www.researchobject.org/ro-crate/specification/1.1/root-data-entity.html)、[data entities](https://www.researchobject.org/ro-crate/specification/1.1/data-entities.html)。当前轻量实现直接输出格式，没有新增 ro-crate-py、MLflow 或 OpenLineage 服务。
