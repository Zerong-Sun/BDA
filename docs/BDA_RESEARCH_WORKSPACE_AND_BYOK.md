# BDA 研究包、结构数据与 BYOK 使用指南

状态：活跃

最后核验：2026-08-31（Asia/Shanghai）

权威范围：公开研究包目录、导入流程、结构展示和用户自有模型密钥（BYOK）。平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：当前研究包目录、导入服务、PD1 manifest、结构界面和 provider 配置实现。

替代关系：取代曾引用私有四项目 deliverables 路径的旧版说明。

## 1. 问题与边界

研究数据不应由前端硬编码，也不应随每次导入把完整 JSON 从浏览器重新上传。前一种做法使软件与数据版本耦合，后一种做法无法可靠地校验来源、版本和对象完整性。BDA 因此把研究包视为服务器端、版本化的发布对象：目录负责发现，manifest 负责身份，checksum 负责内容校验，对象存储 URI 负责定位较大的私有数据。

公开仓库只发布 `pd1-demo-v1`。它包含一个 PD1 项目、12 条精选文献元数据、4 条证据关系和 4 个公开结构引用；另外 6 个小型 `DEMO` PDB fixture 用于迁移与界面演示。候选、指标和 fixture 均明确标为合成演示，不是模型运行或实验结论。

私有研究包不进入公开仓库。私有部署可以在允许的数据目录或 MinIO 中注册自己的 manifest，但不得修改软件代码来适配某个研究项目。

## 2. 目录与导入协议

`GET /api/v2/research-packages` 返回服务器当前可见的 `ResearchPackageDescriptor`，包括 package ID、version、display name、license、checksum、size 和 installed 状态。调用方先读取 descriptor，再按以下请求导入：

```http
POST /api/v2/research-package-imports
Content-Type: application/json

{
  "organization_id": "<organization UUID>",
  "package_id": "pd1-demo-v1",
  "version": "1.0.0",
  "checksum": "<descriptor checksum>"
}
```

服务器重新读取已安装包并验证 checksum，不信任浏览器提供的包正文。旧的 raw-package payload 端点仅保留兼容期，在生产配置中默认禁用。

导入前执行以下校验：

- package ID、schema version、许可与 synthetic 标识符合发布策略；
- project、reference、edge、structure 与 candidate 引用闭合；
- 文献标识符、来源 URL 和核验状态符合服务端约束；
- package checksum 命中该软件版本发布的可信清单。

导入按 package family 与 `source_project_key` 幂等更新。带 package lineage 的托管记录可以随新版本更新或撤回；没有 package 来源标记的用户笔记和自建数据不会被同步过程删除。

## 3. Research workspace 与结构展示

Research 页面只从 `GET /api/v2/projects/{project_id}/research-workspace` 读取展示数据。后端数据库是工作区内容的真源；静态 JSON 只是可重复导入的发布输入，不直接驱动页面。

PD1 包登记 3BIK、3BP5、5IUS 和 6JBT 四个 RCSB 结构引用。Mol* 通过后端返回的授权下载地址加载结构，并支持链筛选、表示方式、着色、相机重置和全屏。演示 fixture 的文件名含 `DEMO` 语义，页面必须持续显示“预计算、合成演示、非真实模型运行或实验结论”的说明。

## 4. 配置 BYOK

开发或单用户环境可以按以下顺序配置 OpenAI-compatible provider：

1. 选择项目；
2. 打开 **设置 → Copilot API**；
3. 填写 API base、模型名和 API key；
4. 保存并执行连接测试；
5. 返回 Research 或 Copilot，在当前项目边界内创建请求。

开发环境不把原始密钥写入普通业务表。服务端将密钥保存在 `BDA_V2_LLM_LOCAL_SECRET_DIR` 指定的受限文件中，数据库只保存 `file:` credential reference，响应只显示末四位预览。

生产环境禁止浏览器提交长期原始密钥。管理员应通过 secret manager 配置 provider，并在 registry 中使用 `env:` 或 `file:` reference。Provider 可用性不改变用户的组织/项目权限，也不能绕过工具白名单、写操作确认或预算限制。

## 5. 验证

公开包与导入逻辑的最小回归集为：

```bash
python scripts/check_public_data.py
backend_v2/.venv/bin/pytest \
  backend_v2/tests/test_bundled_research_package.py \
  backend_v2/tests/test_research_package_validation.py \
  backend_v2/tests/test_pd1_demo_import.py
```

发布验收还应在 PostgreSQL 与 MinIO staging 克隆中执行导入、重复导入、checksum 冲突、跨项目访问和对象缺失测试。通过这些检查只说明包可验证、可重复导入；不构成对文献结论、候选性能或生产基础设施的背书。
