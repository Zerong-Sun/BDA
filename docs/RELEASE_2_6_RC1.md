# BigoBio · Iteravia 2.6 RC1

状态：发布候选版（prerelease），非正式生产版。

最后核验：2026-10-09。

权威范围：`v2.6.0-rc.1` 的软件范围、本地安装、升级、恢复与已知限制。

数据来源：版本化源码、自动化测试、隔离 PostgreSQL/MinIO 恢复演练和本地合成验收。

替代关系：作为 [2.6 学习平台说明](LEARNING_V26.md) 的发行补充；不替代 [生产恢复要求](STAGING_RELEASE_AND_RECOVERY.md)。

## 发行范围

BigoBio 是公司品牌，Iteravia（迭原）是候选产品名。此版本把 Learning as a Service 落实为可追溯的项目学习闭环：冻结目标和测定，导入实验，冻结数据，验证与审查模型，形成预算内的下一批建议，交接实验并接收结果，再交付完整学习记录。

包含两种序列组成基线、四种验证拆分、可选 split conformal 区间、模型提升/退役/回滚、双测定排序、证据来源与撤回、实验回执和成本记录。工作台保留 BigoBio 标识、亮色/纯黑主题、中英文界面及受限 Bot 工作区。

产品候选版标记为 `v2.6.0-rc.1`；已有包身份 `2.0.0`、`/api/v2`、`BDA_V2_*` 和技术目录保持兼容。数据库 revision 为 `0073_learning_lifecycle`。候选版从开发分支发布，主干审阅与合并仍遵循分支保护；发布 tag 不表示主干审阅已经完成。

## 本轮审查修复

- 通用实验 API 和文件导入拒绝保留的 learning 字段、类型与批次命名空间，学习数据必须经过其完整校验路径。
- 已删除的原始文件不能支持新观测、训练、事实记录或模型提升；来源变更使旧建议失效。
- 双测定决策按固定顺序锁定研究与测定，同时核验两个目标契约和模型；修订、退役与并发请求不会使用旧状态。
- 极端但有限的测量值导致数值溢出时，训练返回可处理的验证错误。
- 新实验交接单使用 manifest schema 2，冻结完整候选序列、测定方法、条件、单位与研究目标；旧清单保留可读。
- CSV 验证绑定所选文件及其版本；文件更换或消失后须重新验证。切换研究时清除上一研究的表单草稿。
- 计算任务重试立即恢复待执行状态；Autopilot 等待锁后重新核验工作流，避免旧的失败事件误结算正在重试的阶段。
- 更新锁文件中的 `compression` 1.8.2、`proxy-addr` 2.0.8 和 `source-map-js` 1.2.2，修复本次发布前审计发现的三个依赖漏洞。对应公告：[compression](https://github.com/advisories/GHSA-vc2v-76pw-4v95)、[proxy-addr](https://github.com/advisories/GHSA-jqcg-44mw-7w3h)、[source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)。

## 新的本地安装

需要 Git、Python 3（以下仅使用标准库）、Docker Engine 和 Compose v2。默认使用 8080、8200、5433、6380、9002、9003 端口。在已有 BDA 环境旁部署时，先调整 Compose 端口和项目名，使用独立数据库和卷。

```bash
git clone --branch v2.6.0-rc.1 --depth 1 https://github.com/Zerong-Sun/BDA.git
cd BDA
```

仅在全新目录运行以下初始化。它独占创建配置文件，生成随机密钥，选择 demo 计算后端，并把调度器数据库凭据保存在独立文件。已有安装应使用下一节的升级步骤。

```bash
python3 - <<'PY'
import os
from pathlib import Path
import secrets

os.umask(0o077)
assert not Path('.env').exists(), 'Existing installation: follow the upgrade instructions'
assert not Path('secrets/scheduler.env').exists(), 'Preserve the existing scheduler credentials'
values = {
    'BDA_V2_POSTGRES_PASSWORD': secrets.token_hex(32),
    'BDA_V2_REDIS_PASSWORD': secrets.token_hex(32),
    'BDA_V2_MINIO_SECRET_KEY': secrets.token_hex(32),
    'BDA_V2_JWT_SECRET': secrets.token_hex(32),
    'BDA_V2_COMPUTE_BACKEND': 'demo',
}
lines = Path('.env.example').read_text().splitlines()
with Path('.env').open('x') as out:
    out.write('\n'.join(f'{line.split("=", 1)[0]}={values[line.split("=", 1)[0]]}'
        if '=' in line and line.split('=', 1)[0] in values else line for line in lines) + '\n')
Path('secrets').mkdir(exist_ok=True, mode=0o700)
with Path('secrets/scheduler.env').open('x') as out:
    out.write('BDA_V2_DATABASE_URL=postgresql+psycopg://bda_scheduler:'
        + secrets.token_hex(32) + '@postgres-v2:5432/bda_v2\n')
print('Local configuration created. No credentials were printed.')
PY
docker compose up -d --build --wait api-v2 frontend
```

API 启动会迁移数据库。随后用仓库内 SQL 配置独立 scheduler 身份；密码仅经进程环境传入，不放入命令参数或日志：

```bash
python3 - <<'PY'
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

line = Path('secrets/scheduler.env').read_text().strip()
url = urlsplit(line.split('=', 1)[1])
assert url.username == 'bda_scheduler' and url.hostname == 'postgres-v2'
with Path('backend_v2/deploy/postgres/scheduler.sql').open('rb') as script:
    subprocess.run(['docker', 'compose', 'exec', '-T', '-e', 'BDA_V2_SCHEDULER_PASSWORD',
        'postgres-v2', 'psql', '-U', 'bda', '-d', 'bda_v2'], stdin=script,
        env={**os.environ, 'BDA_V2_SCHEDULER_PASSWORD': url.password}, check=True)
PY
docker compose up -d --wait
docker compose exec api-v2 python -m backend_v2.scripts.bootstrap_admin --username admin
```

最后一条命令交互式设置管理员密码，没有预置账户。打开 `http://localhost:8080` 登录；确认 `/api/v2/health/ready` 返回 `status: ok` 后再使用。首次 worker 心跳可能需要片刻。

创建项目及目标、登记候选并上传原始文件后，进入“项目学习”。Bot 需在项目模型设置中连接可用提供商；全新安装不包含 API Key。Demo 计算产生合成输出，不能作为真实模型或实验结论。

## 已有安装升级与回退

1. 在维护窗口暂停写入和新任务，记录当前应用提交、数据库 revision、工作流状态、worker 队列及对象存储位置。
2. 备份 PostgreSQL、对象文件/版本及独立的配置和 BYOK 密钥存储。配置和密钥不得上传 GitHub。先在隔离环境恢复并校验备份。
3. 检出此 tag，保留自己的配置。已有 0073 环境无需新增迁移；更早版本先在克隆库执行 `alembic upgrade head` 和 `alembic check`，确认后再升级目标库。
4. 同步更新 API、所有 worker、scheduler、beat 和前端。Docker 安装使用 `docker compose up -d --build --wait`；宿主机进程必须显式重启。
5. 检查 readiness、各队列心跳、登录、文件访问、研究/模型列表与交付下载。旧建议如果缺失当前学习状态摘要，重新生成并人工审查。新生成的交接清单应包含 `schema_version: 2`。

升级失败时先停止新写入，回退应用；需要还原数据时使用已经验证的数据库、对象及密钥备份。不能对含业务数据的环境执行 `alembic downgrade base`。完整迁移降级测试仅针对可销毁的隔离空库。

## 验证与发布资产

测试结果与合成两轮闭环记录见 [验收记录](LEARNING_V26.md#本次集成验收记录)。候选版附源代码包、前端静态构建和 `SHA256SUMS`；GitHub 另提供 tag 的源码归档。静态构建需由支持 SPA 回退、并代理 `/api/v2` 的 Web 服务提供，不能双击 `index.html` 代替完整平台。

本次恢复演练将一致性快照恢复到独立的本地 PostgreSQL 实例，比较全部表的记录摘要，并将当前对象文件恢复到独立 bucket 后逐个校验 SHA-256。该演练不等同于生产 PITR、历史对象版本恢复或灾备切换。

## 已知限制与正式版门槛

- 尚无真实项目完成两轮前瞻实验验证，尚未证明科研增益或优于专业蛋白模型。序列组成基线不理解残基顺序、结构和机制。
- 尚无线上部署目标、14 天稳定性记录、真实 LSF 故障恢复或完整生产灾备签收；生产写入开关保持原有保护。
- Autopilot 支持受监督的执行和状态交接；任意自然语言到真实多阶段实验的全无人值守流程仍不成立。外部实验须由获授权人员执行。
- 实验费用是操作者录入的估价与回执，未覆盖发票、人工、计算费用和客户结算。
- Iteravia 名称仍需商标与域名审查。模型/项目数据不自动跨租户共享。

全部原计划 P0、至少一个真实项目两轮闭环、同预算冻结对照和运维验收完成后，才能评估正式版发布。
