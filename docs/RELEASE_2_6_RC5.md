# BDA 2.6 RC5：领域边界与前端分层

状态：活跃

最后核验：2026-11-20

权威范围：v2.6.0-rc.5 软件候选版本的整合范围、结构约束与验证边界。

数据来源：公开 Git 历史、版本化代码、回归测试、边界检查脚本与发布 CI。

替代关系：作为当前候选版说明，取代 [RC4](RELEASE_2_6_RC4.md) 的版本定位；RC4 的安全与整合说明仍有效。

本版本以 `b75d8e7548ec73b5cce0f02ddc88f77f7538067d` 为基础，只做结构治理，不新增功能、
不改动接口契约。公开 API、环境变量和软件包仍为 v2 / 2.0.0；OpenAPI 与数据库迁移头
`0078_design_memory` 均未改变，升级无需迁移。

## 后端：跨领域写入收口

| 范围 | 处理 |
| --- | --- |
| 跨领域 repository 导入 | 全部改为调用所属领域的 service；`autopilot` 新增自有 repository |
| 跨领域 ORM 构造 | 产物与谱系归 `artifacts`，候选与指标归 `candidates`，运行状态与谱系记录归 `workflows`，实验结果归 `experiments`，检索记录归 `literature`，内容寻址条目归 `knowledge`，提供商归 `registry`，Worker 心跳归 `platform`，审计归 `audit` |
| 反向依赖 | `candidates` 不再从 `compute` 导入指标写入 |
| CI 约束 | `backend_v2/scripts/check_domain_boundaries.py` 同时拒绝任何写法的外域 repository 导入和外域模型构造，无待处理例外清单 |

版本号递增、锁顺序和项目归属校验因此只存在于所属领域的 service 中。

## 前端：依赖方向

`components/` 与 `lib/` 不再导入 `features/` 或 `app/`，由 `src/test/layering.test.ts` 约束：

- 应用外壳（Topbar、命令面板、设置抽屉、Copilot 抽屉）移入 `app/shell/`；
- 结构查看器移入 `components/pdb-viewer/`，并纳入 REUI 审计与 `no-raw-ui` 规则范围；
- 导览数据、门控接口类型和流程阶段移入 `lib/`；原 `features` 路径保留再导出；
- 当前角色与只读判定移入 `lib/auth/currentRole.ts` 与 `lib/hooks/useWorkspaceReadOnly.ts`。

## 安装与运维

使用 release 的 `SOURCE_COMMIT` 核对源码提交，并用 `SHA256SUMS` 校验源码归档。
部署配置、数据库角色与模型/集群选择要求与 RC4 相同，见[安全工程规范](SECURITY_ENGINEERING.md)。

软件先在公开仓库验证和发布，再由私有仓库的 `.bda-sync` 单向同步同一提交；不要将私有历史推入公开仓库。

## 验证与边界

本候选的最终检查结果以对应提交的 GitHub Actions 为准。本地未运行依赖 PostgreSQL 的
数据库隔离测试与 `alembic downgrade base`，这两项以 CI 结果为准。
发布源码候选不等于更新某个正在运行的服务。
