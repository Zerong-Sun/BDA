# BDA 安全开发与发布规范

状态：活跃。

最后核验：2026-10-25。

权威范围：公开和私有部署的项目隔离、身份、外部模型、计算接口以及后续代码修改与发布门槛。

数据来源：本次源码审阅、合成回归测试，以及 OWASP API Security 和多租户安全指导。

替代关系：补充 [安全政策](../SECURITY.md)、[账号边界](ACCOUNT_ACCESS.md) 与 [生产恢复要求](STAGING_RELEASE_AND_RECOVERY.md)。

## 不可放松的边界

1. **身份和项目同时检查。** 所有项目资源访问必须验证当前用户权限；写入关联必须验证每个外键的项目归属。管理员能看多个项目，也必须满足关联双方属于同一项目。资源不存在和不可访问均不应暴露另一项目的内容。
2. **前后端各自保护。** 前端缓存键带项目，组件局部状态在项目切换时清空或重挂载；账号变更中止旧请求并拒绝旧响应。后端必须独立拒绝越权，不能依赖界面隐藏。
3. **数据库再次隔离。** 请求身份和 worker 项目上下文使用 transaction-local 设置，每次新事务重新建立。API 和普通 worker 使用 NOBYPASSRLS、非 superuser 角色；生产 readiness 检查实际连接角色。迁移、维护和 scheduler 凭据分开注入。部署前测试连接池复用、回滚和两项目可见性。
4. **延迟执行重新验证。** 消息只携带资源标识，worker 从可信数据库记录恢复项目和操作归属，读取输入、关联候选、收集输出前复核；不能把客户端传来的 project_id 当成授权。重试、幂等键、暂存目录和导出均与操作/项目绑定。
5. **文件并非普通链接。** 发出签名 URL 前验证资源权限；URL 不进日志或持久化缓存。计算输入/输出拒绝绝对路径、父目录、符号链接与异常大小，检查清单和 SHA-256。

## 模型 API：客户明确选择，运维批准目的地

公开版不自动继承管理员默认模型，不因“只有一个供应商”就自动选中。未选择时显示待配置状态。私有管理员仍可显式配置默认项，项目选择只能引用其有权限使用的供应商。

`BDA_V2_LLM_ALLOWED_ENDPOINT_ORIGINS` 是逗号分隔的运维审核 origin 列表；Helm 使用 `config.llmAllowedEndpointOrigins`。默认为空，禁止模型出站。生产仅接受 HTTPS origin，例如 `https://llm-gateway.example.org`；不要填写 API key、路径或用户名。不同厂商使用同一个配置机制，没有内置 DeepSeek 默认项。

升级现有部署时，先确认实际模型供应商的数据保留、日志、研究数据处理和合同要求，把已批准 origin 明确填入配置，再重启 API 和全部 LLM worker。仅填 allowlist 不会配置供应商，也不意味着同意把所有项目数据发送出去。BYOK 密钥只返回设置状态，保存在部署密钥存储中；注册表不能向其他项目泄露其模型配置。

公网和内部模型网关都通过运维 allowlist 授权。对内部网关进一步限制 worker 出站网络；准确的 origin allowlist 不能代替防火墙、DNS 和代理控制。禁止携带密钥自动跟随重定向。

## 启明和本地计算接口

启明使用 LSF，显式配置 SSH host/user/root，保留 known_hosts 主机校验。传输目标不得被解析为 SSH 命令选项；端口名和路径逐段验证，暂存目录使用私有权限。收集节点必须可运行 `python3`，`lsf_remote_root` 应填写无符号链接的 canonical 真实路径；使用机构快捷软链时先向运维确认真实目录。收集器从目录句柄逐段使用 O_NOFOLLOW 打开文件，拒绝硬链接和非普通文件，核对清单长度。默认单次收集最多 10 GiB、10000 个文件，分别由 `BDA_V2_COMPUTE_MAX_COLLECTION_BYTES` 和 `BDA_V2_COMPUTE_MAX_COLLECTION_FILES` 调整；清单本身最多 8 MiB。生产 Docker 必须使用专用远程 daemon 的 mTLS，并验证服务端证书。

共享 Unix 账号不是恶意代码沙箱。客户可执行的插件或脚本若未经信任，必须使用独立 worker/UID、容器或独立计算账号以及出站网络限制。不同租户的凭据不得同时暴露给同一执行环境。正式客户交付前，必须在实际启明和本地环境各完成一次合成输入的提交、查询、取消、收集和权限拒绝验证；在审核环境外不能声称完成真实集群验收。

## 每次修改与发布

- 对每个项目资源入口检查：列表、详情、修改、外键关联、导入、导出、下载、SSE、MCP 和后台任务。新增表要声明归属、RLS 与 flow matrix，并有两项目负向测试。
- 回归要有同项目正例和跨项目负例；还要测试同账号两项目、同组织两账号、不同组织、管理员误关联、撤权后的延迟任务、快速切换和旧响应晚到。
- 运行后端 lint/type/tests、真实 PostgreSQL 隔离/迁移、前端 lint/tests/build/browser、OpenAPI 和生成客户端一致性、公开数据门禁、npm/pip 依赖扫描及镜像扫描。失败或跳过须如实记录，不能降门槛换“全绿”。
- 使用公开源码树生成可复现源码和校验和；私有研究数据、密钥、部署文件及私有 Git 历史不得入包。先发布软件，再单向同步私有部署；保留数据库、对象存储备份和镜像 digest 以便回滚。
- 客户生产上线需要已有生产门槛中的 TLS/OIDC、受限数据库角色、备份恢复、集群验证、监控和回滚证据。候选版本修复了已复现问题，并不证明不存在未知漏洞。

发现串数据时暂停相关写入与共享导出，保留带 trace/actor/project/action 的审计证据，确认受影响范围，再按已验证来源修复关联；不得按名称猜归属或批量搬数据。必要时撤销已发出的凭据/链接，按 [安全政策](../SECURITY.md) 私下处理披露。

参考：[OWASP API Security Top 10](https://devguide.owasp.org/en/07-training-education/07-api-top-ten/)、[OWASP Multi-Tenant Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)。
