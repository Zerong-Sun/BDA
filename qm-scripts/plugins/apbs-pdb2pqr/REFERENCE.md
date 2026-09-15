# APBS+PDB2PQR — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

从全原子结构准备 PQR 并计算连续介质静电势；当前入口是 PDB2PQR → APBS 单条流程。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/apbs-pdb2pqr.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| conda-forge-2026-08 | true | valid | proven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### PQR 准备与静电势 (`electrostatics`)

为可比构象生成电荷/半径与势场。BDA 接入：`declared`。

输入：structure: 一个全原子 PDB

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "forcefield": "AMBER",
  "keep_chain": true
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 指定 pH 质子化 (`ph`)

借助 PROPKA 设置质子化状态后求解。BDA 接入：`declared`。

输入：structure: 一个全原子 PDB

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "with_ph": 7.0
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 自定义 PB 网格/介质/盐条件 (`custom_pb`)

自定义 APBS .in 的网格和物理边界。BDA 接入：`not_exposed`。

输入：已准备 PQR; APBS 输入文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "pdie": 2.0,
  "sdie": 78.54
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 使用方法

1. 选择本页明确版本和功能模式，按模式绑定输入，核对链号、序列和原子完整性。
2. 输入参数后预览最终命令/生成配置；未映射字段不能视为生效，未接入模式需先补适配。
3. 运行条件验证后检查全部原始输出、失败样本和缺失值；保存所用版本、配置、输入输出哈希。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `forcefield`

PDB2PQR 分配原子电荷和半径使用的参数集；AMBER、CHARMM、PARSE 等以所装版本 --help 为准。

类型：`string`；单位：无量纲；来源记录默认：`AMBER`。

适用模式：按相应模式/版本映射检查

生成映射：`--ff`；BDA 别名：`["forcefield"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `with_ph`

指定 PROPKA 质子化处理的 pH；null 时包装器不追加该步骤，不应解释为显式求得 pH 7 的状态。

类型：`number`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`--titration-state-method propka --with-ph`；BDA 别名：`["with_ph"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `keep_chain`

保留 PQR 中链 ID，利于追溯输入结构；不保证下游所有输出都保留链信息。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：按相应模式/版本映射检查

生成映射：`--keep-chain`；BDA 别名：`["keep_chain"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `pdie`

溶质内部相对介电常数；仅可在自定义 APBS 输入中配置，当前 BDA 表单不暴露。

类型：`number`；单位：无量纲；来源记录默认：`未声明`。

适用模式：custom_pb

生成映射：`APBS ELEC pdie`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `sdie`

溶剂相对介电常数；比较时与温度、离子强度一起固定。

类型：`number`；单位：无量纲；来源记录默认：`未声明`。

适用模式：custom_pb

生成映射：`APBS ELEC sdie`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `conda-forge-2026-08`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| forcefield | string | AMBER | {} |
| with_ph | number | null | {} |
| keep_chain | boolean | true | {} |

**input_ports**

```json
[
  {
    "name": "structure",
    "kind": "protein_structure",
    "accepts": [
      "complex_structure",
      "candidate_structure",
      "predicted_structure",
      "structure"
    ],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Full-atom complex or monomer. Backbone-only designs are rejected: pdb2pqr rebuilds hydrogens, not missing side-chain heavy atoms."
  }
]
```

**output_ports**

```json
[
  {
    "name": "potential",
    "kind": "opaque",
    "artifact_type": "electrostatics_map",
    "filename_glob": "*.dx",
    "description": "Poisson-Boltzmann potential grid."
  },
  {
    "name": "pqr",
    "kind": "protein_structure",
    "artifact_type": "prepared_structure",
    "filename_glob": "*.pqr",
    "description": "Protonated structure with charges and radii."
  },
  {
    "name": "log",
    "kind": "opaque",
    "artifact_type": "run_log",
    "filename_glob": "apbs.log",
    "description": "APBS solver log, including the computed energies."
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
  "memory_gb": 16,
  "walltime_minutes": 240,
  "cpus_evidence": "pdb2pqr30 and apbs are invoked without any thread option in this command."
}
```

命令摘要 SHA-256：`7ce9c64ed2eca8f1b9016f143f70b0b00872027562a8b54abc116f4a1dd9117e`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--apbs-input", "--ff", "--titration-state-method", "--with-ph", "-name", "-qE", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "apbs_pdb", "apbs_stem", "forcefield", "keep_chain", "with_ph"]`。

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
| *.pqr | 原子坐标及电荷、半径；核对原子/残基变化和质子化 | Å；电荷 e；半径 Å | 保留原始值；不作为结合亲和力证据 | [upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| *.in | PDB2PQR 自动生成的 APBS 配置：网格点数/中心/边长、介电常数、温度及离子定义 | 各键单独定义 | 必须随势场一起保留，不能仅保存 DX；实际值由该次生成文件读取 | [upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| *.dx | 空间静电势网格；write pot 使用 kBT/e | kBT/e | 不是总结合自由能；比较时统一网格、温度、介质和盐条件 | [potential](https://apbs.readthedocs.io/en/latest/using/input/old/elec/write.html) |
| apbs.log | 求解日志和可能的能量/收敛条目 | 字段依 APBS 版本 | 日志能量需注明计算条件与对应计算块，不从势场颜色推导亲和力 | [upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: dime | 有限差分网格每维点数；需满足所用多重网格层级约束 | 整数三元组 | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: cglen / fglen | 粗/细网格三维物理边长；决定覆盖范围与网格间距 | Å 三元组 | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: cgcent / fgcent | 粗/细网格中心，可由分子 mol 编号或显式坐标指定 | Å 或 mol 选择 | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: pdie / sdie | 溶质/溶剂相对介电常数；与力场和溶剂假设共同影响势场 | 无量纲 | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: temp | 计算温度；决定 kBT/e 的实际电势换算 | K | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: ion charge / conc / radius | 移动离子电荷数、体相浓度及离子半径；逐离子物种记录 | e / M / Å | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: bcfl / lpbe / npbe | 边界条件以及线性/非线性 Poisson–Boltzmann 方程选择 | 枚举 | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: srfm / srad / swin / chgm | 介电表面定义、溶剂探针半径、表面平滑窗口及原子电荷网格分配方式 | 枚举 / Å / Å / 枚举 | 从本次实际 .in 提取；当前 BDA 未提供独立可调表单，不推定固定默认值。 | [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: method mg-auto / mg-para | 自动聚焦/并行聚焦网格计算方式，生成器可能根据内存估计选择 | 枚举 | 保留实际 .in；当前 BDA 不额外转发这些表单参数，不从工具名称推断值。 | [inputgen](https://pdb2pqr.readthedocs.io/en/latest/_modules/pdb2pqr/inputgen.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: mol | 本计算块使用 READ 部分中哪一个 PQR 分子 | 从 1 开始的分子编号 | 保留实际 .in；当前 BDA 不额外转发这些表单参数，不从工具名称推断值。 | [inputgen](https://pdb2pqr.readthedocs.io/en/latest/_modules/pdb2pqr/inputgen.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: sdens | 用于部分表面模型的球面离散点密度；是否使用由 srfm 决定 | 点/Å² | 保留实际 .in；当前 BDA 不额外转发这些表单参数，不从工具名称推断值。 | [inputgen](https://pdb2pqr.readthedocs.io/en/latest/_modules/pdb2pqr/inputgen.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: calcenergy / calcforce | 是否以及以 total/comps 等形式输出能量/力的控制；取值和单位需查实际日志 | 枚举 | 保留实际 .in；当前 BDA 不额外转发这些表单参数，不从工具名称推断值。 | [inputgen](https://pdb2pqr.readthedocs.io/en/latest/_modules/pdb2pqr/inputgen.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| generated .in: write pot dx / print elecEnergy | 势场文件类型/输出前缀和电势能计算块组合表达式 | 输出控制 | 保留实际 .in；当前 BDA 不额外转发这些表单参数，不从工具名称推断值。 | [inputgen](https://pdb2pqr.readthedocs.io/en/latest/_modules/pdb2pqr/inputgen.html), bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 当前仅取 structure 目录排序后的第一个 PDB；多文件应拆开提交，否则不能声称全部计算。
- 缺少显式网格、介电常数、盐强度和温度表单；派生 .in 文件未列为独立输出端口，需补归档收集后支持严格比较。
- 内置侧链原子 grep 仅能发现部分 backbone-only 输入，不能代替全原子/配体参数完整性检查。

## 易错点

- 同一颜色/势值不证明结合；质子化状态与构象均会改变结果。

## 来源与版本

- bda（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：本次实时 BDA 声明；不是上游功能或运行成功证明；commit `未固定/本地快照`；读取 2026-09-15。
- [upstream](https://pdb2pqr.readthedocs.io/en/latest/using/index.html)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
- [potential](https://apbs.readthedocs.io/en/latest/using/input/old/elec/write.html)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
- [apbs_input](https://apbs.readthedocs.io/en/latest/using/input/old/elec/index.html)：APBS ELEC 物理参数、网格与边界定义；commit `未固定/本地快照`；读取 2026-09-15。
- [inputgen](https://pdb2pqr.readthedocs.io/en/latest/_modules/pdb2pqr/inputgen.html)：自动生成 APBS 网格/介质控制文件的逻辑；实际默认以安装版本运行文件为准；commit `未固定/本地快照`；读取 2026-09-15。
