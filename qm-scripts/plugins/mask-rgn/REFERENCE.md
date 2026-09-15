# Mask RGN — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

历史本地MaskRGN配置与BDA实验性声明。模型源码models/maskrgnn_clean在本checkout不存在，未找到固定公开实现；下列49个library字段只解释配置用途和限制，不以同名论文补出未证实能力。BDA已disabled、无输入端口、无参数adapter。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/mask-rgn.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| experimental-0.1 | false | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 结构条件序列设计配置 (`structure_conditioned_config`)

历史示例表达从PDB和checkpoint对指定位置采样序列的意图；仅生成Hydra风格配置。。BDA 接入：`configuration_only`。

输入：PDB结构及编号映射; 真实本地inference.py与依赖; 匹配checkpoint及模型/data配置

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "pdb_path": "input/target.pdb",
  "test_model.path": "checkpoints/model.pt",
  "sample_num": 50,
  "steps": 25,
  "fixed_positions": "A:1-10",
  "output_dir": "output"
}
```

输出检查：源码恢复后验证命令确实读取每个字段；验证FASTA标准AA、数量、固定位置及结构–序列映射；记录模型与checkpoint哈希

限制：BDA disabled且无输入端口/参数传递，配置不能提交为已验证任务；位置语法仅见示例，未获parser实现确认；不能由模型名断言结构预测/结合能力；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-example](../../../qm-scripts/library/examples/02-sequence-design/maskrgn.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 关联位置/同源寡聚体配置 (`tied_design_config`)

历史配置提供tie_chain/tie_positions/homooligomer以表达关联设计意图；实际约束实现未验证。。BDA 接入：`unverified`。

输入：结构条件配置所需全部输入; 各链等价位置映射

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "homooligomer": true
}
```

输出检查：恢复源码后验证相关链/位点输出AA确实一致；确认固定位置与关联位置冲突处理

限制：具体tying规则和位置语法无法从配置字面确定，不能宣称任意对称性支持；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py)

### 训练及架构配置记录 (`training_config`)

记录合并进inference catalog的训练/架构/data字段，不代表inference入口能执行训练。。BDA 接入：`not_exposed`。

输入：实际训练入口及loss实现; 已许可且划分明确的数据集; 架构与checkpoint版本

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "train.lr": "5e-4",
  "train.train_epochs": 100,
  "model.name": "egnn"
}
```

输出检查：恢复源码后确认训练入口和每项配置读取；核对训练/验证划分、保存checkpoint及评估指标

限制：BDA当前不是已支持训练插件；改变架构维数可能与checkpoint不兼容；不能当作推理质量滑块；parameters是上游JSON/YAML/CLI语义的配置片段，不是完整可执行命令；示例路径、链号和位置须替换为实际输入，并按所述BDA绑定状态使用。

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py)

## 使用方法

1. 先查看disabled和源码缺失状态；本页只能用于配置整理。
2. 恢复实际inference.py、配置和checkpoint来源后，确认49个历史键中哪些在推理中读取、哪些只属于训练。
3. 建立PDB输入端口和明确的链/编号映射；解析design_positions、fixed_positions及tying冲突。
4. 实现BDA别名到真实配置键的adapter并保留解析后的完整配置；不要直接用字符串相似性代替映射。
5. 在已核验环境做最小输出与参数确认检查后再更新运行状态；核验序列数、固定残基、tying和得分定义。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `test_model.path`

待加载checkpoint路径；必须查实格式、模型架构及训练来源，历史默认路径不是现有文件证据。

类型：`string`；单位：checkpoint路径；来源记录默认：`outputs/maskrgnn/model/maskrgnn.pt`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:test_model.path=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `target_name`

目标任务标识，用于区分输入/输出；具体命名副作用未取得源码。

类型：`any`；单位：文本/空值；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:target_name=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `design_positions`

希望允许重新设计的位置集合；必须与固定位置、PDB链/编号明确对应，具体语法尚未核验。

类型：`any`；单位：位置集合/空值；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:design_positions=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `fixed_positions`

希望保持原氨基酸的位置集合；历史示例A:1-10仅为配置意图，不证明parser或固定约束有效。

类型：`any`；单位：位置集合/空值；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:fixed_positions=value；live未映射`；BDA 别名：`["fixed_positions"]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "BDA同名字段存在但命令未传递；BDA默认=\"\""]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `steps`

历史推理外层迭代步数设置；不能与diffusion.timesteps或ddim_steps合并，循环含义需源码确认。

类型：`integer`；单位：迭代步（实现未核验）；来源记录默认：`25`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:steps=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `pdb_path`

条件结构PDB路径；缺少有效结构输入时不能声称实现基于骨架的序列设计。

类型：`any`；单位：PDB路径；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:pdb_path=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `sample_num`

历史推理配置要求的输出样本数；需与实际FASTA数量及重复序列处理核对。

类型：`integer`；单位：样本数；来源记录默认：`50`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:sample_num=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `output_dir`

历史推理输出目录；需适配BDA_OUTPUT_DIR收集产物，当前命令未传入。

类型：`any`；单位：目录；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:output_dir=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `tie_chain`

声明需关联设计的链；关联链语法、同长度要求和映射规则未取得源码。

类型：`any`；单位：链关联配置/空值；来源记录默认：`null`。

适用模式：tied_design_config

生成映射：`历史Hydra覆盖:tie_chain=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `tie_positions`

声明需共同取值的位置关联；与fixed_positions冲突时的优先级尚未验证。

类型：`any`；单位：关联位置配置/空值；来源记录默认：`null`。

适用模式：tied_design_config

生成映射：`历史Hydra覆盖:tie_positions=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `homooligomer`

同源寡聚体相关设计开关的历史声明；不等于自动构建任意对称复合物。

类型：`boolean`；单位：布尔；来源记录默认：`false`。

适用模式：tied_design_config

生成映射：`历史Hydra覆盖:homooligomer=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `temp`

历史序列采样温度参数，表示分布采样的控制意图；不是开尔文，实际零温/负值处理需读实现。

类型：`number`；单位：无量纲（实现未核验）；来源记录默认：`0.1`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:temp=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `downweight_aas`

拟降低采样偏好的氨基酸集合；AA编码与允许格式需核验，不能当作强制排除。

类型：`any`；单位：AA集合/空值；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:downweight_aas=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `downweight_factor`

对downweight_aas施加的权重系数；乘概率、logits或其他位置尚无源码证据。

类型：`number`；单位：无量纲权重（运算未核验）；来源记录默认：`1.0`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:downweight_factor=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model_type`

选择模型变体的历史占位；允许值及其与model.name的关系未核验。

类型：`any`；单位：标识/空值；来源记录默认：`null`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:model_type=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `diffusion.objective`

扩散目标的配置标识，当前pred_x0表达原始状态预测命名；不能据此确定实际loss或变量类型。

类型：`string`；单位：枚举标识（实现未核验）；来源记录默认：`pred_x0`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:diffusion.objective=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `diffusion.timesteps`

扩散调度长度配置；通常与训练checkpoint耦合，不能任意改为推理加速参数。

类型：`integer`；单位：离散步数；来源记录默认：`500`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:diffusion.timesteps=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `diffusion.ddim_steps`

DDIM子采样步数配置；与完整调度长度不同，实际是否使用取决于sample_method和代码。

类型：`integer`；单位：采样步数；来源记录默认：`100`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:diffusion.ddim_steps=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `diffusion.noise_type`

噪声分布选择标识，默认marginal；具体氨基酸边缘分布来源和实现未核验。

类型：`string`；单位：枚举标识；来源记录默认：`marginal`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:diffusion.noise_type=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `diffusion.sample_method`

采样算法选择标识，默认ddim；支持枚举和实际算法未取得实现确认。

类型：`string`；单位：枚举标识；来源记录默认：`ddim`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:diffusion.sample_method=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `diffusion.ensemble_num`

扩散配置中的集成数量；不能直接当作输出序列数sample_num，聚合方式未核验。

类型：`integer`；单位：集成成员数（聚合未核验）；来源记录默认：`50`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:diffusion.ensemble_num=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `mask_prior.min_mask_ratio`

掩码先验的最低比例参数；与BDA单一mask_ratio不是已验证的一一映射。

类型：`number`；单位：比例；来源记录默认：`0.4`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:mask_prior.min_mask_ratio=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `mask_prior.dev_mask_ratio`

掩码先验的变化幅度参数；未证实是标准差、均匀范围或其他分布量。

类型：`number`；单位：比例尺度（分布未核验）；来源记录默认：`0.2`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`历史Hydra覆盖:mask_prior.dev_mask_ratio=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `train.lr`

训练优化器学习率；属于训练配置，不能宣称inference.py会用它改变推理；历史值是字符串5e-4。

类型：`string`；单位：学习率；来源记录默认：`5e-4`。

适用模式：training_config

生成映射：`历史Hydra覆盖:train.lr=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `train.weight_decay`

训练优化器权重衰减系数；优化器定义及与L2正则关系需源码确定。

类型：`integer`；单位：正则系数；来源记录默认：`0`。

适用模式：training_config

生成映射：`历史Hydra覆盖:train.weight_decay=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `train.scheduler`

是否启用训练学习率调度的配置开关；没有调度函数及参数的实现证据。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:train.scheduler=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `train.train_epochs`

训练数据遍历轮数配置，非扩散采样步数。

类型：`integer`；单位：epoch；来源记录默认：`100`。

适用模式：training_config

生成映射：`历史Hydra覆盖:train.train_epochs=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `train.batch_size`

训练批内样本数配置；不能自动视为推理并行数。

类型：`integer`；单位：样本/训练批；来源记录默认：`4`。

适用模式：training_config

生成映射：`历史Hydra覆盖:train.batch_size=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `train.save_and_sample_every`

训练期间保存/采样间隔；按epoch还是优化步计未核验，不能擅自补单位。

类型：`integer`；单位：间隔（计数基准未核验）；来源记录默认：`10`。

适用模式：training_config

生成映射：`历史Hydra覆盖:train.save_and_sample_every=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.name`

模型架构名，历史默认egnn；名称不足以证明模型实现等同某公开EGNN论文。

类型：`string`；单位：架构标识；来源记录默认：`egnn`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.name=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.input_feat_dim`

节点输入特征通道数配置；需匹配结构预处理和checkpoint权重形状。

类型：`integer`；单位：特征维数；来源记录默认：`31`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.input_feat_dim=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.edge_attr_dim`

边特征通道数配置；具体几何/序列特征组成未核验。

类型：`integer`；单位：特征维数；来源记录默认：`93`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.edge_attr_dim=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.hidden_dim`

网络隐层通道宽度配置；改变通常需匹配或重新训练权重。

类型：`integer`；单位：通道数；来源记录默认：`128`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.hidden_dim=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.drop_out`

网络dropout比例配置；训练/推理阶段是否启用依代码模式，不能作为序列采样温度。

类型：`number`；单位：概率；来源记录默认：`0.1`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.drop_out=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.depth`

网络堆叠深度配置；具体层/模块计数定义需源码确定。

类型：`integer`；单位：层数配置；来源记录默认：`6`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.depth=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.update_edge`

消息传递是否更新边表示的架构开关；需核验实现读取。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.update_edge=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.update_coors`

是否更新内部坐标表示的架构开关；不能据此承诺输出优化后的真实结构。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.update_coors=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.update_global`

是否更新全局状态表示的架构开关；实际全局特征定义未核验。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.update_global=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.norm_coors`

坐标相关归一化架构开关；归一化公式和对等变性的处理需源码。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.norm_coors=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.embedding`

输入是否使用嵌入表示的架构开关；不代表推理将导出embedding产物。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.embedding=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.embedding_dim`

嵌入表示维数配置，须匹配checkpoint。

类型：`integer`；单位：特征维数；来源记录默认：`128`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.embedding_dim=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.norm_feat`

特征归一化架构开关；归一化层类型和统计使用方式未知。

类型：`boolean`；单位：布尔；来源记录默认：`true`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.norm_feat=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.embed_ss`

二级结构嵌入相关配置，默认-3是未解码的本地约定；不能解释为负维数或具体DSSP类别。

类型：`integer`；单位：实现专用整数标识；来源记录默认：`-3`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.embed_ss=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `model.ipa_drop_out`

IPA相关模块dropout配置；模块是否存在/如何使用未取得源码，不套用AlphaFold能力。

类型：`number`；单位：概率配置；来源记录默认：`0.2`。

适用模式：training_config

生成映射：`历史Hydra覆盖:model.ipa_drop_out=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。", "架构参数须匹配checkpoint，不作为无需重训的推理调节旋钮。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `data.name`

数据配置名称，默认CATH；名称不能证明实际训练集来源、版本或无泄漏。

类型：`string`；单位：数据集标识；来源记录默认：`CATH`。

适用模式：training_config

生成映射：`历史Hydra覆盖:data.name=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `data.train_dir`

训练样本目录；需核对数据清单、版本和分割。

类型：`string`；单位：目录；来源记录默认：`./data/cath/cath_process/train/`。

适用模式：training_config

生成映射：`历史Hydra覆盖:data.train_dir=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `data.val_dir`

验证样本目录；不得与训练样本重复而声称独立验证。

类型：`string`；单位：目录；来源记录默认：`./data/cath/cath_process/validation/`。

适用模式：training_config

生成映射：`历史Hydra覆盖:data.val_dir=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `data.test_dir`

测试样本目录；推理是否使用此目录取决于入口实现。

类型：`string`；单位：目录；来源记录默认：`./data/cath/cath_process/test/`。

适用模式：training_config

生成映射：`历史Hydra覆盖:data.test_dir=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `data.marginal_train_dir`

历史训练边缘分布文件路径；用于哪个噪声/先验分支尚未源码核验，绝对集群路径不是可访问证据。

类型：`string`；单位：数据文件路径；来源记录默认：`<SITE_PATH>`。

适用模式：training_config

生成映射：`历史Hydra覆盖:data.marginal_train_dir=value；live未映射`；BDA 别名：`[]`。

约束与版本差异：["仅据历史catalog/config声明解释，源码缺失，未证实此键在当前入口被读取。", "library按Hydra key=value生成不等于模型安装或计算通过。"]

依据：[catalog](../../../qm-scripts/library/catalog.json), [mask-builder](../../../qm-scripts/library/build_catalog.py), [renderer](../../../qm-scripts/library/qm_job.py)

### `checkpoint_key`

服务器checkpoint别名；目前仅声明maskrgnn_demo，未给出到test_model.path的解析表或文件校验。

类型：`enum`；单位：别名；来源记录默认：`maskrgnn_demo`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`无绑定；不能把别名当成有效权重路径`；BDA 别名：`["checkpoint_key"]`。

约束与版本差异：["BDA disabled且command只有python -m maskrgnn_clean.inference，无kwargs或Hydra覆盖。", "BDA声明options=['maskrgnn_demo']"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [catalog](../../../qm-scripts/library/catalog.json)

### `num_samples`

BDA拟要求输出序列数；历史library键为sample_num，当前命令未作名称转换。

类型：`integer`；单位：样本数；来源记录默认：`64`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`未绑定；候选历史字段sample_num`；BDA 别名：`["num_samples"]`。

约束与版本差异：["BDA disabled且command只有python -m maskrgnn_clean.inference，无kwargs或Hydra覆盖。", "BDA声明min=1", "BDA声明max=100000"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [catalog](../../../qm-scripts/library/catalog.json)

### `mask_ratio`

BDA拟表示未显式选位置时的掩码比例；library只有mask_prior.min_mask_ratio和dev_mask_ratio，不存在已证实直接对应关系。

类型：`number`；单位：0–1比例；来源记录默认：`0.3`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`未绑定；不可擅自映射为mask_prior.min_mask_ratio`；BDA 别名：`["mask_ratio"]`。

约束与版本差异：["BDA disabled且command只有python -m maskrgnn_clean.inference，无kwargs或Hydra覆盖。", "BDA声明min=0", "BDA声明max=1"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [catalog](../../../qm-scripts/library/catalog.json)

### `temperature`

BDA拟控制序列采样分布温度；历史键为temp，未实现映射和边界处理。

类型：`number`；单位：无量纲；来源记录默认：`1.0`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`未绑定；候选历史字段temp`；BDA 别名：`["temperature"]`。

约束与版本差异：["BDA disabled且command只有python -m maskrgnn_clean.inference，无kwargs或Hydra覆盖。", "BDA声明min=0", "BDA声明max=5"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [catalog](../../../qm-scripts/library/catalog.json)

### `random_seed`

BDA声明随机种子，旧帮助说0自动生成；未获得实际入口实现，不能确认0的语义或复现性。

类型：`integer`；单位：整数种子；来源记录默认：`0`。

适用模式：structure_conditioned_config, tied_design_config

生成映射：`未绑定；历史catalog无对应seed键`；BDA 别名：`["random_seed"]`。

约束与版本差异：["BDA disabled且command只有python -m maskrgnn_clean.inference，无kwargs或Hydra覆盖。", "BDA声明min=0"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [catalog](../../../qm-scripts/library/catalog.json)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `experimental-0.1`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| checkpoint_key | enum | maskrgnn_demo | {"options": ["maskrgnn_demo"]} |
| num_samples | integer | 64 | {} |
| mask_ratio | number | 0.3 | {} |
| temperature | number | 1.0 | {} |
| fixed_positions | string |  | {} |
| random_seed | integer | 0 | {} |

**input_ports**

```json
[]
```

**output_ports**

```json
[
  {
    "name": "sequence_set",
    "kind": "protein_sequence",
    "artifact_type": "sequence_set",
    "filename_glob": "*",
    "description": "Sampled sequences."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Model scores and sampling metadata."
  },
  {
    "name": "embedding",
    "kind": "opaque",
    "artifact_type": "embedding",
    "filename_glob": "*",
    "description": "Optional model embeddings or latent features."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "sequence_set",
      "artifact_types": [
        "sequence_set"
      ],
      "required": true,
      "many": true,
      "help": "Sampled sequences."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": false,
      "many": false,
      "help": "Model scores and sampling metadata."
    },
    {
      "name": "embedding",
      "artifact_types": [
        "embedding"
      ],
      "required": false,
      "many": false,
      "help": "Optional model embeddings or latent features."
    }
  ]
}
```

**resources**

```json
{}
```

命令摘要 SHA-256：`7fedf669975df4ad919606cd9e31e10d2cd84baf0a1eeae9c18e864a7f71e423`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-m"]`。

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
| sequence_set（声明） | 预期采样序列集合 | AA序列 | 未验证文件格式、字母合法性、样本数或固定位置规则；非已产生结果。 | [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [mask-example](../../../qm-scripts/library/examples/02-sequence-design/maskrgn.json) |
| score_table（声明） | 预期模型采样统计 | 未确定 | 没有具体模型分数字段/公式/单位，不能命名pLDDT、ΔG或实验性质。 | [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| embedding（声明） | 可选嵌入/潜变量产物 | 未确定维度 | model.embedding=true不证明推理导出该文件；当前无输出parser。 | [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [catalog](../../../qm-scripts/library/catalog.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 缺本地源代码/配置和固定commit；所有算法内涵与默认行为仍需实际实现核验。
- disabled、input_ports为空、runtime_setup为空，未登记可用容器或QM安装。
- 6个BDA字段只有fixed_positions与library同名，其他名称/语义映射均未实现；命令没有传参数。
- 49个历史字段help为空且混合训练/推理/架构；文档已分别说明，不能因此声称全部已可运行。
- 输出仅*通配和无parser，无当前声明的成功运行证据。

## 易错点

- 模型名和egnn/ipa/ddim字符串不能证明某篇公开论文的具体算法被实现。
- 训练参数混入inference catalog不代表当前入口支持训练。
- model.update_coors与embedding开关不能证明会输出结构或embedding文件。
- mask_ratio不能直接映射到mask_prior两参数；steps、timesteps与ddim_steps不可合并。
- historical配置示例的/opt/bda和/work路径不是已安装证据。

## 来源与版本

- [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：审计时BDA注册字段、命令、输入输出端口、enabled及runtime_validation_status；commit `None`；读取 2026-09-15。
- [catalog](../../../qm-scripts/library/catalog.json)：历史参数库的类型和默认值，不等同运行时有效设置；commit `None`；读取 2026-09-15。
- [renderer](../../../qm-scripts/library/qm_job.py)：手工配置生成器的参数映射，区别于live ModelPlugin命令；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/mask-rgn/README.md)：旧运行手册的状态记录；不是安装或运行成功证明；commit `None`；读取 2026-09-15。
- [mask-builder](../../../qm-scripts/library/build_catalog.py)：声明从models/maskrgnn_clean/conf/inference.yaml、model/egnn.yaml、data/cath.yaml读取；本checkout实际源码/配置目录缺失；commit `None`；读取 2026-09-15。
- [mask-example](../../../qm-scripts/library/examples/02-sequence-design/maskrgn.json)：历史PDB条件序列设计配置示例，非真实安装路径或成功运行证据；commit `None`；读取 2026-09-15。
