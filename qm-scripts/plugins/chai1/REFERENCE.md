# Chai-1 — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

Chai多分子结构预测，可用ESM、MSA、模板及约束；当前BDA注册disabled，只提供可审阅配置，不能宣称可运行。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/chai1.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 0.6.1 | false | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### ESM/单序列预测 (`single_sequence`)

特殊FASTA输入，无远端MSA。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_esm_embeddings": true,
  "use_msa_server": false
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### 多分子复合物 (`complex`)

FASTA不同实体定义蛋白、核酸或ligand。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "num_diffn_samples": 5
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### 远端MSA (`msa_server`)

MMseqs服务产生目标MSA。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_msa_server": true
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### 本地MSA (`local_msa`)

使用Chai格式MSA目录。BDA 接入：`not_exposed`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "msa_directory": "/reviewed/chai-msas"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### 接触/成键约束 (`restraints`)

输入兼容Chai schema的约束文件。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "restraints_json": "/reviewed/restraints.csv"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### 模板特征 (`templates`)

服务或template_hits_path加载模板。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_templates_server": true
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：Chai BDA插件disabled；template_cif_folder未映射到实际命令

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

## 使用方法

1. 先按模型与版本确认输入实体、链ID、序列SHA、MSA/模板来源；区分预测、设计与亲和力。
2. 从当前BDA快照核对enabled、command和ports；文档中的configuration_only/not_exposed不是可执行能力承诺。
3. 填写对应模式配置，检查参数最终进入命令或结构化输入；数据库/权重需已存在且记录版本。
4. 预览任务脚本和实际输入文件，核对CPU/GPU、布尔false、输出目录及样本总数；本次审计不提交任务。
5. 完成后逐输入/seed/model核对文件、原始指标和失败样本；声明、成功退出、解析成功及科学结论分开记录。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `constraint_path`

Chai接触约束CSV文件；链ID及带氨基酸字母的一起始位置需匹配FASTA。该commit中confidence/min_distance_angstrom列未被模型使用。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(constraint_path=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [upstream-2](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/examples/restraints/README.md)

### `device`

PyTorch设备字符串，例如cuda:0；按调度器可见设备编号。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(device=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `downloads_dir`

BDA旧Chai缓存目录字段；command未导出CHAI_DOWNLOADS_DIR，当前无生效证据。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；Chai-1@0.6.1: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["downloads_dir"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `fasta_file`

Chai特殊FASTA输入，实体header指定protein/ligand/RNA等；普通氨基酸FASTA只表达蛋白信息。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(fasta_file=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `fasta_names_as_cif_chains`

将FASTA实体名用于输出mmCIF链命名；需遵守可用链ID约束并保留映射。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(fasta_names_as_cif_chains=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `input_fasta`

BDA Chai输入FASTA端口/参数；需核对staging路径是否绑定进command变量。

类型：`artifact_ref`；单位：路径；来源记录默认：``。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；Chai-1@0.6.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["input_fasta"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `low_memory`

启用Chai低内存推理路径，降低内存峰值但可能影响速度。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(low_memory=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `msa_directory`

Chai本地预计算MSA目录，需采用Chai指定格式和序列hash命名；不是任意a3m目录。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(msa_directory=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `msa_server_url`

远端MSA服务地址；启用服务会向该服务发送目标序列，需明确数据流。

类型：`string`；单位：无量纲/不适用；来源记录默认：`https://api.colabfold.com`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(msa_server_url=...)；Chai-1@0.6.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["msa_server_url"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `num_diffn_samples`

每个trunk样本的扩散样本数。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(num_diffn_samples=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `num_diffn_timesteps`

Chai扩散去噪时间步数，非MD时间。

类型：`integer`；单位：计数；来源记录默认：`200`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(num_diffn_timesteps=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `num_samples`

BDA样本数别名；Boltz映射--diffusion_samples，Chai映射--num-diffn-samples。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；Chai-1@0.6.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_samples"]`。

约束与版本差异：{"bda_variants": [{"default": 5, "enabled": false, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `num_trunk_recycles`

Chai主干网络回收次数。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(num_trunk_recycles=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `num_trunk_samples`

独立主干网络采样数，总输出还取决于扩散样本数。

类型：`integer`；单位：计数；来源记录默认：`1`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(num_trunk_samples=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `output_dir`

输出目录；BDA通常以作业隔离的BDA_OUTPUT_DIR接管，不能假定界面值决定实际路径。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(output_dir=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `output_folder`

BDA输出目录草稿；Chai command使用BDA_OUTPUT_DIR，不读取这个字段。

类型：`string`；单位：无量纲/不适用；来源记录默认：`outputs/chai1`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；Chai-1@0.6.1: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["output_folder"]`。

约束与版本差异：{"bda_variants": [{"default": "outputs/chai1", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `recycle_msa_subsample`

回收循环中的MSA子采样量；源码仅在大于0时启用，0禁用该子采样。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`0`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(recycle_msa_subsample=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `restraints_json`

BDA约束文件别名映射Chai --constraint-path；此commit的接触约束是CSV表，名称含JSON不代表接受任意JSON。

类型：`artifact_ref`；单位：无量纲/不适用；来源记录默认：``。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；Chai-1@0.6.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["restraints_json"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [upstream-2](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/examples/restraints/README.md)

### `seed`

推理随机种子；同时记录模型/软件/输入版本，种子不能保证跨硬件完全重现。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(seed=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `template_cif_folder`

BDA旧Chai字段声称自定义模板目录，但command没有使用；不能视作template_hits_path已接通。

类型：`string`；单位：无量纲/不适用；来源记录默认：``。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；Chai-1@0.6.1: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["template_cif_folder"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `template_hits_path`

Chai模板命中数据文件；模板残基映射必须与查询序列一致。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(template_hits_path=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)

### `use_esm_embeddings`

Chai是否使用ESM蛋白语言模型embedding；可无MSA预测不代表无需检查序列与模型限制。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(use_esm_embeddings=...)；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `use_msa_server`

是否使用远端MMseqs/ColabFold服务生成MSA；false本身不等于已经准备好空MSA或本地MSA。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(use_msa_server=...)；Chai-1@0.6.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["use_msa_server"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `use_templates_server`

是否通过Chai模板服务生成模板命中；与本地template_hits_path区分。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：single_sequence, complex, msa_server, local_msa, restraints, templates

生成映射：`Python run_inference(use_templates_server=...)；Chai-1@0.6.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["use_templates_server"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Chai-1", "version": "0.6.1"}], "library_help": "", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `0.6.1`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| input_fasta | artifact_ref |  | {} |
| output_folder | string | outputs/chai1 | {} |
| num_samples | integer | 5 | {} |
| use_msa_server | boolean | true | {} |
| use_templates_server | boolean | true | {} |
| msa_server_url | string |  | {} |
| template_cif_folder | string |  | {} |
| restraints_json | artifact_ref |  | {} |
| downloads_dir | string |  | {} |

**input_ports**

```json
[
  {
    "name": "input_fasta",
    "kind": "protein_sequence",
    "accepts": [],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Input FASTA. FASTA containing proteins, nucleotides, ligands/SMILES, and modified residues. (from field 'input_fasta')"
  },
  {
    "name": "restraints_json",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": false,
    "multiple": false,
    "description": "Restraints JSON. Optional contact/covalent-bond restraints. (from field 'restraints_json')"
  }
]
```

**output_ports**

```json
[
  {
    "name": "predicted_complex",
    "kind": "protein_structure",
    "artifact_type": "complex_structure",
    "filename_glob": "*",
    "description": "Predicted structures."
  },
  {
    "name": "confidence_json",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Confidence outputs."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "predicted_complex",
      "artifact_types": [
        "complex_structure",
        "predicted_structure"
      ],
      "required": true,
      "many": true,
      "help": "Predicted structures."
    },
    {
      "name": "confidence_json",
      "artifact_types": [
        "score_table"
      ],
      "required": true,
      "many": false,
      "help": "Confidence outputs."
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
  "cpus_evidence": "`chai-lab fold` exposes no thread or worker option in the upstream parameter list (qm-scripts/library/catalog.json), and the command passes none."
}
```

命令摘要 SHA-256：`0bc182dc4ff70856a6d853af3eaa740dc78b922653ab630b807a7cac04c5c58f`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--constraint-path", "--msa-server-url", "--num-diffn-samples"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_OUTPUT_DIR", "input_fasta", "msa_server_url", "num_samples", "restraints_json", "use_msa_server", "use_templates_server"]`。

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
| predicted_structure / complex | 预测原子坐标及链/残基映射 | Å | 坐标是假说；保留精确输入实体、模型与seed；不能推断实验结合。 | [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pLDDT | 局部结构置信度 | Python返回0–1；mmCIF B-factor写入时×100 | 逐文件核对尺度，不是概率或亲和力。 | [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pTM / ipTM | 整体折叠/多链相对构象置信度 | 0–1 | 单体没有真实跨链接口ipTM；不要将零占位或对角线当结合分数。 | [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| PAE | 对齐后的相对位置预测误差矩阵 | Å | run_inference返回对象中含PAE/PDE/pLDDT张量；默认scores.npz不等于保存了完整PAE，需显式持久化。 | [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pred.model_idx_<i>.cif / scores.model_idx_<i>.npz | 每样本结构和ranking字段 | 混合字段 | NPZ不是JSON；当前BDA confidence_json端口名称不能替代实际格式检查。 | [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- BDA条目disabled且旧runbook记录环境不可用，所有示例为配置规划。
- input_fasta在command中直接变量使用，需验证artifact staging resolver；output_folder被忽略。
- template_cif_folder/downloads_dir未消费；Chai本地MSA与template_hits_path未暴露。
- restraints_json名称与上游约束文件格式可能不符；需检查格式，不可传任意JSON。
- BDA boolean已正确导出1/空字符串；实际安装API/CLI版本与library固定commit未验证。
- Chai返回PAE/PDE张量但默认保存scores.npz；BDA端口名confidence_json与真实NPZ格式不一致，需明确持久化与解析。

## 易错点

- pLDDT/ipTM/RMSD不等于ΔG/ΔΔG/Kd或生物活性。
- template、initial_guess、空MSA和真实MSA是不同证据条件；不能混成独立交叉验证。
- 未消费的UI参数不可写入报告为已执行条件；本地catalog默认、BDA默认、命令回退和安装默认要区分。
- BDA条目disabled且旧runbook记录环境不可用，所有示例为配置规划。
- input_fasta在command中直接变量使用，需验证artifact staging resolver；output_folder被忽略。
- template_cif_folder/downloads_dir未消费；Chai本地MSA与template_hits_path未暴露。
- restraints_json名称与上游约束文件格式可能不符；需检查格式，不可传任意JSON。
- BDA boolean已正确导出1/空字符串；实际安装API/CLI版本与library固定commit未验证。

## 来源与版本

- [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：2026-09-15 BDA声明、command、schema、ports快照；声明不是运行成功证明；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/chai1/README.md)：2026-08-30历史QM运行手册；与当前声明不同处需单列；commit `None`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交library的chai1参数提取，默认值不是BDA默认值；commit `c544fb183e865c4950909444db860a9d50604f66`；读取 2026-09-15。
- [parameter-env](../../../backend_v2/app/compute/scripts.py)：parameter_environment将boolean true/false导出为1/空字符串；字符串不按boolean解释；commit `None`；读取 2026-09-15。
- [upstream-0](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/chai_lab/chai1.py)：chai_lab/chai1.py；上游源码快照，不证明QM安装代码完全相同；commit `c544fb183e865c4950909444db860a9d50604f66`；读取 2026-09-15。
- [upstream-1](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/README.md)：README.md；上游源码快照，不证明QM安装代码完全相同；commit `c544fb183e865c4950909444db860a9d50604f66`；读取 2026-09-15。
- [upstream-2](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/examples/restraints/README.md)：examples/restraints/README.md；上游源码快照，不证明QM安装代码完全相同；commit `c544fb183e865c4950909444db860a9d50604f66`；读取 2026-09-15。
- [upstream-3](https://github.com/chaidiscovery/chai-lab/blob/c544fb183e865c4950909444db860a9d50604f66/pyproject.toml)：pyproject.toml；上游源码快照，不证明QM安装代码完全相同；commit `c544fb183e865c4950909444db860a9d50604f66`；读取 2026-09-15。
