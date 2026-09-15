# BDA Rosetta：全部可生成参数

本表由 `qm-scripts/plugins/rosetta/spec.py` 自动生成。覆盖本插件显式开放的全部参数，默认值为 BDA 插件默认，不是所有 Rosetta 版本的默认。

版本：`2024.09-bda.1`；模式：7；参数：45。

自定义 XML 的 mover/filter 属性由上传协议决定，不能预先声称覆盖 Rosetta 所有模块。插件会额外导出该 XML 的实际属性与变量清单；它们的语义需匹配实际 Rosetta 构建的 XSD。

## 模式

- `score_jd2`：单点评分：对输入结构评分，不进行 Relax，不等于界面结合能。
- `relax`：FastRelax：侧链重排与局部最小化；不是纳秒分子动力学。
- `InterfaceAnalyzer`：蛋白–蛋白界面分析：已有复合物的界面能、埋藏面积和氢键等。
- `relax_interface`：先用 relax 优化并保存坐标，再对每个优化后的复合物运行 InterfaceAnalyzer。
- `docking_protocol`：RosettaDock：蛋白–蛋白刚体/侧链采样；需要已有组装与明确伙伴链。
- `cartesian_ddg`：Cartesian ΔΔG：匹配 WT/突变体的折叠稳定性分数差；不是结合 ΔΔG。
- `rosetta_scripts`：使用上传的 XML 协议；XML 的 mover/filter 参数与输出由该协议定义。

## 参数

### application — 功能模式

- 类型：`string`；默认：`"score_jd2"`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。
- 可选值：`["score_jd2", "relax", "InterfaceAnalyzer", "relax_interface", "docking_protocol", "cartesian_ddg", "rosetta_scripts"]`。

选择计算阶段；不同模式的分数不能混作同一种结合自由能。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### nstruct — 每输入生成数

- 类型：`integer`；默认：`1`。
- 单位：个；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, rosetta_scripts。
- 生成映射：`-nstruct`。
- 范围：1–10000。

每个输入、每个独立重复生成的 decoy 数；cartesian_ddg 使用 ddg_iterations，不使用本参数。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### replicates — 独立重复数

- 类型：`integer`；默认：`1`。
- 单位：次；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。
- 范围：1–100。

分别启动进程并使用不同随机种子；各重复保留原始结果，不只保存最优值。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### seed — 起始随机种子

- 类型：`integer`；默认：`111111`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-run:constant_seed / -run:jran`。
- 范围：1–2000000000。

启用 constant_seed；每个输入/重复的种子递增。固定种子利于复现，不证明采样收敛。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### score_weights — 评分函数

- 类型：`string`；默认：`"ref2015"`。
- 单位：Rosetta 权重集；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-score:weights`。
- 可选值：`["ref2015", "ref2015_cart", "beta_nov16", "beta_nov16_cart"]`。

所有比较对象使用同一权重。Cartesian 模式必须选择 *_cart；REU 不能直接当 kcal/mol。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### out_scorefile — 评分文件名

- 类型：`string`；默认：`"score.sc"`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-out:file:scorefile`。
- 格式：`^[A-Za-z0-9][A-Za-z0-9_.-]*\.sc$`。

各输入/重复独立目录内的 .sc 文件名；不接受目录或路径穿越。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### ex1 — 额外 χ1 旋转异构体

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-ex1`。

扩大侧链 χ1 rotamer 采样；增加打包计算量，不是独立结构重复。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### ex2 — 额外 χ2 旋转异构体

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-ex2`。

扩大侧链 χ2 rotamer 采样；仅在协议实际执行 packing 时影响采样。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### use_input_sc — 保留输入侧链候选

- 类型：`boolean`；默认：`true`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-use_input_sc`。

将输入侧链构象纳入 packing rotamer 候选集合。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### ignore_unrecognized_res — 忽略无法识别的残基

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-ignore_unrecognized_res`。

默认关闭。开启可能删除糖基、配体或特殊残基，改变体系；须检查运行日志和保存结构。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### extra_res_fa — 全原子残基参数文件

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：score_jd2, relax, InterfaceAnalyzer, relax_interface, docking_protocol, cartesian_ddg, rosetta_scripts。
- 生成映射：`-in:file:extra_res_fa`。

aux 端口下的 .params 相对文件名；为非标准残基提供全原子参数，不自动生成小分子参数。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### extra_res_cen — Centroid 残基参数文件

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：docking_protocol, rosetta_scripts。
- 生成映射：`-in:file:extra_res_cen`。

aux 端口下的 .params 文件；对接低分辨率阶段使用非标准残基时需匹配 centroid 参数。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### constraints_file — 约束文件

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：score_jd2, relax, relax_interface, docking_protocol, rosetta_scripts。
- 生成映射：`-constraints:cst_fa_file`。

aux 端口下的 Rosetta .cst 文件；其中残基编号须对应输入 pose。约束能改变评分，不能与无约束能量混排。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### constraint_weight — 文件约束权重

- 类型：`number`；默认：`1.0`。
- 单位：权重；适用模式：score_jd2, relax, relax_interface, docking_protocol, rosetta_scripts。
- 生成映射：`-constraints:cst_fa_weight`。
- 范围：0–1000。

仅在提供 constraints_file 时传入；不等同于 Relax 自动坐标约束权重。

[官方依据](https://docs.rosettacommons.org/docs/latest/full-options-list)

### pack_input — 先重排输入界面

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`-pack_input`。

分析前是否对输入界面进行侧链 packing；这是评分内部分支，不会覆盖保存的 Relax 坐标。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer)

### pack_separated — 分离后重排界面

- 类型：`boolean`；默认：`true`。
- 单位：无量纲；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`-pack_separated`。

计算 dG_separated 时，是否重排分離伙伴暴露界面的侧链。与 pack_input 分开控制。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer)

### compute_packstat — 计算界面堆积统计

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`-compute_packstat`。

启用有随机成分的 packstat；大界面可能较慢。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer)

### interface — 界面链分组

- 类型：`string`；默认：`""`。
- 单位：无量纲；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`-interface`。
- 格式：`^$|^[A-Za-z0-9]+_[A-Za-z0-9]+$`。

必填，例如 AB_C 表示受体 A/B 与蛋白 C；天然双链配体可为 AB_CD。使用输入文件实际链标识，不能混淆 mmCIF label/auth ID。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer)

### packstat_oversample — Packstat 过采样

- 类型：`integer`；默认：`100`。
- 单位：倍；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`-packstat:oversample`。
- 范围：1–1000。

仅 compute_packstat=true 时生效；增加采样以降低随机波动。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer)

### relax_repeats — Relax 内部循环

- 类型：`integer`；默认：`5`。
- 单位：次；适用模式：relax, relax_interface。
- 生成映射：`-relax:default_repeats`。
- 范围：1–50。

一个 FastRelax 轨迹内的打包/最小化循环；不同于 nstruct 和独立重复。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### relax_cartesian — Cartesian Relax

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：relax, relax_interface。
- 生成映射：`-relax:cartesian`。

使用笛卡尔坐标最小化；必须选 ref2015_cart 或 beta_nov16_cart。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### constrain_start — 约束到输入坐标

- 类型：`boolean`；默认：`true`。
- 单位：无量纲；适用模式：relax, relax_interface。
- 生成映射：`-relax:constrain_relax_to_start_coords`。

由 relax 可执行文件建立起始坐标约束，减少大幅漂移；不作为 XML FastRelax 的通用开关。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### ramp_constraints — 渐弱坐标约束

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：relax, relax_interface。
- 生成映射：`-relax:ramp_constraints`。

配合 constrain_start。false 显式传给 Rosetta，在优化中保留约束；true 渐弱。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### movemap_file — Relax 自由度文件

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：relax, relax_interface。
- 生成映射：`-in:file:movemap`。

aux 端口下的 MoveMap 文件，控制骨架/侧链/jump 可动性。默认未提供时沿用该 relax 构建的自由度；不是受体自动固定。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### relax_script — 自定义 Relax 循环脚本

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：relax, relax_interface。
- 生成映射：`-relax:script`。

aux 端口下的 Relax script；覆盖内部优化流程，需与 repeats/约束策略一起审阅。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)

### dock_partners — 对接伙伴链

- 类型：`string`；默认：`""`。
- 单位：无量纲；适用模式：docking_protocol。
- 生成映射：`-docking:partners`。
- 格式：`^$|^[A-Za-z0-9]+_[A-Za-z0-9]+$`。

必填，例如 AB_C。对接分组与界面分析分组语法类似，但这是 docking:partners。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)

### dock_search — 对接搜索范围

- 类型：`string`；默认：`"local"`。
- 单位：无量纲；适用模式：docking_protocol。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。
- 可选值：`["local", "global"]`。

local 从现有姿态附近扰动；global 随机化两个伙伴取向，须充分采样；都不是物理 MD。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)

### dock_translation — 初始平移扰动

- 类型：`number`；默认：`3.0`。
- 单位：Å；适用模式：docking_protocol。
- 生成映射：`-docking:dock_pert [translation rotation]`。
- 范围：0–100。

local 模式 dock_pert 的平移幅度；不能据此推导结合距离或动力学。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)

### dock_rotation — 初始旋转扰动

- 类型：`number`；默认：`8.0`。
- 单位：度；适用模式：docking_protocol。
- 生成映射：`-docking:dock_pert [translation rotation]`。
- 范围：0–180。

local 模式 dock_pert 的旋转幅度。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)

### dock_local_refine — 仅高分辨率对接精修

- 类型：`boolean`；默认：`false`。
- 单位：无量纲；适用模式：docking_protocol。
- 生成映射：`-docking:docking_local_refine`。

跳过低分辨率搜索，用于已有可信近邻姿态；不能与 global 搜索组合。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)

### native_file — 参考复合物

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：docking_protocol。
- 生成映射：`-in:file:native`。

aux 中用于对接 RMSD 的参考结构，不自动作为位置约束；必须具有匹配的链/残基映射。

[官方依据](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)

### ddg_mut_file — 突变定义文件

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：cartesian_ddg。
- 生成映射：`-ddg:mut_file`。

cartesian_ddg 必填的 aux mut_file。使用 Rosetta pose 编号；需要 WT 与突变定义校验，不能用 PDB 编号直接替代。

[官方依据](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)

### ddg_iterations — WT/突变采样迭代

- 类型：`integer`；默认：`3`。
- 单位：次；适用模式：cartesian_ddg。
- 生成映射：`-ddg:iterations`。
- 范围：1–100。

每个突变定义的采样次数，不是 nstruct；输出的是协议相关折叠稳定性差分。

[官方依据](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)

### ddg_cartesian — DDG Cartesian 优化

- 类型：`boolean`；默认：`true`。
- 单位：无量纲；适用模式：cartesian_ddg。
- 生成映射：`-ddg:cartesian`。
- 可选值：`[true]`。

本插件只支持 Cartesian 协议，必须保持 true。

[官方依据](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)

### ddg_bb_neighbors — 骨架邻居范围

- 类型：`integer`；默认：`1`。
- 单位：残基数；适用模式：cartesian_ddg。
- 生成映射：`-ddg:bbnbrs`。
- 范围：0–10。

围绕突变位置允许处理的序列邻居范围；不是空间半径。

[官方依据](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)

### ddg_dump_pdbs — 保存 DDG 结构

- 类型：`boolean`；默认：`true`。
- 单位：无量纲；适用模式：cartesian_ddg。
- 生成映射：`-ddg:dump_pdbs`。

保存 WT/突变模型供原子级核查；关闭则仅保存原始分数与日志。

[官方依据](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)

### fa_max_dis — 全原子作用距离截断

- 类型：`number`；默认：`9.0`。
- 单位：Å；适用模式：relax, relax_interface, InterfaceAnalyzer, cartesian_ddg。
- 生成映射：`-fa_max_dis`。
- 范围：3–20。

Cartesian DDG 推荐协议的相互作用截断；须与 WT 预先 Cartesian Relax 的设置一致。

[官方依据](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)

### parser_protocol — RosettaScripts XML

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：rosetta_scripts。
- 生成映射：`-parser:protocol`。

rosetta_scripts 必填，aux 下的 XML 文件。平台不会猜测 XML 的科学阶段；生成时验证 XML 可解析，完整 schema 由实际 Rosetta 构建验证。

[官方依据](https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/RosettaScripts)

### parser_script_vars — XML 变量

- 类型：`string`；默认：`""`。
- 单位：无量纲；适用模式：rosetta_scripts。
- 生成映射：`-parser:script_vars`。

空白分隔的 name=value；作为独立 argv 值传入，不运行 shell。所有变量名必须在 XML 的 %%name%% 中出现，所有占位符必须有值。

[官方依据](https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/RosettaScripts)

### xml_expected_output — XML 最低输出契约

- 类型：`string`；默认：`"score"`。
- 单位：无量纲；适用模式：rosetta_scripts。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。
- 可选值：`["score", "structure"]`。

score 要求至少 nstruct 个有效 SCORE 行；structure 还要求对应数量 PDB。自定义协议的完整科学输出仍由协议作者解释。

[官方依据](https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/RosettaScripts)

### geometry_contacts — 计算界面原子距离

- 类型：`boolean`；默认：`true`。
- 单位：无量纲；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。

从同一被评分的复合物坐标提取重原子接触和逐残基对最短距离；内部 packing 的临时姿态不在此几何文件中。

[官方依据](https://docs.python.org/3/library/math.html#math.dist)

### contact_cutoff — 接触距离阈值

- 类型：`number`；默认：`4.5`。
- 单位：Å；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。
- 范围：2–10。

输出此半径内的全部跨界面重原子对及其距离；没有接触不等于证明不结合。

[官方依据](https://docs.python.org/3/library/math.html#math.dist)

### receptor_axis — 受体角度锚点

- 类型：`string`；默认：`""`。
- 单位：PDB链:残基编号；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。

可选，两枚 CA 的 chain:residue 标识，逗号分隔，如 A:10,A:100；方向从第一个指向第二个。须与 binder_axis 一起提供。

[官方依据](https://docs.python.org/3/library/math.html#math.acos)

### binder_axis — 配体蛋白角度锚点

- 类型：`string`；默认：`""`。
- 单位：PDB链:残基编号；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。

可选，两枚 CA 标识，如 C:1,C:50。报告此有向轴与受体轴的夹角；不是未经定义的“整体结合角”。

[官方依据](https://docs.python.org/3/library/math.html#math.acos)

### geometry_reference_file — 天然参考复合物

- 类型：`string`；默认：`""`。
- 单位：文件；适用模式：InterfaceAnalyzer, relax_interface。
- 生成映射：`BDA 控制参数，不直接作为 Rosetta flag`。

可选，aux 下同链分组的参考 PDB；计算其接触、质心距离与相同锚点定义夹角供比较。参考应记录是实验复合物还是对接假说；不同支架的接触编号不能直接当同源位点。

[官方依据](https://docs.python.org/3/library/math.html#math.dist)

## 固定生成参数与输出解释

这些设置不在表单中编辑，但同样纳入执行计划：

- `-in:file:s`：逐个暂存 PDB 输入的绝对路径；本版只接受单模型 PDB，mmCIF 须预先转换并保留链映射。
- `-out:path:all` / `-out:file:scorefile`：每输入、每重复、每阶段的独立输出目录与评分文件；不覆盖已有输出。
- `-run:constant_seed true` / `-run:jran`：显式可追溯种子；不是采样充分性的证明。
- `-add_regular_scores_to_scorefile true`：IA 同时填充常规能量项，避免未计算的占位零值。关闭的 packstat 仍不能把其 0 解释为实际堆积评分。
- `-tracer_data_print false`：InterfaceAnalyzer 写结构/scorefile；避免只有终端文本。
- `-in:file:fullatom true`：RosettaDock 从全原子输入读入，完整协议仍可能包含低分辨率阶段。
- `-docking:randomize1 true` / `-docking:randomize2 true`：global 模式随机化两个伙伴；local 使用 dock_pert。
- `-ddg:legacy false`：显式选择现代 Cartesian DDG 路线，不依赖构建的 legacy 默认值。
- `relax_interface` 的第二阶段固定 `-nstruct 1`，逐一分析第一阶段的全部 Relax PDB，实际命令另存 execution.json。

## 输出参数口径

| 输出 | 解释 |
|---|---|
| total_score / score及各能量项 | 特定权重下的 Rosetta 分数，REU；不可直接换成 kcal/mol |
| dG_separated | 结合/分离伙伴的界面分数差，注明 packing 设置；不是相对 WT 的突变 ΔΔG |
| dSASA_int | 接口埋藏溶剂可及面积，Å² |
| dG_separated/dSASAx100 | 按埋藏面积归一化并乘 100 的界面分数 |
| hbonds_int / delta_unsatHbonds | 接口氢键和埋藏未满足氢键统计，依赖协议及氢键判定 |
| sc_value / packstat | 形状互补与堆积指标；packstat仅启用时有意义 |
| docking RMSD / interface RMSD | 仅有匹配 native 参考时能解释为对参考偏差，单位 Å |
| *.ddg | 原始 WT/突变能量记录，保留协议/迭代；物理稳定性或结合结论须另验证 |
| 其他 SCORE 列 | 全部原名保留，不猜测语义；自定义 XML 新字段须附协议作者定义 |

## 覆盖边界

本插件不会从 Rosetta 输出虚构 pLDDT、ipTM、MSA 深度或 Kd；这些必须来自对应预测/序列分析/实验。不自动参数化小分子、不提供膜 MD；InterfaceAnalyzer 仅用于蛋白–蛋白界面。

详细模式和科学限制见 [SCIENTIFIC_MODES.md](SCIENTIFIC_MODES.md)。
