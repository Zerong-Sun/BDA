# RFdiffusion3 — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

RFdiffusion3 是 Foundry 的全原子条件生成模型；输入条件写在 design_spec JSON，作业参数经 rfd3 design 传入。逐项覆盖8个 library 键和6个 BDA 字段，并补充官方固定 commit 的设计条件与关键采样参数。上游当前接口与站点2025安装并未证明一致。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/rfdiffusion3.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| foundry-2025-12-01 | true | valid | proven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 无条件全原子生成 (`unconditional`)

用长度定义从噪声生成蛋白。。BDA 接入：`declared`。

输入：design_spec JSON，例如 {"design":{"length":100}}

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "n_batches": 1,
  "diffusion_batch_size": 5,
  "ckpt_path": "rfd3"
}
```

输出检查：每个 JSON 顶层设计键应生成 n_batches×diffusion_batch_size 个最终结构；检查有效链长与残基。

限制：模式状态描述声明或配置覆盖；不等于该模式在当前 BDA 声明上已跑通。

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 蛋白靶标/hotspot 条件 (`binder`)

在靶标上下文周围生成结合候选。。BDA 接入：`unverified`。

输入：design_spec.input 指向实际可访问 PDB/CIF；contig 与 select_hotspots

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_spec": {
    "binder": {
      "input": "/staged/target.cif",
      "contig": "50-80,/0,A1-100",
      "select_hotspots": "A45,A60"
    }
  }
}
```

输出检查：逐原子最短热点距离、靶标链身份和严重碰撞；记录实际解析条件，而非只看 exit=0。

限制：design_spec 文件是 BDA 可声明输入，但所有嵌套条件必须匹配站点安装版本。；hotspot 近接是模型偏好，不能证明实验结合、受体激活或 ΔG。

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 固定序号 motif 原子条件 (`indexed_motif`)

保留 motif 原子几何及指定序列位置关系。。BDA 接入：`unverified`。

输入：PDB/CIF；contig 与 select_fixed_atoms 字典

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_spec": {
    "motif": {
      "input": "/staged/motif.pdb",
      "contig": "30,A10,40,A25,30",
      "select_fixed_atoms": {
        "A10": "CA,CB,OG",
        "A25": "BKBN"
      }
    }
  }
}
```

输出检查：对照 input 原子名和映射逐项检查 motif 保留；保留全部失败样本。

限制：live 标记曾有10样本原子几何 smoke evidence，但没有在此审计证明当前完整声明的 fingerprint 匹配，不外推到其他条件模式。

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 不固定序号的 motif 几何 (`unindexed_motif`)

保持指定原子的空间关系，同时允许重新安排序列位置。。BDA 接入：`unverified`。

输入：input；unindex；select_fixed_atoms；总 length

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_spec": {
    "motif": {
      "input": "/staged/motif.pdb",
      "unindex": "A10,A25",
      "length": "100-120",
      "select_fixed_atoms": {
        "A10": "TIP",
        "A25": "BKBN"
      }
    }
  }
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：unindexed 的位置变化必须读取输出映射，不能按原位置序号直接算错误的 RMSD。；站点旧输入方言可能使用不同键名；当前 dialect2 的 unindex/contig 不自动等同旧接口。

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 以 Å 噪声作部分扩散 (`partial`)

给已知结构加入有限坐标噪声再生成变化。。BDA 接入：`unverified`。

输入：input PDB/CIF 与 partial_t；如保留非蛋白组分需明确指定

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_spec": {
    "partial": {
      "input": "/staged/start.cif",
      "partial_t": 2.0
    }
  }
}
```

输出检查：保留输入对齐方式、CA RMSD、固定原子误差和实际噪声配置；不能称为物理时间轨迹。

限制：partial_t 为 Å 噪声标准差，绝不是 RFD1 的 diffuser.partial_T 步数。；实际逆扩散步数由噪声截断调度决定；num_timesteps 不等于部分扩散实际步数。；2 Å 是官方渐增探索起点示例，不是通过阈值；当前源码 ge=0，建议范围不是硬上限。

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 配体与氢键/埋藏条件 (`small_molecule`)

围绕明确化学组分构建蛋白环境。。BDA 接入：`unverified`。

输入：含目标配体的完整 PDB/CIF；ligand 与原子级条件

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_spec": {
    "ligand_design": {
      "input": "/staged/ligand.cif",
      "ligand": "LIG",
      "length": 150,
      "select_hbond_donor": {
        "LIG": "O1"
      }
    }
  }
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：氢键标签是生成条件，不是实测氢键、催化活性、结合能或选择性。；核实质子化/化学组分与实际原子名；不把错误配体几何当作高质量约束。

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json)

### 固定骨架/序列/侧链的条件组合 (`sequence_sidechain`)

通过独立的坐标和序列遮罩进行逆折叠或侧链重建。。BDA 接入：`unverified`。

输入：input 与显式 select_fixed_atoms/select_unfixed_sequence

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "design_spec": {
    "inverse_folding": {
      "input": "/staged/backbone.pdb",
      "contig": "A1-100",
      "select_fixed_atoms": {
        "A1-100": "BKBN"
      },
      "select_unfixed_sequence": true
    }
  }
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：True 表示选择所有可解锁序列区域；官方说明中 True/False 默认文字互相矛盾，实际 parser 默认 False；必须从输出确认。；RFD3 sequence head 输出不等同已完成 ProteinMPNN 或独立 refolding 验证。

依据：[readme](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/README.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### 全原子 C/D 对称生成 (`symmetry`)

使用对称 sampler 与 symmetry 配置生成多亚基结构。。BDA 接入：`not_exposed`。

输入：design_spec.symmetry 与额外 inference_sampler.kind=symmetry

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "inference_sampler.kind": "symmetry",
  "diffusion_batch_size": 1,
  "design_spec": {
    "oligomer": {
      "length": 100,
      "symmetry": {
        "id": "C3"
      }
    }
  }
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：BDA command 未转发 inference_sampler.kind；仅上传 symmetry JSON 不能声称完整模式已接通。；当前官方文档仅C/D；对称 motif 需预先对称化，不可照搬 RFD1 tetrahedral。

依据：[symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### 高级采样与诊断 (`expert_sampling`)

记录当前官方采样器、输出和检查设置以准备独立配置评审。。BDA 接入：`not_exposed`。

输入：与站点安装匹配的配置

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "inference_sampler.num_timesteps": 200,
  "prevalidate_inputs": true
}
```

输出检查：核对请求参数与输出元数据一致；保留失败样本与实际产物数。

限制：当前 BDA 只转发6个作业 fields 和 inputs/out_dir；其他 CLI 配置未暴露，不能直接在任务参数中填了就认为生效。

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

## 使用方法

1. 选择具体插件版本并冻结输入文件、序列/结构编号映射、配置和权重校验值。
2. 按下列模式检查输入条件；先 render/preview，对照实际命令检查每个参数被接收。
3. 按站点流程 validate → render/preview → review → stage → review → submit。
4. 执行后核对输出数量、参数回显、随机种子、条件几何与残基保留，再将结构和元数据一并入库。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `inputs`

承载各个设计任务条件的 JSON/YAML 文件路径；BDA 仅从 design_spec 端口读取首个排序 *.json。

类型：`any`；单位：无；来源记录默认：`null`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`inputs=<value>`；BDA 别名：`[]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "实际 BDA 绑定 design_spec 端口；JSON 内的 input 路径不会在 command 中重写。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### `out_dir`

最终结构与元数据目录；BDA command 固定为 BDA_OUTPUT_DIR。

类型：`any`；单位：无；来源记录默认：`./output`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`out_dir=<value>`；BDA 别名：`[]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "当前上游为必填 ???；library 的 ./output 是本地设置。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### `n_batches`

每个输入 JSON 顶层设计键的批次数。

类型：`integer`；单位：个；来源记录默认：`1`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`n_batches=<value>`；BDA 别名：`["n_batches"]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "BDA RFdiffusion3@foundry-2025-12-01 字段 n_batches 的声明：{\"type\":\"integer\",\"default\":1}；仅记录声明，不等于命令已执行该值。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### `diffusion_batch_size`

每批独立 diffusion 样本数；与 n_batches 相乘决定每个输入键的设计数。

类型：`integer`；单位：个；来源记录默认：`5`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`diffusion_batch_size=<value>`；BDA 别名：`["diffusion_batch_size"]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "BDA/library=5；当前官方 config=8。正整数，按显存调整，不能把5当模型固有常数。", "BDA RFdiffusion3@foundry-2025-12-01 字段 diffusion_batch_size 的声明：{\"type\":\"integer\",\"default\":5}；仅记录声明，不等于命令已执行该值。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### `ckpt_path`

模型 checkpoint 注册名或文件路径；BDA 默认 rfd3，必须保存实际解析文件与 SHA。

类型：`any`；单位：无；来源记录默认：`rfd3`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`ckpt_path=<value>`；BDA 别名：`["ckpt_path"]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "BDA RFdiffusion3@foundry-2025-12-01 字段 ckpt_path 的声明：{\"type\":\"string\",\"default\":\"rfd3\"}；仅记录声明，不等于命令已执行该值。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### `seed`

整个运行的随机种子；固定源码 base config 默认 null，BDA UI 默认0且会传入0，不应套用 ProteinMPNN 的0随机语义。

类型：`integer`；单位：无；来源记录默认：`null`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`seed=<value>`；BDA 别名：`["seed"]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "BDA RFdiffusion3@foundry-2025-12-01 字段 seed 的声明：{\"type\":\"integer\",\"default\":0}；仅记录声明，不等于命令已执行该值。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)

### `low_memory_mode`

使用省显存 tokenization，可能降低吞吐；不是低精度或改变物理噪声。

类型：`boolean`；单位：无；来源记录默认：`null`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`low_memory_mode=<value>`；BDA 别名：`["low_memory_mode"]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "library=null；当前官方与BDA字段默认false；环境层必须把false导出为空，避免 shell ${var:+...} 将非空 false 当 true。", "BDA RFdiffusion3@foundry-2025-12-01 字段 low_memory_mode 的声明：{\"type\":\"boolean\",\"default\":false}；仅记录声明，不等于命令已执行该值。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parameter_env](../../../backend_v2/app/compute/scripts.py)

### `dump_trajectories`

保存加噪/去噪中间原子结构；含虚拟原子时不能当作最终蛋白候选。

类型：`boolean`；单位：无；来源记录默认：`null`。

适用模式：unconditional, binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`dump_trajectories=<value>`；BDA 别名：`["dump_trajectories"]`。

约束与版本差异：["library 默认值来自站点登记，未证明等于当前固定 commit 默认值。", "library=null；当前官方与BDA字段默认false；环境层必须把false导出为空，避免 shell ${var:+...} 将非空 false 当 true。", "BDA RFdiffusion3@foundry-2025-12-01 字段 dump_trajectories 的声明：{\"type\":\"boolean\",\"default\":false}；仅记录声明，不等于命令已执行该值。"]

依据：[library](../../../qm-scripts/library/catalog.json), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parameter_env](../../../backend_v2/app/compute/scripts.py)

### `specification.input`

实际结构 PDB/CIF 路径；不是 BDA artifact id，必须能从计算节点访问。

类型：`string`；单位：路径；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].input`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.contig`

保留输入序号关系的 motif 与生成长度片段；当前方言用逗号分隔和 /0 断链，例如 50-80,/0,A1-100。

类型：`string`；单位：残基/链标识；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].contig`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.unindex`

指定保留空间几何但允许重新安排序列位置的输入片段；不能和 contig 固定片段重叠。

类型：`string|object`；单位：残基/原子选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].unindex`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.length`

生成系统的长度约束，可为固定长度或 min-max；与 contig 同时使用时需一致，不能套用 RFD1 斜杠语法。

类型：`integer|string`；单位：残基；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].length`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.ligand`

按输入化学组分名称或索引选择要纳入设计的配体；未指定的组分不可假定自动保留。

类型：`string`；单位：化学组分标识；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].ligand`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.allow_ligand_on_existing_chain`

允许配体沿用已有链ID，默认false以防链ID信息泄露；需要结构编号审阅。

类型：`boolean`；单位：无；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].allow_ligand_on_existing_chain`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.cif_parser_args`

CIF读取选项（缓存、缺失原子、氢处理、移除CCD等）；改变这些会改变实际参与条件的原子集合。

类型：`object`；单位：混合；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].cif_parser_args`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.extra`

输出附带的自定义来源/记录元数据，非模型条件或任意 CLI 转发入口。

类型：`object`；单位：无；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].extra`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.dialect`

输入方言版本；当前固定源码默认2，1为旧兼容模式。站点2025安装必须另确认支持集。

类型：`integer`；单位：版本号；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].dialect`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_fixed_atoms`

选中的输入原子固定坐标；True为所有输入原子，字典支持 ALL/BKBN/TIP 或明确原子名。

类型：`boolean|string|object`；单位：原子选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_fixed_atoms`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_unfixed_sequence`

选中的蛋白区域解除序列身份限制；True选中全部可选区域、False不解锁，默认解析为False。坐标固定与序列固定是独立条件。

类型：`boolean|string|object`；单位：残基选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_unfixed_sequence`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。", "官方文档与字段 description 的布尔默认文字存在互相矛盾；parser 设置默认 False，并用 inverse mask 标记 fixed sequence，以实际代码为准。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_buried`

为指定原子/残基施加埋藏 RASA 条件；与其他暴露等级不可重叠。

类型：`string|object`；单位：选择；不是已测面积；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_buried`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_partially_buried`

施加部分埋藏 RASA 条件；是生成目标，不是输出已满足证据。

类型：`string|object`；单位：选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_partially_buried`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_exposed`

施加暴露 RASA 条件；需要后验溶剂可及面积检查。

类型：`string|object`；单位：选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_exposed`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_hbond_donor`

在指定原子上标记氢键供体条件；应核实该原子的化学角色。

类型：`object`；单位：原子选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_hbond_donor`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_hbond_acceptor`

在指定原子上标记氢键受体条件；需独立检查距离、角度和质子化。

类型：`object`；单位：原子选择；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_hbond_acceptor`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.select_hotspots`

蛋白界面 hotspot 原子或残基选择；官方描述通常希望距设计重原子约4.5 Å内，不能当硬保证。

类型：`string|object`；单位：选择；距离解释用Å；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].select_hotspots`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.redesign_motif_sidechains`

固定 motif 骨架并允许侧链重新设计的快捷设置；其默认逻辑与显式 selections 应一起检查。

类型：`boolean|string`；单位：无；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].redesign_motif_sidechains`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.symmetry`

包含 id、is_unsym_motif、is_symmetric_motif 的对称配置；还需要 symmetry sampler。

类型：`object`；单位：群标识/选择；来源记录默认：`未声明`。

适用模式：symmetry

生成映射：`design_spec[design_name].symmetry`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.ori_token`

指定 [x,y,z] 生成区域中心引导坐标；必须在输入坐标系中解释。

类型：`array[number]`；单位：Å；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].ori_token`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.infer_ori_strategy`

未显式给 ori_token 时从输入质心 com 或热点 hotspots 推断生成中心的策略。

类型：`string`；单位：枚举；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].infer_ori_strategy`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.plddt_enhanced`

启用训练中使用的 pLDDT 增强条件；不是已经测得的输出 pLDDT。

类型：`boolean`；单位：无；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].plddt_enhanced`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.is_non_loopy`

全局更少/更多loop的条件；null不施加该偏好。

类型：`boolean|null`；单位：无；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].is_non_loopy`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.partial_t`

部分扩散所加坐标噪声标准差，null关闭；不是时间步数或MD时长。

类型：`number|null`；单位：Å；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].partial_t`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。", "当前源码要求 >=0；官方文本既列5–15 Å经验范围，也建议2 Å渐增探索，均非必须通过阈值。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification.atom_array_input`

程序内预加载 AtomArray 对象，不能通过 JSON 上传 Python 对象；BDA文件模式应使用 input。

类型：`internal`；单位：内部对象；来源记录默认：`未声明`。

适用模式：binder, indexed_motif, unindexed_motif, partial, small_molecule, sequence_sidechain

生成映射：`design_spec[design_name].atom_array_input`；BDA 别名：`[]`。

约束与版本差异：["位于 design_spec 的每个设计键下面；当前 BDA 无对应独立表单 field。", "这里说明固定 upstream commit 的接口；站点 foundry-2025-12-01 是否同方言必须验证。"]

依据：[input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json), [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)

### `specification`

覆盖各输入设计的 InputSpecification 字段；BDA command 当前不转发该对象。

类型：`object`；单位：无量纲/见说明；来源记录默认：`{}`。

适用模式：expert_sampling

生成映射：`specification=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `json_keys_subset`

只执行输入文件中列出的顶层设计键。

类型：`array|null`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_sampling

生成映射：`json_keys_subset=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `skip_existing`

跳过已存在产物的设计，重跑时需防止把旧输出误作新样本。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_sampling

生成映射：`skip_existing=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `global_prefix`

覆盖输出文件名前缀；不改变 out_dir。

类型：`string|null`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_sampling

生成映射：`global_prefix=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `prevalidate_inputs`

推理前预验证输入规格与原子选择；不替代后验条件检查。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_sampling

生成映射：`prevalidate_inputs=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.kind`

选择常规或 symmetry 采样器；对称JSON还需要设置此值。

类型：`string`；单位：无量纲/见说明；来源记录默认：`default`。

适用模式：expert_sampling, symmetry

生成映射：`inference_sampler.kind=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.num_timesteps`

逆扩散调度的离散步数；partial_t会截取调度，非物理时间。

类型：`integer`；单位：步；来源记录默认：`200`。

适用模式：expert_sampling

生成映射：`inference_sampler.num_timesteps=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.n_recycle`

每个去噪步的网络recycle数；null使用checkpoint默认。

类型：`integer|null`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_sampling

生成映射：`inference_sampler.n_recycle=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.step_scale`

扩散更新步长倍率；官方描述增大倾向降低多样性、提高可设计性，须按任务比较。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.5`。

适用模式：expert_sampling

生成映射：`inference_sampler.step_scale=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.noise_scale`

推理噪声倍率；改变样本分布，不是结构误差阈值。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.003`。

适用模式：expert_sampling

生成映射：`inference_sampler.noise_scale=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.p`

控制sigma调度形状的指数。

类型：`number`；单位：无量纲/见说明；来源记录默认：`7`。

适用模式：expert_sampling

生成映射：`inference_sampler.p=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.gamma_0`

采样随机扰动强度参数；降低会改变多样性，0对应ODE采样设置。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.6`。

适用模式：expert_sampling

生成映射：`inference_sampler.gamma_0=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.gamma_min`

启用gamma扰动的噪声/时间区间界点。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.0`。

适用模式：expert_sampling

生成映射：`inference_sampler.gamma_min=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.center_option`

以all/motif/diffuse指定采样坐标重居中的原子集合。

类型：`string`；单位：无量纲/见说明；来源记录默认：`all`。

适用模式：expert_sampling

生成映射：`inference_sampler.center_option=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.s_trans`

采样坐标平移增强的噪声尺度。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.0`。

适用模式：expert_sampling

生成映射：`inference_sampler.s_trans=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.allow_realignment`

允许依据motif对加噪结构再次对齐；默认关闭。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_sampling

生成映射：`inference_sampler.allow_realignment=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.s_jitter_origin`

对motif/ORI偏移施加高斯抖动的标准差。

类型：`number`；单位：无量纲/见说明；来源记录默认：`0.0`。

适用模式：expert_sampling

生成映射：`inference_sampler.s_jitter_origin=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.cfg_features`

classifier-free guidance 对照步中清零的条件特征列表。

类型：`array`；单位：无量纲/见说明；来源记录默认：`["active_donor", "active_acceptor", "ref_atomwise_rasa"]`。

适用模式：expert_sampling

生成映射：`inference_sampler.cfg_features=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.use_classifier_free_guidance`

开启对条件/无条件预测差异的引导；不是额外训练分类器。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_sampling

生成映射：`inference_sampler.use_classifier_free_guidance=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.cfg_t_max`

使用classifier-free guidance的最大调度时间/噪声界点。

类型：`number|null`；单位：无量纲/见说明；来源记录默认：`null`。

适用模式：expert_sampling

生成映射：`inference_sampler.cfg_t_max=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.cfg_scale`

classifier-free guidance强度倍率。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.5`。

适用模式：expert_sampling

生成映射：`inference_sampler.cfg_scale=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `inference_sampler.inference_noise_scaling_factor`

配置中存在但已核对官方输入文档明确提示未找到消费实现；不能宣称改变它会影响结果。

类型：`number`；单位：无量纲/见说明；来源记录默认：`1.0`。

适用模式：expert_sampling

生成映射：`inference_sampler.inference_noise_scaling_factor=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `cleanup_guideposts`

清除unindexed motif引导原子链；诊断可保留，但不是最终蛋白的一部分。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_sampling

生成映射：`cleanup_guideposts=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `cleanup_virtual_atoms`

去掉侧链扩散用的虚拟原子；保留用于诊断时不能参与最终原子统计。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_sampling

生成映射：`cleanup_virtual_atoms=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `read_sequence_from_sequence_head`

使用网络序列头确定输出氨基酸身份；官方不建议随意修改。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_sampling

生成映射：`read_sequence_from_sequence_head=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `output_full_json`

输出完整规格与来源信息，支持核对实际条件。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_sampling

生成映射：`output_full_json=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `dump_prediction_metadata_json`

保存每个预测的元数据JSON。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`true`。

适用模式：expert_sampling

生成映射：`dump_prediction_metadata_json=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `align_trajectory_structures`

对齐输出轨迹结构以便可视化；对齐后的坐标不可用于未经说明的绝对位移比较。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_sampling

生成映射：`align_trajectory_structures=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

### `compile_model`

当前官方配置的torch.compile性能选项；站点2025版本未证明存在。

类型：`boolean`；单位：无量纲/见说明；来源记录默认：`false`。

适用模式：expert_sampling

生成映射：`compile_model=<value>`；BDA 别名：`[]`。

约束与版本差异：["当前 BDA command 未转发；新增参数前需验证安装版本与预览渲染。"]

依据：[config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `foundry-2025-12-01`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| n_batches | integer | 1 | {} |
| diffusion_batch_size | integer | 5 | {} |
| ckpt_path | string | rfd3 | {} |
| seed | integer | 0 | {} |
| low_memory_mode | boolean | false | {} |
| dump_trajectories | boolean | false | {} |

**input_ports**

```json
[
  {
    "name": "design_spec",
    "kind": "params",
    "accepts": [
      "design_spec",
      "params",
      "json"
    ],
    "content_types": [
      "application/json"
    ],
    "required": true,
    "multiple": false,
    "description": "RFdiffusion3 input JSON: contig/length plus conditioning such as select_fixed_atoms, select_unfixed_sequence, select_hotspots, partial_t."
  },
  {
    "name": "input_structure",
    "kind": "protein_structure",
    "accepts": [
      "target_structure",
      "backbone_set",
      "complex_structure",
      "structure"
    ],
    "content_types": [],
    "required": false,
    "multiple": true,
    "description": "Structures the specification refers to (motif source, receptor)."
  }
]
```

**output_ports**

```json
[
  {
    "name": "backbones",
    "kind": "protein_structure",
    "artifact_type": "backbone_set",
    "filename_glob": "*.cif",
    "description": "Generated backbones. RFdiffusion3 writes mmCIF, not PDB."
  },
  {
    "name": "metadata",
    "kind": "tabular",
    "artifact_type": "confidence_record",
    "filename_glob": "*.json",
    "description": "Per-design sidecar metadata written next to each structure."
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
  "walltime_minutes": 1440,
  "cpus_evidence": "Diffusion inference on one GPU; the engine config exposes no thread count."
}
```

命令摘要 SHA-256：`5beb86bf5a3bae8373f9ab45931f82b029d06f8738fe794a49063fb0cd4a102d`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-name", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "ckpt_path", "diffusion_batch_size", "dump_trajectories", "low_memory_mode", "n_batches", "rfd3_spec", "seed"]`。

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
| *_model_*.cif[.gz] | 最终设计的全原子坐标与氨基酸身份 | Å | 需清除/区分guideposts和虚拟原子；结构生成不等于独立预测通过。 | [readme](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/README.md), [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [engine](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/engine.py) |
| *_model_*.json | 实际设计条件、sampled_contig、计数与预测元数据 | 混合 | 读取具体键才解释指标；不能笼统称 confidence_record 为已计算结合置信度。 | [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [engine](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/engine.py) |
| ca_rmsd_to_input | 部分扩散输出与输入CA对齐后的RMSD（存在时） | Å | 衡量偏离输入骨架程度；必须说明匹配位置和对齐方式，不代表受体结合好坏。 | [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [engine](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/engine.py) |
| noisy/denoised trajectories | 逆扩散中间坐标帧 | Å与离散步 | 可能没有最终序列标签且含虚拟原子；不是物理MD轨迹或额外候选。 | [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md), [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml), [engine](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/engine.py) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 覆盖前：library8键、BDA6字段；已逐项覆盖8/8与6/6，另补25个设计规格字段及29个当前官方高级配置。
- 当前官方来源固定commit b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c；live 插件版本 foundry-2025-12-01 与 library 的 site-install:<SITE_PATH> 不是Git commit。安装源码/权重SHA未知，不能声称当前接口与站点完全相同。
- 旧catalog repo指向 RosettaCommons/rfdiffusion3；本审计实际核对的是官方 Foundry models/rfd3，不将其冒称RFD1升级。
- BDA command仅转发n_batches/diffusion_batch_size/ckpt_path/seed/low_memory_mode/dump_trajectories；inputs和out_dir由端口/运行目录确定。
- design_spec只扫描JSON首文件，虽然当前上游支持YAML；input_structure端口未有input_adapter/JSON路径重写逻辑，必须在staging后检查JSON引用。
- 当前官方diffusion_batch_size默认8，BDA/library默认5；当前out_dir/inputs必填，library的out_dir默认./output只是本地包装约定。
- 官方 select_unfixed_sequence 描述文字有 True/False矛盾；本档依据实际parser默认False与fixed-sequence反掩码解释，不把矛盾文字照抄为功能。
- symmetry还需要inference_sampler.kind，BDA没有此CLI入口；当前文档仅C/D，不能把RFD1四面体支持归给RFD3。
- live 有曾记录job4137799的10个motif样本几何smoke说明，旧runbook尚无该记录；该局部证据不覆盖所有模式，且本审计没有验证当前声明fingerprint。
- BDA输出glob仅*.cif，而当前官方可产生*.cif.gz；需确认站点实际压缩形式和collector是否分类正确。此任务只补文档，未改collector/输出端口或启动计算。

## 易错点

- RFdiffusion3 partial_t（Å）、RFdiffusion diffuser.partial_T（步数）不能互换。
- RFD3 当前输入主键是 contig/unindex；不要把RFD1 contigmap.*或旧 runbook 的 contigs 复数盲目复制。
- 坐标固定不等于序列固定；必须同时审阅 select_fixed_atoms 与 select_unfixed_sequence。
- 来自JSON的input路径必须在计算节点真实存在；绑定input_structure端口并不会自动把JSON中的本地路径改写。
- 原子近接、motif保留或模型置信度均不能当受体激活、催化或结合自由能。

## 来源与版本

- [live](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：当前 base 与 authoring 草稿的字段、实际 command、输入输出与验证标签；commit `未固定/本地快照`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交库参数清单；不是 BDA command 已转发的证据；commit `未固定/本地快照`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/rfdiffusion3/README.md)：旧集群 runbook；历史记录与当前声明证明边界；commit `未固定/本地快照`；读取 2026-09-15。
- [readme](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/README.md)：RFD3 任务、输出与官方使用入口；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [input](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/input.md)：当前 InputSpecification 与 CLI 参数说明；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/rfdiffusion3.yaml)：当前 inference engine 默认参数；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [base_config](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/configs/inference_engine/base.yaml)：seed 与基础输入必填项；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [parser](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/inference/input_parsing.py)：真实 Pydantic 字段及 select_unfixed_sequence 默认解析；文档文字有矛盾时以代码为准；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [symmetry](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/symmetry.md)：C/D 对称模式与 sampler.kind 要求；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [examples](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/docs/examples/demo.json)：indexed/unindexed、部分扩散、核酸上下文示例；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [entrypoint](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/run_inference.py)：CLI config 处理入口；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [engine](https://github.com/RosettaCommons/foundry/blob/b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c/models/rfd3/src/rfd3/engine.py)：最终结构默认cif.gz写出与metadata/seed记录；commit `b02eed6a6bdf8f44d14a80cc36e3da13c9f2291c`；读取 2026-09-15。
- [parameter_env](../../../backend_v2/app/compute/scripts.py)：参数环境导出：标量小写键、bool为1/空字符串、array/object不导出；commit `未固定/本地快照`；读取 2026-09-15。
