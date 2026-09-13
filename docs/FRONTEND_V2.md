# BDA 前端 v2 说明

状态：活跃

最后核验：2026-09-07（Asia/Shanghai；更新页面、提交、预览及 Copilot 交接说明）

权威范围：本文标题所述主题；平台总览与成熟度以仓库根目录 `README.md` 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

## 1. 技术栈与页面

交付目标为桌面网页版，同时覆盖新手引导与专业操作。页面布局、工作流画布、Copilot 和验收均以桌面浏览器为重点；手机端不在当前开发与交付范围内。浏览器验收默认只运行桌面用例。

前端使用 React 19、TypeScript、Vite、TanStack Query、Zustand、React Flow、Mol*、Tailwind CSS 与 Zod。主要页面为 Experiments、Workflow、Candidates、Results、Research、Lab、Timeline 和无需项目的工具箱，以及全局 Copilot/Settings 抽屉。默认新手路径及 Research 四分区见[使用指南](GUIDED_PLATFORM_WORKFLOW.md)。

项目上下文使用 UUID；一个项目可包含多个 target，并以 primary target 兼容旧的单目标视图。Candidates 在没有项目时禁止发起查询，避免空项目串数据。

## 2. API 契约

`VITE_API_BASE` 默认 `/api/v2`。`backend_v2/openapi.json` 是契约源，执行：

```bash
npm run generate:api
```

生成物位于 `src/lib/api/generated/`，CI 重新生成并检查漂移。静态资源使用生成类型；Literature/Intelligence 等动态科研 JSON 在 `src/lib/schemas/` 继续经过 Zod 边界校验。

成功响应直接解析资源或 `{items,next_cursor}`，不支持 envelope、offset/total 或旧字段名。错误解析 Problem Details，并向 UI 提供 `detail`、`error_code` 和 trace ID。

## 3. 认证刷新

Access token 保存在 sessionStorage；refresh token 不暴露给 JavaScript，只由 Secure/HttpOnly/SameSite Cookie 发送。请求收到 401 后使用 single-flight refresh，同一时刻只发生一次刷新，原请求最多重试一次；失败后清除 access token 并返回登录页。

## 4. Cursor、ETag 与冲突

列表通过 cursor 翻页。项目、target、工作流节点/布局、Campaign decision、Literature/Intelligence review 和知识条目修改发送 `If-Match`。收到 412 时 UI 不覆盖服务器数据，应提示重新加载；成功后缓存新 version/ETag。

工作流先经过 preflight 和脚本预览，用户确认后才提交；提交携带预览时的工作流版本，冲突时重新检查。工作流提交只调用 `/workflow-runs/{id}/submissions`，每次用户动作生成 `Idempotency-Key`。任务状态由 job resource、cursor logs 与 `/jobs/{id}/events` SSE 驱动，不提供同步 `/sync`。

## 5. 上传、查看与下载

持久化浏览器上传执行：创建 upload session → Web Crypto SHA-256 → 预签名 PUT → complete。浏览器不向 API 发送 multipart 文件，也不保存本地文件路径。

target structure、candidate structure、script asset、实验导入和 dossier 都引用 artifact UUID。查看和下载先读取 artifact resource 中的短期预签名 `download_url`。候选批量下载先创建 delivery package，worker 完成 zip artifact 后再下载。

独立工具箱的仪器预览使用受限 base64 JSON 调用 `/wetlab/analysis-previews`，不写 artifact 或实验结果；选择项目并保存时仍走上述持久化上传契约。

配体 UI 必须在项目上下文中调用显式 ligand import；`GET /ligands` 仅查询目录，无写入副作用。

## 6. 科研与 Copilot

Campaign、Literature、Intelligence、Registry、Knowledge 使用各自领域路径；Copilot 不再承载 Literature 等跨域旧接口。Copilot chat 先返回 202 conversation/message，再连接 conversation SSE；连接前后不依赖长持有数据库会话。

聊天、后台 agent、任务书/决策树草案、外部检索和作业执行走异步任务；模型连接测试及路线推荐在当前 HTTP 请求中调用模型。前端按各自契约展示等待和失败，不把预测或 LLM 总结标记为实验事实，审核页面保留证据来源、置信度、限制与人工 decision。

默认 Copilot 使用统一任务工作区，简单问题进入对话，连续任务预览步骤和授权；旧聊天/后台任务的切换不再作为首层入口。交付状态优先于 runner 状态，技术轮次默认折叠。

各入口的实际服务、13 类能力、29 个工具及完整 Copilot HTTP 接口见 [Copilot 服务指南](COPILOT_SERVICE_GUIDE.md)。页面 AI、模型工具和用户确认后的执行接口有不同权限与副作用，不应混为一类服务。

## 7. 历史 URL

首个 v2 发布周期可调用只读 `/legacy-ids/{entity_type}/{legacy_id}`。解析成功后必须立即用 UUID 替换 URL 与本地状态。该入口带弃用信息，计划在 v2.1 删除；不得用它建立双写或旧 envelope。

## 8. 状态与错误处理

- TanStack Query 管理服务器状态，query key 必须包含 project/resource UUID。
- Zustand 只保存 UI 偏好、当前项目和抽屉状态，不复制权威业务资源。
- 401 触发单次刷新；409 展示状态/幂等冲突；412 提示重载；422 展示字段错误；429/5xx 只对 GET/HEAD 做有限退避。
- SSE 断线按资源状态决定是否重连，终态后关闭连接。

## 9. 开发与测试

```bash
npm ci
npm run generate:api
npm run lint
npm test
npm run build
npm run test:browser
```

测试层包括单元/Zod、MSW contract、页面 vertical slice 与浏览器 smoke。关键场景覆盖 local/OIDC 登录、refresh rotation、两阶段上传、多 target、工作流 ETag/提交、job SSE、候选/实验/交付包、Campaign、Literature、Intelligence、Registry、Copilot 与 legacy URL 转换。

正式构建固定 `/api/v2`。Nginx、Compose 与 Helm 不再发布旧 API 路由。
