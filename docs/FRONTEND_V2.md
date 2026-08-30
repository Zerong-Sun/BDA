# BDA 前端 v2 说明

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；当前平台与科研总状态以 docs/refactor/CURRENT_STATE_2026-08-29.md 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

## 1. 技术栈与页面

前端使用 React 19、TypeScript、Vite、TanStack Query、Zustand、React Flow、Mol*、Tailwind CSS 与 Zod。主要页面为 Experiments、Workflow、Candidates、Results、Research，以及全局 Copilot/Settings 抽屉。

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

工作流提交只调用 `/workflow-runs/{id}/submissions`，每次用户动作生成 `Idempotency-Key`。任务状态由 job resource、cursor logs 与 `/jobs/{id}/events` SSE 驱动，不提供同步 `/sync`。

## 5. 上传、查看与下载

所有浏览器上传执行：创建 upload session → Web Crypto SHA-256 → 预签名 PUT → complete。浏览器不向 API 发送 multipart 文件，也不保存本地文件路径。

target structure、candidate structure、script asset、实验导入和 dossier 都引用 artifact UUID。查看和下载先读取 artifact resource 中的短期预签名 `download_url`。候选批量下载先创建 delivery package，worker 完成 zip artifact 后再下载。

配体 UI 必须在项目上下文中调用显式 ligand import；`GET /ligands` 仅查询目录，无写入副作用。

## 6. 科研与 Copilot

Campaign、Literature、Intelligence、Registry、Knowledge 使用各自领域路径；Copilot 不再承载 Literature 等跨域旧接口。Copilot chat 先返回 202 conversation/message，再连接 conversation SSE；连接前后不依赖长持有数据库会话。

LLM/provider、外部检索和计算都是异步能力。前端展示 pending/running/failed 状态，不把预测或 LLM 总结标记为实验事实，审核页面保留证据来源、置信度、限制与人工 decision。

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
