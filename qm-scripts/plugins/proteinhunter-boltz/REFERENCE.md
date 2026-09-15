# proteinhunter_boltz — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

Protein-Hunter以Boltz结构幻觉和LigandMPNN循环生成设计；当前BDA不提供affinity头或seq输入，旧文档与上游seq实现存在冲突。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/proteinhunter-boltz.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| d4bd951-qm-c18-20260416-sampling | true | unknown | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 蛋白靶标设计 (`protein_binder`)

设计链A针对protein_seqs的B/C等目标。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "binder",
  "protein_seqs": "<reviewed_target_amino_acid_sequence>",
  "num_designs": 3,
  "num_cycles": 3
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)

### 小分子靶标设计 (`small_molecule_binder`)

提供一个CCD或SMILES小分子。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "binder",
  "ligand_ccd": "SAM",
  "ligand_smiles": ""
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)

### 核酸靶标设计 (`nucleic_binder`)

设计蛋白针对DNA/RNA目标。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "binder",
  "nucleic_type": "rna",
  "nucleic_seq": "<reviewed_RNA_sequence>"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)

### 无靶标设计 (`unconditional`)

仅生成蛋白结构/序列。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "unconditional",
  "protein_seqs": "",
  "ligand_ccd": "",
  "ligand_smiles": "",
  "nucleic_seq": ""
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)

### 环化链设计配置 (`cyclic`)

在binder配置上请求cyclic。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "mode": "binder",
  "cyclic": true
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：需额外核对实际成键与几何；仅有标记不是闭环验证

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)

### 小分子affinity评估 (`affinity`)

当前Protein-Hunter包装不暴露Boltz-2 affinity head。BDA 接入：`not_exposed`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：command只提供boltz2_conf.ckpt，不可把通用Boltz-2亲和力能力赋予本入口

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)

### 固定支架序列条件 (`scaffold_conditioned`)

BDA不暴露seq；官方起始序列支持与固定支架条件设计须区分。BDA 接入：`not_exposed`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：BDA command没有seq；官方pipeline读取a.seq为初始化，但不保证固定支架或固定序列；旧runbook关于上游完全不读seq的说法与固定源码冲突

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

## 使用方法

1. 先按模型与版本确认输入实体、链ID、序列SHA、MSA/模板来源；区分预测、设计与亲和力。
2. 从当前BDA快照核对enabled、command和ports；文档中的configuration_only/not_exposed不是可执行能力承诺。
3. 填写对应模式配置，检查参数最终进入命令或结构化输入；数据库/权重需已存在且记录版本。
4. 预览任务脚本和实际输入文件，核对CPU/GPU、布尔false、输出目录及样本总数；本次审计不提交任务。
5. 完成后逐输入/seed/model核对文件、原始指标和失败样本；声明、成功退出、解析成功及科学结论分开记录。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `alanine_bias`

在重设计采样中抑制丙氨酸倾向；不能替代完整可开发性筛查。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --alanine_bias；BDA alanine_bias → --alanine_bias；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["alanine_bias"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [parameter-env](../../../backend_v2/app/compute/scripts.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `contact_residues`

指定蛋白靶标接触残基；目标链间用竖线分隔、同链位置用逗号分隔，例如1,2,5|3,5。必须有protein_seqs并核对编号。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：protein_binder, cyclic

生成映射：`固定上游parser声明CLI --contact_residues；BDA contact_residues → --contact_residues；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["contact_residues"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `cyclic`

请求环化设计链；结构成键及参数消费须验证，不能只凭开关认为化学闭环已成功。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --cyclic；BDA cyclic → --cyclic；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["cyclic"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [parameter-env](../../../backend_v2/app/compute/scripts.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `diffuse_steps`

Protein-Hunter内Boltz扩散步骤数，映射--diffuse_steps；不是直接官方Boltz --sampling_steps的界面参数名。

类型：`integer`；单位：计数；来源记录默认：`100`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --diffuse_steps；BDA diffuse_steps → --diffuse_steps；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["diffuse_steps"]`。

约束与版本差异：{"bda_variants": [{"default": 100, "enabled": true, "enum": null, "maximum": 1000, "minimum": 1, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `high_iptm_threshold`

内部high-confidence集合的ipTM阈值，0–1；因用同一模型优化而不能作为独立亲和力或功能验证。

类型：`number`；单位：无量纲/不适用；来源记录默认：`0.8`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --high_iptm_threshold；BDA high_iptm_threshold → --high_iptm_threshold；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["high_iptm_threshold"]`。

约束与版本差异：{"bda_variants": [{"default": 0.8, "enabled": true, "enum": null, "maximum": 1.0, "minimum": 0.0, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `high_plddt_threshold`

内部high-confidence集合的pLDDT阈值，包装使用0–1；不可直接与AF2/AF3的0–100混比。

类型：`number`；单位：无量纲/不适用；来源记录默认：`0.8`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --high_plddt_threshold；BDA high_plddt_threshold → --high_plddt_threshold；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["high_plddt_threshold"]`。

约束与版本差异：{"bda_variants": [{"default": 0.8, "enabled": true, "enum": null, "maximum": 1.0, "minimum": 0.0, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `ligand_ccd`

以PDB CCD代码指定小分子靶标；与ligand_smiles非空值互斥。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：small_molecule_binder

生成映射：`固定上游parser声明CLI --ligand_ccd；BDA ligand_ccd → --ligand_ccd；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["ligand_ccd"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `ligand_smiles`

以SMILES定义小分子靶标，需明确电荷/立体化学；与ligand_ccd互斥。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：small_molecule_binder

生成映射：`固定上游parser声明CLI --ligand_smiles；BDA ligand_smiles → --ligand_smiles；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["ligand_smiles"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `max_protein_length`

随机设计蛋白长度上界，需大于等于下界。

类型：`integer`；单位：aa；来源记录默认：`120`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --max_protein_length；BDA max_protein_length → --max_protein_length；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["max_protein_length"]`。

约束与版本差异：{"bda_variants": [{"default": 120, "enabled": true, "enum": null, "maximum": 2000, "minimum": 4, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `min_protein_length`

随机设计蛋白长度下界，需小于等于上界。

类型：`integer`；单位：aa；来源记录默认：`60`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --min_protein_length；BDA min_protein_length → --min_protein_length；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["min_protein_length"]`。

约束与版本差异：{"bda_variants": [{"default": 60, "enabled": true, "enum": null, "maximum": 2000, "minimum": 4, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `mode`

Protein-Hunter binder模式针对提供靶标生成链A；unconditional模式不应提供任何靶标。

类型：`string`；单位：无量纲/不适用；来源记录默认：`binder`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --mode；BDA mode → --mode；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["mode"]`。

约束与版本差异：{"bda_variants": [{"default": "binder", "enabled": true, "enum": ["binder", "unconditional"], "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `msa_mode`

Protein-Hunter目标MSA路径：single或mmseqs；single并非MMseqs搜索完成后无命中。

类型：`string`；单位：无量纲/不适用；来源记录默认：`single`。

适用模式：protein_binder, cyclic

生成映射：`固定上游parser声明CLI --msa_mode；BDA msa_mode → --msa_mode；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["msa_mode"]`。

约束与版本差异：{"bda_variants": [{"default": "single", "enabled": true, "enum": ["single", "mmseqs"], "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `nucleic_seq`

DNA/RNA靶标序列；不是要表达的设计蛋白DNA构建。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：nucleic_binder

生成映射：`固定上游parser声明CLI --nucleic_seq；BDA nucleic_seq → --nucleic_seq；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["nucleic_seq"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `nucleic_type`

核酸靶标类型dna或rna，与nucleic_seq共同使用。

类型：`string`；单位：无量纲/不适用；来源记录默认：`dna`。

适用模式：nucleic_binder

生成映射：`固定上游parser声明CLI --nucleic_type；BDA nucleic_type → --nucleic_type（仅nucleic_seq非空时传入）；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["nucleic_type"]`。

约束与版本差异：{"bda_variants": [{"default": "dna", "enabled": true, "enum": ["dna", "rna"], "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `num_cycles`

Protein-Hunter结构预测/序列重设计的迭代轮数；每轮序列可能不同，分数必须绑定该轮序列。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --num_cycles；BDA num_cycles → --num_cycles；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_cycles"]`。

约束与版本差异：{"bda_variants": [{"default": 3, "enabled": true, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `num_designs`

独立设计轨迹数量，不等于通过筛选候选数。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --num_designs；BDA num_designs → --num_designs；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_designs"]`。

约束与版本差异：{"bda_variants": [{"default": 3, "enabled": true, "enum": null, "maximum": 10000, "minimum": 1, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `omit_aa`

禁止LigandMPNN采样的氨基酸集合，映射--omit_AA；当前默认排除C，不适合直接宣称保留二硫键支架。

类型：`string`；单位：无量纲/不适用；来源记录默认：`C`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --omit_AA；BDA omit_aa → --omit_AA；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["omit_aa"]`。

约束与版本差异：{"bda_variants": [{"default": "C", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `percent_x`

初始设计链中X未知残基的百分比，映射--percent_X；X是设计初始化标记，不是最终成熟蛋白序列。

类型：`integer`；单位：%；来源记录默认：`90`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --percent_X；BDA percent_x → --percent_X；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["percent_x"]`。

约束与版本差异：{"bda_variants": [{"default": 90, "enabled": true, "enum": null, "maximum": 100, "minimum": 0, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `protein_seqs`

蛋白靶标氨基酸序列，冒号分隔多链；设计链A，目标从B/C等开始，必须核对最终链映射。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：protein_binder, cyclic

生成映射：`固定上游parser声明CLI --protein_seqs；BDA protein_seqs → --protein_seqs；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["protein_seqs"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `recycling_steps`

Boltz结构回收循环数；不是优化轮次num_cycles，也不是物理时间。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --recycling_steps；BDA recycling_steps → --recycling_steps；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["recycling_steps"]`。

约束与版本差异：{"bda_variants": [{"default": 3, "enabled": true, "enum": null, "maximum": 20, "minimum": 0, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `seq`

BDA当前schema限定空值且command不传。官方d4bd951 pipeline实际读取a.seq设定起始序列和长度，和旧runbook说法冲突；起始序列也不等于固定支架/固定残基约束。

类型：`string`；单位：无量纲/不适用；来源记录默认：`未声明`。

适用模式：scaffold_conditioned

生成映射：`固定上游CLI --seq由pipeline读取为初始序列；BDA schema禁止非空且command未传--seq；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["seq"]`。

约束与版本差异：{"bda_variants": [{"default": null, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

### `temperature`

LigandMPNN序列采样温度；BDA默认1.0与上游该commit的0.1不同，必须记录来源。

类型：`number`；单位：无量纲/不适用；来源记录默认：`1.0`。

适用模式：protein_binder, small_molecule_binder, nucleic_binder, unconditional, cyclic, affinity, scaffold_conditioned

生成映射：`固定上游parser声明CLI --temperature；BDA temperature → --temperature；proteinhunter_boltz@d4bd951-qm-c18-20260416-sampling: command引用此变量；仍需验证运行日志`；BDA 别名：`["temperature"]`。

约束与版本差异：{"bda_variants": [{"default": 1.0, "enabled": true, "enum": null, "maximum": 10.0, "minimum": 0.0, "plugin_key": "proteinhunter_boltz", "version": "d4bd951-qm-c18-20260416-sampling"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `d4bd951-qm-c18-20260416-sampling`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| mode | string | binder | {"enum": ["binder", "unconditional"], "required": true, "x-bda-conditional-schemas": [{"branch": "root.allOf[0].if", "schema": {"const": "binder", "required": true}}, {"branch": "root.allOf[1].if", "schema": {"const": "unconditional", "required": true}}]} |
| cyclic | boolean | false | {} |
| omit_aa | string | C | {} |
| msa_mode | string | single | {"enum": ["single", "mmseqs"]} |
| percent_x | integer | 90 | {"maximum": 100, "minimum": 0} |
| ligand_ccd | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[0].then.anyOf[2]", "schema": {"minLength": 1, "required": true}}, {"branch": "root.allOf[1].then", "schema": {"maxLength": 0}}]} |
| num_cycles | integer | 3 | {"maximum": 100, "minimum": 1, "required": true} |
| nucleic_seq | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[0].then.anyOf[3]", "schema": {"minLength": 1, "required": true}}, {"branch": "root.allOf[1].then", "schema": {"maxLength": 0}}]} |
| num_designs | integer | 3 | {"maximum": 10000, "minimum": 1, "required": true} |
| temperature | number | 1.0 | {"maximum": 10.0, "minimum": 0.0} |
| alanine_bias | boolean | false | {} |
| nucleic_type | string | dna | {"enum": ["dna", "rna"]} |
| protein_seqs | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[0].then.anyOf[0]", "schema": {"minLength": 1, "required": true}}, {"branch": "root.allOf[1].then", "schema": {"maxLength": 0}}, {"branch": "root.allOf[2].then", "schema": {"minLength": 1, "required": true}}]} |
| diffuse_steps | integer | 100 | {"maximum": 1000, "minimum": 1} |
| ligand_smiles | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[0].then.anyOf[1]", "schema": {"minLength": 1, "required": true}}, {"branch": "root.allOf[1].then", "schema": {"maxLength": 0}}]} |
| recycling_steps | integer | 3 | {"maximum": 20, "minimum": 0} |
| contact_residues | string |  | {"x-bda-conditional-schemas": [{"branch": "root.allOf[2].if", "schema": {"minLength": 1, "required": true}}]} |
| max_protein_length | integer | 120 | {"maximum": 2000, "minimum": 4} |
| min_protein_length | integer | 60 | {"maximum": 2000, "minimum": 4} |
| high_iptm_threshold | number | 0.8 | {"maximum": 1.0, "minimum": 0.0} |
| high_plddt_threshold | number | 0.8 | {"maximum": 1.0, "minimum": 0.0} |
| seq | string | 未声明 | {"x-bda-conditional-schemas": [{"branch": "root.allOf[3]", "schema": {"description": "Not supported: the ProteinHunter entrypoint parses --seq and never reads it. Use RFdiffusion partial diffusion for scaffold-conditioned design.", "maxLength": 0, "type": "string"}}]} |

**input_ports**

```json
[
  {
    "name": "target_structure",
    "kind": "protein_structure",
    "accepts": [
      "target_structure",
      "backbone_set",
      "predicted_structure",
      "complex_structure"
    ],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Optional target structure. Sequence targets are given via the protein_seqs parameter."
  }
]
```

**output_ports**

```json
[
  {
    "name": "0_protein_hunter_design",
    "kind": "opaque",
    "artifact_type": "design_trajectory",
    "description": "Per-run trajectory: every cycle's predicted structure and the convergence plot."
  },
  {
    "name": "high_iptm_pdb",
    "kind": "protein_structure",
    "artifact_type": "candidate_complex",
    "filename_glob": "*.pdb",
    "description": "High-confidence ProteinHunter complex structures."
  },
  {
    "name": "high_iptm_yaml",
    "kind": "params",
    "artifact_type": "design_spec",
    "filename_glob": "*.yaml",
    "description": "Boltz specifications paired with the high-confidence complexes."
  },
  {
    "name": "summaries",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "summary_*.csv",
    "description": "All-run and high-confidence summaries; the latter promotes candidates."
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
  "cpus_evidence": "Wraps `boltz predict`; the same measurement that fixed Boltz applies."
}
```

命令摘要 SHA-256：`5ed05534820e7fc34e8ad35dc46cd920859a4581f79414fffcc841579dd72c6b`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--boltz_model_path", "--ccd_path", "--contact_residues", "--diffuse_steps", "--gpu_id", "--high_iptm_threshold", "--high_plddt_threshold", "--ligand_ccd", "--ligand_smiles", "--max_protein_length", "--min_protein_length", "--mode", "--msa_mode", "--name", "--nucleic_seq", "--nucleic_type", "--num_cycles", "--num_designs", "--omit_AA", "--percent_X", "--protein_seqs", "--recycling_steps", "--save_dir", "--temperature"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_JOB_NAME", "BDA_OUTPUT_DIR", "alanine_bias", "contact_residues", "cyclic", "diffuse_steps", "high_iptm_threshold", "high_plddt_threshold", "ligand_ccd", "ligand_smiles", "max_protein_length", "min_protein_length", "mode", "msa_mode", "nucleic_seq", "nucleic_type", "num_cycles", "num_designs", "omit_aa", "percent_x", "protein_seqs", "recycling_steps", "temperature"]`。

输入适配器：`null`；输出解析器：`proteinhunter_boltz`。

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
| predicted_structure / complex | 预测原子坐标及链/残基映射 | Å | 坐标是假说；保留精确输入实体、模型与seed；不能推断实验结合。 | [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pLDDT | 局部结构置信度 | 通常0–100；Boltz/Protein-Hunter原始汇总常0–1 | 逐文件核对尺度，不是概率或亲和力。 | [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pTM / ipTM | 整体折叠/多链相对构象置信度 | 0–1 | 单体没有真实跨链接口ipTM；不要将零占位或对角线当结合分数。 | [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| PAE | 对齐后的相对位置预测误差矩阵 | Å | 保留链映射、非对角块和聚合定义；不能单独证明结合位点。 | [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| summary_all_runs.csv / summary_high_iptm.csv | 所有轨迹及内部阈值通过集合 | 混合字段 | 每轮可能换序列；只有与当前候选SHA一致轮次属于该候选。 | [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| 0_protein_hunter_design / high_iptm_pdb / high_iptm_yaml | 设计轨迹、筛选后的结构与配套YAML | 结构+参数 | 内部high confidence不是独立验证；没有affinity JSON不能声称算了亲和力。 | [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 上游commit d4bd951可核实，但QM版本另含c18/sampling本地改动，未证明安装源码逐字一致。
- 仅boltz2_conf.ckpt路径；没有affinity请求和独立亲和力权重，iptm不是小分子Kd或ΔG。
- 目标结构port未在command消费，实际目标来自protein_seqs/ligand/nucleic参数；不能宣称结构模板已用于设计。
- 内部优化后的同模型confidence属于选择偏差，需独立结构方法及实验验证。
- random seed未在此BDA schema/command暴露；seeded_proteinhunter_entry.py历史作业包装不能自动归属于此注册入口。
- BDA禁止seq非空且command未传；但官方d4bd951 pipeline.py读取a.seq作为起始序列，与旧runbook/registry描述冲突。须核验QM本地c18源码；初始化序列不等于固定支架。
- 上游另有template_path/refiner_mode/use_alphafold3_validation/contact过滤控制，但当前BDA未暴露；不能把上游可选AF3验证当作本作业已经执行。

## 易错点

- pLDDT/ipTM/RMSD不等于ΔG/ΔΔG/Kd或生物活性。
- template、initial_guess、空MSA和真实MSA是不同证据条件；不能混成独立交叉验证。
- 未消费的UI参数不可写入报告为已执行条件；本地catalog默认、BDA默认、命令回退和安装默认要区分。
- 上游commit d4bd951可核实，但QM版本另含c18/sampling本地改动，未证明安装源码逐字一致。
- 仅boltz2_conf.ckpt路径；没有affinity请求和独立亲和力权重，iptm不是小分子Kd或ΔG。
- 目标结构port未在command消费，实际目标来自protein_seqs/ligand/nucleic参数；不能宣称结构模板已用于设计。
- 内部优化后的同模型confidence属于选择偏差，需独立结构方法及实验验证。
- random seed未在此BDA schema/command暴露；seeded_proteinhunter_entry.py历史作业包装不能自动归属于此注册入口。
- BDA禁止seq非空且command未传；但官方d4bd951 pipeline.py读取a.seq作为起始序列，与旧runbook/registry描述冲突。须核验QM本地c18源码；初始化序列不等于固定支架。

## 来源与版本

- [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：2026-09-15 BDA声明、command、schema、ports快照；声明不是运行成功证明；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/proteinhunter-boltz/README.md)：2026-08-30历史QM运行手册；与当前声明不同处需单列；commit `None`；读取 2026-09-15。
- [parameter-env](../../../backend_v2/app/compute/scripts.py)：parameter_environment将boolean true/false导出为1/空字符串；字符串不按boolean解释；commit `None`；读取 2026-09-15。
- [upstream-0](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/design.py)：boltz_ph/design.py；上游源码快照，不证明QM安装代码完全相同；commit `d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c`；读取 2026-09-15。
- [upstream-1](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/README.md)：README.md；上游源码快照，不证明QM安装代码完全相同；commit `d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c`；读取 2026-09-15。
- [upstream-2](https://github.com/yehlincho/Protein-Hunter/blob/d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c/boltz_ph/pipeline.py)：boltz_ph/pipeline.py；上游源码快照，不证明QM安装代码完全相同；commit `d4bd9515882c2aa81e97f3d3bf7f42247a9fe80c`；读取 2026-09-15。
