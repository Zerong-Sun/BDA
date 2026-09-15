# DiffAb — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

抗体CDR的序列/结构联合设计、局部优化及固定骨架/固定序列模式。官方模式可以查证，但BDA目前disabled，命令仅python run.py，不能把下列上游能力标作BDA已接入。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/diffab.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 1.0.0 | false | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 单CDR序列和结构共设计 (`codesign_single`)

逐个选定CDR分别采样，框架与抗原作为上下文。。BDA 接入：`not_exposed`。

输入：抗体–抗原复合物PDB及heavy/light链映射; 相应config YAML和匹配checkpoint; AbNumber/ANARCI等编号依赖

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "single_cdr",
  "sampling.sample_structure": true,
  "sampling.sample_sequence": true,
  "sampling.num_samples": 100,
  "sampling.cdrs": [
    "H_CDR3"
  ]
}
```

输出检查：核对输出每个variant的CDR掩码和sample计数；验证框架/未设计序列保留与残基编号映射；保留元数据和原始PDB

限制：BDA disabled且无这些config入口；不能用当前python run.py执行这些模式；同一个num_samples按variant重复，不保证全任务总数等于该值；生成结构不等于已Relax或验证结合；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 多CDR同时共设计 (`codesign_multiple`)

在同一次样本中联合重设计选定CDRs。。BDA 接入：`not_exposed`。

输入：抗体–抗原复合物PDB及heavy/light链映射; 相应config YAML和匹配checkpoint; AbNumber/ANARCI等编号依赖

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "multiple_cdrs",
  "sampling.sample_structure": true,
  "sampling.sample_sequence": true,
  "sampling.num_samples": 100,
  "sampling.cdrs": [
    "H_CDR3"
  ]
}
```

输出检查：核对输出每个variant的CDR掩码和sample计数；验证框架/未设计序列保留与残基编号映射；保留元数据和原始PDB

限制：BDA disabled且无这些config入口；不能用当前python run.py执行这些模式；同一个num_samples按variant重复，不保证全任务总数等于该值；生成结构不等于已Relax或验证结合；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[da-multi](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_multicdrs.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 已有CDR局部优化 (`abopt`)

对已有CDR按不同optimize_steps扰动深度再去噪；不是亲和力保证。。BDA 接入：`not_exposed`。

输入：抗体–抗原复合物PDB及heavy/light链映射; 相应config YAML和匹配checkpoint; AbNumber/ANARCI等编号依赖

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "abopt",
  "sampling.sample_structure": true,
  "sampling.sample_sequence": true,
  "sampling.num_samples": 100,
  "sampling.cdrs": [
    "H_CDR3"
  ],
  "sampling.optimize_steps": [
    1,
    2,
    4,
    8,
    16,
    32,
    64
  ]
}
```

输出检查：核对输出每个variant的CDR掩码和sample计数；验证框架/未设计序列保留与残基编号映射；保留元数据和原始PDB

限制：BDA disabled且无这些config入口；不能用当前python run.py执行这些模式；同一个num_samples按variant重复，不保证全任务总数等于该值；生成结构不等于已Relax或验证结合；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[da-opt](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/abopt_singlecdr.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 固定骨架序列设计 (`fixbb`)

保留选定CDR骨架，只重新采样氨基酸类别。。BDA 接入：`not_exposed`。

输入：抗体–抗原复合物PDB及heavy/light链映射; 相应config YAML和匹配checkpoint; AbNumber/ANARCI等编号依赖

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "single_cdr",
  "sampling.sample_structure": false,
  "sampling.sample_sequence": true,
  "sampling.num_samples": 100,
  "sampling.cdrs": [
    "H_CDR3"
  ]
}
```

输出检查：核对输出每个variant的CDR掩码和sample计数；验证框架/未设计序列保留与残基编号映射；保留元数据和原始PDB

限制：BDA disabled且无这些config入口；不能用当前python run.py执行这些模式；同一个num_samples按variant重复，不保证全任务总数等于该值；生成结构不等于已Relax或验证结合；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[da-fixbb](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/fixbb.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 固定序列结构预测 (`strpred`)

保留CDR序列，仅采样其三维结构。。BDA 接入：`not_exposed`。

输入：抗体–抗原复合物PDB及heavy/light链映射; 相应config YAML和匹配checkpoint; AbNumber/ANARCI等编号依赖

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "single_cdr",
  "sampling.sample_structure": true,
  "sampling.sample_sequence": false,
  "sampling.num_samples": 100,
  "sampling.cdrs": [
    "H_CDR3"
  ]
}
```

输出检查：核对输出每个variant的CDR掩码和sample计数；验证框架/未设计序列保留与残基编号映射；保留元数据和原始PDB

限制：BDA disabled且无这些config入口；不能用当前python run.py执行这些模式；同一个num_samples按variant重复，不保证全任务总数等于该值；生成结构不等于已Relax或验证结合；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[da-strpred](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/strpred.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 无复合物时先对接框架 (`dock_then_design`)

官方design_dock.py以抗原和抗体框架经HDOCK产生起始复合物，再执行CDR设计。。BDA 接入：`not_exposed`。

输入：抗原PDB; 抗体模板PDB（官方有默认示例但需科学选择）; HDOCK/createpl可执行文件; 设计YAML与checkpoint

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "antigen": "antigen.pdb",
  "antibody": "framework.pdb",
  "num_docks": 10,
  "config": "configs/test/codesign_multicdrs.yml"
}
```

输出检查：检查每个对接pose的链映射和框架位置；分别记录对接分数与CDR生成结果

限制：抗原PDB单独不足以完成受控框架设计；BDA没有antibody/config/HDOCK映射，epitope字段也未绑定到此入口；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py), [da-readme](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/README.md), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 使用方法

1. 当前仅审阅文档和配置，保持disabled状态如实展示。
2. 选择已有复合物还是抗原+框架先对接；准备链ID、CDR编号和对应checkpoint。
3. 选择五种上游YAML模式之一；检查sampling.cdrs、sample_structure和sample_sequence。
4. 修复BDA实际命令、输入/输出adapter和运行环境后，先检查最小案例的参数确认、样本数和CDR范围。
5. 将额外Relax/界面分析与生成阶段分开记录；生成分数不当作实测亲和力。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `antigen_pdb`

页面声明的抗原结构。已组装复合物对应上游pdb_path；只有抗原则需design_dock.py --antigen、框架模板和HDOCK，当前命令没有传递此字段。

类型：`artifact_ref`；单位：PDB文件；来源记录默认：``。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`无实际映射；候选上游pdb_path或--antigen`；BDA 别名：`["antigen_pdb"]`。

约束与版本差异：["插件disabled；python run.py没有参数映射或input_adapter。"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `epitope_residues`

页面拟表达引导接触的抗原残基；本次检查官方design_for_pdb/design_dock未找到同名epitope参数，不得宣称填写后形成约束。

类型：`string`；单位：链/残基集合；来源记录默认：``。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`未绑定且无已核验上游同名入口`；BDA 别名：`["epitope_residues"]`。

约束与版本差异：["插件disabled；python run.py没有参数映射或input_adapter。"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `cdr_loops`

拟选择要重设计的CDR。页面H1/H2/H3/L1/L2/L3与上游H_CDR1等名称不同，需明确转换及抗体编号规则。

类型：`string`；单位：CDR名称列表；来源记录默认：`H1,H2,H3,L1,L2,L3`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`未绑定；上游sampling.cdrs`；BDA 别名：`["cdr_loops"]`。

约束与版本差异：["插件disabled；python run.py没有参数映射或input_adapter。"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `num_designs`

拟设采样数量；上游sampling.num_samples作用于每个variant，可因CDR或优化步数组合产生更多总样本。

类型：`integer`；单位：样本数/variant；来源记录默认：`100`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`未绑定；上游sampling.num_samples`；BDA 别名：`["num_designs"]`。

约束与版本差异：["插件disabled；python run.py没有参数映射或input_adapter。", "BDA声明min=1", "BDA声明max=100000"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `sampling_steps`

页面声明的扩散采样步数；该值没有传入命令。不能直接等同abopt optimize_steps（局部扰动起点），完整扩散调度来自模型/配置。

类型：`integer`；单位：扩散步（未绑定）；来源记录默认：`100`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`未绑定；无已核验一一对应`；BDA 别名：`["sampling_steps"]`。

约束与版本差异：["插件disabled；python run.py没有参数映射或input_adapter。", "BDA声明min=1", "BDA声明max=1000"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `seed`

拟设随机数种子。上游代码将显式0作为固定种子0；None才回退config.sampling.seed，页面“0自动随机”的说明无源码支持。

类型：`integer`；单位：整数种子；来源记录默认：`0`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`未绑定；上游--seed优先于sampling.seed`；BDA 别名：`["seed"]`。

约束与版本差异：["插件disabled；python run.py没有参数映射或input_adapter。", "BDA声明min=0"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `pdb_path`

已组装抗体–抗原PDB，design_pdb.py的位置参数；与抗原单独文件区分。

类型：`string`；单位：PDB路径；来源记录默认：`未声明`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`位置参数`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `heavy`

抗体重链ID；未指定时由上游编号工具识别，须核验结果。

类型：`string`；单位：链ID；来源记录默认：`null`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--heavy`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `light`

抗体轻链ID；未指定时由上游识别，不能把抗原链误识别为轻链。

类型：`string`；单位：链ID；来源记录默认：`null`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--light`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `no_renumber`

跳过默认抗体重新编号；只有输入符合模型/CDR识别编号时使用。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--no_renumber`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `config`

设计配置YAML，决定CDR模式、采样和checkpoint；当前BDA缺此入口。

类型：`string`；单位：YAML路径；来源记录默认：`./configs/test/codesign_single.yml`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--config`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `out_root`

生成结果根目录；须与BDA输出收集路径对应。

类型：`string`；单位：目录；来源记录默认：`./results`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--out_root`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `tag`

输出任务附加标识，不是氨基酸标签或表达标签。

类型：`string`；单位：文本；来源记录默认：``。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--tag`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `device`

模型运行设备，需与PyTorch/GPU环境匹配。

类型：`string`；单位：设备标识；来源记录默认：`cuda`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--device`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `batch_size`

同一批并行推理的样本数，主要影响显存和吞吐；不是总样本数。

类型：`integer`；单位：样本/批；来源记录默认：`16`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`--batch_size`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `model.checkpoint`

模型权重文件；fixbb和strpred示例使用不同checkpoint，不能只切布尔而沿用错误权重。

类型：`string`；单位：checkpoint路径；来源记录默认：`./trained_models/codesign_single.pt`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:model.checkpoint`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-fixbb](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/fixbb.yml), [da-strpred](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/strpred.yml)

### `mode`

variant生成模式，single_cdr逐环、multiple_cdrs联合、abopt局部优化。

类型：`string`；单位：枚举；来源记录默认：`single_cdr`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:mode`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `sampling.seed`

未给CLI --seed时使用的配置随机种子；0同样是固定数值。

类型：`integer`；单位：整数种子；来源记录默认：`2022`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:sampling.seed`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `sampling.sample_structure`

是否去除待设计CDR结构信息并采样骨架；false用于固定骨架。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:sampling.sample_structure`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-fixbb](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/fixbb.yml)

### `sampling.sample_sequence`

是否去除待设计CDR序列信息并采样AA；false用于固定序列结构预测。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:sampling.sample_sequence`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-strpred](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/strpred.yml)

### `sampling.cdrs`

上游CDR名称集合，与实际识别CDR取交集；遗漏/错误名称可能改变设计范围。

类型：`array`；单位：CDR集合；来源记录默认：`["H_CDR1", "H_CDR2", "H_CDR3", "L_CDR1", "L_CDR2", "L_CDR3"]`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:sampling.cdrs`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `sampling.num_samples`

每个设计variant重复采样数量；逐CDR或多个优化步数会增大总生成数量。

类型：`integer`；单位：样本/variant；来源记录默认：`100`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:sampling.num_samples`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `sampling.optimize_steps`

abopt每个局部优化variant使用的扩散扰动深度列表；不是物理时间，非一般采样总步数。

类型：`array`；单位：扩散步列表；来源记录默认：`[1, 2, 4, 8, 16, 32, 64]`。

适用模式：codesign_single, codesign_multiple, abopt, fixbb, strpred, dock_then_design

生成映射：`config:sampling.optimize_steps`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-opt](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/abopt_singlecdr.yml), [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)

### `antibody`

抗原单独入口用于初始对接的抗体框架模板；选择会影响CDR环境和可达表面。

类型：`string`；单位：PDB路径；来源记录默认：`./data/examples/3QHF_Fv.pdb`。

适用模式：dock_then_design

生成映射：`--antibody`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `num_docks`

传给对接入口保留/处理的起始框架pose数量，不是每pose的CDR样本数。

类型：`integer`；单位：对接pose数；来源记录默认：`10`。

适用模式：dock_then_design

生成映射：`--num_docks`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `hdock_bin`

HDOCK程序路径，抗原单独设计前置依赖。

类型：`string`；单位：程序路径；来源记录默认：`./bin/hdock`。

适用模式：dock_then_design

生成映射：`--hdock_bin`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `createpl_bin`

HDOCK pose提取程序路径，与HDOCK版本匹配。

类型：`string`；单位：程序路径；来源记录默认：`./bin/createpl`。

适用模式：dock_then_design

生成映射：`--createpl_bin`；BDA 别名：`[]`。

约束与版本差异：["官方参考入口已核验，BDA当前未暴露/绑定；此处默认值为上游示例或CLI值。"]

依据：[da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)

### `antigen`

design_dock.py必需的抗原PDB路径，与抗体框架一起先做HDOCK对接；只有BDA antigen_pdb声明而无当前adapter。

类型：`string`；单位：PDB路径；来源记录默认：`未声明`。

适用模式：dock_then_design

生成映射：`上游--antigen；BDA当前未绑定`；BDA 别名：`[]`。

约束与版本差异：["上游required=True，未定义用户可用默认路径。", "不替代antibody框架与config/checkpoint。"]

依据：[da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `1.0.0`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| antigen_pdb | artifact_ref |  | {} |
| epitope_residues | string |  | {} |
| cdr_loops | string | H1,H2,H3,L1,L2,L3 | {} |
| num_designs | integer | 100 | {} |
| sampling_steps | integer | 100 | {} |
| seed | integer | 0 | {} |

**input_ports**

```json
[
  {
    "name": "antigen_pdb",
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
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Antigen PDB. Target antigen structure passed to DiffAb. (from field 'antigen_pdb')"
  }
]
```

**output_ports**

```json
[
  {
    "name": "cdr_designs",
    "kind": "protein_structure",
    "artifact_type": "backbone_set",
    "filename_glob": "*",
    "description": "Designed antibody CDR backbone/complex candidates."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Sampling scores and metadata."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "cdr_designs",
      "artifact_types": [
        "backbone_set",
        "complex_structure"
      ],
      "required": true,
      "many": true,
      "help": "Designed antibody CDR backbone/complex candidates."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": false,
      "many": false,
      "help": "Sampling scores and metadata."
    }
  ]
}
```

**resources**

```json
{}
```

命令摘要 SHA-256：`7602085a75dcaa3fc62c5f095bbfd04724c173eee9cff3f8cb92cea8d842089f`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`[]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`[]`。

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
| variant/sample PDB | 按CDR选择/优化深度保存的生成复合物结构 | Å坐标 | 核对设计区域与保留区域；不是运行过Rosetta Relax的证明。 | [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py) |
| metadata.json | 任务、结构/设计信息与原配置路径等元数据；源码仅记录配置路径，不自动复制 YAML 配置 | 元数据 | 另行保存实际解析后的配置及原 YAML，不能把路径字符串当作已归档配置内容 | [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| score_table（BDA声明） | 可选生成/评价统计 | 方法相关 | 采样流程未自动保证亲和力或Rosetta能量输出；额外评价需单独运行并注明方法。 | live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [da-readme](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/README.md) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 无官方或本地已核验的run.py adapter；当前6个BDA字段全部未接入命令。
- 缺checkpoint/config、抗体框架、链ID/编号转换、HDOCK依赖和已验证运行环境。
- 输出filename_glob均为*且无parser，产物类型/计数未验证。
- 没有qm-scripts library DiffAb条目；此文档补充官方模式和参数说明，不声称生成器已支持。

## 易错点

- BDA schema valid与disabled/unproven可以同时存在，前者不是可运行结论。
- 上游显式seed=0为固定种子，与BDA旧帮助矛盾。
- H_CDR3等名称依赖抗体编号，不能直接用一般蛋白残基列表替代。
- antigen_pdb单独输入不等于从零生成完整抗体；框架与起始复合物处理是必要条件。
- epitope_residues和sampling_steps目前只是未绑定声明，不能假定产生真实接触约束或调度改动。

## 来源与版本

- live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：审计时BDA注册字段、命令、输入输出端口、enabled及runtime_validation_status；commit `None`；读取 2026-09-15。
- [catalog](../../../qm-scripts/library/catalog.json)：历史参数库的类型和默认值，不等同运行时有效设置；commit `None`；读取 2026-09-15。
- [renderer](../../../qm-scripts/library/qm_job.py)：手工配置生成器的参数映射，区别于live ModelPlugin命令；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/diffab/README.md)：旧运行手册的状态记录；不是安装或运行成功证明；commit `None`；读取 2026-09-15。
- [da-readme](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/README.md)：官方五类模式、抗原单独输入需HDOCK和抗体框架；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-runner](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/diffab/tools/runner/design_for_pdb.py)：复合物入口、参数解析、CDR选择、seed和结构保存；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-dock](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/design_dock.py)：抗原+抗体框架先对接的入口及依赖；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-single](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_single.yml)：单CDR共设计配置；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-multi](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/codesign_multicdrs.yml)：多CDR共设计配置；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-opt](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/abopt_singlecdr.yml)：局部优化扰动步数列表；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-fixbb](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/fixbb.yml)：固定骨架序列设计配置；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
- [da-strpred](https://github.com/luost26/diffab/blob/c3e2966601bf8025025ab87717b31b08fdd4834e/configs/test/strpred.yml)：固定序列结构预测配置；commit `c3e2966601bf8025025ab87717b31b08fdd4834e`；读取 2026-09-15。
