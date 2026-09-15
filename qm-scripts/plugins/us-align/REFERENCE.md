# US-align — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

比较结构的几何相似性；当前批量入口将目录中查询结构逐一比到一个参考。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/us-align.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 20260527 | true | valid | proven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 单体批量结构比对 (`batch`)

目录查询结构对单个参考。BDA 接入：`declared`。

输入：structures: PDB/mmCIF; reference: 一个参考结构

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "tmscore_mode": 0,
  "outfmt": 2
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 按残基编号叠合 (`index`)

针对编号已对应的结构比较。BDA 接入：`declared`。

输入：编号对应的两个结构

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "tmscore_mode": 1,
  "outfmt": 2
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 寡聚复合体比对 (`complex`)

同时处理多链链映射。BDA 接入：`not_exposed`。

输入：两个多链复合物

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mm": 1,
  "ter": 1
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 柔性结构比对 (`flexible`)

上游带铰链的比对。BDA 接入：`not_exposed`。

输入：两个结构

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mm": 7
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 使用方法

1. 选择本页明确版本和功能模式，按模式绑定输入，核对链号、序列和原子完整性。
2. 输入参数后预览最终命令/生成配置；未映射字段不能视为生效，未接入模式需先补适配。
3. 运行条件验证后检查全部原始输出、失败样本和缺失值；保存所用版本、配置、输入输出哈希。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `tmscore_mode`

控制残基对应方式而非归一化长度：0 结构驱动比对；1 同残基编号；2 同编号且同链 ID；5 序列 glocal；6 优化链映射后同编号；7 链序列比对后整体叠合。

类型：`integer`；单位：无量纲；来源记录默认：`0`。

适用模式：batch, index

生成映射：`-TMscore`；BDA 别名：`["tmscore_mode"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `outfmt`

0 完整输出，1 紧凑 FASTA，2 制表符表，-1 完整但省略版本引用。BDA 收集表格时应保持 2。

类型：`integer`；单位：无量纲；来源记录默认：`2`。

适用模式：batch, index

生成映射：`-outfmt`；BDA 别名：`["outfmt"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `mm`

多体模式：0 单体；1 寡聚复合体；2 链对寡聚体；3 环形置换；4 多结构共识；5/6 非顺序；7 柔性。当前 BDA 没有对应字段。

类型：`integer`；单位：无量纲；来源记录默认：`未声明`。

适用模式：complex, flexible

生成映射：`-mm`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `ter`

决定读取哪些 MODEL/链：0 全部；1 首 MODEL 全链；2 首链；3 首链首 TER 段。mm=1/2 需 ter=0/1。

类型：`integer`；单位：无量纲；来源记录默认：`未声明`。

适用模式：complex

生成映射：`-ter`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `a`

额外报告的 TM-score 归一化选择，T/1 平均长度，F（默认）第二结构长度；显式 -a 0 不被该源码接受，-2 较长，-1 较短；不是 -TMscore。

类型：`string`；单位：无量纲；来源记录默认：`未声明`。

适用模式：batch, index, complex

生成映射：`-a`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `chain1`

指定结构 1 的链，可逗号分隔；输入链 ID 需保持一致。

类型：`string`；单位：无量纲；来源记录默认：`未声明`。

适用模式：complex

生成映射：`-chain1`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `chain2`

指定结构 2 的链，可逗号分隔；默认链策略可能只读首链。

类型：`string`；单位：无量纲；来源记录默认：`未声明`。

适用模式：complex

生成映射：`-chain2`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `m`

写入刚体叠合旋转和平移矩阵的路径；当前包装未请求生成。

类型：`string`；单位：文件；来源记录默认：`未声明`。

适用模式：batch, complex

生成映射：`-m`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `o`

叠合后结构输出前缀；当前包装未请求生成。

类型：`string`；单位：文件前缀；来源记录默认：`未声明`。

适用模式：batch, complex

生成映射：`-o`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `20260527`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| tmscore_mode | integer | 0 | {} |
| outfmt | integer | 2 | {} |

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
    "description": "Designs to compare."
  },
  {
    "name": "reference",
    "kind": "protein_structure",
    "accepts": [
      "target_structure",
      "structure"
    ],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Natural sweet protein to compare against (brazzein, MNEI, ...)."
  }
]
```

**output_ports**

```json
[
  {
    "name": "tmscores",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "usalign_tmscores.tsv",
    "description": "Pairwise TM-scores, one line per design."
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
  "cpus": 1,
  "memory_gb": 4,
  "walltime_minutes": 120,
  "cpus_evidence": "Single-threaded pairwise alignment."
}
```

命令摘要 SHA-256：`e011c2c325b3a0dabfe5c87a4b23b5cc006a1ff02a21c35eb2a81ff351ca3bea`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-TMscore", "-dir1", "-maxdepth", "-name", "-o", "-outfmt", "-printf", "-s", "-type", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "outfmt", "tmscore_mode", "usalign_dir", "usalign_ref"]`。

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
| TM1,TM2 | 按两个结构各自长度归一化的 TM-score；务必保留两种归一化 | 0–1 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| RMSD | 参与比对的代表原子（蛋白通常 Cα）叠合偏差 | Å | 不同残基对应和覆盖下不能直接比较；不是原子接触距离 | [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| Lali,L1,L2 | 比对长度和两结构参与读取的长度 | 残基数 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| ID1,ID2,IDali | 分别相对各结构及比对长度的序列一致性；具体列名读版本表头 | 0–1 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| usalign_tmscores.tsv | 批量结果；保存表头与查询/参考文件映射 | 按列定义 | 保留原始值；不作为结合亲和力证据 | [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| query.list | 本次参与批量比较的结构文件名列表 | 文件名 | 生成控制文件，不是序列 | [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- tmscore_mode 的旧 UI label/help 将残基对应策略误写为归一化；文档已纠正，运行字段仍按 -TMscore 消费。
- 当前包装没有 -mm/-ter/-chain1/-chain2，不能把默认单体输出当作完整受体复合物比对。
- outfmt 可变但输出收集预期表格；2 以外模式需单独适配解析器。
- 当前不输出 -m 矩阵或 -o 叠合结构；原子距离/方向角另需一致的受体对齐与链映射流程。

## 易错点


## 来源与版本

- bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：本次实时 BDA 声明；不是上游功能或运行成功证明；commit `未固定/本地快照`；读取 2026-09-15。
- [upstream](https://github.com/pylelab/USalign/blob/fcb0f9d921415a2095bc509975db7fc1e968af1d/USalign.cpp)：功能与参数定义；commit `fcb0f9d921415a2095bc509975db7fc1e968af1d`；读取 2026-09-15。
