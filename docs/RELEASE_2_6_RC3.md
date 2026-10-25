# BigoBio · Iteravia 2.6 RC3

状态：发布候选版（prerelease），非正式生产版。

最后核验：2026-10-16（Asia/Shanghai）。

权威范围：`v2.6.0-rc.3` 相对 RC2 的软件变化、主分支发布、安装升级和验收边界。

数据来源：版本化源码、[六维审查与修复记录](SITE_FUNCTION_UX_AUDIT_20261015.md)、本地运行验收与发布页面所列 CI 检查。

替代关系：替代 RC2 的当前版本入口；[RC2](RELEASE_2_6_RC2.md)、[RC1](RELEASE_2_6_RC1.md) 保留历史记录和初始化步骤；[生产恢复要求](STAGING_RELEASE_AND_RECOVERY.md) 继续有效。

## 本版变化

- Public 无需账号即可进入完整工作区、浏览已发布研究和使用独立计算器。上传、研究写入和 Bot 运行通过 Private 的账号与项目授权控制。
- Private 支持注册独立组织、登录、邀请和账号恢复；共享主机上的不同认证域使用独立会话。跨项目和只读限制由服务端执行。
- 文献以来源链接、原文段落、图表、数据、论点与论据组织。人工论点与模型草稿同时保留；数值必须匹配原文完整数字，零值、撤稿与补充材料未读取状态得到明确处理。
- 新 Bot 文献任务使用 v2 阅读合同，检查图、表、数据、补充材料和分页覆盖；历史 v1 合同保留原有验收条件。模型草稿仍需人工审阅。
- 结构残基、界面分析、原始仪器文件与版本化分析可通过受限工具进入研究记录；实验原始文件不被 Bot 覆写。详见[版本化仪器与结构指南](VERSIONED_INSTRUMENT_BOT_WORKFLOW.md)。
- 整理项目、研究、Workflow、候选、实验、结果与学习入口；空阶段可查看，有权限时可手动添加。修复项目切换、无效链接、候选结果筛选、操作权限与失败重试。
- 优化浅色、纯黑主题、按钮对比度及移动布局。Public、Private 共用公共软件，私有研究记录留在 Private。

## 版本与兼容

本版从 Public `main` 的已合并提交发布；发布资产的 manifest 记录准确 SHA。Private 使用独立候选标签，并通过不可变 Public SHA 固定相同的软件树。API 路径 `/api/v2`、包身份 `2.0.0` 和 `BDA_V2_*` 配置前缀保持不变。

数据库 head 为 `0076_account_audit_compat`。相对 RC2 的 0074，新增账号访问与审计兼容迁移。当前本地 Public 和 Private 已处于 0076，本次只升级软件与运行版本标识，不对业务数据库执行降级。

## 新安装

```bash
git clone --branch v2.6.0-rc.3 --depth 1 https://github.com/Zerong-Sun/BDA.git
cd BDA
```

继续执行 [RC1 初始化步骤](RELEASE_2_6_RC1.md#新的本地安装) 的配置、Compose、对象 bucket、独立 scheduler 身份与管理员创建流程，跳过其旧版 clone 命令。随后按[账号与 Public 工作区配置](ACCOUNT_ACCESS.md)选择部署类型、组织、注册模式及两个入口 URL。

Public 匿名访问必须显式配置专用发布组织和无密码 viewer；未配置不会自动公开现有数据。Private 新注册账号获得独立组织，访问已有团队仍需邀请。没有预置密码或 API Key。

静态 frontend 归档需要提供 `/api/v2` 代理与 SPA 回退的服务。完整运行需部署后端、数据库、Redis、对象存储、worker 和 scheduler。

## 从 RC2 升级

1. 记录现有提交和 schema，暂停新任务，备份数据库与对象存储，并验证恢复方法。
2. 在数据库克隆上验证 0074 → 0076 和 `alembic check`；保留部署配置、账户和模型凭据。业务库不执行 downgrade。
3. 检出本版，按部署方式升级 schema 并构建前后端。API、worker、scheduler、beat 和前端使用同一软件提交；API 与后台进程的 `BDA_V2_BUILD_REVISION`、`BDA_V2_SCHEMA_REVISION` 必须一致。
4. 配置与实际监听队列一致的 `BDA_V2_WORKER_QUEUES`，确认 scheduler 心跳；检查 `/api/v2/health/ready`、Public 匿名访问、Private 登录、原有项目与原始文件、文献锚点和实验分析。

出现问题时停止新写入，使用已验证的代码回退与备份恢复方案；不能以直接降级数据库替代恢复。

## 验证与资产

本轮软件基线：前端 1,189 项通过；启用隔离 PostgreSQL 的后端 2,779 项通过、7 项依赖专用环境的测试跳过，总覆盖率 90.09%，全部核心门槛通过。研究包分支覆盖 104/104。Public、Private 分别 22 个页面/子视图完成浏览器检查，390 px 布局与主题对比度通过。

Ruff、mypy、TypeScript、构建、包体积、接口与文档检查通过；ESLint 保留 4 条既有库兼容性提示。全部检查的范围及测试资源警告见[六维报告](SITE_FUNCTION_UX_AUDIT_20261015.md)。最终提交的 CI 链接与结果记录在发布页面和 manifest，不把历史检查冒充本版新检查。

附件包含源码、静态前端、`RELEASE-MANIFEST.json` 与 `SHA256SUMS`，记录不可变提交、schema、构建标识和验证范围。源码从 Git 提交导出，附件不含运行环境、凭据、数据库备份和私有研究数据。

本版为 GitHub 候选版及本地运行更新。真实项目前瞻实验、持续稳定性、真实集群故障恢复和生产灾备签收仍待完成；未在本次发布重跑付费模型任务或湿实验，不据软件检查宣称科研有效性。
