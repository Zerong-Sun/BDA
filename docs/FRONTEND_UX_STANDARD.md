# BDA 工具工作台前端与交互标准

状态：活跃；与当前后端契约共同使用。
最后核验：2026-10-24（整理说明；原实测日期与结果见正文）。
权威范围：工作区交互规范；执行限制以当前 API 为准。
数据来源：版本化源码、组件测试和正文注明的浏览器验收。
替代关系：当前发布结论见 [公开版本准备](PUBLIC_RELEASE_READINESS.md)。

核查日期：2026-10-20。适用于现有 React 前端及新增工作台。

Bot 入口、执行记录、页面交接、工具栏和设置的进一步约定见 [Bot 交互规范](BOT_INTERACTION_STANDARD.md)。

## 依据与选型

这里的目标是科学工具工作台：项目上下文、工具入口、工作内容和辅助面板各有明确位置。无需实现窗口管理器或模拟操作系统桌面。

| 来源 | 采用原则 | 在 BDA 的解释 |
| --- | --- | --- |
| [Carbon UI shell](https://www.carbondesignsystem.com/building-blocks/core/components/ui-shell-left-panel/guidelines) | 频繁切换或较多导航项适合固定左侧导航；避免三级侧栏导航 | 页面入口统一分组；项目流程和页面标签不再充当第二套全局入口 |
| [Fluent 2 Layout](https://fluent2.microsoft.design/layout) | 用空间、对齐、层次表达内容关系，并随可用宽度重排 | 内容优先，避免连续卡片套卡片；窄屏将导航替换为菜单 |
| [VS Code Custom Layout](https://code.visualstudio.com/docs/configure/custom-layout) | 工作区与辅助区域有清晰分工，布局支持专注工作 | 顶栏管理项目与全局操作，主区域管理内容滚动，助手按需打开 |
| [NN/g Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | 主要操作优先；低频细节按需展开 | 背景、来源、历史保留可展开入口，避免排在主要操作前形成长墙 |
| [NN/g Complex Application Design](https://www.nngroup.com/articles/complex-application-design/) | 支持复杂任务中的学习、发现与高效操作 | 同时提供可见导航、搜索跳转、上下文反馈，保留已有提交确认 |
| [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | 键盘可用、焦点可见、不被完全遮挡、适当目标尺寸和重排 | 验证 Tab、Escape、菜单、抽屉及手机布局；不以隐藏滚动条解决溢出 |

开源实现参考：[Carbon UIShell](https://github.com/carbon-design-system/carbon/blob/main/packages/react/src/components/UIShell/README.md)、[VS Code workbench layout](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/browser/layout.ts)。参考区域职责和交互方式，沿用本项目 Base UI / reui 组件，没有引入另一套组件库。

已检查本会话可用 skills，采用 Playwright skill 做浏览器复核；网页生成和图片生成类 skill 不适合现有 React 工作台的结构调整。

## 本项目采用的规则

以下尺寸、断点与操作步数是 BDA 的实施选择，不是来源文档的统一强制要求，也不代表已取得 WCAG 合规认证。

1. **固定入口**：桌面所有已注册工作台在左侧可见；按工作空间、计算设计、实验学习和平台分组。保持一个路由定义源。切换页面保留项目 ID；支持浏览器返回。
2. **首屏可用**：主要入口不依赖滚到页面末尾。工具切换器放在标题后；目录用于浏览和搜索。主要业务操作放在相关输入附近，底部“下一步”只是补充入口。
3. **页面滚动**：外壳固定为 `100dvh`；主内容区拥有页面纵向滚动，切换路由回到顶部。短文本不设置独立滚动框。画布、表格、长文献、聊天与抽屉可因任务需要独立滚动；不得通过全局去掉 overflow 破坏它们。
4. **减少外框**：分组优先使用标题、留白或一条分隔线。独立任务、可操作记录、风险提示和表单输入仍保留必要边界。禁止对全部卡片或边框做全局清除。
5. **层次**：全局导航负责去哪里；紧凑项目流程表示进度；页面标签负责当前内容。移动端不重复显示项目流程条，通过页面菜单到达各工作台。
6. **响应式**：宽度小于 1100px 时使用页面菜单；工具目录在 1280px 以下按需展开，避免同时挤入两列导航。研究页标签采用手机两列、较宽屏四列。
7. **键盘和触控**：提供跳到工作区入口；所有页面保留搜索与跳转按钮及 Cmd/Ctrl-K。菜单支持键盘操作和 Escape。BDA 桌面导航行至少 36px；WCAG 2.5.8 的 24×24 CSS px 最低目标要求及间距例外见[官方解释](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)，不得混淆为所有控件必须 44px。
8. **业务语义**：导航不触发执行。页面可访问与任务可提交是两个条件；提交、审核、预算和权限门禁保持业务逻辑约束。加载、空白、失败和只读状态应有明确反馈。
9. **按当前操作展示信息**：默认展示任务目标、状态、结果、需要处理的问题和操作入口。校验值、内部编号、原始 JSON、处理来源和包格式放进有明确名称的详情入口。不要重复显示英文栏目眉题、同一句操作说明或空分类卡片。参数用于当前配置、区分实验方法或审核预算时直接显示；不能为了“简洁”隐藏失败原因、权限限制、质控问题、预测与实测的区别或提交确认。标题不套卡片，同一内容只保留一层必要边界。详见 [信息精简复核](FRONTEND_SIMPLIFICATION_REVIEW.md)。

## 问题对照与实施

| 原有问题 | 本次处理 | 代码位置 |
| --- | --- | --- |
| 全局横条和工作台菜单分散入口 | 固定分组导航；窄屏统一页面菜单 | `WorkspaceNavigation.tsx`、`Topbar.tsx` |
| 顶部导航与流程条占用内容高度 | 移除横向全局导航，流程条减少第二行说明并随内容滚走 | `App.tsx`、`PipelineRail.tsx` |
| 页面、外壳滚动边界含糊 | 固定外壳，主内容负责页面滚动，保留画布与抽屉滚动 | `App.tsx`、`science-workspace.css` |
| 工具目录较长，靠下入口难找 | 标题后直接选择任意工具，保留目录搜索 | `Tools.tsx` |
| 中等屏幕挤入两列导航 | 工具目录改为在更宽屏常驻 | `Tools.tsx` |
| 研究页手机标签纵向堆叠 | 手机两列、较宽屏四列 | `Research.tsx` |
| 元信息、背景和研究审阅区重复外框 | 元信息改分隔行；审阅主区域去掉外层装饰边界；目标树去掉重复 Frame | `ResearchWorkspacePanel.tsx`、`ProjectReviewPanel.tsx`、`Research.tsx` |
| 工具工作区与长项目目标形成额外框和滚动 | 去掉工作区外卡片与项目目标的高度限制 | `science-workspace.css` |

## 验收与边界

- 构建、TypeScript 与包体积检查通过，入口约 478.9 KiB；lint 无错误，存在 4 项已有表格兼容性警告。
- 全量前端单测 184 个文件、1176 项通过。
- 桌面浏览器矩阵 90/90 通过；手机项目与工具中英文复核 4/4 通过。
- 新增工作台断点回归 19/19 通过，覆盖 320–1440px、低高度、项目为空及加载失败、工具切换、键盘菜单、焦点与浏览器返回；使用仓库确定性 API fixtures，不代表真实后端已验证。
- 三组完整导览均通过，每组 9 章／23 步。执行方式、修复记录和证据见 [六维复核清单](FRONTEND_UX_REVIEW.md)。
- 画布、表格、聊天、文献等工作台内部仍有必要的独立滚动。本次不宣称每个业务表单都已重做，新增页面与后续细节迭代应依本标准验收。
