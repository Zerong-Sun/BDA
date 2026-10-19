# BDA 文档导航

状态：活跃

最后核验：2026-10-20（补充项目快速切换对抗性审查入口）

权威范围：公开 BDA 软件、PD1 演示包与部署文档的入口及文档分类。

数据来源：仓库内版本化代码、配置、测试与下列文档。

替代关系：取代旧的平铺索引；过期说明和历史验收转入归档，未完成规划单独保留。

## 开始使用

- [近期代码更新、集成状态与维护入口（2026-10-17）](RECENT_UPDATES_2026-10-17.md)
- [设计学习：设计前复核与执行后反馈](design-learning.md)
- [研究团队与结果展示：六项验证及修复清单](SIX_DIMENSION_REVIEW_2026-10-17.md)

- [Public / Private 登录、注册与账号管理](ACCOUNT_ACCESS.md)

- [全平台能力升级与接入账本](PLATFORM_CAPABILITY_UPGRADE.md)

- [Iteravia 2.6 RC3 安装、升级和发布说明](RELEASE_2_6_RC3.md)
- [历史 RC2 发布说明](RELEASE_2_6_RC2.md)
- [历史 RC1 发布说明与安装初始化步骤](RELEASE_2_6_RC1.md)
- [Iteravia / BDA 2.6 项目学习](LEARNING_V26.md)

- [Bot 工作区、项目简报与前端改版验收](BOT_FIRST_WORKSPACE.md)
- [项目引导、Research 四分区、独立工具与可靠执行](GUIDED_PLATFORM_WORKFLOW.md)
- [全局导航与工作区入口契约](NAVIGATION_WORKSPACE_CONTRACT.md)
- [项目空状态、手动候选、人工流程步骤与历史兼容](PROJECT_WORKSPACES.md)
- [项目工作区六维审查与修复清单（2026-10-12）](PROJECT_WORKSPACES_REVIEW_2026-10-12.md)
- [Public / Private 全站逻辑、界面与六维修复验收（2026-10-15）](SITE_FUNCTION_UX_AUDIT_20261015.md)
- [实验工具使用与计算约定](LAB_TOOLS.md)
- [Copilot 服务、任务授权与模型配置](COPILOT_SERVICE_GUIDE.md)
- [DeepSeek Flash 输出验收与优化](DEEPSEEK_OUTPUT_REVIEW.md)
- [六维审查、修复清单与实际运行验证](DEEPSEEK_OUTPUT_AUDIT.md)
- [研究包导入与结构数据](RESEARCH_PACKAGES.md)
- [公开 PD1 演示数据说明](../examples/migration-fixtures/pd1/DATA_CARD.md)
- [工作区结构说明](WORKSPACE_MAP.md)

## Copilot、bots 与工作流

- [版本化科研 Skill 方法包](SCIENTIFIC_METHOD_PACKAGES.md)
- [Bot 名册](COPILOT_BOT_ROSTER.md)
- [Bot 职责与委派规则](COPILOT_BOT_GOVERNANCE.md)
- [团队协作与路线整理六维验证（2026-10-16）](TEAM_ROUTE_REVIEW_2026-10-16.md)
- [MCP 能力与调用契约](MCP_CAPABILITY_SURFACE.md)
- [决策归属与人工放行](DECISION_TRANSPARENCY.md)
- [工作流连接与门控](WORKFLOW_GATES.md)
- [工作流门控验证与修复](WORKFLOW_GATES_REVIEW.md)
- [系统可操作性复核](SYSTEM_OPERABILITY_REVIEW.md)

## 近期前端验收

- [项目快速切换对抗性审查（2026-10-20）](ADVERSARIAL_PROJECT_SWITCH_REVIEW_2026-10-20.md)

- [导航顺序与跳转验收（2026-10-18）](NAVIGATION_REVIEW_2026-10-18.md)
- [其他项目的结果、报告与复核验收（2026-10-19）](OTHER_PROJECTS_DISPLAY_REVIEW_2026-10-19.md)
- [项目结果、团队与工作流卡片验收（2026-10-19）](PROJECT_CARD_REVIEW_2026-10-19.md)
- [项目切换与异步响应隔离验收（2026-10-19）](PROJECT_SWITCH_REVIEW_2026-10-19.md)
- [最新结果、暂停状态与摘要修复（2026-10-19）](RESEARCH_SUMMARY_FIXES_2026-10-19.md)

## 研究记录与审核

- [研究决策中心](RESEARCH_DECISION_CENTER.md)
- [仪器分析与质控审核](WETLAB_QUALITY_CONTROL.md)
- [版本化仪器分析、Bot 证据与结构复核](VERSIONED_INSTRUMENT_BOT_WORKFLOW.md)
- [可核验的研究交付包](RESEARCH_DELIVERY_BUNDLES.md)
- [文献整理开源方法调研与论据工作台](LITERATURE_EVIDENCE_WORKBENCH.md)
- [研究工具能力、输入与来源限制](RESEARCH_TOOL_CAPABILITIES.md)
- [知识库检索与来源保留](KNOWLEDGE_SEARCH.md)
- [研究记录结构](RESEARCH_RECORD_STRUCTURE.md)
- [文献综述写作与审核标准](RESEARCH_REVIEW_WRITING_STANDARD.md)
- [数据目录与公开/私有数据边界](DATA_CATALOG.md)
- [Autopilot 协议、当前实现与未完成闭环](AUTOPILOT_CAMPAIGNS.md)

## 开发、计算与部署

- [前端架构与 API 契约](FRONTEND_V2.md)
- [后端架构与服务边界](BACKEND_V2.md)
- [计算后端与目标配置](COMPUTE_TARGETS.md)
- [扩展中心与模型使用资格](EXTENSION_QUALIFICATION.md)
- [插件接口](PLUGIN_INTERFACE.md)
- [插件参数手册](plugins/INDEX.md)
- [Rosetta 参数](rosetta/PARAMETERS.md)与[科学模式](rosetta/SCIENTIFIC_MODES.md)
- [QM 集群操作规则](QM_CLUSTER_OPERATION_RULES.md)
- [RFdiffusion 工作流提交](RFDIFFUSION_WORKFLOW_SUBMISSION.md)
- [Staging 发布与恢复](STAGING_RELEASE_AND_RECOVERY.md)

插件运行手册位于 `qm-scripts/plugins/`。后端相邻文档见[架构](../backend_v2/docs/architecture.md)、[运维](../backend_v2/docs/operations.md)、[测试](../backend_v2/docs/testing.md)和[运维脚本](../backend_v2/scripts/README.md)。真实模型、检索源和客户集群仍需分别验收。

## 规划与历史

- [待实施规划](plans/README.md)：未完成的产品/工程方向，不作为现有功能承诺。
- [归档索引](archive/README.md)：被替代的说明、阶段计划和历史验收，保留原文、日期及替代文档。

私有研究决策、运行证据和含私有路径的旧记录继续保存在私有恢复归档中，不纳入公开软件文档。

## 验证记录

以下记录只证明对应批次的验证范围。

- [2026-09-16 分支整合与复核](CONSOLIDATION_REVIEW_2026-09-16.md)
- [分支整合六维复核与修复](INTEGRATION_SIX_DIMENSION_REVIEW.md)
- [Bot 工作区视觉层级复审](FRONTEND_VISUAL_REVIEW.md)
- [六维复核与修复清单](GUIDED_PLATFORM_REVIEW.md)
- [前端插件检查与修复](FRONTEND_PLUGIN_CHECK_2026-09-07.md)

- [2026-10-18 工作台整合审阅与修复清单](INTEGRATION_REVIEW_2026-10-18.md)
