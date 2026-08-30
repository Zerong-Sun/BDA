# BDA Copilot 工具与 LLM 使用逻辑

## 1. 一个 Copilot

BDA 项目里只有一个产品级 Copilot：BDA Copilot。DeepSeek、OpenAI-compatible API、本地 vLLM 或 Ollama 都只是这个 Copilot 的 LLM provider，不是新的助手。

前端入口统一为 Copilot 抽屉；后端入口统一为 `/api/v1/copilot/*`。页面可以传入 `project_id`、page context、workflow context 或用户选择，但不能各自实现一套独立 Copilot 判断逻辑。

## 2. 请求主线

1. 前端收集用户输入、当前项目、页面上下文和显式选择。
2. 后端 router 只做权限校验、参数校验和 HTTP/SSE 包装。
3. `backend/app/copilot/runtime.py` 做统一 Copilot 调度：
   - 领域边界检查。
   - skill 匹配。
   - 项目上下文与知识库检索。
   - LLM 可用时调用 LLM provider。
   - LLM 不可用时走规则降级。
4. `backend/app/copilot/tools.py` 是 Copilot 唯一受控工具注册表。
5. 工具只通过 repository/service 访问 BDA 数据，不允许 LLM 直接读取任意文件路径或执行任意 shell。

## 3. 工具分层

工具按用途分为五类：

- 项目数据工具：候选、实验结果、workflow、campaign、delivery package。
- 知识工具：curated knowledge entries、本地文献库、主张和关系。
- 外部科研检索工具：Europe PMC、UniProt、Reactome、PDB。
- 模型/脚本工具：模型插件、参数目录、脚本资产和一致性检查。
- 集群工具：只创建可审核草稿；真实提交必须由用户确认。

所有工具返回结构化 JSON。Copilot 可以解释、组合和提出建议，但不能把建议直接当成实验事实或已完成的计算结果。

## 4. 知识库逻辑

知识库是 Copilot 的第一层上下文，不是聊天记录的附属品。

路线规划、方法解释、模型选择、脚本生成前都应先检索 curated knowledge。文献摄取得到的 claims 在审核前只能作为 pending evidence，不能作为 curated fact。实验事实以 Experiment Service 和项目数据库为准。

默认知识库至少覆盖：

- 证据层级与不确定性。
- PDB/模板选择。
- 文献综合。
- 路线规划。
- 模型模块链。
- 特定应用边界，例如抗虫蛋白的物种、受体、安全性和 assay 约束。

## 5. Route Planning

路线规划不是直接生成脚本。正确顺序是：

1. 读取项目名称、类型、摘要、design task、用户目标和 constraints。
2. 检索知识库，形成 `knowledge_context`。
3. 生成多条 `route_options`。
4. 每条 route 展开为可选择 modules，包含 `model_plugin_id`、`node_type`、说明和默认参数。
5. 用户选择 route 和 modules。
6. `POST /copilot/route-plan/apply` 创建 workflow run、nodes、edges 和 layout。
7. 用户再在 workflow node 上 preview script 或 submit-to-compute。

这样用户可以看到 Copilot 的分析过程、知识来源、路线选项和模块取舍，而不是直接得到一个不可审计的脚本。

## 6. LLM Provider 逻辑

LLM provider 只在 `backend/app/copilot/provider.py` 抽象里管理。`chat_with_llm` 不直接创建 OpenAI client，而是走 `get_llm_provider()`。

配置来源：

- `LLM_API_BASE`
- `LLM_MODEL`
- `LLM_API_KEY`
- `/copilot/config`

如果没有 API key，Copilot 必须降级为规则模式，并继续支持知识库检索、route planning、候选解释和结果解释。

## 7. 安全与确认

Copilot 不直接执行危险动作。

- 不能提交、取消或删除真实集群任务，除非用户通过确认按钮执行。
- 不能把 token、API key、SSH key 写入脚本、日志、prompt 或 artifacts。
- 不能声称 job 已提交、完成或产生结果，除非 compute tool 返回状态。
- 不能把 AlphaFold、Rosetta、docking 或 LLM 判断描述为已验证生物活性。
- 安全敏感 wet-lab 内容保持高层级、非操作性。

## 8. 前端使用逻辑

前端只有一个 Copilot 抽屉。页面级功能可以调用 Copilot API，例如 Workflow 页调用 route planner，但仍然展示为 BDA Copilot 的能力，不创建新的助手概念。

Workflow 页的推荐流程：

1. 用户创建或选择项目。
2. 输入目标，例如“做一个抗虫蛋白”。
3. 点击 Plan routes。
4. 查看 Knowledge used 和 Analysis process。
5. 选择 route。
6. 勾选 modules。
7. 点击 Create workflow from selected route。
8. 在 workflow node 上查看参数、预览脚本、再提交计算。

## 9. 后续优化方向

- 给 route planning 增加结构化 LLM 输出 schema，但仍保留规则降级。
- 将 Copilot 每次建议写入审计表，保存输入摘要、知识条目、工具结果、provider 和用户确认状态。
- 给知识库增加人工编辑、导入和审核 UI。
- 将 route template 持久化为数据库模板，而不是只放在 Python 常量里。
