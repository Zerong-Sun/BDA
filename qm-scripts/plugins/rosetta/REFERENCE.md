# Rosetta — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

评分、Relax、界面分析、对接与稳定性 ΔΔG；不是时间分辨的分子动力学。新版 2024.09-bda.1 使用明确的 7 模式与 45 参数。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/rosetta.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 2024.09 | true | unknown | unproven | false |
| 2024.09-bda.1 | true | valid | unproven | false |
| 2026.06 | true | unknown | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### score_jd2 (`score_jd2`)

单点评分：对输入结构评分，不进行 Relax，不等于界面结合能。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "score_jd2"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### relax (`relax`)

FastRelax：侧链重排与局部最小化；不是纳秒分子动力学。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "relax"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### InterfaceAnalyzer (`InterfaceAnalyzer`)

蛋白–蛋白界面分析：已有复合物的界面能、埋藏面积和氢键等。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "InterfaceAnalyzer"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### relax_interface (`relax_interface`)

先用 relax 优化并保存坐标，再对每个优化后的复合物运行 InterfaceAnalyzer。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "relax_interface"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### docking_protocol (`docking_protocol`)

RosettaDock：蛋白–蛋白刚体/侧链采样；需要已有组装与明确伙伴链。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "docking_protocol"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### cartesian_ddg (`cartesian_ddg`)

Cartesian ΔΔG：匹配 WT/突变体的折叠稳定性分数差；不是结合 ΔΔG。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "cartesian_ddg"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### rosetta_scripts (`rosetta_scripts`)

使用上传的 XML 协议；XML 的 mover/filter 参数与输出由该协议定义。。BDA 接入：`declared`。

输入：structure: PDB；按模式额外提供 aux 文件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "application": "rosetta_scripts"
}
```

输出检查：检查退出状态、日志、非空输出及参数实际读取记录

限制：此为参数片段，输入文件和运行环境需独立绑定；未暴露模式不能直接在当前 BDA 运行

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

## 使用方法

1. 选择本页明确版本和功能模式，按模式绑定输入，核对链号、序列和原子完整性。
2. 输入参数后预览最终命令/生成配置；未映射字段不能视为生效，未接入模式需先补适配。
3. 运行条件验证后检查全部原始输出、失败样本和缺失值；保存所用版本、配置、输入输出哈希。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `application`

选择计算阶段；不同模式的分数不能混作同一种结合自由能。

类型：`string`；单位：无量纲；来源记录默认：`score_jd2`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["application"]`。

约束与版本差异：{"enum": ["score_jd2", "relax", "InterfaceAnalyzer", "relax_interface", "docking_protocol", "cartesian_ddg", "rosetta_scripts"]}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `nstruct`

每个输入、每个独立重复生成的 decoy 数；cartesian_ddg 使用 ddg_iterations，不使用本参数。

类型：`integer`；单位：个；来源记录默认：`1`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, rosetta_scripts

生成映射：`-nstruct`；BDA 别名：`["nstruct"]`。

约束与版本差异：{"maximum": 10000, "minimum": 1}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `replicates`

分别启动进程并使用不同随机种子；各重复保留原始结果，不只保存最优值。

类型：`integer`；单位：次；来源记录默认：`1`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["replicates"]`。

约束与版本差异：{"maximum": 100, "minimum": 1}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `seed`

启用 constant_seed；每个输入/重复的种子递增。固定种子利于复现，不证明采样收敛。

类型：`integer`；单位：无量纲；来源记录默认：`111111`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-run:constant_seed / -run:jran`；BDA 别名：`["seed"]`。

约束与版本差异：{"maximum": 2000000000, "minimum": 1}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `score_weights`

所有比较对象使用同一权重。Cartesian 模式必须选择 *_cart；REU 不能直接当 kcal/mol。

类型：`string`；单位：Rosetta 权重集；来源记录默认：`ref2015`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-score:weights`；BDA 别名：`["score_weights"]`。

约束与版本差异：{"enum": ["ref2015", "ref2015_cart", "beta_nov16", "beta_nov16_cart"]}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `out_scorefile`

各输入/重复独立目录内的 .sc 文件名；不接受目录或路径穿越。

类型：`string`；单位：无量纲；来源记录默认：`score.sc`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-out:file:scorefile`；BDA 别名：`["out_scorefile"]`。

约束与版本差异：{"pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]*\\.sc$"}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ex1`

扩大侧链 χ1 rotamer 采样；增加打包计算量，不是独立结构重复。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-ex1`；BDA 别名：`["ex1"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ex2`

扩大侧链 χ2 rotamer 采样；仅在协议实际执行 packing 时影响采样。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-ex2`；BDA 别名：`["ex2"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `use_input_sc`

将输入侧链构象纳入 packing rotamer 候选集合。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-use_input_sc`；BDA 别名：`["use_input_sc"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ignore_unrecognized_res`

默认关闭。开启可能删除糖基、配体或特殊残基，改变体系；须检查运行日志和保存结构。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-ignore_unrecognized_res`；BDA 别名：`["ignore_unrecognized_res"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `extra_res_fa`

aux 端口下的 .params 相对文件名；为非标准残基提供全原子参数，不自动生成小分子参数。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts

生成映射：`-in:file:extra_res_fa`；BDA 别名：`["extra_res_fa"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `extra_res_cen`

aux 端口下的 .params 文件；对接低分辨率阶段使用非标准残基时需匹配 centroid 参数。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：docking_protocol, rosetta_scripts

生成映射：`-in:file:extra_res_cen`；BDA 别名：`["extra_res_cen"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `constraints_file`

aux 端口下的 Rosetta .cst 文件；其中残基编号须对应输入 pose。约束能改变评分，不能与无约束能量混排。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：score_jd2, relax, relax_interface, docking_protocol, rosetta_scripts

生成映射：`-constraints:cst_fa_file`；BDA 别名：`["constraints_file"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `constraint_weight`

仅在提供 constraints_file 时传入；不等同于 Relax 自动坐标约束权重。

类型：`number`；单位：权重；来源记录默认：`1.0`。

适用模式：score_jd2, relax, relax_interface, docking_protocol, rosetta_scripts

生成映射：`-constraints:cst_fa_weight`；BDA 别名：`["constraint_weight"]`。

约束与版本差异：{"maximum": 1000, "minimum": 0}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `pack_input`

分析前是否对输入界面进行侧链 packing；这是评分内部分支，不会覆盖保存的 Relax 坐标。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`-pack_input`；BDA 别名：`["pack_input"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `pack_separated`

计算 dG_separated 时，是否重排分離伙伴暴露界面的侧链。与 pack_input 分开控制。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`-pack_separated`；BDA 别名：`["pack_separated"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `compute_packstat`

启用有随机成分的 packstat；大界面可能较慢。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`-compute_packstat`；BDA 别名：`["compute_packstat"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `interface`

必填，例如 AB_C 表示受体 A/B 与蛋白 C；天然双链配体可为 AB_CD。使用输入文件实际链标识，不能混淆 mmCIF label/auth ID。

类型：`string`；单位：无量纲；来源记录默认：``。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`-interface`；BDA 别名：`["interface"]`。

约束与版本差异：{"pattern": "^$\|^[A-Za-z0-9]+_[A-Za-z0-9]+$"}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `packstat_oversample`

仅 compute_packstat=true 时生效；增加采样以降低随机波动。

类型：`integer`；单位：倍；来源记录默认：`100`。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`-packstat:oversample`；BDA 别名：`["packstat_oversample"]`。

约束与版本差异：{"maximum": 1000, "minimum": 1}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax_repeats`

一个 FastRelax 轨迹内的打包/最小化循环；不同于 nstruct 和独立重复。

类型：`integer`；单位：次；来源记录默认：`5`。

适用模式：relax, relax_interface

生成映射：`-relax:default_repeats`；BDA 别名：`["relax_repeats"]`。

约束与版本差异：{"maximum": 50, "minimum": 1}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax_cartesian`

使用笛卡尔坐标最小化；必须选 ref2015_cart 或 beta_nov16_cart。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：relax, relax_interface

生成映射：`-relax:cartesian`；BDA 别名：`["relax_cartesian"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `constrain_start`

由 relax 可执行文件建立起始坐标约束，减少大幅漂移；不作为 XML FastRelax 的通用开关。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：relax, relax_interface

生成映射：`-relax:constrain_relax_to_start_coords`；BDA 别名：`["constrain_start"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ramp_constraints`

配合 constrain_start。false 显式传给 Rosetta，在优化中保留约束；true 渐弱。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：relax, relax_interface

生成映射：`-relax:ramp_constraints`；BDA 别名：`["ramp_constraints"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `movemap_file`

aux 端口下的 MoveMap 文件，控制骨架/侧链/jump 可动性。默认未提供时沿用该 relax 构建的自由度；不是受体自动固定。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：relax, relax_interface

生成映射：`-in:file:movemap`；BDA 别名：`["movemap_file"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax_script`

aux 端口下的 Relax script；覆盖内部优化流程，需与 repeats/约束策略一起审阅。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：relax, relax_interface

生成映射：`-relax:script`；BDA 别名：`["relax_script"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `dock_partners`

必填，例如 AB_C。对接分组与界面分析分组语法类似，但这是 docking:partners。

类型：`string`；单位：无量纲；来源记录默认：``。

适用模式：docking_protocol

生成映射：`-docking:partners`；BDA 别名：`["dock_partners"]`。

约束与版本差异：{"pattern": "^$\|^[A-Za-z0-9]+_[A-Za-z0-9]+$"}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `dock_search`

local 从现有姿态附近扰动；global 随机化两个伙伴取向，须充分采样；都不是物理 MD。

类型：`string`；单位：无量纲；来源记录默认：`local`。

适用模式：docking_protocol

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["dock_search"]`。

约束与版本差异：{"enum": ["local", "global"]}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `dock_translation`

local 模式 dock_pert 的平移幅度；不能据此推导结合距离或动力学。

类型：`number`；单位：Å；来源记录默认：`3.0`。

适用模式：docking_protocol

生成映射：`-docking:dock_pert [translation rotation]`；BDA 别名：`["dock_translation"]`。

约束与版本差异：{"maximum": 100, "minimum": 0}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `dock_rotation`

local 模式 dock_pert 的旋转幅度。

类型：`number`；单位：度；来源记录默认：`8.0`。

适用模式：docking_protocol

生成映射：`-docking:dock_pert [translation rotation]`；BDA 别名：`["dock_rotation"]`。

约束与版本差异：{"maximum": 180, "minimum": 0}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `dock_local_refine`

跳过低分辨率搜索，用于已有可信近邻姿态；不能与 global 搜索组合。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：docking_protocol

生成映射：`-docking:docking_local_refine`；BDA 别名：`["dock_local_refine"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `native_file`

aux 中用于对接 RMSD 的参考结构，不自动作为位置约束；必须具有匹配的链/残基映射。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：docking_protocol

生成映射：`-in:file:native`；BDA 别名：`["native_file"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg_mut_file`

cartesian_ddg 必填的 aux mut_file。使用 Rosetta pose 编号；需要 WT 与突变定义校验，不能用 PDB 编号直接替代。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：cartesian_ddg

生成映射：`-ddg:mut_file`；BDA 别名：`["ddg_mut_file"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg_iterations`

每个突变定义的采样次数，不是 nstruct；输出的是协议相关折叠稳定性差分。

类型：`integer`；单位：次；来源记录默认：`3`。

适用模式：cartesian_ddg

生成映射：`-ddg:iterations`；BDA 别名：`["ddg_iterations"]`。

约束与版本差异：{"maximum": 100, "minimum": 1}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg_cartesian`

本插件只支持 Cartesian 协议，必须保持 true。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：cartesian_ddg

生成映射：`-ddg:cartesian`；BDA 别名：`["ddg_cartesian"]`。

约束与版本差异：{"enum": [true]}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg_bb_neighbors`

围绕突变位置允许处理的序列邻居范围；不是空间半径。

类型：`integer`；单位：残基数；来源记录默认：`1`。

适用模式：cartesian_ddg

生成映射：`-ddg:bbnbrs`；BDA 别名：`["ddg_bb_neighbors"]`。

约束与版本差异：{"maximum": 10, "minimum": 0}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg_dump_pdbs`

保存 WT/突变模型供原子级核查；关闭则仅保存原始分数与日志。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：cartesian_ddg

生成映射：`-ddg:dump_pdbs`；BDA 别名：`["ddg_dump_pdbs"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `fa_max_dis`

Cartesian DDG 推荐协议的相互作用截断；须与 WT 预先 Cartesian Relax 的设置一致。

类型：`number`；单位：Å；来源记录默认：`9.0`。

适用模式：relax, relax_interface, InterfaceAnalyzer, cartesian_ddg

生成映射：`-fa_max_dis`；BDA 别名：`["fa_max_dis"]`。

约束与版本差异：{"maximum": 20, "minimum": 3}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `parser_protocol`

rosetta_scripts 必填，aux 下的 XML 文件。平台不会猜测 XML 的科学阶段；生成时验证 XML 可解析，完整 schema 由实际 Rosetta 构建验证。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：rosetta_scripts

生成映射：`-parser:protocol`；BDA 别名：`["parser_protocol"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `parser_script_vars`

空白分隔的 name=value；作为独立 argv 值传入，不运行 shell。所有变量名必须在 XML 的 %%name%% 中出现，所有占位符必须有值。

类型：`string`；单位：无量纲；来源记录默认：``。

适用模式：rosetta_scripts

生成映射：`-parser:script_vars`；BDA 别名：`["parser_script_vars"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `xml_expected_output`

score 要求至少 nstruct 个有效 SCORE 行；structure 还要求对应数量 PDB。自定义协议的完整科学输出仍由协议作者解释。

类型：`string`；单位：无量纲；来源记录默认：`score`。

适用模式：rosetta_scripts

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["xml_expected_output"]`。

约束与版本差异：{"enum": ["score", "structure"]}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `geometry_contacts`

从同一被评分的复合物坐标提取重原子接触和逐残基对最短距离；内部 packing 的临时姿态不在此几何文件中。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["geometry_contacts"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `contact_cutoff`

输出此半径内的全部跨界面重原子对及其距离；没有接触不等于证明不结合。

类型：`number`；单位：Å；来源记录默认：`4.5`。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["contact_cutoff"]`。

约束与版本差异：{"maximum": 10, "minimum": 2}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `receptor_axis`

可选，两枚 CA 的 chain:residue 标识，逗号分隔，如 A:10,A:100；方向从第一个指向第二个。须与 binder_axis 一起提供。

类型：`string`；单位：PDB链:残基编号；来源记录默认：``。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["receptor_axis"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `binder_axis`

可选，两枚 CA 标识，如 C:1,C:50。报告此有向轴与受体轴的夹角；不是未经定义的“整体结合角”。

类型：`string`；单位：PDB链:残基编号；来源记录默认：``。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["binder_axis"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `geometry_reference_file`

可选，aux 下同链分组的参考 PDB；计算其接触、质心距离与相同锚点定义夹角供比较。参考应记录是实验复合物还是对接假说；不同支架的接触编号不能直接当同源位点。

类型：`string`；单位：文件；来源记录默认：``。

适用模式：InterfaceAnalyzer, relax_interface

生成映射：`BDA 控制参数，不直接作为 Rosetta flag`；BDA 别名：`["geometry_reference_file"]`。

约束与版本差异：{}

依据：[workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `s`

Rosetta 输入 PDB 路径；BDA 新版由 structure 端口 staging 决定，不能沿用本机绝对路径。

类型：`artifact_ref`；单位：无量纲；来源记录默认：``。

适用模式：按相应模式/版本映射检查

生成映射：`s`；BDA 别名：`["s"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `parser:protocol`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。rosetta_scripts 必填，aux 下的 XML 文件。平台不会猜测 XML 的科学阶段；生成时验证 XML 可解析，完整 schema 由实际 Rosetta 构建验证。 新版对应键：parser_protocol。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`parser:protocol`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `parser:script_vars`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。空白分隔的 name=value；作为独立 argv 值传入，不运行 shell。所有变量名必须在 XML 的 %%name%% 中出现，所有占位符必须有值。 新版对应键：parser_script_vars。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`parser:script_vars`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `score:weights`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。所有比较对象使用同一权重。Cartesian 模式必须选择 *_cart；REU 不能直接当 kcal/mol。 新版对应键：score_weights。

类型：`string`；单位：无量纲；来源记录默认：`ref2015`。

适用模式：按相应模式/版本映射检查

生成映射：`score:weights`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `resfile`

控制各残基允许氨基酸/重排策略的 Rosetta resfile；只有协议读取时生效，新插件不以通用 resfile 表单承诺任意设计。

类型：`artifact_ref`；单位：无量纲；来源记录默认：``。

适用模式：按相应模式/版本映射检查

生成映射：`resfile`；BDA 别名：`["resfile"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `constraints:cst_fa_file`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。aux 端口下的 Rosetta .cst 文件；其中残基编号须对应输入 pose。约束能改变评分，不能与无约束能量混排。 新版对应键：constraints_file。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`constraints:cst_fa_file`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `out:path:all`

Rosetta 全部输出的目录；新版按输入/重复隔离生成，禁止不同任务共用目录。

类型：`string`；单位：无量纲；来源记录默认：`output`。

适用模式：按相应模式/版本映射检查

生成映射：`out:path:all`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `out:file:scorefile`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。各输入/重复独立目录内的 .sc 文件名；不接受目录或路径穿越。 新版对应键：out_scorefile。

类型：`string`；单位：无量纲；来源记录默认：`score.sc`。

适用模式：按相应模式/版本映射检查

生成映射：`out:file:scorefile`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `out:suffix`

输出结构和 tag 后缀，用于区分样本；不改变氨基酸序列。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`out:suffix`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `beta`

使用 beta 权重相关设置的旧开关；不可与显式 score:weights 混用推断最终权重，需看 scorefile。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`beta`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `overwrite`

允许覆盖既有 Rosetta 输出文件；复现实验应使用新任务目录避免覆盖证据。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`overwrite`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `renumber_pdb`

写 PDB 时重新编号残基，改变编号映射而不是序列；与输入和参考比较前保留映射。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`renumber_pdb`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `per_chain_renumbering`

各链独立开始 PDB 残基编号；只有结合实际输出编号选项才有意义。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`per_chain_renumbering`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `constant_seed`

启用固定随机种子以便复现，需同时记录 jran；新版统一由 seed 控制。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`constant_seed`；BDA 别名：`["constant_seed"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `jran`

固定伪随机种子值；新版为每输入和独立重复生成不同 seed。

类型：`integer`；单位：无量纲；来源记录默认：`1111111`。

适用模式：按相应模式/版本映射检查

生成映射：`jran`；BDA 别名：`["jran"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax:constrain_relax_to_start_coords`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。由 relax 可执行文件建立起始坐标约束，减少大幅漂移；不作为 XML FastRelax 的通用开关。 新版对应键：constrain_start。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`relax:constrain_relax_to_start_coords`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax:ramp_constraints`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。配合 constrain_start。false 显式传给 Rosetta，在优化中保留约束；true 渐弱。 新版对应键：ramp_constraints。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`relax:ramp_constraints`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax:script`

选择或给出 Relax 步骤脚本；不同脚本改变重排/最小化流程和约束方案。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`relax:script`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax:default_repeats`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。一个 FastRelax 轨迹内的打包/最小化循环；不同于 nstruct 和独立重复。 新版对应键：relax_repeats。

类型：`integer`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`relax:default_repeats`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `packing:repack_only`

限制为侧链重排而不更改序列身份；需协议真的执行 packing，不能仅设置字段宣称生效。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`packing:repack_only`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `mute`

关闭指定 Rosetta tracer 的日志；可能隐藏诊断信息，首轮验证不宜全静音。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`mute`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `unmute`

启用指定 tracer 日志，用于检查协议阶段和参数读取。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`unmute`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `database`

Rosetta 化学/打分数据库目录；需与可执行版本匹配，与搜索结构参考库不同。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`database`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `in:file:extra_res_fa`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。aux 端口下的 .params 相对文件名；为非标准残基提供全原子参数，不自动生成小分子参数。 新版对应键：extra_res_fa。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`in:file:extra_res_fa`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg:iterations`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。每个突变定义的采样次数，不是 nstruct；输出的是协议相关折叠稳定性差分。 新版对应键：ddg_iterations。

类型：`integer`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`ddg:iterations`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg:dump_pdbs`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。保存 WT/突变模型供原子级核查；关闭则仅保存原始分数与日志。 新版对应键：ddg_dump_pdbs。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`ddg:dump_pdbs`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `ddg:cartesian`

旧配置中的 Cartesian 开关；固定 cartesian_ddg 可执行程序及 *_cart 权重才是新版入口，不假设所有应用接受此键。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`ddg:cartesian`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:partners`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。必填，例如 AB_C。对接分组与界面分析分组语法类似，但这是 docking:partners。 新版对应键：dock_partners。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:partners`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking_local_refine`

请求局部高分辨率对接 refinement；对应新版 dock_local_refine，仍需指定正确初始伙伴位置。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking_local_refine`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:randomize1`

全局初始对接随机化伙伴 1 的朝向；新版通过 dock_search 模式控制，不能当作MD。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:randomize1`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:randomize2`

全局初始对接随机化伙伴 2 的朝向；会改变初始位姿分布。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:randomize2`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:spin`

绕伙伴分离轴随机旋转对接伙伴的初始化设置，不能单独表示自由方向全局搜索。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:spin`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:dock_pert`

刚体扰动幅度，通常由平移 Å 和旋转度数组成；新版拆为 dock_translation 和 dock_rotation。

类型：`list`；单位：[Å, 度]；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:dock_pert`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:docking_centroid_inner_cycles`

低分辨率 centroid 对接的内层采样次数；改变计算预算，非 MD 时间步。

类型：`integer`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:docking_centroid_inner_cycles`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:sc_min`

启用对接侧链最小化；实际阶段取决于所用 docking 协议。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:sc_min`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:norepack1`

禁止伙伴组 1 的侧链 packing；不等于固定全部受体自由度，骨架/侧链最小化和刚体 jump 需独立控制。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:norepack1`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `docking:norepack2`

禁止伙伴组 2 的侧链重排，会改变界面采样自由度。

类型：`bool`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`docking:norepack2`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `in:file:native`

用于比较的参考/native PDB；仅有文件不意味着自动计算所有 RMSD/接触或角度。

类型：`string`；单位：无量纲；来源记录默认：`null`。

适用模式：按相应模式/版本映射检查

生成映射：`in:file:native`；BDA 别名：`[]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax_constrain_to_start_coords`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。由 relax 可执行文件建立起始坐标约束，减少大幅漂移；不作为 XML FastRelax 的通用开关。 新版对应键：constrain_start。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：按相应模式/版本映射检查

生成映射：`relax_constrain_to_start_coords`；BDA 别名：`["relax_constrain_to_start_coords"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `relax_ramp_constraints`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。配合 constrain_start。false 显式传给 Rosetta，在优化中保留约束；true 渐弱。 新版对应键：ramp_constraints。

类型：`boolean`；单位：无量纲；来源记录默认：`false`。

适用模式：按相应模式/版本映射检查

生成映射：`relax_ramp_constraints`；BDA 别名：`["relax_ramp_constraints"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `cst_fa_file`

历史 CLI/表单键的语义对照，不是新版自动接受的别名；新版 normalize 会拒绝未声明旧键。aux 端口下的 Rosetta .cst 文件；其中残基编号须对应输入 pose。约束能改变评分，不能与无约束能量混排。 新版对应键：constraints_file。

类型：`artifact_ref`；单位：无量纲；来源记录默认：``。

适用模式：按相应模式/版本映射检查

生成映射：`cst_fa_file`；BDA 别名：`["cst_fa_file"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `out_suffix`

输出结构和 tag 后缀，用于区分样本；不改变氨基酸序列。

类型：`string`；单位：无量纲；来源记录默认：``。

适用模式：按相应模式/版本映射检查

生成映射：`out_suffix`；BDA 别名：`["out_suffix"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `protocol`

2026.06 占位表单的协议选择（interface_analyzer/fast_relax/relax_then_analyze）；命令仍读取 application，不消费本键。

类型：`string`；单位：无量纲；来源记录默认：`interface_analyzer`。

适用模式：按相应模式/版本映射检查

生成映射：`protocol`；BDA 别名：`["protocol"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `score_function`

2026.06 占位表单的权重选择；命令实际读取 score_weights，本键没有映射，不能认为选择已生效。

类型：`string`；单位：无量纲；来源记录默认：`beta_nov16`。

适用模式：按相应模式/版本映射检查

生成映射：`score_function`；BDA 别名：`["score_function"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

### `compute_sap`

2026.06 占位表单的 SAP 计算请求；未找到该命令对应计算步骤，不能宣称会生成 SAP。

类型：`boolean`；单位：无量纲；来源记录默认：`true`。

适用模式：按相应模式/版本映射检查

生成映射：`compute_sap`；BDA 别名：`["compute_sap"]`。

约束与版本差异：按所选版本检查；上游扩展键不自动进入 BDA 命令

依据：[rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list), [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [workbench](../../../qm-scripts/plugins/rosetta/options.json)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `2024.09`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| application | enum | rosetta_scripts | {"options": ["rosetta_scripts", "relax", "InterfaceAnalyzer", "cartesian_ddg"]} |
| s | artifact_ref |  | {} |
| parser_protocol | artifact_ref |  | {} |
| nstruct | integer | 1 | {} |
| score_weights | enum | ref2015 | {"options": ["ref2015", "beta_nov16", "beta_cart", "talaris2014"]} |
| interface | string | A_B | {} |
| ex1 | boolean | true | {} |
| ex2 | boolean | true | {} |
| relax_constrain_to_start_coords | boolean | true | {} |
| relax_ramp_constraints | boolean | false | {} |
| relax_script | enum | default | {"options": ["default", "MonomerRelax2019", "InterfaceRelax2019", "always_constrained_relax_script"]} |
| parser_script_vars | string |  | {} |
| resfile | artifact_ref |  | {} |
| cst_fa_file | artifact_ref |  | {} |
| out_suffix | string |  | {} |
| out_scorefile | string | score.sc | {} |
| constant_seed | boolean | false | {} |
| jran | integer | 1111111 | {} |

**input_ports**

```json
[
  {
    "name": "s",
    "kind": "protein_structure",
    "accepts": [
      "backbone_set",
      "candidate_complex",
      "candidate_structure",
      "complex_structure",
      "predicted_structure",
      "relaxed_structure",
      "structure",
      "target_structure"
    ],
    "content_types": [
      "chemical/x-pdb",
      "chemical/x-mmcif"
    ],
    "required": true,
    "multiple": true,
    "description": "PDB structures staged for Rosetta's -in:file input."
  },
  {
    "name": "parser_protocol",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "RosettaScripts XML. XML protocol for rosetta_scripts; omit for standalone relax/interface tools. (from field 'parser:protocol')"
  },
  {
    "name": "resfile",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Resfile. Residue-level design/repacking directives. (from field 'resfile')"
  },
  {
    "name": "constraints_cst_fa_file",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Constraint file. Full-atom constraint file. (from field 'constraints:cst_fa_file')"
  }
]
```

**output_ports**

```json
[
  {
    "name": "relaxed_structure",
    "kind": "protein_structure",
    "artifact_type": "relaxed_structure",
    "filename_glob": "*",
    "description": "Relaxed output models."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Rosetta and interface metrics."
  },
  {
    "name": "interface_metrics",
    "kind": "tabular",
    "artifact_type": "interface_metrics",
    "filename_glob": "*",
    "description": "Structured interface metric JSON."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "relaxed_structure",
      "artifact_types": [
        "relaxed_structure"
      ],
      "required": false,
      "many": true,
      "help": "Relaxed output models."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": true,
      "many": false,
      "help": "Rosetta and interface metrics."
    },
    {
      "name": "interface_metrics",
      "artifact_types": [
        "interface_metrics"
      ],
      "required": false,
      "many": false,
      "help": "Structured interface metric JSON."
    }
  ]
}
```

**resources**

```json
{
  "cpus": 1,
  "memory_gb": 2,
  "walltime_minutes": 240,
  "cpus_evidence": "The reviewed binary is the non-MPI `.default.linuxgccrelease` build, which is serial by construction."
}
```

命令摘要 SHA-256：`0ff0796c00f7aca0ac2abc7b7473f96b7d0dcd929ccb36a2b190bd1b5a056697`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-constraints:cst_fa_file", "-in:file:l", "-iname", "-jran", "-nstruct", "-o", "-out:file:scorefile", "-out:path:all", "-out:suffix", "-parser:protocol", "-parser:script_vars", "-resfile", "-s", "-score:weights", "-type"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "application", "constant_seed", "cst_fa_file", "ex1", "ex2", "jran", "nstruct", "out_scorefile", "out_suffix", "parser_protocol", "parser_script_vars", "resfile", "rosetta_bin", "score_weights"]`。

输入适配器：`null`；输出解析器：`null`。

### 版本 `2024.09-bda.1`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| application | string | score_jd2 | {"enum": ["score_jd2", "relax", "InterfaceAnalyzer", "relax_interface", "docking_protocol", "cartesian_ddg", "rosetta_scripts"], "x-bda-conditional-schemas": [{"branch": "root.allOf[0].if", "schema": {"enum": ["InterfaceAnalyzer", "relax_interface"], "required": true}}, {"branch": "root.allOf[1].if", "schema": {"const": "cartesian_ddg", "required": true}}, {"branch": "root.allOf[2].if", "schema": {"const": "docking_protocol", "required": true}}, {"branch": "root.allOf[3].if", "schema": {"const": "rosetta_scripts", "required": true}}]} |
| nstruct | integer | 1 | {"maximum": 10000, "minimum": 1} |
| replicates | integer | 1 | {"maximum": 100, "minimum": 1} |
| seed | integer | 111111 | {"maximum": 2000000000, "minimum": 1} |
| score_weights | string | ref2015 | {"enum": ["ref2015", "ref2015_cart", "beta_nov16", "beta_nov16_cart"], "x-bda-conditional-schemas": [{"branch": "root.allOf[1].then", "schema": {"enum": ["ref2015_cart", "beta_nov16_cart"], "required": true}}]} |
| out_scorefile | string | score.sc | {} |
| ex1 | boolean | false | {} |
| ex2 | boolean | false | {} |
| use_input_sc | boolean | true | {} |
| ignore_unrecognized_res | boolean | false | {} |
| extra_res_fa | string |  | {} |
| extra_res_cen | string |  | {} |
| constraints_file | string |  | {} |
| constraint_weight | number | 1.0 | {"maximum": 1000, "minimum": 0} |
| pack_input | boolean | false | {} |
| pack_separated | boolean | true | {} |
| compute_packstat | boolean | false | {} |
| interface | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[0].then", "schema": {"minLength": 3, "required": true}}]} |
| packstat_oversample | integer | 100 | {"maximum": 1000, "minimum": 1} |
| relax_repeats | integer | 5 | {"maximum": 50, "minimum": 1} |
| relax_cartesian | boolean | false | {} |
| constrain_start | boolean | true | {} |
| ramp_constraints | boolean | false | {} |
| movemap_file | string |  | {} |
| relax_script | string |  | {} |
| dock_partners | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[2].then", "schema": {"minLength": 3, "required": true}}]} |
| dock_search | string | local | {"enum": ["local", "global"]} |
| dock_translation | number | 3.0 | {"maximum": 100, "minimum": 0} |
| dock_rotation | number | 8.0 | {"maximum": 180, "minimum": 0} |
| dock_local_refine | boolean | false | {} |
| native_file | string |  | {} |
| ddg_mut_file | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[1].then", "schema": {"minLength": 1, "required": true}}]} |
| ddg_iterations | integer | 3 | {"maximum": 100, "minimum": 1} |
| ddg_cartesian | boolean | true | {"enum": [true]} |
| ddg_bb_neighbors | integer | 1 | {"maximum": 10, "minimum": 0} |
| ddg_dump_pdbs | boolean | true | {} |
| fa_max_dis | number | 9.0 | {"maximum": 20, "minimum": 3} |
| parser_protocol | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[3].then", "schema": {"minLength": 1, "required": true}}]} |
| parser_script_vars | string |  | {} |
| xml_expected_output | string | score | {"enum": ["score", "structure"]} |
| geometry_contacts | boolean | true | {} |
| contact_cutoff | number | 4.5 | {"maximum": 10, "minimum": 2} |
| receptor_axis | string |  | {} |
| binder_axis | string |  | {} |
| geometry_reference_file | string |  | {} |

**input_ports**

```json
[
  {
    "name": "s",
    "kind": "protein_structure",
    "accepts": [
      "backbone_set",
      "candidate_structure",
      "complex_structure",
      "relaxed_structure",
      "target_structure"
    ],
    "required": true,
    "multiple": true
  },
  {
    "name": "aux",
    "kind": "params",
    "required": false,
    "multiple": true,
    "description": "XML, mut_file, native PDB, constraints, MoveMap or residue params; paths are relative to this port."
  }
]
```

**output_ports**

```json
[
  {
    "name": "structures",
    "kind": "protein_structure",
    "artifact_type": "candidate_structure",
    "filename_glob": "runs/**/*.pdb"
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*.csv"
  },
  {
    "name": "raw_score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "runs/**/*.sc"
  },
  {
    "name": "raw_ddg",
    "kind": "opaque",
    "artifact_type": "data",
    "filename_glob": "runs/**/*.ddg"
  },
  {
    "name": "run_evidence",
    "kind": "opaque",
    "artifact_type": "data",
    "filename_glob": "*.json"
  },
  {
    "name": "parameter_guide",
    "kind": "opaque",
    "artifact_type": "data",
    "filename_glob": "parameter-explanations.md"
  },
  {
    "name": "run_logs",
    "kind": "opaque",
    "artifact_type": "data",
    "filename_glob": "runs/**/*.log"
  },
  {
    "name": "command_preview",
    "kind": "opaque",
    "artifact_type": "data",
    "filename_glob": "commands.sh"
  }
]
```

**output_schema**

```json
{
  "type": "object",
  "description": "Raw score/structure/log/config artifacts. No inferred Kd. Scientific validation remains separate."
}
```

**resources**

```json
{
  "cpus": 1,
  "gpu": false,
  "memory_gb": 4,
  "walltime_minutes": 240
}
```

命令摘要 SHA-256：`55bae69cff0050496c2e218b3c19c62bcd50109b2869ae6dedb59158925a8821`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--config", "--input-dir", "--output-dir", "--runtime-root", "-add_regular_scores_to_scorefile", "-compute_packstat", "-constraints:cst_fa_file", "-constraints:cst_fa_weight", "-ddg:bbnbrs", "-ddg:cartesian", "-ddg:dump_pdbs", "-ddg:iterations", "-ddg:legacy", "-ddg:mut_file", "-docking:dock_pert", "-docking:docking_local_refine", "-docking:partners", "-docking:randomize1", "-docking:randomize2", "-ex1", "-ex2", "-fa_max_dis", "-ignore_unrecognized_res", "-in:file:extra_res_cen", "-in:file:extra_res_fa", "-in:file:fullatom", "-in:file:movemap", "-in:file:native", "-in:file:s", "-interface", "-nstruct", "-out:file:scorefile", "-out:path:all", "-pack_input", "-pack_separated", "-packstat:oversample", "-parser:protocol", "-parser:script_vars", "-relax:cartesian", "-relax:constrain_relax_to_start_coords", "-relax:default_repeats", "-relax:ramp_constraints", "-relax:script", "-run:constant_seed", "-run:jran", "-score:weights", "-tracer_data_print", "-use_input_sc"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`[]`。

输入适配器：`null`；输出解析器：`null`。

### 版本 `2026.06`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| protocol | string | interface_analyzer | {"enum": ["interface_analyzer", "fast_relax", "relax_then_analyze"], "required": true} |
| score_function | string | beta_nov16 | {"enum": ["ref2015", "beta_nov16"], "required": true} |
| relax_repeats | integer | 3 | {"maximum": 10, "minimum": 1} |
| compute_sap | boolean | true | {} |

**input_ports**

```json
[
  {
    "name": "s",
    "kind": "protein_structure",
    "accepts": [
      "backbone_set",
      "candidate_complex",
      "candidate_structure",
      "complex_structure",
      "predicted_structure",
      "relaxed_structure",
      "structure",
      "target_structure"
    ],
    "content_types": [
      "chemical/x-pdb",
      "chemical/x-mmcif"
    ],
    "required": true,
    "multiple": true,
    "description": "PDB structures staged for Rosetta's -in:file input."
  }
]
```

**output_ports**

```json
[
  {
    "name": "scores",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*.sc",
    "description": "ddG, contact molecular surface, shape complementarity, SAP, unsatisfied buried polars."
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
  "gpu": false,
  "cpus": 1,
  "memory_gb": 32,
  "walltime_minutes": 720,
  "cpus_evidence": "The reviewed binary is the non-MPI `.default.linuxgccrelease` build, which is serial by construction."
}
```

命令摘要 SHA-256：`0ff0796c00f7aca0ac2abc7b7473f96b7d0dcd929ccb36a2b190bd1b5a056697`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-constraints:cst_fa_file", "-in:file:l", "-iname", "-jran", "-nstruct", "-o", "-out:file:scorefile", "-out:path:all", "-out:suffix", "-parser:protocol", "-parser:script_vars", "-resfile", "-s", "-score:weights", "-type"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "application", "constant_seed", "cst_fa_file", "ex1", "ex2", "jran", "nstruct", "out_scorefile", "out_suffix", "parser_protocol", "parser_script_vars", "resfile", "rosetta_bin", "score_weights"]`。

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
| total_score | 所用权重下结构加权总能量 | REU | 只在同协议/权重/组成下比较 | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| dG_separated | InterfaceAnalyzer 的复合态与分离态能量差 | REU | 不是实验结合自由能或 Kd；分离态重排选项影响结果 | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| dSASA_int | 复合形成埋藏的溶剂可及面积 | Å² | 界面大小指标，不能单独证明高亲和力 | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| sc_value | 界面形状互补性 | 通常 0–1 | 结合其他指标与原始结构使用 | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| hbonds_int | 按 Rosetta 几何/能量定义的跨界面氢键数 | 个 | 不是仅凭重原子距离定义的接触数 | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| delta_unsatHbonds | 结合后埋藏未满足极性原子的指标 | 计数 | 需注明协议和原子定义 | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| derived stability ΔΔG（当前未自动汇总） | 配对 WT/MUT 稳定性分数的 MUT−WT 差值；本 runner 只保存原始 WT/MUT 记录，尚不自动生成该汇总 | REU | 需在相同协议下按明确重复聚合规则另行计算；正值通常更不利于稳定性，不是结合 ΔΔG | [science](../../../docs/rosetta/SCIENTIFIC_MODES.md) |
| score.sc: 所有动态列 | 完整保留 Rosetta 分数项、约束项、协议添加列和原始 tag | 依项定义 | 自定义 XML 可新增列；未知列保留并标未解释，不自动纳入筛选 | [runner](../../../qm-scripts/plugins/rosetta/runner.py) |
| contacts / minimum_distance_within_cutoff_angstrom | 阈值内重原子接触及这些接触中的最小距离；没有阈值内接触时最小距离为 null | Å / 个 | 不是无条件全局最近原子距离；接触也不是氢键定义 | [runner](../../../qm-scripts/plugins/rosetta/runner.py) |
| anchored_angle_degrees | 由显式定义的 CA 轴锚点计算的方向角；未给锚点为 null | 度 | 缺锚点时为缺失；与同一参考和映射比较 | [runner](../../../qm-scripts/plugins/rosetta/runner.py) |
| run_manifest / run_plan / metrics | 实际 argv、种子、输入摘要、阶段目录、原始结果及汇总 | JSON | 具体文件名与字段以 runner 和七模式说明为准 | [runner](../../../qm-scripts/plugins/rosetta/runner.py) |
| ddg-records.json / 原始 .ddg | 各 Round 的 WT/WT_ 和每个 MUT_ 标签原始有限分数；检查所有预期突变都出现 | REU | 原始记录，不是已聚合的 ΔΔG；保留原文件与突变编号映射 | [runner](../../../qm-scripts/plugins/rosetta/runner.py) |
| centroid_distance_angstrom | 所选伙伴重原子几何中心间距离 | Å | 不是接触间距；与同一链选择和原子集比较 | [runner](../../../qm-scripts/plugins/rosetta/runner.py) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 2024.09-bda.1 声明/本地测试已通过，但真实 QM Rosetta 运行未验证。
- 2026.06 的 protocol/score_function/compute_sap 与旧命令存在映射缺口，不应作为可用增强版。
- 2024.09 旧声明与 library 的默认权重、ex1/ex2 等不一定相同，应查各版本默认表。
- 新 runner 在 root/bin 解析可执行文件，旧命令使用 root/source/bin；远端实际目录或站点 root 配置必须核验后再运行。
- 新插件只支持 PDB 入口；mmCIF 必须显式转换并保存链/编号映射。
- Rosetta 任意 XML mover/filter 的参数集合不在本有限表中；使用自定义协议必须附 XML、所用组件参数定义及新增输出列说明。

## 易错点


## 来源与版本

- [bda](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：本次实时 BDA 声明；不是上游功能或运行成功证明；commit `未固定/本地快照`；读取 2026-09-15。
- [upstream](https://docs.rosettacommons.org/docs/latest/)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
- [rosetta_options](https://docs.rosettacommons.org/docs/latest/full-options-list)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
- [workbench](../../../qm-scripts/plugins/rosetta/options.json)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
- [runner](../../../qm-scripts/plugins/rosetta/runner.py)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
- [science](../../../docs/rosetta/SCIENTIFIC_MODES.md)：功能与参数定义；commit `未固定/本地快照`；读取 2026-09-15。
