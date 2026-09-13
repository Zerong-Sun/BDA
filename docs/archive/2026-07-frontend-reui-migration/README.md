# 2026-07 前端 REUI 迁移记录

状态：历史归档

这三份文件原先位于 `docs/superpowers/`，是 2026-07-26 那次前端 shadcn/ReUI 迁移的设计、实施计划与
中途评审输出。迁移已经完成，文件按原字节迁入本目录，仅改名，不改内容：

| 归档文件 | 原路径 | SHA-256 |
|---|---|---|
| `design.md` | `docs/superpowers/specs/2026-07-26-frontend-reui-migration-design.md` | `1e525302e9fcb840577fdfe68e52b8b1d5691bdaca3663f60228a58d5f196b47` |
| `implementation-plan.md` | `docs/superpowers/plans/2026-07-26-frontend-reui-migration.md` | `076e31ec4bc5b1aec8a514dc32b8dca03ae99839fe39d99b1a796bea714641d3` |
| `task-4-review.md` | `docs/superpowers/plans/Task-4-review.md` | `75bbcae2d4be333168b5810a0895bae449bf07da48ef2a9477400bbca1b4954e` |

## 为什么归档而不是继续当作活跃文档

计划里的约束现在由代码而不是由文档执行。`frontend/src/test/reuiMigrationAudit.test.ts` 是这次迁移的
**活契约**：它断言 `components.json` 的 registry 与 style、`@/*` 路径别名、必须存在的 ReUI 基元与
worked example、UI 控件的大小写文件名、已废弃适配层的缺席，以及 `.dark` 主题变量映射。要知道当前
必须保留哪些前端组件，读那份测试，不要读这里的计划。

`task-4-review.md` 提出的三条 IMPORTANT 已全部修复，且都有回归保护：

- 只读状态未传入工作流变更 —— `frontend/src/app/Workflow.tsx` 现在向 `WorkflowInspector` 传
  `readOnly`，由 `frontend/src/features/workflow/WorkflowInspector.readOnly.test.tsx` 守住。
- 脚本上传暴露原生 file input —— `frontend/src/features/workflow/ScriptAssetManager.tsx` 的
  `type="file"` 已置于 `className="hidden"`，由本地化的样式触发器代理。
- 作业时间线不随异步日志刷新 —— `frontend/src/features/jobs/JobStatusDrawer.tsx` 的 `Timeline`
  已改为受控 `value`，原因写在该文件的注释里。

## 当前状态以什么为准

前端架构与约定见 [前端 v2 说明](../../FRONTEND_V2.md)；仓库各部分的分工见
[工作区结构说明](../../WORKSPACE_MAP.md)。本目录只用于历史追溯。
