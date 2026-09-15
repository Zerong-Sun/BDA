# RFdiffusion — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

RFdiffusion 第一代骨架生成与条件扩散。118 个旧 library 键逐项解释；17 个 BDA/authoring 字段追踪到实际命令。结构生成、置信度和约束保留均不是结合能或功能证明。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/rfdiffusion.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 1.1.0 | true | unknown | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 无条件 de novo 骨架 (`unconditional`)

按长度从噪声生成骨架。。BDA 接入：`declared`。

输入：

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "contigs": "[100-100]",
  "num_designs": 10,
  "partial_t": 0
}
```

输出检查：顶层 PDB/TRB 一一对应；链长为100；不把轨迹帧计为独立候选。

限制：模式状态描述声明或配置覆盖；不等于该模式在当前 BDA 声明上已跑通。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 靶标与 hotspot 条件 binder (`binder`)

围绕已知靶标和指定热点生成新链。。BDA 接入：`declared`。

输入：靶标 PDB 绑定 inference_input_pdb；实际链号与残基编号

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "contigs": "[A1-150/0 70-100]",
  "hotspot_res": "[A59,A83,A91]",
  "num_designs": 10
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：热点是生成条件，不保证接触全部热点或实验结合；需独立复合物预测、界面评分和功能测试。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 固定 motif scaffolding (`motif`)

保留输入片段坐标并设计连接骨架。。BDA 接入：`declared`。

输入：含 motif 的 PDB 与输入到输出残基映射

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "contigs": "[10-40/A163-181/10-40]",
  "ckpt_override_path": "models/ActiveSite_ckpt.pt"
}
```

输出检查：按 TRB 索引映射计算保留 motif 原子 RMSD；排查链断裂与严重冲突。

限制：ActiveSite 权重针对小 motif；是否必要依 motif 大小选择，站点相对权重路径需核实。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 部分扩散与 provide_seq (`partial`)

对完整已知骨架加有限步噪声再去噪，可固定部分序列。。BDA 接入：`declared`。

输入：每个输出位置都有输入坐标的完整 PDB；不改变总长度或映射偏移

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "contigs": "[100-100/0 20-20]",
  "partial_t": 10,
  "diffuser_t": 50,
  "provide_seq": "[100-119]"
}
```

输出检查：确认总长度和输入输出索引完全一致；验证固定序列保留与几何变化；记录实际 checkpoint。

限制：0 < partial_T <= T；RFD1 的单位是步数。T=200 的 partial_T=80 不能直接照搬到 T=50，README 等效例为20。；provide_seq 按整个映射的零起始、闭区间；不要用输入 PDB 残基号直接代替。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 对称寡聚体与对称 motif (`symmetry`)

按指定群生成对称骨架。。BDA 接入：`unverified`。

输入：群类型、可整除亚基数的总 contig 长度；motif 模式需要预先对称化坐标

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "symmetry": "c4",
  "contigs": "[400]"
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：BDA 转发 symmetry，但未提供官方示例的 --config-name symmetry；不可把单一字段当作完整经过验证的对称流程。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 二级结构/接触拓扑条件 (`fold_conditioned`)

以 SS 与 adjacency 模板约束生成折叠或 binder。。BDA 接入：`configuration_only`。

输入：scaffold_dir 下配套 _ss.pt/_adj.pt；如有靶标则提供靶标 SS/adj

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "scaffoldguided.scaffoldguided": true,
  "scaffoldguided.scaffold_dir": "/staged/scaffolds"
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：旧 library 支持这些 Hydra 键；当前 BDA command 没有转发 scaffoldguided.*。BDA scaffold 下拉框只是元数据，不会自动加载天然模板。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [library](../../../qm-scripts/library/catalog.json)

### RFpeptides 环肽模式 (`macrocycle`)

在上游固定 commit 的环化链表示下生成骨架。。BDA 接入：`configuration_only`。

输入：兼容环化拓扑的 contigs 与相应权重/运行版本

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "inference.cyclic": true,
  "inference.cyc_chains": "a",
  "contigmap.contigs": "[12-18]"
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：当前 BDA 未转发 cyclic/cyc_chains；普通 PDB 也不能单独证明真实化学闭环。

依据：[readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [library](../../../qm-scripts/library/catalog.json)

### 专家网络/噪声配置 (`expert_config`)

记录上游配置而非提供可随意调整的科学筛选阈值。。BDA 接入：`configuration_only`。

输入：与模型 checkpoint 一致的配置

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "diffuser.T": 50
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：模型维度与预处理维度必须匹配权重；不少基础值会由 checkpoint 配置回载，必须检查最终解析配置。

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [library](../../../qm-scripts/library/catalog.json)

## 使用方法

1. 选择具体插件版本并冻结输入文件、序列/结构编号映射、配置和权重校验值。
2. 按下列模式检查输入条件；先 render/preview，对照实际命令检查每个参数被接收。
3. 按站点流程 validate → render/preview → review → stage → review → submit。
4. 执行后核对输出数量、参数回显、随机种子、条件几何与残基保留，再将结构和元数据一并入库。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `inference.input_pdb`

作为 motif、靶标或部分扩散起点的 PDB 坐标文件；BDA 实际读取 inference_input_pdb 输入端口中的首个排序 PDB。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.input_pdb=<Hydra value>`；BDA 别名：`["input_pdb"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 input_pdb 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 input_pdb 的声明：{\"type\":\"artifact_ref\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.num_designs`

生成独立设计的数量；不是轨迹帧数。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`10`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.num_designs=<Hydra value>`；BDA 别名：`["num_designs"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 num_designs 的声明：{\"type\":\"integer\",\"default\":100,\"min\":1,\"max\":100000}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 num_designs 的声明：{\"type\":\"integer\",\"default\":100,\"min\":1,\"max\":100000}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.design_startnum`

输出设计编号起点，便于分块生成时避免编号冲突。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`0`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.design_startnum=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.ckpt_override_path`

覆盖自动选择的模型权重路径；需匹配任务和训练配置。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.ckpt_override_path=<Hydra value>`；BDA 别名：`["ckpt_override_path"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 ckpt_override_path 的声明：{\"type\":\"enum\",\"default\":\"\",\"options\":[\"\",\"models/ActiveSite_ckpt.pt\",\"models/Complex_beta_ckpt.pt\"]}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 ckpt_override_path 的声明：{\"type\":\"enum\",\"default\":\"\",\"options\":[\"\",\"models/ActiveSite_ckpt.pt\",\"models/Complex_beta_ckpt.pt\"]}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.symmetry`

对称群标识，如 c4、d2、tetrahedral；这是寡聚体对称性，不是肽链闭环。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.symmetry=<Hydra value>`；BDA 别名：`["symmetry"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 symmetry 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 symmetry 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.recenter`

对称复制时是否重新居中基本单元，影响亚基相对于对称轴的位置。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.recenter=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.radius`

对称构造中基本单元沿基准轴放置的半径；不能解释为结合距离。

类型：`number`；单位：Å；来源记录默认：`10.0`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.radius=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.model_only_neighbors`

传入对称生成器的邻居建模选项；该固定源码构造函数接收但未使用此值，不能宣称开启后会降低模型规模。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.model_only_neighbors=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.output_prefix`

设计输出路径前缀；BDA 强制置于 BDA_OUTPUT_DIR 下再拼接该值。

类型：`string`；单位：无量纲/见说明；来源记录默认：`samples/design`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.output_prefix=<Hydra value>`；BDA 别名：`["output_prefix"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 output_prefix 的声明：{\"type\":\"string\",\"default\":\"outputs/rfdiffusion/design\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 output_prefix 的声明：{\"type\":\"string\",\"default\":\"outputs/rfdiffusion/design\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.write_trajectory`

是否写去噪中间结构轨迹，增加存储而非独立候选数。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.write_trajectory=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.empty_cache_per_design`

每个设计间清理 GPU 缓存的运行选项，不改变科学筛选定义。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.empty_cache_per_design=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.scaffold_guided`

基础配置保留的旧式 scaffold 开关；实际 runner 选择使用 scaffoldguided.scaffoldguided，不能把此旧键当作已接通。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.scaffold_guided=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.model_runner`

选择采样器实现类，如 SelfConditioning；必须存在于安装版本。

类型：`string`；单位：无量纲/见说明；来源记录默认：`SelfConditioning`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.model_runner=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.cautious`

避免覆盖已有结果的谨慎输出策略；重跑需确认跳过行为。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.cautious=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.align_motif`

去噪预测中将固定 motif 与输入对齐的几何处理开关。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.align_motif=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.symmetric_self_cond`

对称任务中对上一轮预测进行对称化后作为 self-conditioning 输入。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.symmetric_self_cond=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.final_step`

逆扩散的终止时间步，通常到1；提前终止可能留下未完成去噪结构。

类型：`integer`；单位：步；来源记录默认：`1`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.final_step=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.deterministic`

为设计设置确定性随机状态的运行选项；仍需保存软件/硬件与权重版本。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.deterministic=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.trb_save_ckpt_path`

内部写入TRB的真实checkpoint路径记录槽；用户必须保持null，runner断言非null会失败，并自动填写实际加载路径。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.trb_save_ckpt_path=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.schedule_directory_path`

扩散旋转噪声调度缓存目录；用于预计算数据，不是输出候选目录。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.schedule_directory_path=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.model_directory_path`

自动寻找模型权重的目录；不同于直接指定 checkpoint 文件。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.model_directory_path=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.cyclic`

启用 RFpeptides 的宏环链索引处理；需结合 cyc_chains。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.cyclic=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `inference.cyc_chains`

要采用闭环索引的输出链字母字符串，例如 a 或 ab；与 contigs 必须一致。

类型：`string`；单位：无量纲/见说明；来源记录默认：`a`。

适用模式：unconditional, binder, motif, partial, symmetry

生成映射：`inference.cyc_chains=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)

### `contigmap.contigs`

输入片段和新生长度的 Hydra 列表；A10-20 引用输入编号、10-20 采样新长度、/0 后的空格标识链断点。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.contigs=<Hydra value>`；BDA 别名：`["contigs"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 contigs 的声明：{\"type\":\"string\",\"default\":\"[A1-150/0 70-100]\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 contigs 的声明：{\"type\":\"string\",\"default\":\"[A1-150/0 70-100]\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `contigmap.inpaint_seq`

隐藏指定输入位置的氨基酸身份并允许重新设计；使用输入链/残基标识。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.inpaint_seq=<Hydra value>`；BDA 别名：`["inpaint_seq"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 inpaint_seq 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 inpaint_seq 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `contigmap.inpaint_str`

隐藏指定输入片段的结构条件，使这些区域重新生成。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.inpaint_str=<Hydra value>`；BDA 别名：`["inpaint_str"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 inpaint_str 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 inpaint_str 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `contigmap.inpaint_str_helix`

结构重绘区域中要求螺旋的残基选择；需要支持二级结构条件的 runner/checkpoint。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.inpaint_str_helix=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py)

### `contigmap.inpaint_str_strand`

结构重绘区域中要求 β 链的残基选择；不等于固定实验二级结构。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.inpaint_str_strand=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py)

### `contigmap.inpaint_str_loop`

结构重绘区域中指定 loop 的残基选择；与其他 SS 选择避免重叠。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.inpaint_str_loop=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py)

### `contigmap.provide_seq`

部分扩散中保留序列身份的零起始闭区间列表；触发相应序列条件 checkpoint 自动选择。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.provide_seq=<Hydra value>`；BDA 别名：`["provide_seq"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 provide_seq 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 provide_seq 的声明：{\"type\":\"string\",\"default\":\"\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `contigmap.length`

限定生成部分的长度或范围，以拒绝采样不符合长度的 contig；不是任意裁剪输入结构。

类型：`any`；单位：残基；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`contigmap.length=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py)

### `model.n_extra_block`

处理额外 MSA 轨道的迭代块数，属于权重结构。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.n_extra_block=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.n_main_block`

主迭代轨道块数，属于权重结构。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`32`。

适用模式：expert_config

生成映射：`model.n_main_block=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.n_ref_block`

结构细化块数，属于权重结构。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.n_ref_block=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.d_msa`

主 MSA 表征通道维度，不是 MSA 序列条数或 Neff。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`256`。

适用模式：expert_config

生成映射：`model.d_msa=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.d_msa_full`

额外 MSA 表征通道维度，不是输入同源序列深度。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`64`。

适用模式：expert_config

生成映射：`model.d_msa_full=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.d_pair`

残基对表征通道维度。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`128`。

适用模式：expert_config

生成映射：`model.d_pair=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.d_templ`

模板嵌入表征维度。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`64`。

适用模式：expert_config

生成映射：`model.d_templ=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.n_head_msa`

MSA 注意力头数。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`8`。

适用模式：expert_config

生成映射：`model.n_head_msa=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.n_head_pair`

残基对注意力头数。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.n_head_pair=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.n_head_templ`

模板注意力头数。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.n_head_templ=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.d_hidden`

主网络内部隐藏通道宽度。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`32`。

适用模式：expert_config

生成映射：`model.d_hidden=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.d_hidden_templ`

模板模块内部隐藏通道宽度。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`32`。

适用模式：expert_config

生成映射：`model.d_hidden_templ=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.p_drop`

网络 dropout 概率配置；推理模型通常处于 eval 模式，不等于推理噪声比例。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.15`。

适用模式：expert_config

生成映射：`model.p_drop=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.num_layers`

完整图配置的等变结构模块层数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：expert_config

生成映射：`model.SE3_param_full.num_layers=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.num_channels`

完整图配置的等变特征通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`32`。

适用模式：expert_config

生成映射：`model.SE3_param_full.num_channels=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.num_degrees`

完整图配置的等变表示包含的 degree 数量；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`2`。

适用模式：expert_config

生成映射：`model.SE3_param_full.num_degrees=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.n_heads`

完整图配置的等变注意力头数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.SE3_param_full.n_heads=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.div`

完整图配置的等变注意力通道分割/压缩系数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.SE3_param_full.div=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.l0_in_features`

完整图配置的标量（degree 0）输入通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`8`。

适用模式：expert_config

生成映射：`model.SE3_param_full.l0_in_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.l0_out_features`

完整图配置的标量（degree 0）输出通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`8`。

适用模式：expert_config

生成映射：`model.SE3_param_full.l0_out_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.l1_in_features`

完整图配置的向量（degree 1）输入通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`3`。

适用模式：expert_config

生成映射：`model.SE3_param_full.l1_in_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.l1_out_features`

完整图配置的向量（degree 1）输出通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`2`。

适用模式：expert_config

生成映射：`model.SE3_param_full.l1_out_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_full.num_edge_features`

完整图配置的等变模块边特征通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`32`。

适用模式：expert_config

生成映射：`model.SE3_param_full.num_edge_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.num_layers`

top-k 邻接图配置的等变结构模块层数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.num_layers=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.num_channels`

top-k 邻接图配置的等变特征通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`32`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.num_channels=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.num_degrees`

top-k 邻接图配置的等变表示包含的 degree 数量；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`2`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.num_degrees=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.n_heads`

top-k 邻接图配置的等变注意力头数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.n_heads=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.div`

top-k 邻接图配置的等变注意力通道分割/压缩系数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`4`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.div=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.l0_in_features`

top-k 邻接图配置的标量（degree 0）输入通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`64`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.l0_in_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.l0_out_features`

top-k 邻接图配置的标量（degree 0）输出通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`64`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.l0_out_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.l1_in_features`

top-k 邻接图配置的向量（degree 1）输入通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`3`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.l1_in_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.l1_out_features`

top-k 邻接图配置的向量（degree 1）输出通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`2`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.l1_out_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.SE3_param_topk.num_edge_features`

top-k 邻接图配置的等变模块边特征通道数；属于 checkpoint 架构，不是用户的 MSA 或筛选指标。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`64`。

适用模式：expert_config

生成映射：`model.SE3_param_topk.num_edge_features=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.freeze_track_motif`

网络结构更新时冻结 motif 轨道的模型选项；必须与训练配置匹配。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_config

生成映射：`model.freeze_track_motif=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `model.use_motif_timestep`

对 motif 使用专门时间步条件的模型选项；由匹配 checkpoint 决定。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_config

生成映射：`model.use_motif_timestep=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `diffuser.T`

扩散离散总步数；决定 partial_T 所在的噪声调度，不能当作物理模拟时长。

类型：`integer`；单位：步；来源记录默认：`50`。

适用模式：motif, partial, binder, unconditional

生成映射：`diffuser.T=<Hydra value>`；BDA 别名：`["diffuser_t"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 diffuser_t 的声明：{\"type\":\"integer\",\"default\":50,\"min\":1,\"max\":200}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 diffuser_t 的声明：{\"type\":\"integer\",\"default\":50,\"min\":1,\"max\":200}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `diffuser.b_0`

平移扩散 beta 调度的起始系数。

类型：`string`；单位：无量纲/见说明；来源记录默认：`1e-2`。

适用模式：expert_config

生成映射：`diffuser.b_0=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.b_T`

平移扩散 beta 调度的末端系数。

类型：`string`；单位：无量纲/见说明；来源记录默认：`7e-2`。

适用模式：expert_config

生成映射：`diffuser.b_T=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.schedule_type`

平移 beta 随时间变化的调度类型。

类型：`string`；单位：无量纲/见说明；来源记录默认：`linear`。

适用模式：expert_config

生成映射：`diffuser.schedule_type=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.so3_type`

旋转扩散的实现族，基础配置为 IGSO(3)。

类型：`string`；单位：无量纲/见说明；来源记录默认：`igso3`。

适用模式：expert_config

生成映射：`diffuser.so3_type=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.crd_scale`

坐标进入扩散噪声计算前的缩放因子。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.25`。

适用模式：expert_config

生成映射：`diffuser.crd_scale=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.partial_T`

部分扩散的加噪起始步；null 关闭，BDA 当前传0会走普通全扩散分支。

类型：`any`；单位：步；来源记录默认：`null`。

适用模式：motif, partial, binder, unconditional

生成映射：`diffuser.partial_T=<Hydra value>`；BDA 别名：`["partial_t"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 partial_t 的声明：{\"type\":\"integer\",\"default\":0,\"min\":0,\"max\":50}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 partial_t 的声明：{\"type\":\"integer\",\"default\":0,\"min\":0,\"max\":50}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `diffuser.so3_schedule_type`

旋转噪声随时间的调度类型。

类型：`string`；单位：无量纲/见说明；来源记录默认：`linear`。

适用模式：expert_config

生成映射：`diffuser.so3_schedule_type=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.min_b`

SO(3) 旋转 beta 调度的低端参数。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.5`。

适用模式：expert_config

生成映射：`diffuser.min_b=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.max_b`

SO(3) 旋转 beta 调度的高端参数。

类型：`number`；单位：无量纲/见说明；来源记录默认：`2.5`。

适用模式：expert_config

生成映射：`diffuser.max_b=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.min_sigma`

SO(3) 扩散 sigma 的最小值。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.02`。

适用模式：expert_config

生成映射：`diffuser.min_sigma=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `diffuser.max_sigma`

SO(3) 扩散 sigma 的最大值。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.5`。

适用模式：expert_config

生成映射：`diffuser.max_sigma=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `denoiser.noise_scale_ca`

逆扩散 CA 平移随机噪声的倍率，降低会减少采样随机性。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：expert_config

生成映射：`denoiser.noise_scale_ca=<Hydra value>`；BDA 别名：`["noise_scale_ca"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 noise_scale_ca 的声明：{\"type\":\"number\",\"default\":1.0,\"min\":0,\"max\":5}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 noise_scale_ca 的声明：{\"type\":\"number\",\"default\":1.0,\"min\":0,\"max\":5}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `denoiser.final_noise_scale_ca`

CA 噪声调度终点倍率；是否生效取决于调度实现。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：expert_config

生成映射：`denoiser.final_noise_scale_ca=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py)

### `denoiser.ca_noise_schedule_type`

CA 噪声倍率调度类型，默认恒定。

类型：`string`；单位：无量纲/见说明；来源记录默认：`constant`。

适用模式：expert_config

生成映射：`denoiser.ca_noise_schedule_type=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py)

### `denoiser.noise_scale_frame`

逆扩散局部残基坐标框旋转噪声倍率。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：expert_config

生成映射：`denoiser.noise_scale_frame=<Hydra value>`；BDA 别名：`["noise_scale_frame"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 noise_scale_frame 的声明：{\"type\":\"number\",\"default\":1.0,\"min\":0,\"max\":5}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 noise_scale_frame 的声明：{\"type\":\"number\",\"default\":1.0,\"min\":0,\"max\":5}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `denoiser.final_noise_scale_frame`

坐标框旋转噪声调度终点倍率；默认恒定调度下不应假定独立可调效果。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`1`。

适用模式：expert_config

生成映射：`denoiser.final_noise_scale_frame=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py)

### `denoiser.frame_noise_schedule_type`

局部坐标框旋转噪声倍率随时间的调度。

类型：`string`；单位：无量纲/见说明；来源记录默认：`constant`。

适用模式：expert_config

生成映射：`denoiser.frame_noise_schedule_type=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py)

### `ppi.hotspot_res`

靶标表面的 hotspot 残基列表；指定输入 PDB 链号及编号，作为生成接触偏好。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：binder, motif, symmetry

生成映射：`ppi.hotspot_res=<Hydra value>`；BDA 别名：`["hotspot_res"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 hotspot_res 的声明：{\"type\":\"string\",\"default\":\"[A59,A83,A91]\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 hotspot_res 的声明：{\"type\":\"string\",\"default\":\"[A59,A83,A91]\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `potentials.guiding_potentials`

一个或多个辅助势定义的 Hydra 字符串列表，例如 type:monomer_ROG；这是生成过程引导，不是 Rosetta 能量。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：binder, motif, symmetry

生成映射：`potentials.guiding_potentials=<Hydra value>`；BDA 别名：`["guiding_potentials"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 guiding_potentials 的声明：{\"type\":\"json\",\"default\":\"[]\"}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 guiding_potentials 的声明：{\"type\":\"json\",\"default\":\"[]\"}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [parameter_env](../../../backend_v2/app/compute/scripts.py)

### `potentials.guide_scale`

辅助势梯度的总体倍率，不是 kcal/mol 或结合自由能。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`10`。

适用模式：binder, motif, symmetry

生成映射：`potentials.guide_scale=<Hydra value>`；BDA 别名：`["guide_scale"]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "BDA 别名已出现在 command；字段默认值/范围可能与 upstream 不同，见 gaps。", "BDA RFdiffusion@1.1.0 字段 guide_scale 的声明：{\"type\":\"number\",\"default\":1.0,\"min\":0,\"max\":20}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 guide_scale 的声明：{\"type\":\"number\",\"default\":1.0,\"min\":0,\"max\":20}；仅记录声明，不等于命令已执行该值。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `potentials.guide_decay`

引导梯度随时间的衰减方式，如 constant、linear、quadratic、cubic；需安装代码支持。

类型：`string`；单位：无量纲/见说明；来源记录默认：`constant`。

适用模式：binder, motif, symmetry

生成映射：`potentials.guide_decay=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md)

### `potentials.olig_inter_all`

寡聚体接触势中是否对所有不同链对开启吸引项。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：binder, motif, symmetry

生成映射：`potentials.olig_inter_all=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md)

### `potentials.olig_intra_all`

寡聚体接触势中是否对所有链内接触开启吸引项。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：binder, motif, symmetry

生成映射：`potentials.olig_intra_all=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md)

### `potentials.olig_custom_contact`

自定义链对接触规则字符串；覆盖自动链对接触矩阵部分元素。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：binder, motif, symmetry

生成映射：`potentials.olig_custom_contact=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md)

### `potentials.substrate`

底物接触势引用的输入配体标识；需要对应输入原子和实现支持。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：binder, motif, symmetry

生成映射：`potentials.substrate=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py), [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md)

### `contig_settings.ref_idx`

手动输入参考结构索引映射，须同时给 hal_idx 和 idx_rf；基础 runner 是否读取该独立配置节点需另核对。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_config

生成映射：`contig_settings.ref_idx=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `contig_settings.hal_idx`

手动指定输出链/残基索引映射；必须与 ref_idx 等长对应。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_config

生成映射：`contig_settings.hal_idx=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `contig_settings.idx_rf`

RoseTTAFold 内部连续/跳跃残基索引，表达链断点；不是 PDB 展示编号。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_config

生成映射：`contig_settings.idx_rf=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `contig_settings.inpaint_seq_tensor`

直接给出序列保留/遮罩布尔张量，属于程序内部接口；shell Hydra 配置不能自动提供 tensor 对象。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_config

生成映射：`contig_settings.inpaint_seq_tensor=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.sidechain_input`

是否将非 motif 侧链作为预处理结构输入；必须匹配模型训练方式。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_config

生成映射：`preprocess.sidechain_input=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.motif_sidechain_input`

是否保留 motif 侧链作为结构条件。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_config

生成映射：`preprocess.motif_sidechain_input=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.d_t1d`

一维模板/时间条件特征通道数，与模型权重输入维度一致。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`22`。

适用模式：expert_config

生成映射：`preprocess.d_t1d=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.d_t2d`

二维模板/几何条件特征通道数，与模型权重输入维度一致。

类型：`integer`；单位：无量纲/见说明；来源记录默认：`44`。

适用模式：expert_config

生成映射：`preprocess.d_t2d=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.prob_self_cond`

预处理配置保留的 self-conditioning 概率；基础 runner 的实际使用未在已核对路径中确认，不能当作已生效开关。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.0`。

适用模式：expert_config

生成映射：`preprocess.prob_self_cond=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.str_self_cond`

预处理配置中的结构 self-conditioning 标记；与实际模型采样器逻辑需一起核实。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_config

生成映射：`preprocess.str_self_cond=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `preprocess.predict_previous`

预处理配置中的预测前一步目标标记，属于训练/模型兼容性配置。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_config

生成映射：`preprocess.predict_previous=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `logging.inputs`

输入日志配置标记；当前执行路径是否消费未确认，应依实际日志验证。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_config

生成映射：`logging.inputs=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json)

### `scaffoldguided.scaffoldguided`

启用 SS/adjacency 条件的 scaffold-guided 采样器，并选择相应 checkpoint。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.scaffoldguided=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.target_pdb`

scaffold-guided binder 模式是否含独立靶标 PDB。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.target_pdb=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.target_path`

scaffold-guided 靶标坐标路径。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.target_path=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.scaffold_list`

待采样 scaffold 标识列表或每行一个标识的文本文件。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.scaffold_list=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.scaffold_dir`

保存配套 scaffold 二级结构和 adjacency 张量的目录。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.scaffold_dir=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.sampled_insertion`

每段 loop 中随机增加残基数的上限或范围；不 masking loops 时要求0。

类型：`integer`；单位：残基；来源记录默认：`0`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.sampled_insertion=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.sampled_N`

N 端随机增加残基数的上限或范围；不是直接指定总长度。

类型：`integer`；单位：残基；来源记录默认：`0`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.sampled_N=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.sampled_C`

C 端随机增加残基数的上限或范围。

类型：`integer`；单位：残基；来源记录默认：`0`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.sampled_C=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.ss_mask`

每段 helix/strand 两端隐藏二级结构标签的残基数。

类型：`integer`；单位：残基；来源记录默认：`0`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.ss_mask=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.systematic`

按 scaffold 列表顺序系统遍历而非随机抽取。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.systematic=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.target_ss`

靶标二级结构张量路径；须与靶标裁剪和编号一致。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.target_ss=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.target_adj`

靶标残基接触/拓扑 adjacency 张量路径；须与 target_ss 对应。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.target_adj=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.mask_loops`

将 loop 条件遮罩以允许重新生成；false 时禁止额外 N/C/loop 插入。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.mask_loops=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffoldguided.contig_crop`

按 contig 选择裁剪靶标及对应 SS/adjacency，以降低上下文大小。

类型：`any`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：fold_conditioned

生成映射：`scaffoldguided.contig_crop=<Hydra value>`；BDA 别名：`[]`。

约束与版本差异：["默认值来自固定 commit 的 base config；最终 checkpoint 回载配置应作为运行证据。", "当前 BDA command 未映射此键；仅旧 library 配置覆盖或内部配置，不能从 UI 凭空提交。"]

依据：[config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml), [library](../../../qm-scripts/library/catalog.json), [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)

### `scaffold`

BDA 模板家族标签（custom/monellin/brazzein/thaumatin/mabinlin）；实际 command 未读取该字段，不会自动加载模板。

类型：`enum`；单位：无；来源记录默认：`custom`。

适用模式：motif, fold_conditioned

生成映射：`无上游命令映射`；BDA 别名：`["scaffold"]`。

约束与版本差异：["必须实际绑定模板 PDB 并提供 contigs，不能只选模板名。", "BDA RFdiffusion@1.1.0 字段 scaffold 的声明：{\"type\":\"enum\",\"default\":\"custom\",\"options\":[\"custom\",\"monellin\",\"brazzein\",\"thaumatin\",\"mabinlin\"]}；仅记录声明，不等于命令已执行该值。", "BDA RFdiffusion-authoring-6810138a@1.1.0-draft.1 字段 scaffold 的声明：{\"type\":\"enum\",\"default\":\"custom\",\"options\":[\"custom\",\"monellin\",\"brazzein\",\"thaumatin\",\"mabinlin\"]}；仅记录声明，不等于命令已执行该值。"]

依据：[live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `1.1.0`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| input_pdb | artifact_ref |  | {} |
| scaffold | enum | custom | {"options": ["custom", "monellin", "brazzein", "thaumatin", "mabinlin"]} |
| contigs | string | [A1-150/0 70-100] | {} |
| hotspot_res | string | [A59,A83,A91] | {} |
| num_designs | integer | 100 | {} |
| output_prefix | string | outputs/rfdiffusion/design | {} |
| partial_t | integer | 0 | {} |
| diffuser_t | integer | 50 | {} |
| noise_scale_ca | number | 1.0 | {} |
| noise_scale_frame | number | 1.0 | {} |
| inpaint_seq | string |  | {} |
| inpaint_str | string |  | {} |
| provide_seq | string |  | {} |
| ckpt_override_path | enum |  | {"options": ["", "models/ActiveSite_ckpt.pt", "models/Complex_beta_ckpt.pt"]} |
| symmetry | string |  | {} |
| guiding_potentials | json | [] | {} |
| guide_scale | number | 1.0 | {} |

**input_ports**

```json
[
  {
    "name": "inference_input_pdb",
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
    "required": false,
    "multiple": false,
    "description": "Input PDB. Target or motif PDB passed as inference.input_pdb. (from field 'inference.input_pdb')"
  }
]
```

**output_ports**

```json
[
  {
    "name": "backbone_set",
    "kind": "protein_structure",
    "artifact_type": "backbone_set",
    "filename_glob": "*.pdb",
    "description": "Generated backbone structures."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Sampling scores and metadata."
  },
  {
    "name": "run_manifest",
    "kind": "params",
    "artifact_type": "manifest",
    "filename_glob": "*",
    "description": "Machine-readable output manifest."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "backbone_set",
      "artifact_types": [
        "backbone_set"
      ],
      "required": true,
      "many": true,
      "help": "Generated backbone structures."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": false,
      "many": false,
      "help": "Sampling scores and metadata."
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
  "walltime_minutes": 1440,
  "cpus_evidence": "Diffusion inference on one GPU; no thread count is exposed."
}
```

命令摘要 SHA-256：`eb90ec7737d514eb9abd94f09e75f0b95f74b36a81a59d25757b8df8c20cd66c`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-n", "-name", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "ckpt_override_path", "contigs", "diffuser_t", "guide_scale", "guiding_potentials", "hotspot_res", "inpaint_seq", "inpaint_str", "noise_scale_ca", "noise_scale_frame", "num_designs", "output_prefix", "partial_t", "provide_seq", "requires_input_structure", "rfd_input", "symmetry"]`。

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
| design_*.pdb | 生成骨架坐标 | Å | 固定源码最终PDB只写前4个骨架原子；未指定身份的生成位置输出Gly占位。B-factor写1/0标记固定/扩散位置，绝不能把该列当pLDDT；pLDDT在TRB中。 | [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py) |
| design_*.trb | 配置、输入输出编号映射和预测轨迹元数据 | 混合 | 用 con_ref/con_hal 对齐保留片段；预测 pLDDT 不能用作结合能。 | [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py), [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py) |
| traj/*_Xt-1_traj.pdb / traj/*_pX0_traj.pdb | 中间去噪结构 | Å | 同一设计的时间步，不是额外候选或物理 MD。 | [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md), [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 覆盖前：library 118 键多无帮助文本；base/authoring 17 字段；现逐项 118/118 与 17/17 覆盖。
- RFdiffusion-authoring-6810138a 1.1.0-draft.1 与 base 1.1.0 的 command/字段键一致；仅文档覆盖，不写数据库或宣称草稿已验证。
- input_pdb UI 字段未直接参与 command；实际使用 inference_input_pdb 端口首个排序 PDB，多文件会静默取首个。
- UI 默认 num_designs=100 而 shell 缺值=10；output_prefix UI=outputs/rfdiffusion/design 但 shell 缺值=design；guide_scale UI=1 与 upstream=10；partial_t UI=0 与 upstream=null。
- BDA diffuser_t 范围1–200、partial_t 范围0–50只是表单约束；仍需满足 partial_t<=diffuser_t。
- guiding_potentials 为 JSON 字段；如果解析成原生 array/object，当前环境导出层不导出复杂对象，必须 preview 验证字符串传参，未证明复杂配置可执行。
- symmetry 缺少官方 --config-name symmetry 切换；scaffoldguided/cyclic 等不在当前 command 中；这些模式不能标记为全流程跑通。
- 118 个配置键包括 checkpoint 架构和可能未消费的旧配置，不应作为119项可自由更改的运行参数；contig_settings.*、logging.inputs 等消费边界已明确。
- 旧 runbook 没有当前声明的源支持运行证明；live 的 unknown/unproven 标签不能升级为通过。

## 易错点

- RFD1 diffusion 是生成模型的加噪/去噪，不是 Rosetta、分子动力学或结合 ΔG。
- provide_seq 的零起始映射索引与 hotspot/contigs 的 PDB 链编号不同，必须保存转换表。
- 降低噪声可能减少多样性；不能把某个噪声倍率设为通用优秀候选阈值。
- Hydra 列表要保持单一参数与引号；potentials 的 JSON 对象不能假定被 BDA 环境变量自动序列化。
- 最终PDB的Gly是占位，B-factor是固定/扩散掩码；不能把它当最终候选序列或pLDDT。

## 来源与版本

- [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：当前 base 与 authoring 草稿的字段、实际 command、输入输出与验证标签；commit `未固定/本地快照`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交库参数清单；不是 BDA command 已转发的证据；commit `未固定/本地快照`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/rfdiffusion/README.md)：旧集群 runbook；历史记录与当前声明证明边界；commit `未固定/本地快照`；读取 2026-09-15。
- [readme](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/README.md)：官方模式、contig、hotspot、partial/provide_seq、symmetry 与 RFpeptides；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [config](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/config/inference/base.yaml)：固定 commit 的 118 个基础 Hydra 配置及默认值；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [runner](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/model_runners.py)：checkpoint 选择、partial 长度/索引断言、模型配置回载与采样；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [contigs](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/contigs.py)：contig 解析、序列遮罩与输入/输出索引；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [utils](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/utils.py)：去噪与 scaffold SS/adjacency 采样；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [network](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/RoseTTAFoldModel.py)：神经网络维度与模型参数传递；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [symmetry](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/inference/symmetry.py)：对称操作、半径与重居中；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [potentials](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/rfdiffusion/potentials/manager.py)：势函数构造、链间接触与衰减；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [entrypoint](https://github.com/RosettaCommons/RFdiffusion/blob/2d0c003df46b9db41d119321f15403dec3716cd9/scripts/run_inference.py)：输出PDB/TRB、占位Gly、B-factor掩码、确定性与编号逻辑；commit `2d0c003df46b9db41d119321f15403dec3716cd9`；读取 2026-09-15。
- [parameter_env](../../../backend_v2/app/compute/scripts.py)：参数环境导出：标量小写键、bool为1/空字符串、array/object不导出；commit `未固定/本地快照`；读取 2026-09-15。
