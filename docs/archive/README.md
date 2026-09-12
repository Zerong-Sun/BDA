# 文档与代码归档索引

状态：历史归档

本目录保存已经完成或已被取代的文档。归档件不再是判断当前行为的依据——它们记录"当时是怎么想的、后来怎么收口的"。当前状态一律以 [文档索引](../README.md) 下的活跃文档为准。

含私有路径或研究运行的历史文档不在这里，只保留在私有恢复库，不在公开树重建。

## 归档目录

| 目录 | 内容 | 当前以什么为准 |
|---|---|---|
| [2026-07-frontend-reui-migration/](2026-07-frontend-reui-migration/README.md) | 2026-07-26 前端 shadcn/ReUI 迁移的设计、实施计划与中途评审 | `frontend/src/test/reuiMigrationAudit.test.ts`（活契约）与 [前端 v2 说明](../FRONTEND_V2.md) |

## 已退役的代码

删除的代码由 Git 历史保存。下表记下它们是什么、为什么退役，以及取回的命令——这样"以前是不是有过这个东西"不必靠翻提交记录回答。

取回某个文件：

```bash
git show 9b9ceff3:<路径> > <落点>
```

| 原路径 | 是什么 | 为什么退役 |
|---|---|---|
| `frontend/src/features/workflow/PluginRegistryPanel.tsx` | 展示已注册模型插件的 Frame 面板 | 没有任何路由渲染它。`model_plugins` 在数据流矩阵里声明的 `workflow` UI 落点由 `NodeBuilder` 满足；同时移除了只服务于它的 `workflowExt.pluginRegistry` 文案键 |
| `frontend/src/lib/api/legacy.ts` | `GET /api/v2/legacy-ids/{entity_type}/{legacy_id}` 的薄封装 | 无调用方。接口仍在，需要时可直接用生成 SDK 的 `resolveLegacyIdApiV2LegacyIdsEntityTypeLegacyIdGet` |
| `frontend/src/lib/ui/interactionStates.ts` | hover / selected / disabled 的 Tailwind 片段常量 | 无引用方；实际交互态直接写在组件里 |
| `frontend/src/features/candidates/index.ts` 等 7 个 | 功能域的 re-export barrel（candidates、copilot、experiments、pdb-viewer、research、results、workflow） | 无引用方。保留下来的 barrel（artifacts、guide、jobs、plugins、tour）确有导入方，删掉空转的那批之后，"存在 barrel"才等于"这是该功能域对外的入口" |

## 归档规则

- 已完成的计划、设计与评审 → `docs/archive/<时间>-<主题>/`，附 README 写明退役原因与当前依据，并按原字节迁入、记录 SHA-256。
- 跑完不会再跑的一次性脚本 → `backend_v2/scripts/archive/`，见 [脚本归档](../../backend_v2/scripts/archive/README.md)。
- 没有引用方的代码 → 直接删除并登记在上表。
