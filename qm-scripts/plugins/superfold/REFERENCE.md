# superfold — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

QM AF2 monomer_ptm包装，支持PDB initial_guess或FASTA预测、伪MSA、多模型/种子；不是AF2-Multimer通用入口。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/superfold.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| qm-20260803 | true | unknown | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 序列单体PTM权重预测 (`sequence_prediction`)

FASTA输入及伪MSA特征。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "initial_guess": false,
  "mock_msa_depth": 1,
  "models": "all",
  "nstruct": 1
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### PDB坐标条件预测 (`initial_guess`)

用输入PDB坐标初始化网络。BDA 接入：`declared`。

输入：与设计序列/链边界一致的PDB

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "initial_guess": true,
  "mock_msa_depth": 1,
  "models": "all"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### 多权重/种子重复 (`ensemble`)

比较跨权重和seed的稳健性。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "models": "all",
  "nstruct": 3,
  "seed_start": 0,
  "enable_dropout": false
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### AF-Multimer权重 (`af_multimer_weights`)

官方superfold所查commit明确不执行此路径。BDA 接入：`not_exposed`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：--type/--version历史参数已失效，当前上游固定monomer_ptm/monomer代码；多链输入不等于Multimer权重

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

## 使用方法

1. 先按模型与版本确认输入实体、链ID、序列SHA、MSA/模板来源；区分预测、设计与亲和力。
2. 从当前BDA快照核对enabled、command和ports；文档中的configuration_only/not_exposed不是可执行能力承诺。
3. 填写对应模式配置，检查参数最终进入命令或结构化输入；数据库/权重需已存在且记录版本。
4. 预览任务脚本和实际输入文件，核对CPU/GPU、布尔false、输出目录及样本总数；本次审计不提交任务。
5. 完成后逐输入/seed/model核对文件、原始指标和失败样本；声明、成功退出、解析成功及科学结论分开记录。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `enable_dropout`

推理时启用dropout增加采样变化；需记录并与不启用情况区分。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --enable_dropout；BDA enable_dropout → --enable_dropout；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["enable_dropout"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `initial_guess`

用输入结构坐标初始化AF2包装的预测；属于有坐标条件预测，不能当完全独立的从序列验证。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：sequence_prediction, initial_guess

生成映射：`固定上游parser声明CLI --initial_guess；BDA initial_guess → --initial_guess；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["initial_guess"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `max_recycles`

superfold最多回收循环数。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --max_recycles；BDA max_recycles → --max_recycles；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["max_recycles"]`。

约束与版本差异：{"bda_variants": [{"default": 3, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `mock_msa_depth`

superfold复制/伪MSA深度；默认1表示单序列特征，不是检索得到的真实同源MSA深度。

类型：`integer`；单位：计数；来源记录默认：`1`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --mock_msa_depth；BDA mock_msa_depth → --mock_msa_depth；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["mock_msa_depth"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `models`

选择模型权重；superfold接受all或1–5列表，另一个predict.py包装声明整数1–5，不能混用。

类型：`string`；单位：无量纲/不适用；来源记录默认：`all`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --models；BDA models → --models；BDA把整个字符串作为单一argv，不能用字符串1 2代替上游nargs多值；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["models"]`。

约束与版本差异：{"bda_variants": [{"default": "all", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `nstruct`

superfold每套权重生成的结构数，总输出还要乘选中权重与输入数量。

类型：`integer`；单位：计数；来源记录默认：`1`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --nstruct；BDA nstruct → --nstruct；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["nstruct"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `num_ensemble`

AF2网络内部ensemble设置；不等于独立随机种子或实验重复数。

类型：`integer`；单位：计数；来源记录默认：`1`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --num_ensemble；BDA num_ensemble → --num_ensemble；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_ensemble"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `output_pae`

保存superfold PAE矩阵/统计；单体没有跨链接口PAE。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --output_pae；BDA output_pae → --output_pae；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["output_pae"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `output_summary`

生成reports.txt汇总供后续读取；仍须保留逐模型JSON。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --output_summary；BDA output_summary → --output_summary；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["output_summary"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `overwrite`

允许替换已有superfold结果，防止误混新旧版本。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --overwrite；BDA overwrite → --overwrite；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["overwrite"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `recycle_tol`

按相邻回收输出的Cα RMSD设置提前停止阈值；0禁用提前停止。

类型：`number`；单位：Å；来源记录默认：`0.0`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --recycle_tol；BDA recycle_tol → --recycle_tol；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["recycle_tol"]`。

约束与版本差异：{"bda_variants": [{"default": 0.0, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `reference_pdb`

superfold用于对齐/RMSD的参考结构，不自动等同initial_guess的输入坐标。

类型：`string`；单位：路径；来源记录默认：``。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --reference_pdb；BDA reference_pdb → --reference_pdb；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["reference_pdb"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

### `seed_start`

superfold生成种子序列的起始整数。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`0`。

适用模式：sequence_prediction, initial_guess, ensemble, af_multimer_weights

生成映射：`固定上游parser声明CLI --seed_start；BDA seed_start → --seed_start；superfold@qm-20260803: command引用此变量；仍需验证运行日志`；BDA 别名：`["seed_start"]`。

约束与版本差异：{"bda_variants": [{"default": 0, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "superfold", "version": "qm-20260803"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `qm-20260803`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| initial_guess | boolean | true | {} |
| mock_msa_depth | integer | 1 | {} |
| models | string | all | {} |
| nstruct | integer | 1 | {} |
| max_recycles | integer | 3 | {} |
| recycle_tol | number | 0.0 | {} |
| seed_start | integer | 0 | {} |
| num_ensemble | integer | 1 | {} |
| reference_pdb | string |  | {} |
| enable_dropout | boolean | false | {} |
| output_pae | boolean | true | {} |
| output_summary | boolean | true | {} |
| overwrite | boolean | false | {} |

**input_ports**

```json
[
  {
    "name": "structures",
    "kind": "protein_structure",
    "accepts": [
      "backbone_set",
      "candidate_structure",
      "predicted_structure",
      "complex_structure",
      "target_structure"
    ],
    "content_types": [],
    "required": true,
    "multiple": true,
    "description": "PDB designs to predict, required when initial_guess is enabled.",
    "exclusive_group": "superfold_input_source"
  },
  {
    "name": "sequences",
    "kind": "protein_sequence",
    "accepts": [
      "sequence_set",
      "sequence"
    ],
    "content_types": [
      "text/x-fasta",
      "text/plain"
    ],
    "required": true,
    "multiple": true,
    "description": "FASTA sequences to predict without a coordinate initial guess.",
    "exclusive_group": "superfold_input_source"
  }
]
```

**output_ports**

```json
[
  {
    "name": "structures",
    "kind": "protein_structure",
    "artifact_type": "predicted_structure",
    "filename_glob": "*_unrelaxed.pdb",
    "description": "Predicted structures, pLDDT in the B-factor column."
  },
  {
    "name": "metrics",
    "kind": "tabular",
    "artifact_type": "confidence_record",
    "filename_glob": "*_prediction_results.json",
    "description": "Per-prediction pLDDT, pTM and (with output_pae) PAE."
  },
  {
    "name": "summary",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "reports.txt",
    "description": "One line per prediction; the ranking input."
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
  "walltime_minutes": 720,
  "cpus_evidence": "The superfold wrapper takes no thread or worker argument (see the command registered by 0028); it runs AlphaFold2 weights on one GPU. The 2 it carried was never traced to anything."
}
```

命令摘要 SHA-256：`53d4d9148e1885a405def703768d0c9cf72dfafacd1a43f0bcafe934499c4a96`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--max_recycles", "--mock_msa_depth", "--models", "--nstruct", "--num_ensemble", "--out_dir", "--recycle_tol", "--reference_pdb", "--seed_start", "-d", "-eq", "-name", "-o", "-print0", "-r"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "enable_dropout", "initial_guess", "max_recycles", "mock_msa_depth", "models", "nstruct", "num_ensemble", "output_pae", "output_summary", "overwrite", "recycle_tol", "reference_pdb", "seed_start", "superfold_input", "superfold_inputs"]`。

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
| predicted_structure / complex | 预测原子坐标及链/残基映射 | Å | 坐标是假说；保留精确输入实体、模型与seed；不能推断实验结合。 | [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pLDDT | 局部结构置信度 | 0–100 | 逐文件核对尺度，不是概率或亲和力。 | [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pTM | monomer_ptm权重的整体拓扑置信度 | 0–1 | 固定源码强制monomer_ptm；ipTM仅在不可达的multimer分支，不是此入口可生成输出，多链initial_guess也不改变该限制。 | [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| PAE | 对齐后的相对位置预测误差矩阵 | Å | 保留链映射、非对角块和聚合定义；不能单独证明结合位点。 | [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| mean_pae_interaction | 跨链PAE汇总 | Å | 单体NaN为N/A，不应存零或算通过；跨链亦须说明initial_guess。 | [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| reports.txt / *_prediction_results.json | 逐模型/种子置信度与回收信息 | 混合字段 | 不要只保留最优模型；已装包装字段以实际输出核验。 | [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- QM安装源码commit未与此次上游021d2d1逐文件比较；当前声明参数仅有配置级证据。
- upstream固定monomer_ptm，不能把多链initial_guess叫成AF2-Multimer独立验证。
- initial_guess默认true，FASTA输入必须关闭，或使用上游支持的明确坐标路径方式，但当前BDA字段仅boolean。
- reference_pdb是string而非artifact_ref，跨机器路径是否staging需显式处理。
- mock_msa_depth是伪特征规模，不能当真实MSA或Neff；单体mean_pae_interaction为NaN应N/A。

## 易错点

- pLDDT/ipTM/RMSD不等于ΔG/ΔΔG/Kd或生物活性。
- template、initial_guess、空MSA和真实MSA是不同证据条件；不能混成独立交叉验证。
- 未消费的UI参数不可写入报告为已执行条件；本地catalog默认、BDA默认、命令回退和安装默认要区分。
- QM安装源码commit未与此次上游021d2d1逐文件比较；当前声明参数仅有配置级证据。
- upstream固定monomer_ptm，不能把多链initial_guess叫成AF2-Multimer独立验证。
- initial_guess默认true，FASTA输入必须关闭，或使用上游支持的明确坐标路径方式，但当前BDA字段仅boolean。
- reference_pdb是string而非artifact_ref，跨机器路径是否staging需显式处理。
- mock_msa_depth是伪特征规模，不能当真实MSA或Neff；单体mean_pae_interaction为NaN应N/A。

## 来源与版本

- [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：2026-09-15 BDA声明、command、schema、ports快照；声明不是运行成功证明；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/superfold/README.md)：2026-08-30历史QM运行手册；与当前声明不同处需单列；commit `None`；读取 2026-09-15。
- [parameter-env](../../../backend_v2/app/compute/scripts.py)：parameter_environment将boolean true/false导出为1/空字符串；字符串不按boolean解释；commit `None`；读取 2026-09-15。
- [upstream-0](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/run_superfold.py)：run_superfold.py；上游源码快照，不证明QM安装代码完全相同；commit `021d2d1d0501cf67c83039d18225ed3eab0bcefa`；读取 2026-09-15。
- [upstream-1](https://github.com/rdkibler/superfold/blob/021d2d1d0501cf67c83039d18225ed3eab0bcefa/README.md)：README.md；上游源码快照，不证明QM安装代码完全相同；commit `021d2d1d0501cf67c83039d18225ed3eab0bcefa`；读取 2026-09-15。
