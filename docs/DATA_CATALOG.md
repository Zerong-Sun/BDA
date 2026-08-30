# BDA 外部数据目录

状态：活跃 / 外部数据入口

最后核验：2026-08-29 22:35（Asia/Shanghai）

权威范围：定义代码仓库如何稳定引用已移出的科研产物；不复制或改写原始数据。

数据来源：`BDA-data`、2026-08-29 worktree 保全副本及其 SHA-256 清单。

替代关系：替代指向仓库内 `analysis/`、`research projects/`、`deliverables/`、`fig/` 的失效相对链接。

## 唯一逻辑入口

所有活跃文档和代码都用环境变量 `BDA_DATA_ROOT` 表示数据仓库根目录。开发机默认由
`backend_v2/scripts/_data_root.py` 解析；linked worktree 会通过 Git common directory 找到主检出旁的
数据仓库，因此不得假定当前 worktree 自己包含 `backend_v2/.venv` 或相邻的 `BDA-data`。

2026-08-29 的收口数据位于：

- `BDA_DATA_ROOT/analysis/2026-08-29/analysis/`：审计报告、表格、带输出 notebook、证据包和作业提交记录；
- `BDA_DATA_ROOT/analysis/2026-08-29/worktree-recovery/`：两个旧研究工作区中仍有独立价值的数据树；
- `BDA_DATA_ROOT/analysis/2026-08-29/SHA256SUMS`：544 条 payload 校验记录；
- `BDA_DATA_ROOT/analysis/2026-08-29/SOURCES.json`：来源说明。
- [`docs/data/BDA_DATA_INDEX_2026-08-29.json`](data/BDA_DATA_INDEX_2026-08-29.json)：代码仓库内的机器可读目录，记录快照、清单哈希和 payload 数量。

当前物理副本共 546 个文件、约 185 MiB。`SHA256SUMS` 自身 SHA-256 为
`fc68f3a2a04ce6ecb4747cde733d9191d96069a0540907cb4397319f41fe080b`。

## 验证

CI 没有外部数据仓库时，文档检查器验证逻辑路径格式和版本化机器目录；开发机解析到
`BDA_DATA_ROOT` 时，它还验证被活跃文档引用的物理文件、`SHA256SUMS` 自身哈希，以及清单内全部
544 个 payload 的路径、数量和 SHA-256。独立复核命令为：

```bash
cd "$BDA_DATA_ROOT/analysis/2026-08-29"
shasum -a 256 -c SHA256SUMS
```

代码内记录的历史路径由 `_data_root.resolve_recorded()` 转换；文档中不得重新引入指向仓库内
`../analysis/` 的相对链接。
