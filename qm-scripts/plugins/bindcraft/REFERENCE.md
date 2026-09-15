# BindCraft — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

AF2反向传播生成蛋白结合支架，经ProteinMPNN改序列、AF2复核和PyRosetta筛选。live已启用但运行证明为unproven；289个library键可经手工JSON bundle生成，BDA界面的多数同名标量尚无写回JSON映射。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/bindcraft.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 2025.09 | true | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 两阶段：logits→PSSM半贪心 (`2stage`)

先连续优化序列偏好，再依据PSSM尝试降低loss的突变。。BDA 接入：`configuration_only`。

输入：目标PDB及其链/编号映射; target settings JSON内真实starting_pdb路径; advanced JSON及filters JSON; 匹配的AF2/MPNN权重、PyRosetta、DSSP与DAlphaBall

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_algorithm": "2stage",
  "soft_iterations": 75,
  "greedy_iterations": 15
}
```

输出检查：保存解析后的三份JSON及源码/权重身份；检查Trajectory、MPNN和Accepted统计的不同来源；逐序列核对复核模型ID、结构文件和全部过滤值

限制：library生成JSON已实现；live仅传文件路径，不自动接入界面同名标量；算法改变的是优化策略，不生成可解释为Kd的分数；本次未运行GPU任务；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [renderer](../../../qm-scripts/library/qm_job.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 三阶段：logits→softmax→one-hot (`3stage`)

逐步将连续氨基酸偏好变为离散序列。。BDA 接入：`configuration_only`。

输入：目标PDB及其链/编号映射; target settings JSON内真实starting_pdb路径; advanced JSON及filters JSON; 匹配的AF2/MPNN权重、PyRosetta、DSSP与DAlphaBall

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_algorithm": "3stage",
  "soft_iterations": 75,
  "temporary_iterations": 45,
  "hard_iterations": 5
}
```

输出检查：保存解析后的三份JSON及源码/权重身份；检查Trajectory、MPNN和Accepted统计的不同来源；逐序列核对复核模型ID、结构文件和全部过滤值

限制：library生成JSON已实现；live仅传文件路径，不自动接入界面同名标量；算法改变的是优化策略，不生成可解释为Kd的分数；本次未运行GPU任务；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [renderer](../../../qm-scripts/library/qm_job.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 四阶段并分段筛查 (`4stage`)

在logits/softmax/one-hot后加入PSSM半贪心，固定版本含中间pLDDT终止条件。。BDA 接入：`configuration_only`。

输入：目标PDB及其链/编号映射; target settings JSON内真实starting_pdb路径; advanced JSON及filters JSON; 匹配的AF2/MPNN权重、PyRosetta、DSSP与DAlphaBall

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_algorithm": "4stage",
  "soft_iterations": 75,
  "temporary_iterations": 45,
  "hard_iterations": 5,
  "greedy_iterations": 15
}
```

输出检查：保存解析后的三份JSON及源码/权重身份；检查Trajectory、MPNN和Accepted统计的不同来源；逐序列核对复核模型ID、结构文件和全部过滤值

限制：library生成JSON已实现；live仅传文件路径，不自动接入界面同名标量；算法改变的是优化策略，不生成可解释为Kd的分数；本次未运行GPU任务；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [renderer](../../../qm-scripts/library/qm_job.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 半贪心突变优化 (`greedy`)

以降低设计loss的随机突变搜索序列。。BDA 接入：`configuration_only`。

输入：目标PDB及其链/编号映射; target settings JSON内真实starting_pdb路径; advanced JSON及filters JSON; 匹配的AF2/MPNN权重、PyRosetta、DSSP与DAlphaBall

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_algorithm": "greedy",
  "greedy_iterations": 15,
  "greedy_percentage": 1
}
```

输出检查：保存解析后的三份JSON及源码/权重身份；检查Trajectory、MPNN和Accepted统计的不同来源；逐序列核对复核模型ID、结构文件和全部过滤值

限制：library生成JSON已实现；live仅传文件路径，不自动接入界面同名标量；算法改变的是优化策略，不生成可解释为Kd的分数；本次未运行GPU任务；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [renderer](../../../qm-scripts/library/qm_job.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### MCMC序列搜索 (`mcmc`)

用源码设定的初始温度及退火策略进行突变搜索，不是分子动力学。。BDA 接入：`configuration_only`。

输入：目标PDB及其链/编号映射; target settings JSON内真实starting_pdb路径; advanced JSON及filters JSON; 匹配的AF2/MPNN权重、PyRosetta、DSSP与DAlphaBall

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_algorithm": "mcmc",
  "greedy_iterations": 15,
  "greedy_percentage": 1
}
```

输出检查：保存解析后的三份JSON及源码/权重身份；检查Trajectory、MPNN和Accepted统计的不同来源；逐序列核对复核模型ID、结构文件和全部过滤值

限制：library生成JSON已实现；live仅传文件路径，不自动接入界面同名标量；算法改变的是优化策略，不生成可解释为Kd的分数；本次未运行GPU任务；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [renderer](../../../qm-scripts/library/qm_job.py), live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 仅生成初始设计轨迹 (`hallucination_only`)

关闭ProteinMPNN分支，保留AF2初始设计及其轨迹评价。。BDA 接入：`unverified`。

输入：相同target/advanced/filters依赖

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "enable_mpnn": false,
  "max_trajectories": 10
}
```

输出检查：核对Trajectory统计和结构；确认终止条件使用轨迹上限，不能只等待Accepted数量

限制：不等于完成MPNN改序列和完整复核接受流程；示例max_trajectories=10是上游JSON有效意图，但当前library布尔类型会拒绝数值；生成器类型未修复前此有限轨迹模式不能完整生成。；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py)

## 使用方法

1. 选择设计算法并明确目标PDB、链映射和热点；先检查裁剪是否改变目标表面。
2. 用library配置生成target.json、advanced.json、filters.json，审阅所有默认阈值；与live界面字段分开核对。
3. 将三个JSON及其引用PDB/权重路径在执行节点落实；live settings端口并不自动上传JSON引用的所有文件。
4. 当前enabled不等于已证明运行；按BDA预览检查环境、实际命令、输出根目录及声明输出端口。
5. 实际运行后按当前候选序列汇总Trajectory/MPNN/Accepted与逐模型结构；补独立预测/实验，不从ipTM或Rosetta分数反算Kd。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `design_path`

输出根目录，存放轨迹、MPNN、接受设计和统计。须指向运行节点可写路径；live不会自动替换成BDA_OUTPUT_DIR。

类型：`string`；单位：路径；来源记录默认：`/content/drive/My Drive/BindCraft/PDL1/`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:design_path（library JSON bundle）；live只读上传JSON`；BDA 别名：`["design_path"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=\"outputs/bindcraft\""]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `binder_name`

设计名称前缀；用于文件和统计标识，不是蛋白序列。

类型：`string`；单位：文本；来源记录默认：`PDL1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:binder_name（library JSON bundle）；live只读上传JSON`；BDA 别名：`["binder_name"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=\"BDA_Binder\""]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `starting_pdb`

目标蛋白PDB路径；由target JSON引用，必须在执行节点存在。

类型：`string`；单位：PDB路径；来源记录默认：`/content/bindcraft/example/PDL1.pdb`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:starting_pdb（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `chains`

选择输入PDB中参与目标建模的链，其余链被忽略；用真实PDB链ID并保留映射。

类型：`string`；单位：链ID列表；来源记录默认：`A`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:chains（library JSON bundle）；live只读上传JSON`；BDA 别名：`["chains"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=\"A\""]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `target_hotspot_residues`

目标接触引导残基，可用1,2-10或A1-10,B1-20；null/空字符串表示不指定热点。热点不是已验证表位。

类型：`string`；单位：链/残基编号；来源记录默认：`56`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:target_hotspot_residues（library JSON bundle）；live只读上传JSON`；BDA 别名：`["target_hotspot_residues"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=\"\""]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `lengths`

设计binder长度的整数范围；源码从min到max含端点抽样，须为JSON数值数组，不能直接写UI字符串70-120。

类型：`json`；单位：残基；来源记录默认：`[65, 150]`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:lengths（library JSON bundle）；live只读上传JSON`；BDA 别名：`["lengths"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=\"70-120\""]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `number_of_final_designs`

期望得到通过全部已启用筛选的设计数量；是停止目标，不是启动轨迹数或实验成功数。

类型：`integer`；单位：设计数；来源记录默认：`100`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`target.json:number_of_final_designs（library JSON bundle）；live只读上传JSON`；BDA 别名：`["number_of_final_designs"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=100"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md), [catalog](../../../qm-scripts/library/catalog.json)

### `omit_AAs`

设计阶段排除的单字母氨基酸集合；约束并非绝对保证，需配合force_reject_AA和输出序列检查。

类型：`string`；单位：单字母AA集合；来源记录默认：`C`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:omit_AAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `force_reject_AA`

在序列含omit_AAs时强制拒绝该序列；与优化阶段的氨基酸排除机制分开。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:force_reject_AA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `use_multimer_design`

选择AF2-multimer或AF2-ptm用于设计；固定版本根据此开关设置后续复核模型，不代表正交实验。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:use_multimer_design（library JSON bundle）；live只读上传JSON`；BDA 别名：`["use_multimer_design"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=true"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `design_algorithm`

选择2stage、3stage、4stage、greedy或mcmc的序列优化策略；不同阶段只读取其适用迭代字段。

类型：`string`；单位：枚举；来源记录默认：`4stage`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:design_algorithm（library JSON bundle）；live只读上传JSON`；BDA 别名：`["design_algorithm"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=\"4stage\""]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `sample_models`

在设计过程中抽样不同AF2参数模型以减少针对单模型优化；不是生成结构数。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:sample_models（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `rm_template_seq_design`

设计阶段移除目标模板的序列特征，以改变模板约束信息；不删除输入目标蛋白。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:rm_template_seq_design（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `rm_template_seq_predict`

复核阶段移除目标模板序列特征；需记录以解释与原始设计的差异。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:rm_template_seq_predict（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `rm_template_sc_design`

设计阶段移除目标模板侧链信息；不是侧链能量项权重。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:rm_template_sc_design（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `rm_template_sc_predict`

复核阶段移除目标模板侧链信息；不等于已采样所有侧链构象。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:rm_template_sc_predict（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `predict_initial_guess`

复核时把设计的原子坐标作为初始猜测，会使复核带有起始构象信息。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:predict_initial_guess（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `predict_bigbang`

控制复核结构模块的原子坐标初始化偏置；不是新的独立物理模拟。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:predict_bigbang（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `soft_iterations`

连续logits序列优化阶段迭代预算；4stage另含源码固定的初筛步骤。

类型：`integer`；单位：优化步；来源记录默认：`75`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:soft_iterations（library JSON bundle）；live只读上传JSON`；BDA 别名：`["soft_iterations"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=50", "4stage先固定执行50步logits；soft_iterations≤50不会取消这50步，只令后续额外logits为零。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `temporary_iterations`

softmax序列概率逐步离散化阶段的迭代数；仅适用于包含此阶段的算法。

类型：`integer`；单位：优化步；来源记录默认：`45`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:temporary_iterations（library JSON bundle）；live只读上传JSON`；BDA 别名：`["temporary_iterations"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=50"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `hard_iterations`

one-hot离散序列优化阶段迭代数；仅适用于包含此阶段的算法。

类型：`integer`；单位：优化步；来源记录默认：`5`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:hard_iterations（library JSON bundle）；live只读上传JSON`；BDA 别名：`["hard_iterations"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=10"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `greedy_iterations`

半贪心或MCMC突变搜索阶段迭代数；不是每位点允许的突变数。

类型：`integer`；单位：优化步；来源记录默认：`15`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:greedy_iterations（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `greedy_percentage`

每轮尝试突变数量由ceil(binder长度×此值/100)计算；是长度百分数。

类型：`integer`；单位：%；来源记录默认：`1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:greedy_percentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `save_design_animations`

保存设计过程动画；增加存储，不改变科学评分。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:save_design_animations（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `save_design_trajectory_plots`

保存设计loss/指标轨迹图；用于追踪优化过程，不替代原始统计。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:save_design_trajectory_plots（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_plddt`

设计目标中的binder pLDDT loss系数；不是最终pLDDT筛选阈值。

类型：`number`；单位：loss权重；来源记录默认：`0.1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_plddt（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_pae_intra`

binder内部预测对齐误差loss系数；不是Å单位误差值。

类型：`number`；单位：loss权重；来源记录默认：`0.4`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_pae_intra（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_pae_inter`

binder–目标跨链预测对齐误差loss系数；不代表结合能。

类型：`number`；单位：loss权重；来源记录默认：`0.1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_pae_inter（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_con_intra`

binder内部接触loss的系数；接触定义由距离和数目参数给定。

类型：`number`；单位：loss权重；来源记录默认：`1.0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_con_intra（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_con_inter`

binder–目标跨链接触loss的系数；优化接触不等于证明结合。

类型：`number`；单位：loss权重；来源记录默认：`1.0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_con_inter（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `intra_contact_distance`

设计loss内部Cβ接触距离截断；固定代码同时设置seqsep=9以排除邻近序列局部接触。

类型：`number`；单位：Å；来源记录默认：`14.0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:intra_contact_distance（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `inter_contact_distance`

设计loss跨链Cβ接触距离截断；与后处理4Å原子接触界面定义不同。

类型：`number`；单位：Å；来源记录默认：`20.0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:inter_contact_distance（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `intra_contact_number`

设计loss希望每个接触残基形成的链内接触数；用于loss构造而非已观察接触计数。

类型：`integer`；单位：接触数；来源记录默认：`2`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:intra_contact_number（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `inter_contact_number`

设计loss希望形成的跨链接触数量设置；不是输出界面残基数。

类型：`integer`；单位：接触数；来源记录默认：`2`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:inter_contact_number（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_helicity`

螺旋倾向loss系数；符号改变结构偏好，负值用于偏向较少螺旋/更多β倾向，不保证拓扑。

类型：`number`；单位：loss权重；来源记录默认：`-0.3`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_helicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `random_helicity`

逐轨迹从Uniform(-3,1)抽样螺旋倾向权重并四舍五入至两位小数；固定源码与README所写-1到1不同，以源码及实际日志为准。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:random_helicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py)

### `use_i_ptm_loss`

是否加入界面pTM设计loss；开关与其权重独立。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:use_i_ptm_loss（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_iptm`

界面pTM loss系数，仅use_i_ptm_loss启用时生效；不是结合概率。

类型：`number`；单位：loss权重；来源记录默认：`0.05`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_iptm（library JSON bundle）；live只读上传JSON`；BDA 别名：`["weights_iptm"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=1.0"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `use_rg_loss`

是否加入binder回转半径约束loss，用于几何紧致性偏好。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:use_rg_loss（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_rg`

回转半径loss系数；不是回转半径本身。

类型：`number`；单位：loss权重；来源记录默认：`0.3`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_rg（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `use_termini_distance_loss`

是否加入binder N端至C端距离loss，用于拉近两端的设计偏好。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:use_termini_distance_loss（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `weights_termini_loss`

端点距离loss系数，仅对应loss启用时生效；不是Å距离。

类型：`number`；单位：loss权重；来源记录默认：`0.1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:weights_termini_loss（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `enable_mpnn`

是否在通过初始轨迹检查后执行ProteinMPNN及后续序列复核分支。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:enable_mpnn（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `mpnn_fix_interface`

ProteinMPNN改序列时固定初始设计界面残基；固定的是序列设计位置，不保证构象不动。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:mpnn_fix_interface（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `num_seqs`

每条初始binder轨迹尝试抽样的ProteinMPNN序列数；经重复/氨基酸等筛选后实际复核数可能更少。

类型：`integer`；单位：序列数；来源记录默认：`20`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:num_seqs（library JSON bundle）；live只读上传JSON`；BDA 别名：`["num_seqs"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=8"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `max_mpnn_sequences`

单条轨迹最多保留多少个通过筛选的MPNN设计，避免同一骨架占据过多接受名额。

类型：`integer`；单位：接受序列数/轨迹；来源记录默认：`2`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:max_mpnn_sequences（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `sampling_temp`

ProteinMPNN类别采样温度，控制序列多样性；无热力学温度意义，边界行为按依赖版本验证。

类型：`number`；单位：无量纲；来源记录默认：`0.1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:sampling_temp（library JSON bundle）；live只读上传JSON`；BDA 别名：`["sampling_temp"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=0.1"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `backbone_noise`

ProteinMPNN采样时添加的骨架坐标噪声尺度；不是AF2回收次数或MD热噪声。

类型：`number`；单位：坐标噪声尺度（Å，需匹配MPNN版本）；来源记录默认：`0.0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:backbone_noise（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `model_path`

传给ProteinMPNN模型加载器的模型名/权重标识，例如v_48_020；不是目标蛋白PDB。

类型：`string`；单位：权重标识；来源记录默认：`v_48_020`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:model_path（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `mpnn_weights`

选择original或soluble ProteinMPNN权重族；soluble是训练权重类型，不保证产物可溶。

类型：`string`；单位：枚举；来源记录默认：`soluble`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:mpnn_weights（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `save_mpnn_fasta`

是否另存MPNN序列FASTA；即使关闭仍需从CSV保留序列身份。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:save_mpnn_fasta（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `num_recycles_design`

设计阶段AF2内部recycle次数，增加模型迭代；不是独立模型重复数。

类型：`integer`；单位：recycle次数；来源记录默认：`1`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:num_recycles_design（library JSON bundle）；live只读上传JSON`；BDA 别名：`["num_recycles_design"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=3"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `num_recycles_validation`

复核阶段AF2内部recycle次数；设计与复核使用不同设置需记录。

类型：`integer`；单位：recycle次数；来源记录默认：`3`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:num_recycles_validation（library JSON bundle）；live只读上传JSON`；BDA 别名：`["num_recycles_validation"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=3"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `optimise_beta`

检测到β富集轨迹后启用额外优化设置；属于算法条件分支。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:optimise_beta（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `optimise_beta_extra_soft`

β优化触发时增加的logits软阶段迭代数。

类型：`integer`；单位：额外优化步；来源记录默认：`0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:optimise_beta_extra_soft（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `optimise_beta_extra_temp`

β优化触发时增加的softmax阶段迭代数。

类型：`integer`；单位：额外优化步；来源记录默认：`0`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:optimise_beta_extra_temp（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `optimise_beta_recycles_design`

β优化触发后的设计recycle设置；不是总轨迹数。

类型：`integer`；单位：recycle次数；来源记录默认：`3`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:optimise_beta_recycles_design（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `optimise_beta_recycles_valid`

β轨迹后续复核的recycle设置；与通常复核设置区分。

类型：`integer`；单位：recycle次数；来源记录默认：`3`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:optimise_beta_recycles_valid（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `remove_unrelaxed_trajectory`

删除初始设计未Relax PDB以省空间；设true将失去前后坐标直接对照。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:remove_unrelaxed_trajectory（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `remove_unrelaxed_complex`

删除MPNN复核复合物的未Relax PDB；Relax后结构仍保留。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:remove_unrelaxed_complex（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `remove_binder_monomer`

评价后删除binder单独预测结构以省空间；不利于追踪Binder_RMSD/置信度证据。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:remove_binder_monomer（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `zip_animations`

流程结束时压缩动画文件，不是额外科学计算。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:zip_animations（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `zip_plots`

流程结束时压缩轨迹图文件，不是重新计算统计。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:zip_plots（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `save_trajectory_pickle`

保存初始设计的Python序列化完整轨迹；体积大，跨依赖版本读取需谨慎。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:save_trajectory_pickle（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `max_trajectories`

设计轨迹上限；源码以false表示不启用上限，也接受数值计数。旧catalog误归boolean，无法表达整数上限。

类型：`boolean`；单位：false或正整数轨迹数；来源记录默认：`false`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:max_trajectories（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "当前catalog type=boolean与源码false\|integer不完全一致；整数上限需修正/验证生成器后再用。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `enable_rejection_check`

是否在达到监测起点后根据接受率提前终止低产出流程。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:enable_rejection_check（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `acceptance_rate`

早停监测的最低接受设计/轨迹比值；不是生物学结合成功率。

类型：`number`；单位：比例；来源记录默认：`0.01`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:acceptance_rate（library JSON bundle）；live只读上传JSON`；BDA 别名：`["acceptance_rate"]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。", "BDA字段存在但live命令没有读取该标量；需在对应JSON内明确设置。", "live UI默认值=0.01"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `start_monitoring`

达到此轨迹数后才检查接受率，避免过早停止。

类型：`integer`；单位：轨迹数；来源记录默认：`600`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:start_monitoring（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `af_params_dir`

AF2模型参数所在目录；空值可能由初始化逻辑补为安装路径，须保存解析后路径。

类型：`string`；单位：目录；来源记录默认：``。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:af_params_dir（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `dssp_path`

DSSP二级结构分析程序路径，影响二级结构比例与相关统计是否可算。

类型：`string`；单位：程序路径；来源记录默认：``。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:dssp_path（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `dalphaball_path`

DAlphaBall辅助程序路径，用于BuriedUnsatHbonds等SASA计算依赖。

类型：`string`；单位：程序路径；来源记录默认：``。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`advanced.json:dalphaball_path（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定版本library，不代表live UI或实际提交JSON。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json), [catalog](../../../qm-scripts/library/catalog.json)

### `MPNN_score`

单序列统计。ProteinMPNN返回的序列评分（通常平均负对数似然）；较低表示模型更偏好该序列，不能解释为结合能。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：模型分数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:MPNN_score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `MPNN_seq_recovery`

单序列统计。MPNN序列相对原轨迹序列的一致比例；保真程度不是性能提升。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:MPNN_seq_recovery（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_pLDDT`

跨实际有记录的AF2模型均值。AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_pLDDT`

第1个AF2参数模型结果；编号不是重复或排名。AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_pLDDT`

第2个AF2参数模型结果；编号不是重复或排名。AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_pLDDT`

第3个AF2参数模型结果；编号不是重复或排名。AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_pLDDT`

第4个AF2参数模型结果；编号不是重复或排名。AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_pLDDT`

第5个AF2参数模型结果；编号不是重复或排名。AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_pTM`

跨实际有记录的AF2模型均值。AF2复合物的全局拓扑置信评分。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.55}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_pTM`

第1个AF2参数模型结果；编号不是重复或排名。AF2复合物的全局拓扑置信评分。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.55}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_pTM`

第2个AF2参数模型结果；编号不是重复或排名。AF2复合物的全局拓扑置信评分。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.55}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_pTM`

第3个AF2参数模型结果；编号不是重复或排名。AF2复合物的全局拓扑置信评分。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_pTM`

第4个AF2参数模型结果；编号不是重复或排名。AF2复合物的全局拓扑置信评分。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_pTM`

第5个AF2参数模型结果；编号不是重复或排名。AF2复合物的全局拓扑置信评分。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_i_pTM`

跨实际有记录的AF2模型均值。AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_i_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_i_pTM`

第1个AF2参数模型结果；编号不是重复或排名。AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_i_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_i_pTM`

第2个AF2参数模型结果；编号不是重复或排名。AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_i_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_i_pTM`

第3个AF2参数模型结果；编号不是重复或排名。AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_i_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_i_pTM`

第4个AF2参数模型结果；编号不是重复或排名。AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_i_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_i_pTM`

第5个AF2参数模型结果；编号不是重复或排名。AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_i_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_pAE`

跨实际有记录的AF2模型均值。ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_pAE`

第1个AF2参数模型结果；编号不是重复或排名。ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_pAE`

第2个AF2参数模型结果；编号不是重复或排名。ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_pAE`

第3个AF2参数模型结果；编号不是重复或排名。ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_pAE`

第4个AF2参数模型结果；编号不是重复或排名。ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_pAE`

第5个AF2参数模型结果；编号不是重复或排名。ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_i_pAE`

跨实际有记录的AF2模型均值。跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": 0.35}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_i_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_i_pAE`

第1个AF2参数模型结果；编号不是重复或排名。跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": 0.35}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_i_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_i_pAE`

第2个AF2参数模型结果；编号不是重复或排名。跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": 0.35}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_i_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_i_pAE`

第3个AF2参数模型结果；编号不是重复或排名。跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_i_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_i_pAE`

第4个AF2参数模型结果；编号不是重复或排名。跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_i_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_i_pAE`

第5个AF2参数模型结果；编号不是重复或排名。跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_i_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_i_pLDDT`

跨实际有记录的AF2模型均值。4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_i_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_i_pLDDT`

第1个AF2参数模型结果；编号不是重复或排名。4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_i_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_i_pLDDT`

第2个AF2参数模型结果；编号不是重复或排名。4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_i_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_i_pLDDT`

第3个AF2参数模型结果；编号不是重复或排名。4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_i_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_i_pLDDT`

第4个AF2参数模型结果；编号不是重复或排名。4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_i_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_i_pLDDT`

第5个AF2参数模型结果；编号不是重复或排名。4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_i_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_ss_pLDDT`

跨实际有记录的AF2模型均值。binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_ss_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_ss_pLDDT`

第1个AF2参数模型结果；编号不是重复或排名。binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_ss_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_ss_pLDDT`

第2个AF2参数模型结果；编号不是重复或排名。binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_ss_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_ss_pLDDT`

第3个AF2参数模型结果；编号不是重复或排名。binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_ss_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_ss_pLDDT`

第4个AF2参数模型结果；编号不是重复或排名。binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_ss_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_ss_pLDDT`

第5个AF2参数模型结果；编号不是重复或排名。binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_ss_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Unrelaxed_Clashes`

跨实际有记录的AF2模型均值。Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Unrelaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Unrelaxed_Clashes`

第1个AF2参数模型结果；编号不是重复或排名。Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Unrelaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Unrelaxed_Clashes`

第2个AF2参数模型结果；编号不是重复或排名。Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Unrelaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Unrelaxed_Clashes`

第3个AF2参数模型结果；编号不是重复或排名。Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Unrelaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Unrelaxed_Clashes`

第4个AF2参数模型结果；编号不是重复或排名。Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Unrelaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Unrelaxed_Clashes`

第5个AF2参数模型结果；编号不是重复或排名。Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Unrelaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Relaxed_Clashes`

跨实际有记录的AF2模型均值。Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Relaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Relaxed_Clashes`

第1个AF2参数模型结果；编号不是重复或排名。Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Relaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Relaxed_Clashes`

第2个AF2参数模型结果；编号不是重复或排名。Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Relaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Relaxed_Clashes`

第3个AF2参数模型结果；编号不是重复或排名。Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Relaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Relaxed_Clashes`

第4个AF2参数模型结果；编号不是重复或排名。Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Relaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Relaxed_Clashes`

第5个AF2参数模型结果；编号不是重复或排名。Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：原子对数；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Relaxed_Clashes（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_Energy_Score`

跨实际有记录的AF2模型均值。复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": 0}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_Energy_Score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_Energy_Score`

第1个AF2参数模型结果；编号不是重复或排名。复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": 0}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_Energy_Score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_Energy_Score`

第2个AF2参数模型结果；编号不是重复或排名。复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": 0}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_Energy_Score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_Energy_Score`

第3个AF2参数模型结果；编号不是重复或排名。复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_Energy_Score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_Energy_Score`

第4个AF2参数模型结果；编号不是重复或排名。复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_Energy_Score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_Energy_Score`

第5个AF2参数模型结果；编号不是重复或排名。复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_Energy_Score（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Surface_Hydrophobicity`

跨实际有记录的AF2模型均值。独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": 0.35}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Surface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Surface_Hydrophobicity`

第1个AF2参数模型结果；编号不是重复或排名。独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": 0.35}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Surface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Surface_Hydrophobicity`

第2个AF2参数模型结果；编号不是重复或排名。独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": 0.35}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Surface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Surface_Hydrophobicity`

第3个AF2参数模型结果；编号不是重复或排名。独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Surface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Surface_Hydrophobicity`

第4个AF2参数模型结果；编号不是重复或排名。独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Surface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Surface_Hydrophobicity`

第5个AF2参数模型结果；编号不是重复或排名。独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1比例；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Surface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_ShapeComplementarity`

跨实际有记录的AF2模型均值。InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲；来源记录默认：`{"higher": true, "threshold": 0.6}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_ShapeComplementarity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_ShapeComplementarity`

第1个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲；来源记录默认：`{"higher": true, "threshold": 0.55}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_ShapeComplementarity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_ShapeComplementarity`

第2个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲；来源记录默认：`{"higher": true, "threshold": 0.55}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_ShapeComplementarity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_ShapeComplementarity`

第3个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_ShapeComplementarity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_ShapeComplementarity`

第4个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_ShapeComplementarity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_ShapeComplementarity`

第5个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_ShapeComplementarity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_PackStat`

跨实际有记录的AF2模型均值。InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_PackStat（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_PackStat`

第1个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_PackStat（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_PackStat`

第2个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_PackStat（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_PackStat`

第3个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_PackStat（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_PackStat`

第4个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_PackStat（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_PackStat`

第5个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_PackStat（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_dG`

跨实际有记录的AF2模型均值。InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": 0}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_dG（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_dG`

第1个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": 0}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_dG（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_dG`

第2个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": 0}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_dG（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_dG`

第3个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_dG（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_dG`

第4个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_dG（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_dG`

第5个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：REU；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_dG（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_dSASA`

跨实际有记录的AF2模型均值。InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å²；来源记录默认：`{"higher": true, "threshold": 1}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_dSASA`

第1个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å²；来源记录默认：`{"higher": true, "threshold": 1}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_dSASA`

第2个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å²；来源记录默认：`{"higher": true, "threshold": 1}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_dSASA`

第3个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å²；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_dSASA`

第4个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å²；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_dSASA`

第5个AF2参数模型结果；编号不是重复或排名。InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å²；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_dG/dSASA`

跨实际有记录的AF2模型均值。源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：100×REU/Å²；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_dG/dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_dG/dSASA`

第1个AF2参数模型结果；编号不是重复或排名。源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：100×REU/Å²；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_dG/dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_dG/dSASA`

第2个AF2参数模型结果；编号不是重复或排名。源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：100×REU/Å²；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_dG/dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_dG/dSASA`

第3个AF2参数模型结果；编号不是重复或排名。源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：100×REU/Å²；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_dG/dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_dG/dSASA`

第4个AF2参数模型结果；编号不是重复或排名。源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：100×REU/Å²；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_dG/dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_dG/dSASA`

第5个AF2参数模型结果；编号不是重复或排名。源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：100×REU/Å²；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_dG/dSASA（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Interface_SASA_%`

跨实际有记录的AF2模型均值。源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%（源码定义比值）；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Interface_SASA_%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Interface_SASA_%`

第1个AF2参数模型结果；编号不是重复或排名。源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%（源码定义比值）；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Interface_SASA_%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Interface_SASA_%`

第2个AF2参数模型结果；编号不是重复或排名。源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%（源码定义比值）；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Interface_SASA_%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Interface_SASA_%`

第3个AF2参数模型结果；编号不是重复或排名。源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%（源码定义比值）；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Interface_SASA_%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Interface_SASA_%`

第4个AF2参数模型结果；编号不是重复或排名。源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%（源码定义比值）；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Interface_SASA_%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Interface_SASA_%`

第5个AF2参数模型结果；编号不是重复或排名。源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%（源码定义比值）；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Interface_SASA_%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Interface_Hydrophobicity`

跨实际有记录的AF2模型均值。binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Interface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Interface_Hydrophobicity`

第1个AF2参数模型结果；编号不是重复或排名。binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Interface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Interface_Hydrophobicity`

第2个AF2参数模型结果；编号不是重复或排名。binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Interface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Interface_Hydrophobicity`

第3个AF2参数模型结果；编号不是重复或排名。binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Interface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Interface_Hydrophobicity`

第4个AF2参数模型结果；编号不是重复或排名。binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Interface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Interface_Hydrophobicity`

第5个AF2参数模型结果；编号不是重复或排名。binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Interface_Hydrophobicity（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_n_InterfaceResidues`

跨实际有记录的AF2模型均值。与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：残基数；来源记录默认：`{"higher": true, "threshold": 7}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_n_InterfaceResidues（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_n_InterfaceResidues`

第1个AF2参数模型结果；编号不是重复或排名。与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：残基数；来源记录默认：`{"higher": true, "threshold": 7}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_n_InterfaceResidues（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_n_InterfaceResidues`

第2个AF2参数模型结果；编号不是重复或排名。与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：残基数；来源记录默认：`{"higher": true, "threshold": 7}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_n_InterfaceResidues（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_n_InterfaceResidues`

第3个AF2参数模型结果；编号不是重复或排名。与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：残基数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_n_InterfaceResidues（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_n_InterfaceResidues`

第4个AF2参数模型结果；编号不是重复或排名。与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：残基数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_n_InterfaceResidues（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_n_InterfaceResidues`

第5个AF2参数模型结果；编号不是重复或排名。与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：残基数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_n_InterfaceResidues（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_n_InterfaceHbonds`

跨实际有记录的AF2模型均值。Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：氢键数；来源记录默认：`{"higher": true, "threshold": 3}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_n_InterfaceHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_n_InterfaceHbonds`

第1个AF2参数模型结果；编号不是重复或排名。Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：氢键数；来源记录默认：`{"higher": true, "threshold": 3}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_n_InterfaceHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_n_InterfaceHbonds`

第2个AF2参数模型结果；编号不是重复或排名。Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：氢键数；来源记录默认：`{"higher": true, "threshold": 3}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_n_InterfaceHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_n_InterfaceHbonds`

第3个AF2参数模型结果；编号不是重复或排名。Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_n_InterfaceHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_n_InterfaceHbonds`

第4个AF2参数模型结果；编号不是重复或排名。Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_n_InterfaceHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_n_InterfaceHbonds`

第5个AF2参数模型结果；编号不是重复或排名。Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_n_InterfaceHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_InterfaceHbondsPercentage`

跨实际有记录的AF2模型均值。100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_InterfaceHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_InterfaceHbondsPercentage`

第1个AF2参数模型结果；编号不是重复或排名。100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_InterfaceHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_InterfaceHbondsPercentage`

第2个AF2参数模型结果；编号不是重复或排名。100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_InterfaceHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_InterfaceHbondsPercentage`

第3个AF2参数模型结果；编号不是重复或排名。100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_InterfaceHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_InterfaceHbondsPercentage`

第4个AF2参数模型结果；编号不是重复或排名。100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_InterfaceHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_InterfaceHbondsPercentage`

第5个AF2参数模型结果；编号不是重复或排名。100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的氢键数；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_InterfaceHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_n_InterfaceUnsatHbonds`

跨实际有记录的AF2模型均值。BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：计数/差分统计；来源记录默认：`{"higher": false, "threshold": 4}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_n_InterfaceUnsatHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_n_InterfaceUnsatHbonds`

第1个AF2参数模型结果；编号不是重复或排名。BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：计数/差分统计；来源记录默认：`{"higher": false, "threshold": 4}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_n_InterfaceUnsatHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_n_InterfaceUnsatHbonds`

第2个AF2参数模型结果；编号不是重复或排名。BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：计数/差分统计；来源记录默认：`{"higher": false, "threshold": 4}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_n_InterfaceUnsatHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_n_InterfaceUnsatHbonds`

第3个AF2参数模型结果；编号不是重复或排名。BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：计数/差分统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_n_InterfaceUnsatHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_n_InterfaceUnsatHbonds`

第4个AF2参数模型结果；编号不是重复或排名。BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：计数/差分统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_n_InterfaceUnsatHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_n_InterfaceUnsatHbonds`

第5个AF2参数模型结果；编号不是重复或排名。BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：计数/差分统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_n_InterfaceUnsatHbonds（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_InterfaceUnsatHbondsPercentage`

跨实际有记录的AF2模型均值。100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的未满足统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_InterfaceUnsatHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_InterfaceUnsatHbondsPercentage`

第1个AF2参数模型结果；编号不是重复或排名。100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的未满足统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_InterfaceUnsatHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_InterfaceUnsatHbondsPercentage`

第2个AF2参数模型结果；编号不是重复或排名。100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的未满足统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_InterfaceUnsatHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_InterfaceUnsatHbondsPercentage`

第3个AF2参数模型结果；编号不是重复或排名。100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的未满足统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_InterfaceUnsatHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_InterfaceUnsatHbondsPercentage`

第4个AF2参数模型结果；编号不是重复或排名。100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的未满足统计；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_InterfaceUnsatHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_InterfaceUnsatHbondsPercentage`

第5个AF2参数模型结果；编号不是重复或排名。100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：每100个界面残基的未满足统计；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_InterfaceUnsatHbondsPercentage（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。", "固定默认higher=true与其余同类字段方向不一致，虽threshold=null停用，启用前应审查，不能静默替用户改科学方向。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Interface_Helix%`

跨实际有记录的AF2模型均值。binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Interface_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Interface_Helix%`

第1个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Interface_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Interface_Helix%`

第2个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Interface_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Interface_Helix%`

第3个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Interface_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Interface_Helix%`

第4个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Interface_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Interface_Helix%`

第5个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Interface_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Interface_BetaSheet%`

跨实际有记录的AF2模型均值。binder界面中DSSP E残基占比；不是整个复合物β含量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Interface_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Interface_BetaSheet%`

第1个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP E残基占比；不是整个复合物β含量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Interface_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Interface_BetaSheet%`

第2个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP E残基占比；不是整个复合物β含量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Interface_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Interface_BetaSheet%`

第3个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP E残基占比；不是整个复合物β含量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Interface_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Interface_BetaSheet%`

第4个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP E残基占比；不是整个复合物β含量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Interface_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Interface_BetaSheet%`

第5个AF2参数模型结果；编号不是重复或排名。binder界面中DSSP E残基占比；不是整个复合物β含量。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Interface_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Interface_Loop%`

跨实际有记录的AF2模型均值。binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Interface_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Interface_Loop%`

第1个AF2参数模型结果；编号不是重复或排名。binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Interface_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Interface_Loop%`

第2个AF2参数模型结果；编号不是重复或排名。binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Interface_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Interface_Loop%`

第3个AF2参数模型结果；编号不是重复或排名。binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Interface_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Interface_Loop%`

第4个AF2参数模型结果；编号不是重复或排名。binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Interface_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Interface_Loop%`

第5个AF2参数模型结果；编号不是重复或排名。binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Interface_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_Helix%`

跨实际有记录的AF2模型均值。binder全部DSSP可统计残基中H/G/I比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_Helix%`

第1个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中H/G/I比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_Helix%`

第2个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中H/G/I比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_Helix%`

第3个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中H/G/I比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_Helix%`

第4个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中H/G/I比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_Helix%`

第5个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中H/G/I比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_Helix%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_BetaSheet%`

跨实际有记录的AF2模型均值。binder全部DSSP可统计残基中E比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_BetaSheet%`

第1个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中E比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_BetaSheet%`

第2个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中E比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_BetaSheet%`

第3个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中E比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_BetaSheet%`

第4个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中E比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_BetaSheet%`

第5个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中E比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_BetaSheet%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_Loop%`

跨实际有记录的AF2模型均值。binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": 90}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_Loop%`

第1个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": 90}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_Loop%`

第2个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": 90}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_Loop%`

第3个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_Loop%`

第4个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_Loop%`

第5个AF2参数模型结果；编号不是重复或排名。binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：%；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_Loop%（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_InterfaceAAs`

跨实际有记录的AF2模型均值。binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：按AA分组的残基数；来源记录默认：`{"A": {"higher": false, "threshold": null}, "C": {"higher": false, "threshold": null}, "D": {"higher": false, "threshold": null}, "E": {"higher": false, "threshold": null}, "F": {"higher": false, "threshold": null}, "G": {"higher": false, "threshold": null}, "H": {"higher": false, "threshold": null}, "I": {"higher": false, "threshold": null}, "K": {"higher": false, "threshold": 3}, "L": {"higher": false, "threshold": null}, "M": {"higher": false, "threshold": 3}, "N": {"higher": false, "threshold": null}, "P": {"higher": false, "threshold": null}, "Q": {"higher": false, "threshold": null}, "R": {"higher": false, "threshold": null}, "S": {"higher": false, "threshold": null}, "T": {"higher": false, "threshold": null}, "V": {"higher": false, "threshold": null}, "W": {"higher": false, "threshold": null}, "Y": {"higher": false, "threshold": null}}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_InterfaceAAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["每种AA分别设置threshold/higher；null关闭该AA过滤，计数均值可为小数。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_InterfaceAAs`

第1个AF2参数模型结果；编号不是重复或排名。binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：按AA分组的残基数；来源记录默认：`{"A": {"higher": false, "threshold": null}, "C": {"higher": false, "threshold": null}, "D": {"higher": false, "threshold": null}, "E": {"higher": false, "threshold": null}, "F": {"higher": false, "threshold": null}, "G": {"higher": false, "threshold": null}, "H": {"higher": false, "threshold": null}, "I": {"higher": false, "threshold": null}, "K": {"higher": false, "threshold": null}, "L": {"higher": false, "threshold": null}, "M": {"higher": false, "threshold": null}, "N": {"higher": false, "threshold": null}, "P": {"higher": false, "threshold": null}, "Q": {"higher": false, "threshold": null}, "R": {"higher": false, "threshold": null}, "S": {"higher": false, "threshold": null}, "T": {"higher": false, "threshold": null}, "V": {"higher": false, "threshold": null}, "W": {"higher": false, "threshold": null}, "Y": {"higher": false, "threshold": null}}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_InterfaceAAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["每种AA分别设置threshold/higher；null关闭该AA过滤，计数均值可为小数。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_InterfaceAAs`

第2个AF2参数模型结果；编号不是重复或排名。binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：按AA分组的残基数；来源记录默认：`{"A": {"higher": false, "threshold": null}, "C": {"higher": false, "threshold": null}, "D": {"higher": false, "threshold": null}, "E": {"higher": false, "threshold": null}, "F": {"higher": false, "threshold": null}, "G": {"higher": false, "threshold": null}, "H": {"higher": false, "threshold": null}, "I": {"higher": false, "threshold": null}, "K": {"higher": false, "threshold": null}, "L": {"higher": false, "threshold": null}, "M": {"higher": false, "threshold": null}, "N": {"higher": false, "threshold": null}, "P": {"higher": false, "threshold": null}, "Q": {"higher": false, "threshold": null}, "R": {"higher": false, "threshold": null}, "S": {"higher": false, "threshold": null}, "T": {"higher": false, "threshold": null}, "V": {"higher": false, "threshold": null}, "W": {"higher": false, "threshold": null}, "Y": {"higher": false, "threshold": null}}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_InterfaceAAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["每种AA分别设置threshold/higher；null关闭该AA过滤，计数均值可为小数。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_InterfaceAAs`

第3个AF2参数模型结果；编号不是重复或排名。binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：按AA分组的残基数；来源记录默认：`{"A": {"higher": false, "threshold": null}, "C": {"higher": false, "threshold": null}, "D": {"higher": false, "threshold": null}, "E": {"higher": false, "threshold": null}, "F": {"higher": false, "threshold": null}, "G": {"higher": false, "threshold": null}, "H": {"higher": false, "threshold": null}, "I": {"higher": false, "threshold": null}, "K": {"higher": false, "threshold": null}, "L": {"higher": false, "threshold": null}, "M": {"higher": false, "threshold": null}, "N": {"higher": false, "threshold": null}, "P": {"higher": false, "threshold": null}, "Q": {"higher": false, "threshold": null}, "R": {"higher": false, "threshold": null}, "S": {"higher": false, "threshold": null}, "T": {"higher": false, "threshold": null}, "V": {"higher": false, "threshold": null}, "W": {"higher": false, "threshold": null}, "Y": {"higher": false, "threshold": null}}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_InterfaceAAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["每种AA分别设置threshold/higher；null关闭该AA过滤，计数均值可为小数。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_InterfaceAAs`

第4个AF2参数模型结果；编号不是重复或排名。binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：按AA分组的残基数；来源记录默认：`{"A": {"higher": false, "threshold": null}, "C": {"higher": false, "threshold": null}, "D": {"higher": false, "threshold": null}, "E": {"higher": false, "threshold": null}, "F": {"higher": false, "threshold": null}, "G": {"higher": false, "threshold": null}, "H": {"higher": false, "threshold": null}, "I": {"higher": false, "threshold": null}, "K": {"higher": false, "threshold": null}, "L": {"higher": false, "threshold": null}, "M": {"higher": false, "threshold": null}, "N": {"higher": false, "threshold": null}, "P": {"higher": false, "threshold": null}, "Q": {"higher": false, "threshold": null}, "R": {"higher": false, "threshold": null}, "S": {"higher": false, "threshold": null}, "T": {"higher": false, "threshold": null}, "V": {"higher": false, "threshold": null}, "W": {"higher": false, "threshold": null}, "Y": {"higher": false, "threshold": null}}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_InterfaceAAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["每种AA分别设置threshold/higher；null关闭该AA过滤，计数均值可为小数。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_InterfaceAAs`

第5个AF2参数模型结果；编号不是重复或排名。binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：按AA分组的残基数；来源记录默认：`{"A": {"higher": false, "threshold": null}, "C": {"higher": false, "threshold": null}, "D": {"higher": false, "threshold": null}, "E": {"higher": false, "threshold": null}, "F": {"higher": false, "threshold": null}, "G": {"higher": false, "threshold": null}, "H": {"higher": false, "threshold": null}, "I": {"higher": false, "threshold": null}, "K": {"higher": false, "threshold": null}, "L": {"higher": false, "threshold": null}, "M": {"higher": false, "threshold": null}, "N": {"higher": false, "threshold": null}, "P": {"higher": false, "threshold": null}, "Q": {"higher": false, "threshold": null}, "R": {"higher": false, "threshold": null}, "S": {"higher": false, "threshold": null}, "T": {"higher": false, "threshold": null}, "V": {"higher": false, "threshold": null}, "W": {"higher": false, "threshold": null}, "Y": {"higher": false, "threshold": null}}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_InterfaceAAs（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["每种AA分别设置threshold/higher；null关闭该AA过滤，计数均值可为小数。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Hotspot_RMSD`

跨实际有记录的AF2模型均值。复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 6}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Hotspot_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Hotspot_RMSD`

第1个AF2参数模型结果；编号不是重复或排名。复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 6}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Hotspot_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Hotspot_RMSD`

第2个AF2参数模型结果；编号不是重复或排名。复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 6}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Hotspot_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Hotspot_RMSD`

第3个AF2参数模型结果；编号不是重复或排名。复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Hotspot_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Hotspot_RMSD`

第4个AF2参数模型结果；编号不是重复或排名。复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Hotspot_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Hotspot_RMSD`

第5个AF2参数模型结果；编号不是重复或排名。复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Hotspot_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Target_RMSD`

跨实际有记录的AF2模型均值。输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Target_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Target_RMSD`

第1个AF2参数模型结果；编号不是重复或排名。输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Target_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Target_RMSD`

第2个AF2参数模型结果；编号不是重复或排名。输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Target_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Target_RMSD`

第3个AF2参数模型结果；编号不是重复或排名。输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Target_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Target_RMSD`

第4个AF2参数模型结果；编号不是重复或排名。输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Target_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Target_RMSD`

第5个AF2参数模型结果；编号不是重复或排名。输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Target_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_pLDDT`

跨实际有记录的AF2模型均值。binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_pLDDT`

第1个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_pLDDT`

第2个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_pLDDT`

第3个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_pLDDT`

第4个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_pLDDT`

第5个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": 0.8}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_pLDDT（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_pTM`

跨实际有记录的AF2模型均值。binder单独预测分支的pTM拓扑置信度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_pTM`

第1个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pTM拓扑置信度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_pTM`

第2个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pTM拓扑置信度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_pTM`

第3个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pTM拓扑置信度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_pTM`

第4个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pTM拓扑置信度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_pTM`

第5个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的pTM拓扑置信度。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：0–1；来源记录默认：`{"higher": true, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_pTM（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_pAE`

跨实际有记录的AF2模型均值。binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_pAE`

第1个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_pAE`

第2个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_pAE`

第3个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_pAE`

第4个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_pAE`

第5个AF2参数模型结果；编号不是重复或排名。binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：无量纲（PAE/31）；来源记录默认：`{"higher": false, "threshold": null}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_pAE（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `Average_Binder_RMSD`

跨实际有记录的AF2模型均值。单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 3.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:Average_Binder_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `1_Binder_RMSD`

第1个AF2参数模型结果；编号不是重复或排名。单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 3.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:1_Binder_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `2_Binder_RMSD`

第2个AF2参数模型结果；编号不是重复或排名。单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 3.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:2_Binder_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `3_Binder_RMSD`

第3个AF2参数模型结果；编号不是重复或排名。单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 3.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:3_Binder_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `4_Binder_RMSD`

第4个AF2参数模型结果；编号不是重复或排名。单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 3.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:4_Binder_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `5_Binder_RMSD`

第5个AF2参数模型结果；编号不是重复或排名。单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 此参数是筛选规则对象，不是已计算的测量值。

类型：`json`；单位：Å；来源记录默认：`{"higher": false, "threshold": 3.5}`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc

生成映射：`filters.json:5_Binder_RMSD（library JSON bundle）；live只读上传JSON`；BDA 别名：`[]`。

约束与版本差异：["threshold=null关闭该过滤条件；higher=true保留≥阈值，false保留≤阈值。", "缺失值在check_filters中被跳过；均值helper把None当0，须先审核每模型覆盖，不能把通过筛选等同完整证据。"]

依据：[bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py), [catalog](../../../qm-scripts/library/catalog.json)

### `settings`

target JSON文件入口；live从settings端口选择排序第一项，JSON中的starting_pdb和design_path必须在执行节点可用。

类型：`artifact_ref`；单位：JSON文件；来源记录默认：``。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`--settings`；BDA 别名：`["settings"]`。

约束与版本差异：["文件需可解析且与固定版本键一致；端口绑定不等于已执行。"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py)

### `filters`

接受筛选JSON入口；相对默认路径取决于工作目录，不能假定指向安装目录。

类型：`artifact_ref`；单位：JSON文件；来源记录默认：`settings_filters/default_filters.json`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`--filters`；BDA 别名：`["filters"]`。

约束与版本差异：["文件需可解析且与固定版本键一致；端口绑定不等于已执行。"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py)

### `advanced`

设计高级JSON入口；live将路径交给--advanced，而不自动把页面标量写回文件。

类型：`artifact_ref`；单位：JSON文件；来源记录默认：`settings_advanced/default_4stage_multimer.json`。

适用模式：2stage, 3stage, 4stage, greedy, mcmc, hallucination_only

生成映射：`--advanced`；BDA 别名：`["advanced"]`。

约束与版本差异：["文件需可解析且与固定版本键一致；端口绑定不等于已执行。"]

依据：live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `2025.09`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| settings | artifact_ref |  | {} |
| filters | artifact_ref | settings_filters/default_filters.json | {} |
| advanced | artifact_ref | settings_advanced/default_4stage_multimer.json | {} |
| design_path | string | outputs/bindcraft | {} |
| binder_name | string | BDA_Binder | {} |
| chains | string | A | {} |
| target_hotspot_residues | string |  | {} |
| lengths | string | 70-120 | {} |
| number_of_final_designs | integer | 100 | {} |
| design_algorithm | enum | 4stage | {"options": ["2stage", "3stage", "4stage", "greedy", "mcmc"]} |
| use_multimer_design | boolean | true | {} |
| num_recycles_design | integer | 3 | {} |
| num_recycles_validation | integer | 3 | {} |
| num_seqs | integer | 8 | {} |
| sampling_temp | number | 0.1 | {} |
| soft_iterations | integer | 50 | {} |
| temporary_iterations | integer | 50 | {} |
| hard_iterations | integer | 10 | {} |
| weights_iptm | number | 1.0 | {} |
| acceptance_rate | number | 0.01 | {} |

**input_ports**

```json
[
  {
    "name": "settings",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Target settings JSON. BindCraft settings_target JSON. (from field 'settings')"
  },
  {
    "name": "filters",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Filter settings JSON. Filter JSON controlling acceptance thresholds. (from field 'filters')"
  },
  {
    "name": "advanced",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Advanced settings JSON. Advanced design algorithm/settings JSON. (from field 'advanced')"
  }
]
```

**output_ports**

```json
[
  {
    "name": "binder_designs",
    "kind": "protein_sequence",
    "artifact_type": "sequence_set",
    "filename_glob": "*",
    "description": "Accepted binder sequences and structures."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "BindCraft/AF2/MPNN/PyRosetta metrics."
  },
  {
    "name": "run_manifest",
    "kind": "params",
    "artifact_type": "manifest",
    "filename_glob": "*",
    "description": "Pipeline manifest."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "binder_designs",
      "artifact_types": [
        "sequence_set",
        "complex_structure"
      ],
      "required": true,
      "many": true,
      "help": "Accepted binder sequences and structures."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": true,
      "many": false,
      "help": "BindCraft/AF2/MPNN/PyRosetta metrics."
    },
    {
      "name": "run_manifest",
      "artifact_types": [
        "manifest"
      ],
      "required": true,
      "many": false,
      "help": "Pipeline manifest."
    }
  ]
}
```

**resources**

```json
{
  "gpu": true,
  "gpu_count": 1,
  "cpus": 1,
  "walltime_minutes": 2880,
  "cpus_evidence": "bindcraft.py takes --settings/--filters/--advanced only; no worker count is exposed upstream and none has been measured. Raise it from a measurement, not from the length of the pipeline."
}
```

命令摘要 SHA-256：`8d69ab7169f5c6ec35498071d2e557b4528f516959df2a72d8d91997dda0158d`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--advanced", "--filters", "--settings", "-maxdepth", "-type", "-u", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "advanced", "filters", "settings"]`。

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
| Trajectory statistics / PDB | AF2设计原始轨迹及其自评 | 序列、Å坐标、模型分数 | 不能与MPNN当前候选的复核记录混属同一序列；逐条存sequence SHA。 | [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py) |
| MPNN statistics / PDB | 每条MPNN序列及复合物、单独binder复核统计 | 按指标 | 保留所有模型身份和缺失状态；是否接受单独记录。 | [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py), [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py) |
| Accepted / final_design_stats.csv | 满足已启用规则的设计及排序统计 | 设计集合 | 不是实验验证；按序列映射结构，不把其他轨迹评分归给当前候选。 | [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py) |
| run_manifest（BDA声明端口） | BDA宣称需要的运行清单 | JSON/清单 | 上游未保证产生同名BDA清单，live无output_parser，必须另行核验产物契约。 | live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| MPNN_score | ProteinMPNN返回的序列评分（通常平均负对数似然）；较低表示模型更偏好该序列，不能解释为结合能。 | 模型分数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| MPNN_seq_recovery | MPNN序列相对原轨迹序列的一致比例；保真程度不是性能提升。 | 0–1比例 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| pLDDT | AF2复合物复核日志中的pLDDT，ColabDesign binder协议指标；保存其评价掩码，不能当作实验结构准确度。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| pTM | AF2复合物的全局拓扑置信评分。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| i_pTM | AF2复合物界面相对布置的置信评分，不是Kd或ΔG。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| pAE | ColabDesign复合物复核的归一化PAE摘要；此版本README定义为原Å值除31，不可直接标Å。 | 无量纲（PAE/31） | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| i_pAE | 跨链PAE的归一化摘要；需与原始PAE矩阵和受体/binder掩码对应。 | 无量纲（PAE/31） | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| i_pLDDT | 4Å原子接触定义的binder界面残基，其PDB B因子编码pLDDT均值除100；空界面源码回填0。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| ss_pLDDT | binder中DSSP螺旋或β折叠残基的pLDDT均值除100，排除loop；无相应残基时源码回填0。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Unrelaxed_Clashes | Relax前跨链非氢原子距离低于2.4Å的原子对计数；不是MolProbity标准clashscore。 | 原子对数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Relaxed_Clashes | Relax后同样2.4Å阈值的跨链非氢原子对计数；0只说明该阈值未检出冲突。 | 原子对数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Binder_Energy_Score | 复合物pose上以ChainSelector选择binder的TotalEnergyMetric分数；不是提取并独立Relax的apo蛋白能量。 | REU | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| Surface_Hydrophobicity | 独立binder链上LayerSelector选定表面残基中，apolar或PHE/TRP/TYR残基的数量比例；不是疏水SASA面积比。 | 0–1比例 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| ShapeComplementarity | InterfaceAnalyzer的界面几何形状互补统计；越高通常更互补，但不是亲和力。 | 无量纲 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| PackStat | InterfaceAnalyzer界面packing统计，带随机采样；须保留采样设置。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| dG | InterfaceAnalyzer得到的复合/分离评分差，源码启用pack_separated；不等于物理结合自由能或突变ΔΔG。 | REU | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| dSASA | InterfaceAnalyzer复合前后界面可及表面积差，保留Rosetta算法定义；不是单侧配体埋藏面积。 | Å² | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| dG/dSASA | 源码输出100×InterfaceAnalyzer.dG_dSASA_ratio，即面积归一化界面能的缩放值；不是原始无缩放比值。 | 100×REU/Å² | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| Interface_SASA_% | 源码计算100×interface_dSASA/binder链SasaMetric(pose)，分子为两侧界面差，不能按单侧物理覆盖率套0–100硬边界。 | %（源码定义比值） | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| Interface_Hydrophobicity | binder界面4Å接触残基中ACFILMPVWY数量占比乘100；与表面疏水比例不同。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| n_InterfaceResidues | 与目标A链任一原子距离≤4Å的binder B链残基数；不是两侧残基总数。 | 残基数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| n_InterfaceHbonds | Rosetta InterfaceAnalyzer跨界面氢键统计；不等于4Å接触数。 | 氢键数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| InterfaceHbondsPercentage | 100×跨界面氢键数/binder界面残基数；不是有氢键残基占比，可超过100。 | 每100个界面残基的氢键数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| n_InterfaceUnsatHbonds | BuriedUnsatHbonds filter的ddG-style未满足重原子极性统计；源码用DAlphaBall probe1.1、burial_cutoff_apo0.2，不是通用氢键断裂计数。 | 计数/差分统计 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| InterfaceUnsatHbondsPercentage | 100×未满足极性统计/binder界面残基数；空界面返回None，不能自动解读为零缺陷。 | 每100个界面残基的未满足统计 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| Interface_Helix% | binder界面中DSSP H/G/I残基占比；界面采用4Å原子接触。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Interface_BetaSheet% | binder界面中DSSP E残基占比；不是整个复合物β含量。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Interface_Loop% | binder界面中未归入H/G/I/E的残基比例；与是否无序不等价。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Binder_Helix% | binder全部DSSP可统计残基中H/G/I比例。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Binder_BetaSheet% | binder全部DSSP可统计残基中E比例。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Binder_Loop% | binder全部DSSP可统计残基中其余类别比例；不是实验无序比例。 | % | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| InterfaceAAs | binder 4Å接触界面每种标准单字母氨基酸的残基计数字典，各AA分别具有threshold/higher。 | 按AA分组的残基数 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py) |
| Hotspot_RMSD | 复核复合物binder相对初始轨迹binder的未另行最佳拟合RMSD；用于位置漂移，不是输入hotspot残基的自身RMSD。 | Å | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py) |
| Target_RMSD | 输入目标结构与复合物中目标的Cα配对/拟合RMSD；须追溯残基配对和缺失残基。 | Å | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py) |
| Binder_pLDDT | binder单独预测分支的pLDDT；与复合物binder置信度是不同状态证据。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| Binder_pTM | binder单独预测分支的pTM拓扑置信度。 | 0–1 | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| Binder_pAE | binder单独预测分支的归一化PAE摘要；不是复合物界面误差。 | 无量纲（PAE/31） | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py) |
| Binder_RMSD | 单独预测binder经前序对齐后相对初始轨迹binder的RMSD；失败可为None，需保留结构和配对。 | Å | 同名filter参数设置阈值；这里只说明运行输出，缺失不可当0。 | [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- live未将17个同名标量字段映射到JSON（仅3个路径传给程序）；多数library字段未在live界面逐项暴露。
- live input_adapter/output_parser均为空，目标PDB间接引用和BDA_OUTPUT_DIR收集契约未验证。
- 未绑定实际安装源码/权重哈希的运行证据；固定参考commit不代表集群安装一致。
- max_trajectories配置类型须支持false|integer；并核查5_InterfaceUnsatHbondsPercentage默认方向。

## 易错点

- 4stage有源码固定50步logits预筛和0.65等内部判据；用户filters并不控制所有内部提前淘汰。
- 复核模型编号1–5不是五次独立随机重复；Average也不保证五模型齐全。
- 归一化pAE不能按Å与AF3/PAE矩阵直接混排；输出阈值0.35不是0.35Å。
- InterfaceAnalyzer能量保持REU；n_InterfaceResidues和疏水性由4Å残基集合定义，不能与loss的20Å Cβ接触混用。
- 初始猜测/模板偏置必须记录；设计自评不等于独立验证。
- 保留原始结构与单独binder结构时关闭相应删除设置；缺失值或空界面返回的0需要额外状态。
- random_helicity源码抽样范围为-3到1，与同commit README的-1到1不一致；必须保留实际轨迹权重。

## 来源与版本

- live（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：审计时BDA注册字段、命令、输入输出端口、enabled及runtime_validation_status；commit `None`；读取 2026-09-15。
- [catalog](../../../qm-scripts/library/catalog.json)：历史参数库的类型和默认值，不等同运行时有效设置；commit `None`；读取 2026-09-15。
- [renderer](../../../qm-scripts/library/qm_job.py)：手工配置生成器的参数映射，区别于live ModelPlugin命令；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/bindcraft/README.md)：旧运行手册的状态记录；不是安装或运行成功证明；commit `None`；读取 2026-09-15。
- [bc-readme](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/README.md)：五种设计算法及设置概览；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-main](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/bindcraft.py)：序列筛选、三阶段统计文件、输出组织和终止条件；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-af](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/colabdesign_utils.py)：设计loss、分阶段算法、MPNN、复核模型指标；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-rosetta](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/pyrosetta_utils.py)：界面能/SASA/氢键/表面疏水性与Relax的真实公式；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-bio](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/biopython_utils.py)：4Å界面残基、2.4Å冲突计数、DSSP和结构比较；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-generic](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/functions/generic_utils.py)：模型选择、均值、缺失值和filter比较实现；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-advanced](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_advanced/default_4stage_multimer.json)：固定版本高级默认设置；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-filters](https://github.com/martinpacesa/BindCraft/blob/b971db42ba6e091afab63ccb30ae02215150a990/settings_filters/default_filters.json)：固定版本filter阈值对象；commit `b971db42ba6e091afab63ccb30ae02215150a990`；读取 2026-09-15。
- [bc-example](../../../qm-scripts/library/examples/04-binder-design/bindcraft.json)：可供手工生成三JSON的示例；不是live标量adapter；commit `None`；读取 2026-09-15。
