# BDA 文档导航

状态：活跃

最后核验：2026-09-07（Asia/Shanghai；按当前使用、工程、规划与归档重新整理）

权威范围：公开 BDA 软件、PD1 演示包与部署文档的入口及文档分类。

数据来源：仓库内版本化代码、配置、测试与下列文档。

替代关系：取代旧的平铺索引；过期说明和历史验收转入归档，未完成规划单独保留。

## 开始使用

按下面顺序阅读即可了解从建项目到运行的完整路径；只想使用计算器或仪器预览，可直接看第一份指南的“独立实验工具”。

- [项目引导、Research 四分区、独立工具与可靠执行](GUIDED_PLATFORM_WORKFLOW.md)
- [Copilot 服务指南：能力、页面入口、模型配置、工具权限与 HTTP 接口](COPILOT_SERVICE_GUIDE.md)
- [研究包导入与结构数据](RESEARCH_PACKAGES.md)
- [公开 PD1 演示数据说明](../examples/migration-fixtures/pd1/DATA_CARD.md)

## 研究记录与审核

- [研究记录结构](RESEARCH_RECORD_STRUCTURE.md)
- [文献综述写作与审核标准](RESEARCH_REVIEW_WRITING_STANDARD.md)
- [数据目录与公开/私有数据边界](DATA_CATALOG.md)
- [Autopilot 协议、当前实现与未完成闭环](AUTOPILOT_CAMPAIGNS.md)

## 开发、计算与部署

- [前端架构与 API 契约](FRONTEND_V2.md)
- [后端架构与服务边界](BACKEND_V2.md)
- [计算后端与目标配置](COMPUTE_TARGETS.md)
- [插件接口](PLUGIN_INTERFACE.md)
- [QM 集群操作规则](QM_CLUSTER_OPERATION_RULES.md)
- [RFdiffusion 工作流提交](RFDIFFUSION_WORKFLOW_SUBMISSION.md)
- [Staging 发布与恢复](STAGING_RELEASE_AND_RECOVERY.md)

插件生成的运行手册位于 `qm-scripts/plugins/`。当前能力与部署要求以活跃文档和对应代码为准；真实模型、检索源和客户集群仍需按使用指南分别验收。

## 规划与历史

- [待实施规划](plans/README.md)：未完成的产品/工程方向，不作为现有功能承诺。
- [归档索引](archive/README.md)：被替代的说明、阶段计划和历史验收，保留原文、日期及替代文档。

私有研究决策、运行证据和含私有路径的旧记录继续保存在私有恢复归档中，不纳入公开软件文档。

## 验证记录

- [六维复核与修复清单](GUIDED_PLATFORM_REVIEW.md)
- [前端插件检查与修复](FRONTEND_PLUGIN_CHECK_2026-09-07.md)
