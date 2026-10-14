# 历史文档与退役代码

本目录用于追溯已完成或被替代的方案、设计与验收。当前行为见[文档导航](../README.md)，未完成工作见[规划区](../plans/README.md)。含私有路径或研究运行的旧记录只保留在私有恢复归档。

## 归档批次

| 批次 | 内容与校验 |
| --- | --- |
| [2026-09-30](2026-09-30/README.md) | 研究室、蛋白质能力、专利与前端方案，共 5 份原件；[清单与 SHA-256](2026-09-30/manifest.json)。 |
| [2026-09-13](2026-09-13/COPILOT_CAPABILITY_PLAN_V2.md) | 新增 bots 后的 Copilot 能力规划版本；[来源提交与 SHA-256](2026-09-13/manifest.json)。不覆盖 9 月 7 日版本。 |
| 2026-09-07 | 9 份被替代或阶段性文档，详见下表与[清单](2026-09-07/manifest.json)。每份归档提示之后保留原始字节。 |
| [2026-07 前端迁移](2026-07-frontend-reui-migration/README.md) | shadcn/ReUI 迁移设计、计划与中途评审；当前规则见[前端说明](../FRONTEND_V2.md)及 `frontend/src/test/reuiMigrationAudit.test.ts`。 |

### 2026-09-07 文档去向

| 历史文档 | 归档原因 | 替代入口 |
| --- | --- | --- |
| [COPILOT_CAPABILITY_PLAN_V2.md](2026-09-07/copilot/COPILOT_CAPABILITY_PLAN_V2.md) | 能力规划缺少完整入口/API映射及新增实验服务 | [当前说明](../COPILOT_SERVICE_GUIDE.md) |
| [COPILOT_DEEPSEEK_配置指南.md](2026-09-07/copilot/COPILOT_DEEPSEEK_配置指南.md) | 密钥、数据库与配置变量说明过时 | [当前说明](../COPILOT_SERVICE_GUIDE.md) |
| [COPILOT_VALIDATION_REPORT.md](2026-09-07/copilot/COPILOT_VALIDATION_REPORT.md) | 仅保留当时验证证据，不作为当前能力承诺 | [当前说明](../COPILOT_SERVICE_GUIDE.md) |
| [RESEARCH_INTERFACE_USAGE_GUIDE.md](2026-09-07/research/RESEARCH_INTERFACE_USAGE_GUIDE.md) | 旧五页签与当前四分区不符 | [当前说明](../GUIDED_PLATFORM_WORKFLOW.md) |
| [BDA_RESEARCH_WORKSPACE_AND_BYOK.md](2026-09-07/research/BDA_RESEARCH_WORKSPACE_AND_BYOK.md) | 研究包与模型配置职责拆分，移除重复操作说明 | [当前说明](../RESEARCH_PACKAGES.md) |
| [2026-07-26-frontend-reui-migration.md](2026-09-07/frontend/2026-07-26-frontend-reui-migration.md) | 阶段性界面迁移实施计划，当前规则由架构文档与自动检查维护 | [当前说明](../FRONTEND_V2.md) |
| [Task-4-review.md](2026-09-07/frontend/Task-4-review.md) | 旧行号和阶段审查意见，仅供历史追溯 | [当前说明](../FRONTEND_V2.md) |
| [2026-07-26-frontend-reui-migration-design.md](2026-09-07/frontend/2026-07-26-frontend-reui-migration-design.md) | 阶段性迁移设计，不代表当前页面入口清单 | [当前说明](../FRONTEND_V2.md) |
| [V2_LOCAL_ACCEPTANCE.md](2026-09-07/validation/V2_LOCAL_ACCEPTANCE.md) | 旧测试数量与迁移head仅属于历史验收批次 | [当前说明](../STAGING_RELEASE_AND_RECOVERY.md) |

## 已退役代码

以下文件由 Git 历史保存。恢复前先检查当前调用方和接口；取回命令为 `git show 9b9ceff3:<原路径> > <恢复路径>`。

| 原路径 | 是什么 | 为什么退役 |
|---|---|---|
| `frontend/src/features/workflow/PluginRegistryPanel.tsx` | 展示已注册模型插件的 Frame 面板 | 没有任何路由渲染它。`model_plugins` 在数据流矩阵里声明的 `workflow` UI 落点由 `NodeBuilder` 满足；同时移除了只服务于它的 `workflowExt.pluginRegistry` 文案键 |
| `frontend/src/lib/api/legacy.ts` | `GET /api/v2/legacy-ids/{entity_type}/{legacy_id}` 的薄封装 | 无调用方。接口仍在，需要时可直接用生成 SDK 的 `resolveLegacyIdApiV2LegacyIdsEntityTypeLegacyIdGet` |
| `frontend/src/lib/ui/interactionStates.ts` | hover / selected / disabled 的 Tailwind 片段常量 | 无引用方；实际交互态直接写在组件里 |
| `frontend/src/features/candidates/index.ts` 等 7 个 | 功能域的 re-export barrel（candidates、copilot、experiments、pdb-viewer、research、results、workflow） | 无引用方。保留下来的 barrel（artifacts、guide、jobs、plugins、tour）确有导入方，删掉空转的那批之后，"存在 barrel"才等于"这是该功能域对外的入口" |

## 归档规则

- 完成或被替代的文档按日期归档，保留原始字节、SHA-256、原路径及当前入口；同步更新活跃引用。
- 已归档原文的相对链接、行号、命令和测试数量属于当时版本，不保证仍适用。恢复前校验清单并审查与现行文件的差异。
- 一次性退役脚本见[脚本归档](../../backend_v2/scripts/archive/README.md)；移除无调用方代码时登记原路径和原因。
