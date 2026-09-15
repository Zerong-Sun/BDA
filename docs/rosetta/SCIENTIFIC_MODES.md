# BDA Rosetta 模式与参数的科学语义

审查日期：2026-09-14。当前插件完整45参数见 [PARAMETERS.md](PARAMETERS.md)；本文还审计旧library的47项历史参数，后者不是新插件表单开放清单。本文界定常用任务模式、输入和解释范围，**不是全部 Rosetta 应用或所有 flags 的覆盖声明**。界面能生成文件不代表本机/集群已安装对应程序，也不代表计算已执行。每次结果应绑定实际 executable、Rosetta/database 版本、权重、输入与 XML/flags 哈希。

本次只读审查起点为 `qm-scripts/library/catalog.json` 的 Rosetta 条目：实际47个参数、声明 `parameter_count=36`、36条help为空；这是扩展前快照，不代表扩展后的字段数。快照 SHA256：`09aa9ebd0b7d216e3eb54627ba5f02b2a8f6cac2cb026885729ece7a0fe61d78`。本文未修改catalog、manifest或运行代码。

## 推荐的7个受支持工作模式

这里的“支持”指应在插件中提供明确输入与参数生成路径；真正执行仍须由对应版本程序验证。额外专用模块不能因存在自由文本入口就自动算作已验证支持。

| 模式 | 程序 / 过程 | 最低输入 | 输出及能回答的问题 | 不能据此声称 |
|---|---|---|---|---|
| 结构评分 | `score_jd2` | 可读取的结构、明确权重、必要的非标准残基参数 | scorefile与各能量项；同协议结构的静态评分 | 全局折叠预测、已做Relax、结合自由能 |
| 局部Relax | `relax` | 起始结构；主链/侧链/jump可动范围、约束及权重 | 局部优化结构和分数；改善Rosetta局部几何/packing | 物理时间MD、自动修复未知构象或发现真实结合位点 |
| PPI界面分析 | `InterfaceAnalyzer` | 已有蛋白复合物；明确链分组，如受体AB、配体C用 `AB_C` | `dG_separated`、`dSASA_int`、氢键/未满足极性/packing等 | 小分子界面评分、自动突变ΔΔG、实验Kd |
| PPI对接 | `docking_protocol` | 同坐标文件中的两个蛋白伙伴组；初始安排及采样模式 | 刚体/侧链采样的decoys与scorefile；局部或更广搜索 | 无输入结构的蛋白折叠；对接分数证明功能 |
| 折叠稳定性突变比较 | `cartesian_ddg` | 匹配Cartesian预处理的WT结构、`ddg:mut_file`、Cartesian权重与迭代设置 | WT/MUT能量与差值、可选突变结构；给定协议的稳定性变化预测 | 默认结合ΔΔG、FEP、任意不同蛋白的物理自由能比较 |
| 复合物Relax后界面分析 | standalone `relax` → 保存每个 PDB → standalone `InterfaceAnalyzer` | PPI复合物、链分组、显式权重/MoveMap/packing设置 | 保存优化结构和其界面分析；统一处理多个候选 | 没有残基选择器时不能称“仅界面残基Relax”；本组合使用standalone约束开关；自定义XML仍需独立设置 |
| 自定义XML | `rosetta_scripts` | XML、XML引用的所有文件、`script_vars`、匹配的程序版本 | 由XML的Movers/Filters/OUTPUT决定 | 任意XML都已被科学验证，或所有CLI参数都会被XML使用 |

依据：[Score Commands](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/score-commands)、[Relax](https://docs.rosettacommons.org/docs/latest/application_documentation/structure_prediction/relax)、[InterfaceAnalyzer](https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer)、[RosettaDock](https://docs.rosettacommons.org/docs/latest/application_documentation/docking/docking-protocol)、[Cartesian ddG](https://docs.rosettacommons.org/docs/latest/cartesian-ddG)、[RosettaScripts](https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/RosettaScripts)。

## 能量和结构指标的边界

Rosetta常规能量保持 **REU**。不按一个通用常数自动转换成 kcal/mol，不从分数反算Kd。`total_score`依赖权重、原子类型和系统组成；不同长度、化学形式、受体范围或权重不可直接当作同一基准比较。[Rosetta scoring](https://docs.rosettacommons.org/demos/latest/tutorials/scoring/scoring)

`dG_separated`是特定复合物与分开伙伴的Rosetta评分差；pack_input/pack_separated会改变计算条件。`dG_cross`的跨界面项求和不与它等价。`dSASA_int`为Å²；packing、形状互补和氢键数量有各自定义，不是能量。未启用/未输出的指标要标 `not_computed`，不能把占位0当作计算值。IA官方应用说明明确不用于蛋白–小分子界面；XML的`ligandchain`属性名称不能推翻这个范围限制。

Cartesian稳定性模式的核心差值是 MUT 与 WT 的同协议评分差；通常正值对应不利稳定性变化，但必须写明符号和聚合方法。文档中的interface扩展明确基准不足，本插件的稳定性模式不暴露为通用结合ΔΔG预测。要比较突变对结合的影响，应另行设计明确的结合/分开状态协议，不能改一列名字冒充。

## XML专用模式：属性已经核对

以下是官方XSD/源码支持的**属性名**，不是声称已经执行的完整XML。生成器仍须按安装版本作schema校验。

| 组件 | 可用属性 / 元素 | 关键注意 |
|---|---|---|
| `FastRelax` | `name`、`scorefxn`、`repeats`、`cartesian`、`disable_design` | `disable_design=true`用于保持序列；repeats是优化重复，不是MD时间 |
| `FastRelax/MoveMap` | `bb`、`chi`、`jump`，可进一步按链/残基范围指定 | 只限制最小化自由度；`chi=false`本身不禁止侧链重新packing；限定packing要TaskOperations |
| `FastRelax`约束 | `cst_file`、`ramp_down_constraints`；坐标约束需要真实约束生成步骤及非零相应权重 | `ramp_down_constraints`不负责创建约束；自定义relaxscript也要审计是否自行改权重 |
| `FastRelax`高级范围 | `relaxscript`、`task_operations`、`movemap_factory` | 命令行`relax:script`与XML`relaxscript`不是同名属性；没有选择器则是全局允许范围 |
| `InterfaceAnalyzerMover` | `name`、`scorefxn`、`interface`、`pack_input`、`pack_separated`、**`packstat`**、`interface_sc` | XML用`packstat`，standalone CLI用`compute_packstat`；分组必须真实存在 |
| `InterfaceAnalyzerMover`输出 | `tracer`、`scorefile_reporting_prefix`、`use_jobname` | scorefile与日志输出位置须明确；内部重打包不等于输入/输出原始坐标被同样修改 |
| `InterfaceAnalyzerMover`resfile | `resfile`是**布尔值** | 不是文件路径；它控制是否使用已指定的resfile；IA不做序列设计 |
| `SCOREFXNS` / `OUTPUT` | 定义具名ScoreFunction并被Mover引用；OUTPUT指向相应评分函数 | CLI `score:weights`不能保证覆盖XML中明确指定的weights；最终以解析后的XML为准 |

**不能直接迁移的CLI开关**：官方FastRelaxMover说明，`relax:constrain_relax_to_start_coords`、`relax:constrain_relax_to_native_coords`、`relax:ramp_constraints`由standalone Relax包装代码解释，不能假定XML FastRelax读取；`in:file:movemap`也不能代替XML MoveMap。生成复合物Relax→IA时，要么生成正确约束/MoveMap，要么明确该选项不支持，不能默默忽略后显示成功。[FastRelaxMover](https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/Movers/movers_pages/FastRelaxMover)、[IA XML XSD](https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/xsd/mover_InterfaceAnalyzerMover_type)

Cartesian FastRelax使用匹配的Cartesian权重；官方示例要求 `cart_bonded=0.5`、`pro_close=0.0`，可选用合适的 `ref2015_cart`而非直接继承普通`ref2015`。应保留Cartesian预处理和最终打分设置，不能只把`cartesian=true`当成完整方法。

## 现有47个catalog参数：建议说明及适用模式

下表是对审查快照的说明底稿。各参数只向使用它的程序/协议生成；不要把47个值无条件传给每个application。`bool`/`boolean`应统一为同一类型语义，列表必须保持逐argv元素。

| 参数 | 应显示的简明含义与注意 |
|---|---|
| `application` | BDA选择可执行程序的包装字段，不是传给Rosetta的`-application`。使用受支持枚举 |
| `s` | 输入结构；Rosetta支持文件列表，当前单字符串UI只代表单文件路径。不能为空 |
| `parser:protocol` | RosettaScripts XML路径；自定义XML模式条件必需，其他程序不需要 |
| `parser:script_vars` | XML变量`name=value`列表；上游类型StringVector，不能把多个赋值作为单个含空格argv |
| `nstruct` | 通常每个输入产生的decoy数；不是FastRelax内部cycles、ddG迭代数或独立实验数 |
| `score:weights` | 命名权重集或权重文件；显式保存。XML可能另定义权重；Cartesian需相容权重 |
| `interface` | IA的伙伴链组，如`AB_C`；不是`docking:partners`的通用替代，不能对所有输入默认A_B |
| `resfile` | packing/设计规则文件；程序或XML需实际调用读取，单给路径不保证生效 |
| `constraints:cst_fa_file` | 全原子约束文件；还需加载该文件的协议和非零对应评分项，不能“有文件即有约束” |
| `out:path:all` | 输出目录；每次运行隔离目录并保留最终解析路径 |
| `out:file:scorefile` | 分数表文件名；程序/XML决定有哪些列；IA tracer输出需另设 |
| `out:suffix` | 输出名称后缀，不改变科学计算 |
| `ex1`、`ex2` | 扩展χ1/χ2侧链rotamer采样；增加计算量，仅在发生packing时有意义 |
| `beta` | 版本相关的beta评分预设，不是质量增强开关；与显式weights的组合需按版本核验 |
| `overwrite` | 允许覆盖输出；改变数据保留行为，不是采样参数 |
| `renumber_pdb` | 输出用Rosetta编号/链标识；必须保存旧编号→新编号映射 |
| `per_chain_renumbering` | 配合renumber_pdb按链重新从起始编号计；单独启用不代表输入已重映射 |
| `ignore_unrecognized_res` | 允许忽略无法识别的残基；可能删去配体/修饰，不能作为通用输入修复 |
| `constant_seed`、`jran` | 固定随机数起点及seed；重复用同一seed不是独立采样。jran单独出现不保证启用固定seed模式 |
| `relax:constrain_relax_to_start_coords` | standalone Relax的起始坐标约束；不限制为“仅界面”，XML FastRelax不能直接沿用 |
| `relax:ramp_constraints` | standalone Relax约束权重是否递减；显式true/false，false不等于“去掉约束” |
| `relax:script` | 自定义Relax优化脚本；必须读脚本而非只看其他UI开关 |
| `relax:default_repeats` | FastRelax内部默认重复数；自定义脚本可令其无效，与nstruct不同 |
| `packing:repack_only` | 对读取该选项的packer限制为重打包、不改序列；XML仍须检查TaskOperations/disable_design |
| `pack_input` | IA在结合状态评分前重打包检测到的界面；不能代替全结构Relax |
| `use_input_sc` | 将输入侧链构象加入候选rotamers；不表示冻结该侧链 |
| `mute`、`unmute` | 控制tracer日志；避免静默掉输入修复/跳过残基等关键证据 |
| `database` | Rosetta参数数据库路径；与二进制/权重版本相容，并记录来源 |
| `in:file:extra_res_fa` | 非标准残基全原子`.params`文件，可多个；不自动建立正确质子化/共价连接，也不保证所有应用支持该残基 |
| `ddg:iterations` | WT/突变的计算迭代上限/次数，受force_iterations与收敛设置影响；不是nstruct |
| `ddg:dump_pdbs` | 保存ddG过程的结构以核查突变和处理；不改变ΔΔG的物理含义 |
| `ddg:cartesian` | ddG的Cartesian设置；须配合相应输入、权重和协议版本，不单独构成稳定性方法 |
| `fa_max_dis` | 全原子相关势的距离范围（Å）；影响能量，预处理与ddG阶段应匹配，不能跨设置比较 |
| `docking:partners` | 两个对接链组，如AB_C；链组内保持伙伴关系。第一组并非保证所有侧链/主链绝对冻结 |
| `docking_local_refine` | 只做高分辨率局部对接阶段；仍需已有邻近pose，仅知道表位不能自动定位配体 |
| `docking:randomize1`、`docking:randomize2` | 随机化各伙伴起始方向，属于广搜索初始化；局部模板不应默认同时开启 |
| `docking:spin` | 关于伙伴间轴的初始旋转；改变起始安排，不等于充分全局搜索 |
| `docking:dock_pert` | 两个数值的初始平移/转动扰动，单位Å/degrees；保留为长度2的数值列表 |
| `docking:docking_centroid_inner_cycles` | 低分辨率centroid阶段循环数；无低分辨率阶段时不适用，但并非只适用于global初始化 |
| `docking:sc_min` | 对接中的侧链最小化；与侧链重打包不同 |
| `docking:norepack1`、`docking:norepack2` | 禁止相应伙伴重打包；不自动禁止所有最小化自由度 |
| `in:file:native` | 参考结构。对接中用于参考RMSD；Relax的native-coordinate约束或XML也可能读取它，不能全局写“只算RMSD，绝非约束” |

基础类型/默认值参考catalog所指commit的[上游options源码](https://github.com/RosettaCommons/rosetta/blob/bbb6a2d27c70be05b2fb2409f3920b5894967d60/source/src/basic/options/options_rosetta.py)。默认值会随版本变化；该commit的`relax:ramp_constraints`为false、`ddg:legacy`为true。不要用旧教程的默认值代替实际二进制设置。

## 新增参数的最低要求与容易误用的组合

| 需要补齐 / 条件 | 建议生成与验证 |
|---|---|
| Cartesian稳定性缺少突变文件 | 提供必需`ddg:mut_file`；核对WT氨基酸和pose编号；多突变组合与多条独立mutant block不能混淆 |
| 现代Cartesian协议 | 明确`ddg:legacy=false`；`ddg:bbnbrs`指定序列邻居范围；`ddg:force_iterations`、`ddg:score_cutoff`说明何时提前结束；`fa_max_dis`和`ref2015_cart`与预处理一致。旧教程`bbnbr`等别名以版本help为准 |
| IA不完整 | 提供`pack_separated`、CLI `compute_packstat`、scorefile/tracer输出选择；IA use_resfile与resfile路径关联；链组和模型残基完整性必查 |
| score_jd2的“仅评分” | 默认不启用`score_app:linmin`；若启用，就说明先做小幅最小化，输出不再是原坐标的纯评分 |
| Relax约束文件 | 配套约束权重/坐标约束强度与可动范围；自定义脚本覆盖关系要显示；native约束必须有native文件 |
| XML验证 | 可提供`parser:validate_and_exit`进行安装版本schema检查；这只验证解析/语法，不证明几何、分组或科学合理性 |
| 布尔值生成 | 区分未指定与显式false；`-flag false`不可误输出成仅`-flag`或被吞掉。尤其约束递减、ddg:legacy、force_iterations等 |
| 同时选局部/广搜索 | 作为互斥预设；高级用户覆写必须能看到最终flags，不能同时宣称“保持局部起始pose”与“全局随机化” |
| 普通ref2015 + Cartesian | 不作为默认组合；给出匹配Cartesian评分函数或明确自定义要求 |
| resfile要求设计 + 保序列模式 | 生成器阻止含糊组合；保存输出序列验证，不能只靠repack_only的名称 |
| 非标准残基/糖 | 需参数化与应用支持；不要自动打开ignore_unrecognized_res使程序通过却改变体系 |
| IA多链/链子集 | 受体两链保持一组；官方提醒超过三链的分组场景验证有限。天然双链配体需实际测试链组，不自动拆成单链 |

上述互斥策略是BDA对可解释生成的产品约束，不宣称Rosetta底层对所有混合flags都会报错。大多数选项“能够被命令行解析”也不等于某个Mover确实使用它。

## 输出记录的最低解释字段

每个可下载结果保留：模式与application、输入序列/结构SHA、链/残基映射、实际CLI/XML、weights与约束设置、随机seed和重复归属、程序版本、输出结构和scorefile路径。新增能量列至少带`value`、`unit=REU`（或真实几何单位）、`method`、`status`；没有完成计算的栏不补0。

对接/Relax迭代不计ns，静态评分不命名为MD，折叠稳定性ΔΔG不命名为结合ΔΔG。参数解释可以覆盖已生成字段；插件页面不得因此宣称“Rosetta全部功能已覆盖”。完整原始来源见 [sources.json](sources.json)。
