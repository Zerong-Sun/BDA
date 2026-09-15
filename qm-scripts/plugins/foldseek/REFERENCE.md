# Foldseek — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

结构数据库搜索；命中和结构相似性需与比对模式、覆盖率和数据库版本一起解释。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/foldseek.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| conda-forge-2026-08 | true | valid | proven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### easy-search (`search`)

一批结构对参考数据库搜索。BDA 接入：`declared`。

输入：structures: PDB/mmCIF; reference_db: 完整 Foldseek 数据库前缀及伴随文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "alignment_type": 2,
  "evalue": 0.001
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### TMalign 重比对 (`tmalign`)

全局 TM 比对已预筛命中。BDA 接入：`declared`。

输入：查询结构; 完整参考数据库

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "alignment_type": 1
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：输出 evalue 列在该模式不再是统计 E-value；当前预筛设置可能遗漏远缘结构

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### createdb (`createdb`)

从结构集构建可重用数据库。BDA 接入：`not_exposed`。

输入：结构文件集合

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### easy-cluster (`cluster`)

结构聚类与代表结构输出。BDA 接入：`not_exposed`。

输入：结构集合

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 多链结构搜索/聚类 (`multimer`)

上游 easy-multimersearch / easy-multimercluster。BDA 接入：`not_exposed`。

输入：多链结构和对应数据库

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

## 使用方法

1. 选择本页明确版本和功能模式，按模式绑定输入，核对链号、序列和原子完整性。
2. 输入参数后预览最终命令/生成配置；未映射字段不能视为生效，未接入模式需先补适配。
3. 运行条件验证后检查全部原始输出、失败样本和缺失值；保存所用版本、配置、输入输出哈希。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `format_output`

逗号分隔输出列及顺序；解析器需与列设置一致；自定义字段需补定义。

类型：`string`；单位：无量纲；来源记录默认：`query,target,fident,alntmscore,evalue,prob`。

适用模式：search, tmalign

生成映射：`--format-output`；BDA 别名：`["format_output"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `evalue`

在默认 3Di+AA 模式下报告命中的 E-value 上限；不是结合置信度。alignment-type=1 时输出 evalue 列改作两种长度 TM-score 的平均，不能沿用统计 E-value 解释。

类型：`number`；单位：无量纲；来源记录默认：`0.001`。

适用模式：search, tmalign

生成映射：`-e`；BDA 别名：`["evalue"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `alignment_type`

结构比对算法：0 为 3Di 局部，1 为全局 TMalign，2 为 3Di+AA 局部；当前上游还列 3 LoLalign，部署版本支持情况待核验。

类型：`integer`；单位：无量纲；来源记录默认：`2`。

适用模式：search, tmalign

生成映射：`--alignment-type`；BDA 别名：`["alignment_type"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `max_seqs`

送入精细比对的预筛候选数量上限；不是保证返回的最终命中条数。

类型：`integer`；单位：无量纲；来源记录默认：`1000`。

适用模式：search, tmalign

生成映射：`--max-seqs`；BDA 别名：`["max_seqs"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `threads`

并行 CPU 线程数，由 BDA_CPUS 生成，应与申请的 CPU 一致。

类型：`integer`；单位：个；来源记录默认：`未声明`。

适用模式：search, tmalign

生成映射：`--threads`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `coverage`

覆盖比例下限，需同时指定覆盖率归一化对象。

类型：`number`；单位：0–1；来源记录默认：`未声明`。

适用模式：search, tmalign

生成映射：`-c`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `cov_mode`

0 查询和目标均满足覆盖；1 目标；2 查询。

类型：`integer`；单位：无量纲；来源记录默认：`未声明`。

适用模式：search, tmalign

生成映射：`--cov-mode`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `sensitivity`

预筛灵敏度与速度权衡；GPU 预筛的适用性以版本为准。

类型：`number`；单位：无量纲；来源记录默认：`未声明`。

适用模式：search, tmalign

生成映射：`-s`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `conda-forge-2026-08`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| format_output | string | query,target,fident,alntmscore,evalue,prob | {} |
| evalue | number | 0.001 | {} |
| alignment_type | integer | 2 | {} |
| max_seqs | integer | 1000 | {} |

**input_ports**

```json
[
  {
    "name": "structures",
    "kind": "protein_structure",
    "accepts": [
      "backbone_set",
      "candidate_structure",
      "predicted_structure",
      "structure"
    ],
    "content_types": [],
    "required": true,
    "multiple": true,
    "description": "Designs to screen for fold-space collisions."
  },
  {
    "name": "reference_db",
    "kind": "opaque",
    "accepts": [
      "structure_database",
      "sequence_set",
      "structure"
    ],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Foldseek target database, or a FASTA/structure set it can build from."
  }
]
```

**output_ports**

```json
[
  {
    "name": "hits",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "foldseek_hits.m8",
    "description": "One row per hit; alntmscore drives the IP gate."
  }
]
```

**output_schema**

```json
{}
```

**resources**

```json
{
  "cpus": 8,
  "memory_gb": 16,
  "walltime_minutes": 240,
  "cpus_evidence": "Verified on qm 2026-08-28 (foldseek 10.941cd33): `foldseek easy-search --help` lists `--threads INT  Number of CPU-cores used (all by default)` under `common:`, and its printed default was 64 - the login node's nproc, not the reservation. The command now passes --threads \"$BDA_CPUS\", which the renderer sets from the same number as -n and span[ptile], so 8 threads run on the 8 reserved slots."
}
```

命令摘要 SHA-256：`bc3466e693fa0672860039759ffa37dce8556439df6d2e573b6ee33514dee438`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--alignment-type", "--format-output", "--max-seqs", "--threads", "-e", "-maxdepth", "-name", "-type", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_CPUS", "BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "alignment_type", "evalue", "foldseek_target", "format_output", "max_seqs"]`。

输入适配器：`null`；输出解析器：`null`。

## 自动生成参数与可复现记录

| 项目 | 含义、生成方法与核对要求 |
|---|---|
| 最终 argv/config | 由上面的模式映射、端口文件和包装器默认共同产生；保存渲染后的最终版本，检查用户值是否被覆盖。命令摘要只标识文本，不证明参数得到消费。 |
| BDA_INPUT_DIR / BDA_OUTPUT_DIR | 每次任务 staging 输入/输出根目录；内部端口相对路径对应实际工件，不能填本机路径代替。 |
| BDA_CPUS / 资源 | 由资源声明及调度分配产生；CPU、GPU、内存、墙钟上限不是科学结果。资源与程序线程数需一致。 |
| seed / model / sample / tag | 由所用 wrapper/模型分配。每项保存实际值与对应输出；没有固定种子接口时明确不可由此配置复现。tag/数字是身份元数据，不是序列。 |
| 链、残基与结构映射 | 记录输入至输出的链 ID、残基编号、裁剪、重编号与修饰残基处理。由实际结构/映射文件提取，不能从文件名猜。 |
| 生效配置、权重和数据库 | 保存完整配置、输入 SHA-256、实际软件版本/commit、权重/参考库标识及哈希；当前未自动生成的字段标“待补采集”。 |
| 缺失结果 | 区分未请求、未支持、未计算、计算失败和解析失败。无结果不写 0。 |

## 生成的结果参数

| 输出 | 定义 | 单位/尺度 | 解释与限制 | 依据 |
|---|---|---|---|---|
| query,target | 输入和命中数据库记录 ID；不是序列 | 无量纲 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| fident | 比对位点中的序列一致性比例 | 0–1 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| alntmscore | 按较短对齐跨度归一化的 TM-score；固定实现使用 min(qEndPos−qStartPos, dbEndPos−dbStartPos)，不等同于无缺口比对残基对数或全长归一化 | 0–1 | 不是全长相似性或专利自由实施判断；历史上游版本有该字段问题，应以固定版本输出核验 | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [convertalis](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/src/strucclustutils/structureconvertalis.cpp) |
| evalue | 默认结构局部搜索的统计显著性；TMalign 模式此列为两种归一化 TM-score 的平均；上游 alignment-type=3 LoLalign 时该列为归一化 LoLscore，部署支持待核验 | 依 alignment_type | 越小并不在所有模式都越好；必须保存 alignment_type | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| prob | Foldseek 估计的同源性概率 | 0–1 | 是同源性模型输出，不是受体结合概率 | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| qtmscore,ttmscore | 分别按查询/目标全长归一化的 TM-score | 0–1 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| foldseek_hits.m8 | 按 format_output 指定顺序生成的结果表 | 按列定义 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 现有界面把 max_seqs 叫 Max hits，会误导为最终条数，应按预筛上限理解。
- 旧 help 将 TM < 0.40 当 IP gate；结构分数不能单独证明新颖性或知识产权结论。
- reference_db 按目录首个文件猜前缀，不能保证配套数据库文件齐全或选择正确；需要显式前缀与完整性校验。
- createdb/聚类/多链模式未接入当前 BDA；不能仅改参数启用。
- 旧结果解析器须按 alignment_type 和列设置复核；自定义输出列未验证前不得用于自动筛选。

## 易错点


## 来源与版本

- [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：本次实时 BDA 声明；不是上游功能或运行成功证明；commit `未固定/本地快照`；读取 2026-09-15。
- [upstream](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/README.md)：功能与参数定义；commit `e1a766e82d6e3049471fcbd647852f162960a182`；读取 2026-09-15。
- [convertalis](https://github.com/steineggerlab/foldseek/blob/e1a766e82d6e3049471fcbd647852f162960a182/src/strucclustutils/structureconvertalis.cpp)：alntmscore 实际归一化实现；commit `e1a766e82d6e3049471fcbd647852f162960a182`；读取 2026-09-15。
