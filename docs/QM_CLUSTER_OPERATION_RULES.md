# IBM Spectrum LSF 集群操作规则

状态：活跃

最后核验：2026-08-30（Asia/Shanghai）

权威范围：BDA 经 SSH 连接 IBM Spectrum LSF 集群时的认证、资源、提交、同步与审计约束。

数据来源：`qm-scripts/library/qm_job.py`、插件 manifest、LSF 适配器及对应自动化测试。

替代关系：取代包含个人账号、课题组队列、真实 job ID、私有远端路径和研究运行统计的旧操作记录。

## 1. 风险与方法

集群作业同时涉及凭证、共享资源和长时计算。直接复制历史批处理脚本容易继承错误队列或 CPU 数，自动处理密码提示会扩大凭证暴露面，而只凭传输退出码判定成功会把不完整输出注册为科研制品。

BDA 因此把版本化 JSON job config 作为声明源，由统一工具验证参数并渲染 LSF 脚本。人负责建立交互认证会话和确认资源；平台或受控代理只复用已确认会话，并通过 manifest、checksum 和幂等 job identity 管理执行。

## 2. 认证边界

- 用户在自己的终端完成 VPN 和 `ssh <site-alias>` 登录，并亲自处理密码或多因素认证。
- 自动化只使用站点批准的非交互凭证引用，或在用户明确确认后复用现有会话；不得读取、保存、回显或尝试填写密码。
- 会话不可用时立即停止并报告 `authentication_required`，不得自动重连、降低 SSH 安全设置或循环探测。
- API key、token、私钥和密码不得进入命令参数、环境输出、Git、作业脚本、日志或报告。
- 首次使用远端根目录前，以一次只读批量命令核对账号、主机、工作目录、队列和目标路径。

## 3. 登录节点与资源纪律

登录节点只用于检查、轻量暂存、传输和 `bsub` 提交，不运行模型、大内存分析或长时间压缩。集群调度器是 IBM Spectrum LSF，提交使用 `bsub`，不是 `sbatch`。

CPU 申请必须与程序真实并行度一致：

- `-n` 默认值为 1；
- 只有 MPI 构建、显式线程/worker 参数或可复核性能测试能支持 `-n > 1`；
- `span[ptile=…]` 与 `-n` 保持一致；
- CPU-only 作业显式声明 0 GPU；
- `cpus_evidence` 记录程序参数、上游文档或测量证据。

低 CPU/GPU 利用率告警属于失败信号。负责人应停止或修正资源声明，并把原因和处理结果写入私有运行记录；不能以“作业仍在运行”为由忽略。

## 4. 生成与审查作业

从版本化配置生成脚本：

```bash
cd qm-scripts/library
python qm_job.py params <model>
python qm_job.py validate <job-config.json>
python qm_job.py render <job-config.json> --output <review-dir>
```

提交前同时核对：

1. 插件版本、镜像/上游 commit、命令模板与 config checksum；
2. 输入 manifest 的对象、chain/residue 编号、参数和预期数量；
3. 当前开放队列、CPU/GPU、内存、wall time 与真实并行度；
4. `logs/`、`work/`、`output/` 分离，脚本使用 `set -Eeuo pipefail`；
5. 输出 contract 和 checksum writer 已启用，脚本中没有凭证。

队列属于站点部署配置，不写入公开仓库。需要现场选择队列时，使用命令行覆盖经过审查的占位值，但不得改变已绑定的其余脚本内容。

## 5. 提交与状态

平台提交必须以 job UUID 和 attempt 生成确定性外部名称。重试前先查询外部状态；已有作业时恢复跟踪，不重复提交。

人工审查后的基本命令形态为：

```bash
cd <remote-job-dir>
bsub -q <approved-queue> < submit.lsf
```

提交成功只证明调度器接受作业，状态应记录为 `queued` 或 `submitted`，不能记录为 `succeeded`。终止使用 `bkill <job-id>`，且目标必须来自当前项目的持久化 job 记录。

## 6. 输出与同步

- 输入契约为 `input/manifest.json`，输出契约为 `output/manifest.json`。
- 同步前先检查 LSF 终态和输出 manifest；两者不一致时保持失败或待人工处理。
- 使用支持续传的工具复制到新的版本化暂存键，不以 `--delete` 覆盖其他运行。
- 校验远端与本地的文件数量、size、SHA-256 和 manifest 成员；传输命令返回 0 不是充分证据。
- `collect()` 拒绝路径穿越，并在同一数据库事务中登记 artifact、lineage、candidate 和 result。
- 原始输出进入开启 versioning 的 MinIO，Git 只保存小型 manifest 和公开许可允许的数据。

## 7. 故障与验收

网络中断或 LSF 暂时无法回答时，适配器返回非终态 `unknown`，由 job deadline 决定最终失败；不得把“查不到”映射为成功，也不得无界轮询。Redis 故障时 outbox 保留提交意图，恢复后再发布；worker 重启后依靠确定性 job identity 与外部状态恢复。

真实站点启用前必须完成一次无敏感数据的 smoke：提交、排队、运行、收集、checksum、取消和重投均通过，并由站点负责人确认资源与队列策略。该证据保存在私有部署记录中，不把账号、路径或 job ID复制到公开文档。
