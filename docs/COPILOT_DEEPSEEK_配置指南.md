# BDA Copilot：DeepSeek 配置与验证

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

## 前提

- BDA 后端运行在 `http://127.0.0.1:8100`
- BDA 前端运行在 `http://127.0.0.1:5173`
- 使用管理员账号登录

## 在前端配置

1. 点击顶部 `Copilot`。
2. 点击 Copilot 抽屉中的 `Model settings`。
3. 填写：
   - API base URL：`https://api.deepseek.com`
   - Model：`deepseek-v4-pro`，需要更低延迟时可使用 `deepseek-v4-flash`
   - API key：DeepSeek 控制台创建的 Key
4. 点击 `Save configuration`。
5. 点击 `Test API`。
6. 出现 `Connected to ...: BDA_OK` 表示验证成功。

完整 Key 不会通过配置查询接口返回前端。当前版本将 Key 保存在后端进程内存中；后端重启后需要重新填写。

## 通过环境变量配置

也可以在本地 `.env` 中配置：

```bash
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
LLM_API_KEY=你的Key
```

`.env` 不应提交到 Git。

## 当前 Copilot 能力

- 可编程生物材料领域限制与系统提示词。
- 项目候选查询和解释。
- BLI/SEC 结果解释。
- 工作流约束建议。
- 本地知识库检索。
- DeepSeek/OpenAI-compatible Chat Completions 与 tool calls。

## 当前限制

- 知识库目前是 SQLite 关键词检索，不是向量 RAG。
- 当前知识库有 10 条人工整理条目，主要覆盖 RFdiffusion、ProteinMPNN、AlphaFold2、Rosetta、Mask RGN、artifact contract、闭环设计、界面指标、可开发性和 BLI/SEC。
- 集群脚本草稿、提交确认和 LSF 任务操作尚未注册成 Copilot tools。
- API Key 当前不持久化到 secret manager。
