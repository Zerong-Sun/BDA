# 启明集群连接、脚本、提交与同步规则

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；当前平台与科研总状态以 docs/refactor/CURRENT_STATE_2026-08-29.md 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

更新日期：2026-08-20

本文整理 BDA 项目已有工作流约定、启明 2.0 登录提示和本次甜味蛋白
项目实测结果。集群使用 IBM Spectrum LSF；提交命令是 `bsub`，不是
Slurm 的 `sbatch`。

## 1. 连接规则

启明永久采用“用户手工密码登录、代理只复用已确认会话”的访问规约。
本规约约束人和 Agent 经 SSH 别名 `qm` 的交互访问；不是临时权宜，
也不再规划改成代理自动公钥登录。

本机 SSH 别名为 `qm`，对应账号 `bme-sunzr`、端口 `18188`。用户先连接
南科大校园网或可信 VPN，在自己的交互终端中执行 `ssh qm` 并亲手输入
密码。服务端仅公布 GSSAPI/密码认证；现有本机公钥不能直接登录。

用户确认已有认证会话后，代理才可复用该会话做远端动作，且必须带
`BatchMode=yes`，避免落入密码提示：

```bash
ssh -o BatchMode=yes qm 'bjobs -V; bjobs; bhosts -gpu -w'
```

- 禁止代理自动登录、自动重连、后台连通性探测、循环轮询和密码提示处理。
- 会话缺失或过期（`BatchMode` 失败、Permission denied、无 ControlMaster）
  即停止，并请用户手工登录；不得重试、不得改客户端选项再试。
- 每次用户明确请求只做一次批量查询或一次明确传输；不得为“确认还活着”
  再开探测循环。
- OpenSSH 的非后量子密钥交换提示是服务器能力警告，不是认证失败：
  不触发重试，也不通过降低或改写客户端安全设置（例如
  `KexAlgorithms`）来屏蔽。
- 密码不得保存、回显或进入命令、环境变量、脚本、Git、日志和报告。
  API key、token 和私钥同样不得写入仓库、作业脚本、日志或结果制品。
- 平台 LSF worker 的 `file:` credential_ref 是另一条路径，仍不得进入
  Git、命令、日志或报告；Agent 不得把该文件内容读进会话或写进命令行。
- 第一次操作远端目录前，必须用 `pwd`、`id -un`、`hostname` 和只读
  `find`/`du` 核对账号、主机、源路径及目标路径。
- 不在登录节点运行模型、大内存计算或长时间压缩任务。登录节点只用于
  查看、轻量整理、传输和提交。

## 2. 撰写脚本规则

蛋白设计模型优先使用 `qm-scripts/library/qm_job.py` 的 JSON 配置作为
唯一源文件：

```bash
cd qm-scripts/library
python qm_job.py params <model>
python qm_job.py validate <config.json>
python qm_job.py render <config.json> --output <job-dir>
```

- 不直接复制并随意修改历史 `submit.lsf`。只使用目录中
  `catalog.json` 支持的参数，并保留上游仓库和固定 commit。
- 模型入口、conda 环境、数据库、输入和运行目录使用集群上真实存在的
  绝对路径；提交前逐项检查。
- LSF 头至少明确 job name、queue、CPU、GPU、stdout 和 stderr。队列
  状态会变化，每次提交前重新检查，不能因为历史脚本中写过某队列就默认
  它仍开放。
- shell 主体使用 `set -Eeuo pipefail`，固定 `RUN_ROOT`，预建
  `logs/`、`work/` 和 `output/`，并在输入目录缺失或输入数量为零时立即
  失败。
- 作业必须打印主机、运行根目录和关键参数，但不得打印凭证。
- RFdiffusion 输入契约为 `input/manifest.json`，输出契约为
  `output/manifest.json`；ProteinMPNN 同样必须生成 BDA 可解析的
  `output/manifest.json`。没有 manifest 的结果不能视为已完成平台同步。
- RFdiffusion 提交前额外核对输入 PDB 的 chain/residue 编号、contig、
  `partial_T`、`provide_seq`、设计数量、输出 prefix 和参数 checksum。
- 避免作业持续生成大量小文件；必须产生大量文件时，先与集群支持团队
  确认存储方案。

### 2.1 资源申请与利用率规则（收到巡检邮件即视为违规）

集群会巡检作业利用率并发提醒邮件：

> 我们巡检发现您有以下 1 个作业利用率低，请检查是否正常……

**这封邮件本身就是本项目的失败信号，不是"如作业正常运行请忽略"的通知。**
已经被抓过两次：Rosetta `4135684`/`4137475` 申请 16 核实跑 1 核（6.00%）。
再出现即按违规处理，必须当场整改并把结论写回 `RUNS.md`。

核心规则：**申请的核数必须等于进程实际能用到的并行度，宁少勿多。**
`-n` 默认写 1；只有拿到下列任一条实证后才允许调大，且必须把实证写进
`submit.lsf` 注释和 `RUNS.md`：

| 允许 `-n > 1` 的实证 | 核对方式 |
|---|---|
| 二进制是 MPI 构建 | 集群上确认存在 `*.mpi*` 可执行文件，且脚本确实用 `mpirun` 启动 |
| 程序是多线程且线程数显式设定 | 脚本里写死 `OMP_NUM_THREADS` / `--num_workers` / `torch.set_num_threads`，且该值等于 `-n` |
| 上游文档明确要求的最小核数 | 引用文档出处，不靠猜 |

没有实证就是 `-n 1`。历史脚本里的 `-n` 不构成实证，禁止直接复制。

其余固定条款：

- `span[ptile=]` 必须等于 `-n`（单节点占满），只有真正跨节点 MPI 才例外。
  `ptile` 是每节点 slot 数，`ptile=1` 会把 `-n` 个 slot 摊到 `-n` 台机器上。
- GPU 作业按 GPU 是瓶颈来配 CPU：只申请 dataloader 真正用到的核。
  Boltz `predict` 是单进程推理，`-n 1`（最多 2，且必须同时显式设 `--num_workers`）。
- CPU-only 作业必须显式 `"gpus": 0`；`qm_job.py` 的 `gpus` 默认是 1，
  漏写会让作业白排在 GPU 队列后面。
- 单进程 + 内存 1–20G：1 核，投 `73x`、`63`、`52`，不投 `v3-64`。
- 需要独占整节点（大内存、间歇性低利用率的多线程作业）时，申请满节点
  而不是"多申请几个核碰运气"，并在 `RUNS.md` 写明理由。

提交前的自查（并入 §3 提交前确认清单第 3 条）：

```text
这个 -n 的数字，来自哪一条实证？答不上来就改成 1。
```

收到巡检邮件后的固定处置，不得"忽略邮件提醒"：

1. 用已确认会话做**一次**只读核对：`bjobs -l <id>`，看实际 CPU 使用与申请值。
2. 确认属于超申请，就 `bkill <id>`，按本节改小 `-n` 后重新提交（重新提交属于
   整改，不是 §3 禁止的"重复提交试探状态"）。
3. 把 job id、原申请值、实测利用率、整改后的值写进 `RUNS.md`，并更新受影响
   冻结文件的 SHA-256。

已整改（2026-08-20）：`route0a/fold/submit.lsf` 与
`developability/qc40_fold/submit.lsf` 原写 `-n 4` + `span[ptile=4]` + 1 GPU，
而 Boltz 是单进程推理。首轮 `4167123`/`4167124` 在 PEND 期间 `bkill` 作废（未运行、
无产物），两条流程以 `-n 1` + `span[ptile=1]` 重新冻结并重算 SHA-256，重新提交为
`4167148`/`4167149`。两轮输入 FASTA 与哈希完全一致。科学契约与调度资源的分界见
决策 D061。

### 2.2 每个插件必须有独立集群档案

所有注册模型插件（包括停用项与同 key 的不同版本）必须出现在
[`qm-scripts/plugins/registry.json`](../qm-scripts/plugins/registry.json)，并由它生成一份
[`qm-scripts/plugins/<plugin>/README.md`](../qm-scripts/plugins/README.md)。档案至少写明：

- 适用的 registry 版本、QM 环境或脚本路径、LSF CPU/GPU/ptile/walltime 规则；
- 使用平台预览还是 `qm_job.py`，以及可用的起始配置；
- 插件特有的输入、参数回显、产物计数和 fail-closed 检查；
- 每次真实运行的日期、LSF job ID（若原始记录没有 ID 必须明确写 `not recorded`）、
  成败/科学判读和仓库内证据来源；
- 该条记录是历史观察、安装核验还是失败观察。历史上跑过不等于当前声明已有 runtime proof；
  只有带当前 declaration fingerprint 的 registry evidence 才能消除 preflight 警告。

更新结构化台账后必须重新生成并检查：

```bash
python qm-scripts/plugins/generate_docs.py --write
python qm-scripts/plugins/generate_docs.py --check
```

CI 的 plugin catalog drift gate 同时检查：每个已注册 plugin key/版本都有档案，日期有来源，
生成文档没有过期。不得只在项目周报里写一次，然后让新插件或新版本脱离集群规则。

## 3. 上传与提交规则

固定顺序为：

```text
编辑 JSON → validate → render → 审阅 submit.lsf → 上传 → 再审阅 → bsub
```

上传操作不得自动提交：

```bash
bash qm-scripts/library/upload_to_cluster.sh <job-dir> qm
```

提交前必须确认以下内容：

1. 远端目录是本次 job 的唯一目录，不会覆盖其他项目。
2. 输入文件、manifest、模型路径和 conda 环境存在。
3. queue、CPU、GPU、内存和预计运行时长合理；`-n` 有 §2.1 要求的实证，
   `ptile` 等于 `-n`，CPU-only 作业已写 `"gpus": 0`。
4. 输出落在 `output/`，日志落在 `logs/`，脚本中没有凭证。
5. 预览脚本与准备提交的脚本一致，参数 checksum 未变化。

确认后才运行：

```bash
ssh qm
cd <remote-job-dir>
bsub < submit.lsf
```

注意必须保留 `<`。提交后记录 LSF job ID，并用 `bjobs` 监控；确需终止
时使用 `bkill <job-id>`，不得重复提交同一作业来试探状态。

### 3.1 代理复用已确认会话的提交流程（2026-08-20 实测）

本节是 Agent 在用户手工 `ssh qm` 之后可以执行的**唯一**提交路径，已按
Route 0a `4167148` 与 QC40 `4167149` 两次真实提交验证。用户未确认会话时，
不得开始其中任何一步。

固定顺序：

```text
一次批量只读核对 → 建目录 + rsync 到日期快照 → 当场 bqueues
→ bsub -q <queue> < submit.lsf → 记录 job id → 停止
```

1. **一次批量只读核对**。身份、主机、队列、cache 与目标根目录合并成一条命令，
   不拆成多次探测：

   ```bash
   ssh -o BatchMode=yes qm 'id -un; hostname; pwd; bjobs; ls -d /work/bme-liz/.boltz/mols'
   ```

   `BatchMode` 失败、`Permission denied` 或无 ControlMaster 即停止并请用户重新
   手工登录，不重试、不改客户端选项再试。

2. **传输**。目标是带日期的唯一 run root，先 `mkdir -p` 再 `rsync`；不要用
   `--delete`，避免误删同目录下其他内容：

   ```bash
   rsync -a -e 'ssh -o BatchMode=yes' <local-job-dir>/ qm:/work/bme-sunzr/bda/<name>_<date>/fold/
   ```

   传完立即在远端复核输入计数，与本地冻结的成员数逐一对齐。

3. **队列与资源当场决定**。提交前读 `bqueues`，确认目标队列为 `Open:Active` 且
   pending 不异常；**不得把队列硬编码进已绑定的 `submit.lsf`**。本账号的
   GPU 作业用本组队列 `gpu-bme-liz`，其余 `gpu-*` 队列属于其他课题组，不得占用。
   资源声明不从参照作业继承：`-n` 默认为 1，只有在有证据（MPI 构建、显式线程/worker
   数）时才提高，`ptile` 等于 `-n`，CPU-only 作业设 `gpus: 0`。首轮 `4167123`/`4167124`
   因直接沿用参照作业的 `-n 4` 被作废重跑，见决策 D061。

4. **提交时用命令行覆盖队列**。冻结的 `submit.lsf` 里写的是占位符
   `#BSUB -q QUEUE_SET_AT_SUBMIT`；命令行 `-q` 会覆盖脚本内的 `#BSUB -q`，
   这样本地脚本的 SHA-256 绑定保持不变：

   ```bash
   cd <remote-job-dir> && bsub -q <queue> < submit.lsf
   ```

   必须保留 `<`。

5. **记录后立即停止**。把 LSF job id 写回冻结文件（例如
   `prepare_route0a_surface_compatibility.py --record-submission <id> --queue <q>`）、
   `RUNS.md` 和 artifact bindings，并重算被改文件的 SHA-256。状态只能写
   `submitted`，不能写 `succeeded`。**不轮询、不后台守候**；下次状态由用户下一次
   明确请求触发。

6. **不重复提交同一作业来试探状态**；确需终止用 `bkill <job-id>`，且只针对
   本项目登记的 job id。

冻结文件必须让"重新冻结"对已提交的运行 fail-closed：重跑 preparer 若会把
`submitted` 退回 `not_run`，应直接报错，避免把一个真实在跑的作业写成未提交。

## 4. 结果同步规则

- 先确认 `bjobs`/历史记录和 `output/manifest.json`，再下载结果。
- 同步到带日期的本地快照目录，不覆盖输入、脚本或人工整理内容。
- 使用 `rsync --partial` 支持续传。RFdiffusion 默认同步最终 PDB、
  `.trb`、run record 和 manifest；`traj/` 仅在需要复盘扩散轨迹时下载。
- ProteinMPNN 至少同步 combined FASTA、manifest、逐骨架 FASTA 和
  packed PDB。
- 同步后核对远端与本地的文件数、manifest 记录数、路线拆分数量和
  checksum/size；不能只凭传输命令退出码判断成功。
- 集群数据必须定期备份到本地。快照和大模型结果放在 Git 忽略目录，
  不把成百上千个运行制品提交到源码仓库。

## 5. 本次甜味蛋白项目实测

远端目录：

- Monellin RFdiffusion：
  `/work/bme-sunzr/bda/jobs/job_9ca5d2d649a9/output`
- Brazzein RFdiffusion：
  `/work/bme-sunzr/bda/jobs/job_4de7a7ebdc11/output`
- ProteinMPNN：
  `/work/bme-sunzr/bda/proteinmpnn_sweetprotein_20260627/outputs_temp0.2_5seq`

2026-07-27 核验结果：

- Monellin 最终骨架 100 个。
- Brazzein 最终骨架 100 个。
- ProteinMPNN 逐骨架 FASTA 200 个、设计序列 1000 条，其中两条路线
  各 500 条。
- ProteinMPNN packed PDB 1000 个。

本地结果快照：

`backups/cluster-sync/2026-07-27/sweet_protein_rfdiffusion_100x2_20260626/`

## 6. AlphaFold 固定同步与注册流程

甜味蛋白 AlphaFold 结果统一通过以下命令处理，不再人工逐文件导入：

```bash
backend_v2/.venv/bin/python \
  -m backend_v2.scripts.sync_sweet_protein_alphafold_from_qiming
```

固定顺序为：

```text
复用已确认会话做一次判定 → 只读发现项目输出 → 日期快照 rsync
→ 路径与序列校验 → 指标校验 → v2 幂等注册 → Workflow 进度刷新
→ 覆盖数核验
```

- 未连接校园网时返回状态 `qiming_unreachable` 和退出码 `75`，不得误报为
  作业或导入失败。不得因此循环探测。
- 端口已通但无非交互 SSH 会话时返回 `qiming_authentication_required`
  和退出码 `77`，然后停止并请用户手工登录。密码不得写入脚本、仓库、
  自动化提示或日志；只复用用户已确认的 `qm` ControlMaster，不得发起
  交互登录或处理密码提示。
- 只发现输入 manifest 属于甜味蛋白项目且插件为 AlphaFold2 的输出，
  另兼容本项目已知的历史 smoke 作业目录；所有远端路径必须严格位于
  `/work/bme-sunzr/bda/jobs/<job-id>/output`。
- 快照保存到
  `backups/cluster-sync/<date>/sweet_protein_rfdiffusion_100x2_20260626/alphafold/`，
  使用 `rsync --partial` 续传，不删除或覆盖其他日期快照。
- 注册前逐一核对候选物 ID、PDB 序列、pLDDT/pTM 范围及 PAE 有限值。
  单体中不适用的界面 PAE（`NaN`）按缺失处理，不能写成
  `interface_pae`。
- 所有原始 PDB、置信度 JSON 和汇总文件均保存为 artifacts；候选物保存
  pLDDT、pTM、平均 PAE 等指标，并关联预测结构。
- 同一候选物存在多个预测时保留全部原始产物；主指标优先采用候选物覆盖
  数更多的运行，再以文件时间选择较新的结果，避免 smoke 覆盖全量结果。
- 注册器和同步器均可安全重复运行。Results 从 v2 动态读取数据，新增
  导入不需要重新构建前端；双路线汇总 Workflow 同步刷新 RFdiffusion、
  ProteinMPNN、Rosetta 与 AlphaFold 的真实覆盖数。
