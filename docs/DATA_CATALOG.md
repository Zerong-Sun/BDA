# BDA 数据发布与外部数据目录

状态：活跃

最后核验：2026-08-30（Asia/Shanghai）

权威范围：定义公开演示数据、私有研究包和外部制品如何与 BDA 软件关联。

数据来源：仓库内 PD1 数据卡、研究包 schema、对象存储接口和公开数据门禁。

替代关系：取代任何包含本机路径、worktree 清单、私有快照哈希或研究运行数量的旧目录。

## 1. 发布问题

软件版本与研究数据具有不同的发布周期和访问边界。把私有研究文件、运行快照或本机目录写入代码仓库，会使软件发布携带无法撤回的数据披露；反过来，让软件依赖某台开发机的相对路径，也会破坏克隆后的可复现性。

BDA 因此只在 Git 中保存可公开审查的小型数据、schema 和 manifest。业务记录由 PostgreSQL 管理，计算制品由 MinIO 管理；私有研究数据通过服务器端研究包目录注册，不要求前端上传完整 JSON，也不要求软件仓库知道物理数据副本的位置。

## 2. 公开数据

公开仓库当前只发布 `pd1-demo-v1`：

- 研究包：`frontend/public/research-packages/pd1-demo-v1.json`；
- 数据卡与 manifest：`examples/migration-fixtures/pd1/`；
- 六个带固定 SHA-256 的合成 `DEMO` PDB fixture。

候选标识、指标和 fixture 结构均明确标记为 synthetic demonstration。新增或升级公开数据时，必须更新 package version、schema version、来源、许可、免责声明和 checksum，并通过人工审查。

## 3. 私有研究包

私有数据不进入公开 Git 历史。站点管理员在服务端登记版本化 manifest，至少包含：

- package ID、version 与 schema version；
- display name、license 与数据卡位置；
- 内容大小、SHA-256 和 MinIO URI；
- 安装状态及允许访问的组织范围。

客户端使用 `GET /api/v2/research-packages` 获取可见目录，再用 package ID、version 和 checksum 请求导入。对象路径、预签名凭证和私有 manifest 内容不得反向写入公开 BDA。

## 4. 开发脚本的外部数据根

少数离线迁移或验证脚本支持 `BDA_DATA_ROOT`，用于在获授权的环境中解析外部数据。该变量是本地输入边界，不是公开数据目录：

- CI 不发现、不下载也不验证任何私有数据根；
- 文档不得记录用户目录、worktree 路径、私有 payload 数量或 manifest 哈希；
- 脚本输出进入 Git 前必须经过公开数据门和 secret scan；
- 缺少外部数据时，公开软件和 PD1 演示仍必须能够独立测试。

## 5. 验证

公开数据门执行：

```bash
python scripts/check_public_data.py
```

该检查要求研究包目录只有 `pd1-demo-v1`，PD1 引用关系闭合，六个 fixture checksum 与 manifest 一致，并拒绝数据库备份、压缩运行包、超大文件和常见密钥格式。私有仓库另行验证其 overlay 和 LFS 清单；两套检查不能互相替代。
