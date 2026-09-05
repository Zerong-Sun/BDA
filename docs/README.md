# BDA documentation

状态：活跃

最后核验：2026-08-30（Asia/Shanghai；公开仓库首发基线）

权威范围：公开 BDA 软件、PD1 演示包与可复现 staging 文档索引。

数据来源：仓库内版本化代码、配置、测试、公开 PD1 数据卡与本文列明的来源。

替代关系：取代私有工作区状态、分支收口与具体研究项目索引；这些内容不在公开仓库发布。

This directory documents the public BDA software and its reproducible staging
baseline. Private research decisions, results, run evidence, and worktree audit
reports are maintained only in the private BDA-demo archive.

## Active guides

- [Autopilot protocol and implementation boundary](AUTOPILOT_CAMPAIGNS.md)
- [Backend v2](BACKEND_V2.md)
- [Frontend v2](FRONTEND_V2.md)
- [Research workspace and BYOK](BDA_RESEARCH_WORKSPACE_AND_BYOK.md)
- [Compute targets](COMPUTE_TARGETS.md)
- [Copilot capability plan](COPILOT_CAPABILITY_PLAN_V2.md)
- [Copilot DeepSeek configuration](COPILOT_DEEPSEEK_配置指南.md)
- [Copilot validation report](COPILOT_VALIDATION_REPORT.md)
- [Data catalog](DATA_CATALOG.md)
- [Dual-mode operation plan (automated / manual)](DUAL_MODE_OPERATION_PLAN.md)
- [Plugin interface](PLUGIN_INTERFACE.md)
- [QM cluster operating rules](QM_CLUSTER_OPERATION_RULES.md)
- [Research interface usage](RESEARCH_INTERFACE_USAGE_GUIDE.md)
- [Research record structure](RESEARCH_RECORD_STRUCTURE.md)
- [Research review writing standard](RESEARCH_REVIEW_WRITING_STANDARD.md)
- [RFdiffusion workflow submission](RFDIFFUSION_WORKFLOW_SUBMISSION.md)
- [Staging release and recovery evidence](STAGING_RELEASE_AND_RECOVERY.md)
- [Local staging acceptance](V2_LOCAL_ACCEPTANCE.md)
- [PD1 demo data card](../examples/migration-fixtures/pd1/DATA_CARD.md)

Generated plugin runbooks live under `qm-scripts/plugins/`. Historical v1
documents that contain private paths or research runs are retained only in the
private recovery archive, not in this public repository.
