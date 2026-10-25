# 研究团队与结果展示六项验证及修复清单

状态：活跃

最后核验：2026-10-18（Asia/Shanghai；验证始于 10 月 17 日）

权威范围：近期研究团队、答复折叠、项目结果和 Bot 记录改动的专项验证；不代表整个仓库或科学结论已获得最终批准。

数据来源：本次提交的回归用例、构建、静态检查和真实 Chromium 验收；浏览器自动化使用本地确定性接口夹具，不调用模型。

替代关系：补充[近期更新记录](RECENT_UPDATES_2026-10-17.md)，不替代 CI、外部代码审阅或真实科研实验。

## 六个验证方面

| 方面 | 核查范围 | 结果与边界 |
|---|---|---|
| 需求完整性 | 最新结论、报告、复核、下一步；旧过程和参考资料默认折叠；历史可追溯 | 保留报告/复核入口与原文，补上空 Markdown 表格折叠；已完成项目从已保存报告及任务书读取目标和问题，不伪造结构化完成记录 |
| 逻辑正确性 | 段落重排、日志识别、归档判定、项目和 Bot 归属 | 修复正文被日志规则吞掉、嵌套标题脱离结论、归档真假值不一致；既有项目隔离与授权测试通过 |
| 边界情况 | 长短代码围栏、无空行正文、空表/有数据表、异常 JSON、归档 pending 消息 | 新增先失败后通过的回归用例；不会把“无记录”转成“成功” |
| 代码质量 | 表示层与原始数据分离、归档元数据规范化、类型检查和 lint | 抽出围栏状态判断和归档规范化；展示层不修改消息，不产生模型调用；无数据库/API 契约变更 |
| 测试覆盖 | 前端组件、后端持久化和检索、上下文/预算、工作流门控、复核、浏览器导航 | 覆盖正常路径和本次缺陷；修复旧浏览器验收入口与缺失的接口参数夹具，稳定异步路由断言 |
| 实际运行结果 | 生产构建在真实 Chromium 中运行；英文/中文、桌面/移动、报告展开和历史展开 | 浏览器使用明确的合成数据；不把界面通过等同于真实科研任务执行成功。私有服务的模型调用账本未增加 |

## 修复清单

| 编号 | 问题及影响 | 修复 | 回归证据 |
|---|---|---|---|
| R1 | `chat_archive` 为字符串、列表或布尔值时，记录钩子调用 `.items()` 导致消息事务失败 | 仅接收对象中的允许字段，忽略异常元数据 | `test_malformed_archive_metadata_does_not_break_message_commit_or_hide_work` |
| R2 | 字符串 `"false"` 被当成真值，当前工作误从检索中隐藏 | 仅 JSON 布尔值 `true` 表示归档；读取旧快照时同样处理 | 同一参数化测试及既有归档搜索/MD 下载测试 |
| R3 | 打开归档审计后，已归档但状态为 pending 的消息进入当前区 | 当前事项选择统一排除归档消息，历史仍可查 | `roomFocus.test.ts` |
| R4 | 子标题被独立排序，限制条件与所属结论分离 | 保留章节内的 Markdown 标题层级 | `keeps subordinate review headings attached to their conclusion` |
| R5 | 较短围栏错误关闭较长代码块，原始工具输出变成可见结论 | 关闭围栏必须同字符、长度足够且尾部为空 | `does not interpret a shorter fence inside a longer code block as prose` |
| R6 | 代码块之后没有空行时，后续正文随日志一起隐藏 | 代码块边界独立切分，保留相邻正文 | `keeps prose after a fenced log even without a blank line` |
| R7 | 任意包含工作流编号的单行都被当成过程日志 | 只折叠独立编号，保留含编号的结果陈述与引用 | `keeps a meaningful conclusion containing a workflow identifier visible` |
| R8 | 只有表头和分隔线的空 Markdown 表格仍占据默认视图 | 空表移到过程详情，有数据的结果表保留 | 空表/结果表两项用例及 Chromium 展开验证 |
| R9 | 英文工具回执后的同段下一行解释被整块隐藏 | 按回执行识别，保留解释和科学限定 | `keeps a caveat on the line after an English tool receipt visible` |
| R10 | 浏览器验收仍断言旧简报入口、任务侧栏和旧默认历史布局，且未匹配 `include_archived=false` | 更新为结果、报告与复核导航，验证历史默认折叠和手动展开，补接口夹具 | `browser-bot-workspace.mjs`、`browser-harness-core.mjs` |
| R11 | 路由更新中旧节点短暂匹配，异步测试偶发断言已卸载节点 | 在 `waitFor` 中重新查询当前节点并断言可见 | `researchPage.test.tsx` |

以上修复不删除、改写历史对话，不自动启动任务或付费重试。归档内容仍保留在完整 Markdown 中；归档不代表科学复核通过。

## 本轮验证结果

- 前端专项回归：20 个文件、258 项通过。
- 后端专项回归：168 项通过、3 项按环境门控跳过。其中 PostgreSQL 锁范围用例随后在实际 PostgreSQL 上单独通过（仅随机 advisory lock 与读取，无表写入）；剩余 2 项需要未配置的门控运行镜像。
- 真实 Chromium：19 组工作区场景通过，覆盖 320–2560 像素宽度、英文/中文、明暗主题、只读权限、路由往返、模拟 SSE、错误恢复及最新答复的折叠/展开。接口响应为合成夹具，没有真实模型调用。
- lint、TypeScript/Vite 构建、bundle gate 和变更 Python 文件 Ruff 通过。构建保留已有动态/静态混用导入提示；lint 保留既有 learning/lab 表格的 4 条编译兼容性警告。
- 浏览器夹具核心的 18 项自测试通过。
- 实际数据库只读核查覆盖 13 个项目、547 条研究室事件与 2757 次可解析的项目引用，未发现跨项目归属；另有 374 个共享、外部或未解析引用 ID，未据此声称其归属已验证。模型调用账本保持 7 条，未新增付费调用。

## 验证入口

- 前端：`answerPresentation.test.ts`、`roomFocus.test.ts`、`Room.test.tsx`、Bot 工作区组件、`ProjectResearchOverview.test.tsx`、`ReviewMarkdown.test.tsx`、`researchBriefs.test.ts`、`researchPage.test.tsx`。
- 后端：记录/研究室/团队与预览、离线预算边界、调用范围、交付/聊天上下文、强制复核/拒绝复核、工作流门控/复核/运行时集成测试。
- 浏览器：构建后运行 `npm --prefix frontend run test:bot-workspace`。使用 Chromium、确定性 API 响应、模拟 SSE；全部外部模型调用为零。原始截图与运行日志保留在私有验收目录。
- 静态检查：独立运行 frontend lint、TypeScript/Vite build 与 bundle gate、变更 Python 文件 Ruff、文档清单、公开数据边界及 `git diff --check`。

本次不声称全仓库覆盖率达到 CI 门槛。两个依赖未配置门控运行镜像的测试仍跳过；没有在真实科研数据上新开任务、重跑实验或发送 DeepSeek 请求。main 合并仍遵守外部审阅与 CI 要求。
