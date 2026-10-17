# 近期代码更新与集成状态（2026-10-17）

状态：活跃

最后核验：2026-10-17（Asia/Shanghai；Git 提交、分支包含关系、PR 状态与本地验收记录）

权威范围：2026-10-16 至 2026-10-17 的软件更新导航、集成边界与验证范围；这是开发分支快照，不是 main 发布公告。

数据来源：`c4a71056..2a34d932` 的提交和测试、版本化源码，以及 [PR #75](https://github.com/Zerong-Sun/BDA/pull/75) 的只读状态。

替代关系：补充 [RC3 发布说明](RELEASE_2_6_RC3.md)与[工作区结构说明](WORKSPACE_MAP.md)，不取代正式发布、CI 或外部审阅记录。

## 当前基线

| 项目 | 核验结果 |
|---|---|
| 集成分支 | `codex/workflow-settings-20261016` |
| 本轮软件验收基线 | `2a34d932f0607463f294af8dbf9d77c08df6e151` |
| 相对 RC3 准备提交 `c4a71056` | 34 个提交，215 个文件发生变化；含生成的 API 契约文件 |
| 远端 main 快照 | `d615f120`；上述软件基线领先 103 个提交、落后 0 个提交 |
| 合入状态 | PR #75 为 OPEN / REVIEW_REQUIRED；尚未合入 main |
| 部署与发布区别 | 软件基线已在本地私有工作台验收；这不代表 main 或公开发布已更新 |

本文件及其索引整理会产生后续文档提交。软件部署基线仍以上表为准；比较最近软件增量用 `c4a71056..2a34d932`，比较整个待合入分支用 `main...HEAD`，两者范围不同。

## 更新按功能查找

| 功能 | 当前行为 | 代表提交 | 代码入口 |
|---|---|---|---|
| 任务交付与最终复核 | 分字段控制上下文和报告压缩，保留必要证据、未通过复核与部分交付状态；任务成功不自动等于科学验证通过 | `81f23cd1`、`3e3f754b`、`ed49f702`、`7e519671` | [交付上下文](../backend_v2/app/copilot/delivery_context.py)、[研究代理](../backend_v2/app/copilot/research_agent.py)、[交付显示](../frontend/src/features/copilot/deliveryDisplay.ts) |
| 模型调用控制 | 任务调用前持久预留、轮数与费用硬限制、重复请求约束；限制后的继续对话和新建对话保留独立入口，界面不展示计费 | `b4c82088`、`d2bdb7c9` | [调用守卫](../backend_v2/app/copilot/call_guard.py)、[对话上下文](../backend_v2/app/copilot/chat_context.py) |
| 项目结果与报告 | 优先展示保存的结果、报告和复核；结构化目标缺失时保留原报告和任务书来源；项目条目索引不冒充结果报告或科研进展 | `93f1c7cf`、`cf5df6f1`、`7e281983`、`ef6d12cc` | [研究总览](../frontend/src/features/research/ProjectResearchOverview.tsx)、[报告选择](../frontend/src/lib/api/researchBriefs.ts) |
| 项目内研究团队 | 聊天按项目保存；默认最新有效答复、待处理事项与报告入口；旧讨论、归档记录和重复过程按需展开 | `a15e6e3c`、`3d5855ed`、`bd9e5589` | [研究团队](../frontend/src/features/copilot/Room.tsx)、[焦点选择](../frontend/src/features/copilot/roomFocus.ts)、[服务端事件流](../backend_v2/app/copilot/room.py) |
| 最新答复排版 | 优先结论、复核/关键限制及下一步；工具回读、空表、代码块、节点明细默认折叠，参考资料继续折叠；保留原文和引用编号 | `5fec1df2`、`c7f67d0f`、`2a34d932` | [答复展示规则](../frontend/src/features/copilot/answerPresentation.ts)、[最新答复组件](../frontend/src/features/copilot/LatestAnswer.tsx) |
| Bot 工作记录 | 每个项目与 Bot 的 Markdown 记录可查、可下载；已归档答复不进入当前记录检索，完整 MD 保留其原文及归档标记 | `afcd1b91`、`cdf7eb1c`、`b3fa0e02` | [工作记录服务](../backend_v2/app/copilot/records.py)、[工作记录页面](../frontend/src/features/copilot/BotRecords.tsx) |
| 工作流与模型入口 | 模型、脚本从主导航可达；历史卡片布局稳定；缺失的门控来源明确显示，默认参数不冒充论文支持 | `577d9ea6`、`ce147b0d`、`13f81f88`、`f336ca1e` | [工作流门控](WORKFLOW_GATES.md)、[导航契约](NAVIGATION_WORKSPACE_CONTRACT.md) |

## 分支包含关系

核验时，本地公开仓库所有分支的**已提交历史**均包含在上述集成基线中，包括以下近期入口：

| 分支 | 已核验提交 | 处理状态 |
|---|---|---|
| `codex/platform-gates-bot-records` | `c96d2b39` | 已包含，无需重复 cherry-pick |
| `codex/pd1-bot-validation` | `c4a71056` | RC3 准备基线已包含 |
| `codex/design-learning-loop` | `c7f67d0f` | 已提交历史已包含；其工作区另有未提交变更，需独立审阅 |
| `codex/public-view-private-accounts` | `b3aced08` | 已提交历史已包含；其工作区另有未提交变更，需独立审阅 |
| `codex/workflow-settings-20261016` | `2a34d932` | 当前软件集成与验收基线 |

包含关系不表示工作区可以删除，也不包含未提交或未跟踪文件。本轮只建立清单与导航，没有清理其他工作区、改写历史或重置分支。私有覆盖仓库独立管理；其研究资料和恢复清单不进入公开软件 Git。

## 验证记录与边界

以下是各次修改对应的本地验证，不等于整条分支通过完整 CI：

- 最新答复排版：38 项针对性测试、相关 ESLint、TypeScript 构建与 bundle gate 通过；实际检查报告入口、原文展开、引用折叠和摘要/下一步顺序。
- 项目研究总览及聊天焦点：47 项针对性前端测试通过；Bot 工作记录另有 2 项前端、23 项后端相关测试通过。
- 项目范围核验覆盖群聊、任务、交接、决策、讨论与可解析的项目引用；项目字段归属正确不能代替正文语义复核。
- 私有运行服务的版本与健康检查通过。最近的显示、归档与仓库整理使用已有数据及本地测试，没有新增模型调用。
- 未完成的科学复核继续显示未完成；归档、报告接受状态、任务成功、自动复核和人工批准是不同状态。

原始浏览器截图、研究记录、数据库回执、清理恢复清单及环境配置继续存于授权的私有数据区，公开仓库只保留软件行为、验证范围和可复现检查入口。

本轮后续专项验证与缺陷修复见[六项验证及修复清单](SIX_DIMENSION_REVIEW_2026-10-17.md)，其范围和测试结果独立列出。

## 后续维护顺序

1. 继续开发时以实际 Git 分支、工作区状态和部署 revision 为准；不把本地旧 main 当作最新部署。
2. 未提交变更单独整理与审阅，不直接混入本批软件基线。
3. 恢复合入工作后，先取得 PR 必要的外部审阅与该次提交的完整 CI 结果，再正常合入；不绕过保护规则。
4. 部署前按[发布与恢复流程](STAGING_RELEASE_AND_RECOVERY.md)核对迁移、配置和回滚版本；文档整理本身无需重启运行服务。

文档入口检查可在仓库根运行：

```bash
PYTHONPATH=. python backend_v2/scripts/check_document_inventory.py
python scripts/check_public_data.py
git diff --check
```

解释器选择与完整代码验证命令见 [CLAUDE.md](../CLAUDE.md)。
