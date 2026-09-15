# ProteinMPNN — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

ProteinMPNN 在给定蛋白骨架和链/位置约束下采样序列，或计算序列条件概率。覆盖34个 library 参数与所有版本25个唯一 BDA 字段；概率分数不代表结合 ΔG、热稳定性或实验活性。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/proteinmpnn.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 1.0.0 | true | unknown | unproven | false |
| 1.0.1 | true | unknown | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 骨架条件序列采样 (`sample`)

对指定链的可设计残基采样序列。。BDA 接入：`declared`。

输入：pdb_path 或 jsonl_path 一个骨架输入；明确 pdb_path_chains

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "num_seq_per_target": 8,
  "batch_size": 1,
  "sampling_temp": "0.1",
  "seed": 37
}
```

输出检查：每个温度实际样本数为 floor(num_seq_per_target/batch_size)*batch_size；排除第一条参考序列。；核对链顺序、序列长度与氨基酸字母表；保存每条 FASTA score/global_score/seed/model。

限制：模式状态描述声明或配置覆盖；不等于该模式在当前 BDA 声明上已跑通。

依据：[readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 固定位置和跨链 tied 设计 (`fixed_tied`)

保留 motif 的序列身份，或让多位置共享氨基酸。。BDA 接入：`unverified`。

输入：骨架与设计链；逐结构名/逐链的一开始编号位置 JSONL

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "fixed_positions_jsonl": "/staged/fixed.jsonl",
  "tied_positions_jsonl": "/staged/ties.jsonl",
  "num_seq_per_target": 8
}
```

输出检查：逐样本验证固定位置完全保留、tied 组身份一致；不能只检查任务 exit=0。

限制：command 有参数入口；fixed_positions 端口有明确 staging，其他 artifact_ref 路径需 preview 检查实际解析，不能假定 UI 资产ID可作为文件路径。；固定和 tied 条件冲突、链号错误必须提前检查。

依据：[fixed](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_fixed_positions_dict.py), [ties](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_tied_positions_dict.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py)

### 可溶蛋白专用权重 (`soluble`)

采用仅可溶蛋白训练的权重进行条件序列设计。。BDA 接入：`declared`。

输入：完整 N/CA/C/O 骨架与可用 soluble checkpoint

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_soluble_model": true,
  "model_name": "v_48_020"
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：官方 soluble 权重列出 v_48_010、v_48_020；并非所有 UI model_name 都有 soluble 版本。；不保证表达可溶性，也不能据此断言 vanilla 权重一定产生表面疏水聚集。

依据：[readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### CA-only 逆折叠 (`ca_only`)

对仅有 CA 的骨架使用专门模型。。BDA 接入：`unverified`。

输入：CA 骨架和 ca_model_weights；不能同时 soluble

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "ca_only": true,
  "use_soluble_model": false,
  "model_name": "v_48_020"
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：BDA 先运行 parse_multiple_chains.py，未显式传 CA-only 解析选项；需核实预解析与模型输入兼容。；官方 CA+soluble 路径会退出，不能视为合法组合。

依据：[readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 已有序列评分 (`score`)

计算给定骨架与已有序列的负对数概率。。BDA 接入：`configuration_only`。

输入：骨架；可选按链字母排序并以 / 分隔的 path_to_fasta

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "score_only": 1,
  "path_to_fasta": "/staged/candidates.fa",
  "num_seq_per_target": 8
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：BDA command 未转发 score_only/path_to_fasta；旧 library 支持。；保持相同骨架、链mask、噪声与checkpoint比较；不是通用跨蛋白亲和力排序。

依据：[readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [library](../../../qm-scripts/library/catalog.json)

### 逐位置条件概率 (`conditional`)

给出 p(s_i | 其余序列, backbone)，可切到仅骨架条件。。BDA 接入：`configuration_only`。

输入：骨架及参考序列

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "conditional_probs_only": 1,
  "conditional_probs_only_backbone": 0,
  "num_seq_per_target": 8
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：BDA command 未转发此分支开关；conditional_probs_only_backbone 只有配合 conditional_probs_only 才生效。

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [library](../../../qm-scripts/library/catalog.json)

### 仅骨架概率 (`unconditional_probs`)

单次 forward 得到 p(s_i | backbone)，此处 unconditional 仍以骨架为条件。。BDA 接入：`configuration_only`。

输入：骨架

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "unconditional_probs_only": 1,
  "num_seq_per_target": 8
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：不是无骨架 de novo 序列生成；BDA 未转发此分支开关。

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [library](../../../qm-scripts/library/catalog.json)

### 氨基酸限制、偏置与 PSSM (`bias_pssm`)

控制全局/逐位氨基酸组成、禁用集合或与 PSSM 概率混合。。BDA 接入：`configuration_only`。

输入：编号对齐的 bias/omit/PSSM JSONL

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "bias_AA_jsonl": "/staged/bias.jsonl",
  "pssm_multi": 0.5,
  "pssm_bias_flag": 1
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：BDA 只转发全局 omit_aas；多数 bias/PSSM fields 虽可见但 command 不读取。

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

## 使用方法

1. 选择具体插件版本并冻结输入文件、序列/结构编号映射、配置和权重校验值。
2. 按下列模式检查输入条件；先 render/preview，对照实际命令检查每个参数被接收。
3. 按站点流程 validate → render/preview → review → stage → review → submit。
4. 执行后核对输出数量、参数回显、随机种子、条件几何与残基保留，再将结构和元数据一并入库。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `backbone_noise`

向骨架原子加入高斯坐标扰动的标准差；属于推理噪声，区别于模型名中的训练噪声。

类型：`number`；单位：Å；来源记录默认：`0.0`。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--backbone_noise <value>`；BDA 别名：`["backbone_noise"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 backbone_noise 的声明：{\"type\":\"number\",\"default\":0.0,\"min\":0,\"max\":1}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 backbone_noise 的声明：{\"type\":\"number\",\"default\":0.0,\"min\":0,\"max\":1}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `batch_size`

每批并行样本数；固定代码用整数除法决定批次数，不能超过请求样本数。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--batch_size <value>`；BDA 别名：`["batch_size"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "正整数且不大于 num_seq_per_target；建议整除以免静默少样本。", "BDA ProteinMPNN@1.0.0 字段 batch_size 的声明：{\"type\":\"integer\",\"default\":1,\"min\":1,\"max\":1024}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 batch_size 的声明：{\"type\":\"integer\",\"default\":1,\"min\":1,\"max\":1024}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `bias_AA_jsonl`

按氨基酸类型给全局 logits 添加偏置的 JSONL，正值提高相对采样倾向、负值降低。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：bias_pssm

生成映射：`--bias_AA_jsonl <value>`；BDA 别名：`["bias_aa_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 bias_aa_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 bias_aa_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `bias_by_res_jsonl`

逐结构、逐位置、逐氨基酸的 logits 偏置矩阵路径，必须与解析后位置对齐。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：bias_pssm

生成映射：`--bias_by_res_jsonl <value>`；BDA 别名：`["bias_by_res_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 bias_by_res_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 bias_by_res_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `ca_only`

启用仅 CA 输入与专用 CA 模型；不补全原子，也不能与 soluble 默认权重组合。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：sample, soluble, ca_only

生成映射：`--ca_only (flag)`；BDA 别名：`["ca_only"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 ca_only 的声明：{\"type\":\"boolean\",\"default\":false}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 ca_only 的声明：{\"type\":\"boolean\",\"default\":false}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [parameter_env](../../../backend_v2/app/compute/scripts.py)

### `chain_id_jsonl`

逐结构指定设计链与固定链的 JSONL；上游缺省会设计所有链，BDA 则自行生成此文件。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：sample, fixed_tied

生成映射：`--chain_id_jsonl <value>`；BDA 别名：`["chain_id_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 chain_id_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 chain_id_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [fixed](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_fixed_positions_dict.py), [ties](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_tied_positions_dict.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `conditional_probs_only`

进入逐位置条件概率分支，保存 log p(s_i | 其余序列, X)；1开启、0关闭。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：conditional

生成映射：`--conditional_probs_only <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `conditional_probs_only_backbone`

配合 conditional_probs_only，将条件从其余序列+骨架改为仅骨架。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：conditional

生成映射：`--conditional_probs_only_backbone <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `fixed_positions_jsonl`

保留设计链中指定位置氨基酸身份的 JSONL；位置为解析链内一开始编号，非任意原始 PDB 编号。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：sample, fixed_tied

生成映射：`--fixed_positions_jsonl <value>`；BDA 别名：`["fixed_positions_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 fixed_positions_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 fixed_positions_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [fixed](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_fixed_positions_dict.py), [ties](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_tied_positions_dict.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `jsonl_path`

解析骨架 JSONL 文件，包含结构名、各链序列及坐标；官方 help 的 folder 措辞不应误导成目录。

类型：`string`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--jsonl_path <value>`；BDA 别名：`["jsonl_path"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 jsonl_path 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 jsonl_path 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `max_length`

读取数据时允许的最大序列长度过滤上限；不是模型可承受的显存保证。

类型：`integer`；单位：残基；来源记录默认：`200000`。

适用模式：sample

生成映射：`--max_length <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `model_name`

权重文件基名；v_48_020 表示48邻边、0.20 Å训练噪声版本，须检查具体权重目录。

类型：`string`；单位：无量纲/见说明；来源记录默认：`v_48_020`。

适用模式：sample, soluble, ca_only

生成映射：`--model_name <value>`；BDA 别名：`["model_name"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 model_name 的声明：{\"type\":\"enum\",\"default\":\"v_48_020\",\"options\":[\"v_48_002\",\"v_48_010\",\"v_48_020\",\"v_48_030\"]}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 model_name 的声明：{\"type\":\"enum\",\"default\":\"v_48_020\",\"options\":[\"v_48_002\",\"v_48_010\",\"v_48_020\",\"v_48_030\"]}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `num_seq_per_target`

每个骨架每个温度请求的序列样本数；实际按 batch_size 整数批截断。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--num_seq_per_target <value>`；BDA 别名：`["num_seq_per_target"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "选择 batch_size 的正整数倍；每个温度独立产生该数量。", "BDA ProteinMPNN@1.0.0 字段 num_seq_per_target 的声明：{\"type\":\"integer\",\"default\":8,\"min\":1,\"max\":10000}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 num_seq_per_target 的声明：{\"type\":\"integer\",\"default\":8,\"min\":1,\"max\":10000}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `omit_AA_jsonl`

逐链、逐位置的禁止氨基酸集合映射文件。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：bias_pssm

生成映射：`--omit_AA_jsonl <value>`；BDA 别名：`["omit_aa_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 omit_aa_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 omit_aa_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `omit_AAs`

所有可设计位置全局禁止的氨基酸字母串，默认禁止 X；不可将所有允许类型排除。

类型：`string`；单位：无量纲/见说明；来源记录默认：`X`。

适用模式：bias_pssm

生成映射：`--omit_AAs <value>`；BDA 别名：`["omit_aas"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 omit_aas 的声明：{\"type\":\"string\",\"default\":\"X\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 omit_aas 的声明：{\"type\":\"string\",\"default\":\"X\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `out_folder`

序列与概率/评分文件的输出目录；BDA command 强制使用 BDA_OUTPUT_DIR，忽略同名 UI 值。

类型：`string`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--out_folder <value>`；BDA 别名：`["out_folder"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 out_folder 的声明：{\"type\":\"string\",\"default\":\"outputs/proteinmpnn\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 out_folder 的声明：{\"type\":\"string\",\"default\":\"outputs/proteinmpnn\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `path_to_fasta`

score_only 模式要评估的序列 FASTA；多链按字母顺序以 / 分隔并匹配骨架长度。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：score

生成映射：`--path_to_fasta <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `path_to_model_weights`

直接指定权重目录，优先于自动 vanilla/soluble/CA 目录选择；需留存文件 SHA。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：sample, soluble, ca_only

生成映射：`--path_to_model_weights <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `pdb_path`

上游单个 PDB 输入路径；BDA 通过 pdb_path 端口目录批量预解析 PDB。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--pdb_path <value>`；BDA 别名：`["pdb_path"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 pdb_path 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 pdb_path 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `pdb_path_chains`

用空格分隔要设计的链字母；BDA 使用它生成 assigned_pdbs.jsonl，缺值默认 A。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：sample, fixed_tied

生成映射：`--pdb_path_chains <value>`；BDA 别名：`["pdb_path_chains"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 pdb_path_chains 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 pdb_path_chains 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [fixed](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_fixed_positions_dict.py), [ties](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_tied_positions_dict.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `pssm_bias_flag`

是否把 PSSM 概率按 pssm_multi 与模型采样概率混合；1开启。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：bias_pssm

生成映射：`--pssm_bias_flag <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py)

### `pssm_jsonl`

含逐位 PSSM 系数、概率和 log-odds 的 JSONL；须与解析链及位置一一对应。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：bias_pssm

生成映射：`--pssm_jsonl <value>`；BDA 别名：`["pssm_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 pssm_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 pssm_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `pssm_log_odds_flag`

是否应用 PSSM log-odds 阈值产生的逐位氨基酸允许掩码。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：bias_pssm

生成映射：`--pssm_log_odds_flag <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py)

### `pssm_multi`

PSSM 概率混合强度，0忽略混合、1尽量由PSSM决定；须配合 pssm_bias_flag 和有效逐位系数。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.0`。

适用模式：bias_pssm

生成映射：`--pssm_multi <value>`；BDA 别名：`["pssm_multi"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 pssm_multi 的声明：{\"type\":\"number\",\"default\":0.0,\"min\":0,\"max\":1}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 pssm_multi 的声明：{\"type\":\"number\",\"default\":0.0,\"min\":0,\"max\":1}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `pssm_threshold`

将逐位 PSSM log-odds 与此阈值比较，代码使用严格大于；须启用 pssm_log_odds_flag 才用于采样限制。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.0`。

适用模式：bias_pssm

生成映射：`--pssm_threshold <value>`；BDA 别名：`["pssm_threshold"]`。

约束与版本差异：["BDA 字段存在；command 未读取或被内部生成值替代，不能依字段存在推断生效。", "BDA ProteinMPNN@1.0.0 字段 pssm_threshold 的声明：{\"type\":\"number\",\"default\":0.0}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 pssm_threshold 的声明：{\"type\":\"number\",\"default\":0.0}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `sampling_temp`

空格分隔的一组采样温度字符串；越高通常越多样，不是物理温度。

类型：`string`；单位：无量纲/见说明；来源记录默认：`0.1`。

适用模式：sample

生成映射：`--sampling_temp <value>`；BDA 别名：`["sampling_temp"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "必须正数；1.0.1 schema 是单数 number，不能表示多个温度；UI 允许0但上游除以温度不应设0。", "BDA ProteinMPNN@1.0.0 字段 sampling_temp 的声明：{\"type\":\"string\",\"default\":\"0.1\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN@1.0.1 字段 sampling_temp 的声明：{\"type\":\"number\",\"default\":0.0001,\"minimum\":0.0,\"maximum\":1.0}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 sampling_temp 的声明：{\"type\":\"string\",\"default\":\"0.1\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `save_probs`

保存序列采样时每位概率及相关数组的开关（整数0/1）。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：sample

生成映射：`--save_probs <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `save_score`

额外保存负对数概率评分数组的开关（整数0/1），与 FASTA 头中的分数记录不同。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：score

生成映射：`--save_score <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `score_only`

只计算输入骨架/序列评分，不生成新序列；优先于其他概率分支。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：score

生成映射：`--score_only <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `seed`

随机种子；官方0会自动抽取随机种子，复现实验需保留实际非零 seed。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：sample, score, conditional, unconditional_probs

生成映射：`--seed <value>`；BDA 别名：`["seed"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 seed 的声明：{\"type\":\"integer\",\"default\":0,\"min\":0}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 seed 的声明：{\"type\":\"integer\",\"default\":0,\"min\":0}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `suppress_print`

抑制常规终端打印，整数0/1；不应因此省略采样参数的证据保存。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：sample

生成映射：`--suppress_print <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `tied_positions_jsonl`

规定多个位置同次采样共享氨基酸的组映射，可跨链实现序列对称；位置必须与解析序列一致。

类型：`string`；单位：无量纲/见说明；来源记录默认：``。

适用模式：sample, fixed_tied

生成映射：`--tied_positions_jsonl <value>`；BDA 别名：`["tied_positions_jsonl"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 tied_positions_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 tied_positions_jsonl 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [fixed](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_fixed_positions_dict.py), [ties](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_tied_positions_dict.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `unconditional_probs_only`

输出仅骨架条件的逐位 log 概率，使用一次前向计算；不以其他位置的序列为条件。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：unconditional_probs

生成映射：`--unconditional_probs_only <value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA schema/command 未公开此 CLI 参数；手工 library 可表达。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json)

### `use_soluble_model`

选择仅可溶蛋白训练的权重目录；不能直接预测表达可溶性。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：sample, soluble, ca_only

生成映射：`--use_soluble_model (flag)`；BDA 别名：`["use_soluble_model"]`。

约束与版本差异：["BDA 字段存在；command 有读取/输入 staging 映射，仍应核对实际路径。", "BDA ProteinMPNN@1.0.0 字段 use_soluble_model 的声明：{\"type\":\"boolean\",\"default\":false}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN@1.0.1 字段 use_soluble_model 的声明：{\"type\":\"boolean\",\"default\":true}；仅记录声明，不等于命令已执行该值。", "BDA ProteinMPNN-authoring-6810138a@1.0.0-draft.1 字段 use_soluble_model 的声明：{\"type\":\"boolean\",\"default\":false}；仅记录声明，不等于命令已执行该值。"]

依据：[cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [parameter_env](../../../backend_v2/app/compute/scripts.py)

### `seqs_per_struct`

BDA 1.0.1 中表示每个结构序列数的旧包装字段；实际 command 仅读取 num_seq_per_target，因此该值目前不控制样本数。

类型：`integer`；单位：无；来源记录默认：`8`。

适用模式：sample, fixed_tied

生成映射：`当前无有效 CLI 映射`；BDA 别名：`["seqs_per_struct"]`。

约束与版本差异：["这是可追溯的接口缺口，不能为该字段编造官方含义或声称已生效。", "BDA ProteinMPNN@1.0.1 字段 seqs_per_struct 的声明：{\"type\":\"integer\",\"default\":8,\"minimum\":1,\"maximum\":64}；仅记录声明，不等于命令已执行该值。"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py)

### `relax_cycles`

BDA 1.0.1 的旧包装 relax 轮数字段；官方 ProteinMPNN CLI 不做 Rosetta relax，当前 command 也无 relax 阶段。

类型：`integer`；单位：轮；来源记录默认：`0`。

适用模式：sample, fixed_tied

生成映射：`当前无有效 CLI 映射`；BDA 别名：`["relax_cycles"]`。

约束与版本差异：["这是可追溯的接口缺口，不能为该字段编造官方含义或声称已生效。", "BDA ProteinMPNN@1.0.1 字段 relax_cycles 的声明：{\"type\":\"integer\",\"default\":0,\"minimum\":0,\"maximum\":10}；仅记录声明，不等于命令已执行该值。"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py)

### `fixed_positions`

BDA 1.0.1 的字符串属性；与名为 fixed_positions 的文件输入端口不是同一对象，command 使用 staged JSON/JSONL，未解析此字符串。

类型：`string`；单位：无；来源记录默认：``。

适用模式：sample, fixed_tied

生成映射：`当前无有效 CLI 映射`；BDA 别名：`["fixed_positions"]`。

约束与版本差异：["这是可追溯的接口缺口，不能为该字段编造官方含义或声称已生效。", "BDA ProteinMPNN@1.0.1 字段 fixed_positions 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `1.0.0`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| pdb_path | artifact_ref |  | {} |
| jsonl_path | artifact_ref |  | {} |
| out_folder | string | outputs/proteinmpnn | {} |
| num_seq_per_target | integer | 8 | {} |
| batch_size | integer | 1 | {} |
| sampling_temp | string | 0.1 | {} |
| model_name | enum | v_48_020 | {"options": ["v_48_002", "v_48_010", "v_48_020", "v_48_030"]} |
| pdb_path_chains | string |  | {} |
| chain_id_jsonl | artifact_ref |  | {} |
| fixed_positions_jsonl | artifact_ref |  | {} |
| omit_aas | string | X | {} |
| bias_aa_jsonl | artifact_ref |  | {} |
| bias_by_res_jsonl | artifact_ref |  | {} |
| omit_aa_jsonl | artifact_ref |  | {} |
| pssm_jsonl | artifact_ref |  | {} |
| pssm_multi | number | 0.0 | {} |
| pssm_threshold | number | 0.0 | {} |
| tied_positions_jsonl | artifact_ref |  | {} |
| backbone_noise | number | 0.0 | {} |
| use_soluble_model | boolean | false | {} |
| ca_only | boolean | false | {} |
| seed | integer | 0 | {} |

**input_ports**

```json
[
  {
    "name": "pdb_path",
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
      "chemical/x-pdb"
    ],
    "required": true,
    "multiple": true,
    "description": "Staged PDB backbones. Alternatively bind a parsed ProteinMPNN JSONL file.",
    "exclusive_group": "backbone_source"
  },
  {
    "name": "jsonl_path",
    "kind": "params",
    "accepts": [
      "parameter_file",
      "proteinmpnn_jsonl"
    ],
    "content_types": [
      "application/x-ndjson",
      "application/json",
      "text/plain"
    ],
    "required": true,
    "multiple": false,
    "description": "Parsed ProteinMPNN JSONL input. Alternatively bind staged PDB backbones.",
    "exclusive_group": "backbone_source"
  },
  {
    "name": "chain_id_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Chain design JSONL. Dictionary specifying designed vs fixed chains. (from field 'chain_id_jsonl')"
  },
  {
    "name": "fixed_positions_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Fixed positions JSONL. Dictionary of fixed residue positions. (from field 'fixed_positions_jsonl')"
  },
  {
    "name": "bias_AA_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "AA bias JSONL. Global amino-acid composition bias. (from field 'bias_AA_jsonl')"
  },
  {
    "name": "bias_by_res_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Per-residue bias JSONL. Per-position amino-acid bias. (from field 'bias_by_res_jsonl')"
  },
  {
    "name": "omit_AA_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Per-residue omit JSONL. Per-position omitted amino acids. (from field 'omit_AA_jsonl')"
  },
  {
    "name": "pssm_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "PSSM JSONL. PSSM constraints for sequence sampling. (from field 'pssm_jsonl')"
  },
  {
    "name": "tied_positions_jsonl",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Tied positions JSONL. Groups positions that should share sampled amino acids. (from field 'tied_positions_jsonl')"
  },
  {
    "name": "fixed_positions",
    "kind": "params",
    "accepts": [
      "parameter_file",
      "fixed_positions"
    ],
    "content_types": [
      "application/json",
      "application/x-ndjson",
      "text/plain"
    ],
    "required": false,
    "multiple": false,
    "description": "Immutable fixed-position map for constrained sequence design."
  }
]
```

**output_ports**

```json
[
  {
    "name": "sequence_set",
    "kind": "protein_sequence",
    "artifact_type": "sequence_set",
    "filename_glob": "*.fa*",
    "description": "Designed sequences in FASTA/CSV form."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*.csv",
    "description": "Sequence design scores."
  },
  {
    "name": "run_manifest",
    "kind": "params",
    "artifact_type": "manifest",
    "filename_glob": "*.jsonl",
    "description": "Machine-readable output manifest."
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
      "help": "Designed sequences in FASTA/CSV form."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": true,
      "many": false,
      "help": "Sequence design scores."
    },
    {
      "name": "run_manifest",
      "artifact_types": [
        "manifest"
      ],
      "required": true,
      "many": false,
      "help": "Machine-readable output manifest."
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
  "walltime_minutes": 720,
  "cpus_evidence": "Sequence design on one GPU; no thread count is exposed."
}
```

命令摘要 SHA-256：`6fce63e7654f9ad88e6baff995410ec92348cef0aa78d6c24b021fa07b339236`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--backbone_noise", "--batch_size", "--chain_id_jsonl", "--chain_list", "--fixed_positions_jsonl", "--input_path", "--jsonl_path", "--model_name", "--num_seq_per_target", "--omit_AAs", "--out_folder", "--output_path", "--sampling_temp", "--seed", "--tied_positions_jsonl", "-d", "-gt", "-l", "-n", "-name", "-o", "-type", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "backbone_noise", "batch_size", "ca_only", "fixed_positions_jsonl", "fixed_positions_staged", "model_name", "num_seq_per_target", "omit_aas", "parsed_jsonl", "pdb_path_chains", "requires_fixed_positions", "sampling_temp", "seed", "staged_jsonl", "staged_pdb_count", "tied_positions_jsonl", "use_soluble_model"]`。

输入适配器：`null`；输出解析器：`proteinmpnn_fasta`。

### 版本 `1.0.1`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| sampling_temp | number | 0.0001 | {"maximum": 1.0, "minimum": 0.0, "required": true} |
| seqs_per_struct | integer | 8 | {"maximum": 64, "minimum": 1, "required": true} |
| use_soluble_model | boolean | true | {} |
| relax_cycles | integer | 0 | {"maximum": 10, "minimum": 0} |
| fixed_positions | string |  | {} |

**input_ports**

```json
[
  {
    "name": "pdb_path",
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
      "chemical/x-pdb"
    ],
    "required": true,
    "multiple": true,
    "description": "Staged PDB backbones. Alternatively bind a parsed ProteinMPNN JSONL file.",
    "exclusive_group": "backbone_source"
  },
  {
    "name": "jsonl_path",
    "kind": "params",
    "accepts": [
      "parameter_file",
      "proteinmpnn_jsonl"
    ],
    "content_types": [
      "application/x-ndjson",
      "application/json",
      "text/plain"
    ],
    "required": true,
    "multiple": false,
    "description": "Parsed ProteinMPNN JSONL input. Alternatively bind staged PDB backbones.",
    "exclusive_group": "backbone_source"
  },
  {
    "name": "fixed_positions",
    "kind": "params",
    "accepts": [
      "parameter_file",
      "fixed_positions"
    ],
    "content_types": [
      "application/json",
      "application/x-ndjson",
      "text/plain"
    ],
    "required": false,
    "multiple": false,
    "description": "Immutable fixed-position map for constrained sequence design."
  }
]
```

**output_ports**

```json
[
  {
    "name": "sequences",
    "kind": "protein_sequence",
    "artifact_type": "sequence_set",
    "filename_glob": "*.fa",
    "description": "Designed binder sequences."
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
  "gpu": true,
  "gpu_count": 1,
  "cpus": 1,
  "memory_gb": 16,
  "walltime_minutes": 240,
  "cpus_evidence": "Sequence design on one GPU; no thread count is exposed."
}
```

命令摘要 SHA-256：`6fce63e7654f9ad88e6baff995410ec92348cef0aa78d6c24b021fa07b339236`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--backbone_noise", "--batch_size", "--chain_id_jsonl", "--chain_list", "--fixed_positions_jsonl", "--input_path", "--jsonl_path", "--model_name", "--num_seq_per_target", "--omit_AAs", "--out_folder", "--output_path", "--sampling_temp", "--seed", "--tied_positions_jsonl", "-d", "-gt", "-l", "-n", "-name", "-o", "-type", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "backbone_noise", "batch_size", "ca_only", "fixed_positions_jsonl", "fixed_positions_staged", "model_name", "num_seq_per_target", "omit_aas", "parsed_jsonl", "pdb_path_chains", "requires_fixed_positions", "sampling_temp", "seed", "staged_jsonl", "staged_pdb_count", "tied_positions_jsonl", "use_soluble_model"]`。

输入适配器：`null`；输出解析器：`proteinmpnn_fasta`。

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
| seqs/*.fa | 参考序列与设计序列；多链以 / 分隔 | 氨基酸单字母 | FASTA 头的编号、T、sample、score 是元数据，不能拼入序列；首条通常为原骨架序列。 | [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py) |
| score | 设计且可设计位置上的平均负自然对数概率 | nats/残基 | 同一骨架、权重、mask 和协议下较低表示模型更偏好；不是 REU/kcal/mol/亲和力。 | [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py) |
| global_score | 所有有坐标残基含固定链的平均负对数概率 | nats/残基 | 大靶标固定链可主导分数，不能替代 binder 设计区域 score。 | [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md), [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py) |
| seq_recovery | 设计掩码区域与参考序列相同的残基比例 | 0–1 | 参考恢复率，不是功能恢复率。 | [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py) |
| score_only/*.npz / scores/*.npz | 评分分支或额外保存的评分数组 | nats/残基 | 需保留 seed/重复、链 mask、native 与 FASTA来源；BDA 当前未暴露该分支。 | [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py) |
| conditional_probs_only/*.npz / unconditional_probs_only/*.npz / probs/*.npz | 逐位置21字母概率或 log_p 与位置/设计 mask | 概率或 log 概率，按数组名 | 区分条件定义并核对 shape、字母顺序和掩码；未自动转成受体结合证据。 | [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py), [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 覆盖前：library 34 键；1.0.0/authoring 22 字段，1.0.1 5 properties；并集25。已覆盖34/34及25/25。
- ProteinMPNN-authoring-6810138a 1.0.0-draft.1 字段与base1.0.0一致，但 command 新增 pdb_path_chains 非空检查；base 缺值默认 A。
- 1.0.1 同一 command 与新版 properties 不匹配：seqs_per_struct/relax_cycles/fixed_positions 字符串无对应实现，不能声称这三个设置已经运行。
- 1.0.1 sampling_temp 默认0.0001、use_soluble_model=true；这些是本地策略，不是官方推荐普适阈值，原描述的表面疏水归因无普适证据。
- 1.0.0 UI num_seq_per_target=8、sampling_temp=0.1、seed=0；shell缺值分别5、0.2、37；文档 default 指 upstream，必须另看选定BDA版本的最终配置。
- bias_aa_jsonl/bias_by_res_jsonl/omit_aa_jsonl/pssm_jsonl/pssm_multi/pssm_threshold 存在表单字段但未进 command；chain_id_jsonl 被内部 assign_fixed_chains 输出替代。
- fixed_positions 端口有明确 staging；tied_positions_jsonl 等 artifact_ref 是否被转换成运行路径需实际 preview/小样验证。
- 上游示例默认权重支持集与 BDA model_name 枚举不同；CA-only 不支持 soluble 组合。
- 输出端口宣称 *.csv score_table，但官方主要分数位于 FASTA/NPY/NPZ；不得保证产生 CSV，需检查 proteinmpnn_fasta parser 的实际入库结果。
- 站点 <SITE_PATH> 的具体 commit 与 CLI 差异未由 live 快照证明；此处 pinned GitHub 语义不能当成站点二进制完全等同证据。
- 官方 argparse 帮助把 save_score 称为写npy，但固定源码实际 np.savez 写 scores/*.npz；按代码记录真实产物。

## 易错点

- ProteinMPNN 不进行 MD、Rosetta relax 或亲和力测量；scoring、conditional 和 sampling 是不同分支。
- 固定位置与 tied 映射按解析链的一开始位置，不宜直接输入含缺口/插入码的原 PDB 编号。
- FASTA 描述行有数字和字母是元数据；真正序列行只应含氨基酸符号及约定链分隔符。
- 不同温度、骨架长度、固定靶标比例的 score 不能不加说明混排。
- 0 seed 不是固定种子；num_seq_per_target 不整除 batch_size 会减少实际输出数。

## 来源与版本

- [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：当前 base 与 authoring 草稿的字段、实际 command、输入输出与验证标签；commit `未固定/本地快照`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交库参数清单；不是 BDA command 已转发的证据；commit `未固定/本地快照`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/proteinmpnn/README.md)：旧集群 runbook；历史记录与当前声明证明边界；commit `未固定/本地快照`；读取 2026-09-15。
- [readme](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/README.md)：采样、评分、概率模式、权重种类与 FASTA 指标；commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`；读取 2026-09-15。
- [cli](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_run.py)：完整34参数、分支优先级、数量取整、路径与权重加载；commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`；读取 2026-09-15。
- [utils](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/protein_mpnn_utils.py)：采样概率、PSSM、tied positions 与 mask；commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`；读取 2026-09-15。
- [fixed](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_fixed_positions_dict.py)：一开始编号的解析链位置映射；commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`；读取 2026-09-15。
- [ties](https://github.com/dauparas/ProteinMPNN/blob/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57/helper_scripts/make_tied_positions_dict.py)：同源链与跨链等同残基映射；commit `8907e6671bfbfc92303b5f79c4b5e6ce47cdef57`；读取 2026-09-15。
- [parameter_env](../../../backend_v2/app/compute/scripts.py)：参数环境导出：标量小写键、bool为1/空字符串、array/object不导出；commit `未固定/本地快照`；读取 2026-09-15。
