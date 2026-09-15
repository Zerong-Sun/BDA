# AlphaFold2 — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

区分官方AF2单体/多聚体与BDA initial-guess包装；两条同名插件的输入、权重和参数消费并不相同。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/alphafold2.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 2.3.0 | false | valid | unproven | false |
| 2.3.2 | true | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### 官方AF2单体 (`monomer`)

使用单链FASTA与单体权重。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "model_preset": "monomer"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### 单体pTM (`monomer_ptm`)

单体折叠并输出pTM。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "model_preset": "monomer_ptm"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### CASP14 ensemble (`monomer_casp14`)

使用额外ensemble配置。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "model_preset": "monomer_casp14"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### 官方AF2-Multimer (`multimer`)

多链同一目标联合预测。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "model_preset": "multimer",
  "num_multimer_predictions_per_model": 5
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### BDA predict.py初始坐标包装 (`initial_guess_wrapper`)

仅文档化现有2.3.2包装，不能视作官方AF2入口。BDA 接入：`unverified`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "initial_guess": true,
  "recycles": 3,
  "models": 1,
  "db_preset": "reduced_dbs"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：本快照包装命令及容器身份不同于官方入口，未取得实际predict.py源码；ensemble_predictions未出现在command

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

## 使用方法

1. 先按模型与版本确认输入实体、链ID、序列SHA、MSA/模板来源；区分预测、设计与亲和力。
2. 从当前BDA快照核对enabled、command和ports；文档中的configuration_only/not_exposed不是可执行能力承诺。
3. 填写对应模式配置，检查参数最终进入命令或结构化输入；数据库/权重需已存在且记录版本。
4. 预览任务脚本和实际输入文件，核对CPU/GPU、布尔false、输出目录及样本总数；本次审计不提交任务。
5. 完成后逐输入/seed/model核对文件、原始指标和失败样本；声明、成功退出、解析成功及科学结论分开记录。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `benchmark`

重复JAX评估以区分编译耗时与推理耗时；不会增加独立实验数。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --benchmark；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["benchmark"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Run multiple JAX model evaluations to obtain a timing that excludes the compilation time, which should be more indicative of the time required for inferencing many proteins.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `bfd_database_path`

bfd数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --bfd_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the BFD database for use by HHblits.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `data_dir`

AF2支持数据及模型参数根目录；必须与其余数据库路径配套。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --data_dir；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["data_dir"]`。

约束与版本差异：{"bda_variants": [{"default": "/data/alphafold", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Path to directory of supporting data.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `db_preset`

MSA数据库方案：full_dbs与reduced_dbs使用不同数据库集合，不是是否启用MSA的开关。

类型：`string`；单位：无量纲/不适用；来源记录默认：`full_dbs`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --db_preset；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志；AlphaFold2@2.3.2: command引用此变量；仍需验证运行日志`；BDA 别名：`["db_preset"]`。

约束与版本差异：{"bda_variants": [{"default": "reduced_dbs", "enabled": false, "enum": ["full_dbs", "reduced_dbs"], "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}, {"default": "reduced_dbs", "enabled": true, "enum": ["reduced_dbs", "full_dbs"], "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.2"}], "library_help": "Choose preset MSA database configuration - smaller genetic database config (reduced_dbs) or full genetic database config  (full_dbs)", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `ensemble_predictions`

BDA AF2 initial-guess包装声明的每输入种子数；command不消费此键，不能据UI值计算实际输出数。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`1`。

适用模式：initial_guess_wrapper

生成映射：`BDA包装字段；不是同名官方CLI参数；AlphaFold2@2.3.2: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["ensemble_predictions"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "AlphaFold2", "version": "2.3.2"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `fasta_paths`

按逗号分隔的FASTA文件路径；每个文件是一个预测目标，文件basename应唯一，多链目标需选择multimer模型。

类型：`list`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --fasta_paths；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["fasta_paths"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Paths to FASTA files, each containing a prediction target that will be folded one after another. If a FASTA file contains multiple sequences, then it will be folded as a multimer. Paths should be separated by commas. All FASTA paths must have a unique basename as the basename is used to name the output directories for each prediction.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `hhblits_binary_path`

hhblits搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --hhblits_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the HHblits executable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `hhsearch_binary_path`

hhsearch搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --hhsearch_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the HHsearch executable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `hhsearch_n_cpu`

hhsearch搜索线程数；未指定时上游可按min(cpu_count,8)选择，需与LSF分配协调。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --hhsearch_n_cpu；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["hhsearch_n_cpu"]`。

约束与版本差异：{"bda_variants": [{"default": 8, "enabled": false, "enum": null, "maximum": 256, "minimum": 1, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Number of CPUs to use for HHsearch. Defaults to min(cpu_count, 8). Going above 8 CPUs provides very little additional speedup.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `hmmbuild_binary_path`

hmmbuild搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --hmmbuild_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the hmmbuild executable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `hmmsearch_binary_path`

hmmsearch搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --hmmsearch_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the hmmsearch executable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `hmmsearch_n_cpu`

hmmsearch搜索线程数；未指定时上游可按min(cpu_count,8)选择，需与LSF分配协调。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --hmmsearch_n_cpu；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["hmmsearch_n_cpu"]`。

约束与版本差异：{"bda_variants": [{"default": 8, "enabled": false, "enum": null, "maximum": 256, "minimum": 1, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Number of CPUs to use for HMMsearch. Defaults to min(cpu_count, 8). Going above 8 CPUs provides very little additional speedup.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `initial_guess`

用输入结构坐标初始化AF2包装的预测；属于有坐标条件预测，不能当完全独立的从序列验证。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：initial_guess_wrapper

生成映射：`BDA包装字段；不是同名官方CLI参数；AlphaFold2@2.3.2: command引用此变量；仍需验证运行日志`；BDA 别名：`["initial_guess"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.2"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `jackhmmer_binary_path`

jackhmmer搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --jackhmmer_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the JackHMMER executable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `jackhmmer_n_cpu`

jackhmmer搜索线程数；未指定时上游可按min(cpu_count,8)选择，需与LSF分配协调。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --jackhmmer_n_cpu；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["jackhmmer_n_cpu"]`。

约束与版本差异：{"bda_variants": [{"default": 8, "enabled": false, "enum": null, "maximum": 256, "minimum": 1, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Number of CPUs to use for Jackhmmer. Defaults to min(cpu_count, 8). Going above 8 CPUs provides very little additional speedup.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `kalign_binary_path`

kalign搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --kalign_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Kalign executable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `max_template_date`

模板发布日期上限，格式YYYY-MM-DD；用于限制结构信息泄漏。AF3还会据此限制CCD参考构象回退。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --max_template_date；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["max_template_date"]`。

约束与版本差异：{"bda_variants": [{"default": "2026-01-01", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Maximum template release date to consider. Important if folding historical test sets.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `mgnify_database_path`

mgnify数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --mgnify_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the MGnify database for use by JackHMMER.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `model_preset`

AF2权重/推理配置：monomer、monomer_casp14、monomer_ptm或multimer；多条链不是自动等价于已选multimer模型。

类型：`string`；单位：无量纲/不适用；来源记录默认：`monomer`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --model_preset；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["model_preset"]`。

约束与版本差异：{"bda_variants": [{"default": "multimer", "enabled": false, "enum": ["monomer", "monomer_casp14", "monomer_ptm", "multimer"], "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Choose preset model configuration - the monomer model, the monomer model with extra ensembling, monomer model with pTM head, or multimer model", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `models`

选择模型权重；superfold接受all或1–5列表，另一个predict.py包装声明整数1–5，不能混用。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`1`。

适用模式：initial_guess_wrapper

生成映射：`BDA包装字段；不是同名官方CLI参数；AlphaFold2@2.3.2: command引用此变量；仍需验证运行日志`；BDA 别名：`["models"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": 5, "minimum": 1, "plugin_key": "AlphaFold2", "version": "2.3.2"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `models_to_relax`

AF2输出Amber几何优化范围all/best/none；relax不计算结合自由能，也不是长时间MD。

类型：`string`；单位：无量纲/不适用；来源记录默认：`BEST`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --models_to_relax；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["models_to_relax"]`。

约束与版本差异：{"bda_variants": [{"default": "best", "enabled": false, "enum": ["all", "best", "none"], "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "The models to run the final relaxation step on. If `all`, all models are relaxed, which may be time consuming. If `best`, only the most confident model is relaxed. If `none`, relaxation is not run. Turning off relaxation might result in predictions with distracting stereochemical violations but might help in case you are having issues with the relaxation stage.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `num_multimer_predictions_per_model`

每套multimer模型的随机种子采样次数，总数还需乘模型套数；单体模式不适用。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：multimer

生成映射：`官方CLI --num_multimer_predictions_per_model；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_multimer_predictions_per_model"]`。

约束与版本差异：{"bda_variants": [{"default": 5, "enabled": false, "enum": null, "maximum": 20, "minimum": 1, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "How many predictions (each with a different random seed) will be generated per model. E.g. if this is 2 and there are 5 models then there will be 10 predictions per input. Note: this FLAG only applies if model_preset=multimer", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `obsolete_pdbs_path`

失效PDB编号到替代编号的映射文件。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --obsolete_pdbs_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to file containing a mapping from obsolete PDB IDs to the PDB IDs of their replacements.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `output_dir`

输出目录；BDA通常以作业隔离的BDA_OUTPUT_DIR接管，不能假定界面值决定实际路径。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --output_dir；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["output_dir"]`。

约束与版本差异：{"bda_variants": [{"default": "outputs/alphafold", "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Path to a directory that will store the results.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `pdb70_database_path`

pdb70数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --pdb70_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the PDB70 database for use by HHsearch.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `pdb_seqres_database_path`

pdb_seqres数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --pdb_seqres_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Full filepath to the PDB seqres database file (not just the directory) for use by hmmsearch.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `random_seed`

随机种子。官方AF2未指定才自动生成；0是有效种子，不等于自动模式；GPU过程也未必完全确定。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --random_seed；AlphaFold2@2.3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["random_seed"]`。

约束与版本差异：{"bda_variants": [{"default": 0, "enabled": false, "enum": null, "maximum": null, "minimum": 0, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "The random seed for the data pipeline. By default, this is randomly generated. Note that even if this is set, Alphafold may still not be deterministic, because processes like GPU inference are nondeterministic.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `recycles`

BDA predict.py包装的循环数，映射-recycles；不是官方run_alphafold.py通用CLI。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：initial_guess_wrapper

生成映射：`BDA包装字段；不是同名官方CLI参数；AlphaFold2@2.3.2: command引用此变量；仍需验证运行日志`；BDA 别名：`["recycles"]`。

约束与版本差异：{"bda_variants": [{"default": 3, "enabled": true, "enum": null, "maximum": 20, "minimum": 0, "plugin_key": "AlphaFold2", "version": "2.3.2"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `small_bfd_database_path`

small_bfd数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --small_bfd_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the small version of BFD used with the \"reduced_dbs\" preset.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `template_mmcif_dir`

模板结构mmCIF目录，文件按PDB编号组织；不是initial_guess坐标输入。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --template_mmcif_dir；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to a directory with template mmCIF structures, each named <pdb_id>.cif", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `uniprot_database_path`

uniprot数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --uniprot_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Uniprot database for use by JackHMMer.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `uniref30_database_path`

uniref30数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --uniref30_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the UniRef30 database for use by HHblits.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `uniref90_database_path`

uniref90数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --uniref90_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Uniref90 database for use by JackHMMER.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)

### `use_gpu_relax`

是否在GPU执行AF2的Amber几何优化；需有可用GPU且核对布尔开关渲染。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --use_gpu_relax；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["use_gpu_relax"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Whether to relax on GPU. Relax on GPU can be much faster than CPU, so it is recommended to enable if possible. GPUs must be available if this setting is enabled.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `use_precomputed_msas`

读取输出目录已有MSA，跳过相应搜索；上游不会自动核对旧MSA与新序列/数据库配置的一致性。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, monomer_ptm, monomer_casp14, multimer, initial_guess_wrapper

生成映射：`官方CLI --use_precomputed_msas；AlphaFold2@2.3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["use_precomputed_msas"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": false, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold2", "version": "2.3.0"}], "library_help": "Whether to read MSAs that have been written to disk instead of running the MSA tools. The MSA files are looked up in the output directory, so it must stay the same between multiple runs that are to reuse the MSAs. WARNING: This will not check if the sequence, database or configuration have changed.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `2.3.0`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| fasta_paths | artifact_ref |  | {} |
| output_dir | string | outputs/alphafold | {} |
| data_dir | string | /data/alphafold | {} |
| model_preset | enum | multimer | {"options": ["monomer", "monomer_casp14", "monomer_ptm", "multimer"]} |
| db_preset | enum | reduced_dbs | {"options": ["full_dbs", "reduced_dbs"]} |
| max_template_date | string | 2026-01-01 | {} |
| num_multimer_predictions_per_model | integer | 5 | {} |
| models_to_relax | enum | best | {"options": ["all", "best", "none"]} |
| use_gpu_relax | boolean | true | {} |
| use_precomputed_msas | boolean | false | {} |
| benchmark | boolean | false | {} |
| random_seed | integer | 0 | {} |
| jackhmmer_n_cpu | integer | 8 | {} |
| hmmsearch_n_cpu | integer | 8 | {} |
| hhsearch_n_cpu | integer | 8 | {} |

**input_ports**

```json
[
  {
    "name": "fasta_paths",
    "kind": "protein_sequence",
    "accepts": [],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "FASTA paths. Comma-separated FASTA files; multisequence FASTA is folded as multimer. (from field 'fasta_paths')"
  }
]
```

**output_ports**

```json
[
  {
    "name": "predicted_structure",
    "kind": "protein_structure",
    "artifact_type": "predicted_structure",
    "filename_glob": "*",
    "description": "Predicted model structures."
  },
  {
    "name": "complex_structure",
    "kind": "protein_structure",
    "artifact_type": "complex_structure",
    "filename_glob": "*",
    "description": "Predicted complexes."
  },
  {
    "name": "score_table",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Confidence metrics."
  },
  {
    "name": "pae_matrix",
    "kind": "tabular",
    "artifact_type": "pae_matrix",
    "filename_glob": "*",
    "description": "PAE matrix artifact."
  }
]
```

**output_schema**

```json
{
  "ports": [
    {
      "name": "predicted_structure",
      "artifact_types": [
        "predicted_structure"
      ],
      "required": true,
      "many": true,
      "help": "Predicted model structures."
    },
    {
      "name": "complex_structure",
      "artifact_types": [
        "complex_structure"
      ],
      "required": false,
      "many": true,
      "help": "Predicted complexes."
    },
    {
      "name": "score_table",
      "artifact_types": [
        "score_table"
      ],
      "required": true,
      "many": false,
      "help": "Confidence metrics."
    },
    {
      "name": "pae_matrix",
      "artifact_types": [
        "pae_matrix"
      ],
      "required": false,
      "many": false,
      "help": "PAE matrix artifact."
    }
  ]
}
```

**resources**

```json
{
  "gpu": true,
  "gpu_count": 1,
  "cpus": 8,
  "walltime_minutes": 1440,
  "cpus_evidence": "Upstream exposes jackhmmer_n_cpu / hhsearch_n_cpu / hmmsearch_n_cpu, default 8; the MSA stage starts that many."
}
```

命令摘要 SHA-256：`c00ea8a0fa2cf3971be8baff2b1604b7c29cfaee0030767d57a8b8c9856cbd2d`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--data_dir", "--db_preset", "--fasta_paths", "--max_template_date", "--mgnify_database_path", "--model_preset", "--models_to_relax", "--num_multimer_predictions_per_model", "--obsolete_pdbs_path", "--output_dir", "--template_mmcif_dir", "--uniref90_database_path", "-name"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "af2_fasta", "db_preset", "max_template_date", "model_preset", "models_to_relax", "num_multimer_predictions_per_model", "use_gpu_relax", "use_precomputed_msas"]`。

输入适配器：`null`；输出解析器：`null`。

### 版本 `2.3.2`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| initial_guess | boolean | true | {} |
| recycles | integer | 3 | {"maximum": 20, "minimum": 0, "required": true} |
| models | integer | 1 | {"maximum": 5, "minimum": 1, "required": true} |
| db_preset | string | reduced_dbs | {"enum": ["reduced_dbs", "full_dbs"], "required": true} |
| ensemble_predictions | integer | 1 | {"maximum": 100, "minimum": 1} |

**input_ports**

```json
[
  {
    "name": "complex_input",
    "kind": "protein_structure",
    "accepts": [
      "backbone_set",
      "target_structure",
      "sequence_set",
      "prepared_structure"
    ],
    "content_types": [
      "chemical/x-pdb",
      "chemical/x-mmcif"
    ],
    "required": true,
    "multiple": true,
    "description": "Designed complexes to score, or a target to predict."
  }
]
```

**output_ports**

```json
[
  {
    "name": "predictions",
    "kind": "protein_structure",
    "artifact_type": "predicted_structure",
    "filename_glob": "*.pdb",
    "description": "Predicted complexes."
  },
  {
    "name": "scores",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*.sc",
    "description": "Per-design pae_interaction, binder pLDDT, and RMSD to the design model."
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
  "cpus": 8,
  "memory_gb": 64,
  "walltime_minutes": 1440,
  "cpus_evidence": "Upstream exposes jackhmmer_n_cpu / hhsearch_n_cpu / hmmsearch_n_cpu, default 8; the MSA stage starts that many."
}
```

命令摘要 SHA-256：`0a56e9e979f0abd2ef44e92640e478455dc68ebb62d2559ce7a498f8ed6abb19`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["-db_preset", "-indir", "-models", "-outdir", "-recycles"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "db_preset", "initial_guess", "models", "recycles"]`。

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
| predicted_structure / complex | 预测原子坐标及链/残基映射 | Å | 坐标是假说；保留精确输入实体、模型与seed；不能推断实验结合。 | [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pLDDT | 局部结构置信度 | 通常0–100；Boltz/Protein-Hunter原始汇总常0–1 | 逐文件核对尺度，不是概率或亲和力。 | [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pTM / ipTM | 整体折叠/多链相对构象置信度 | 0–1 | 单体没有真实跨链接口ipTM；不要将零占位或对角线当结合分数。 | [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| PAE | 对齐后的相对位置预测误差矩阵 | Å | 保留链映射、非对角块和聚合定义；不能单独证明结合位点。 | [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- 官方2.3.0条目disabled；2.3.2是另一个predict.py包装，不是官方run_alphafold.py运行证明。
- 2.3.0 command从sequences目录找FASTA，但声明端口是fasta_paths，需查adapter或修复staging映射。
- benchmark/random_seed/搜索CPU字段未被2.3.0 command消费；data_dir/output_dir硬编码。
- 2.3.2 ensemble_predictions未消费；正常BDA boolean正确序列化为1/空字符串，手工脚本不得将false写成非空字符串。
- 官方AF2无initial_guess CLI；本地包装的代码commit/安装可用性未取得一致性证明。

## 易错点

- pLDDT/ipTM/RMSD不等于ΔG/ΔΔG/Kd或生物活性。
- template、initial_guess、空MSA和真实MSA是不同证据条件；不能混成独立交叉验证。
- 未消费的UI参数不可写入报告为已执行条件；本地catalog默认、BDA默认、命令回退和安装默认要区分。
- 官方2.3.0条目disabled；2.3.2是另一个predict.py包装，不是官方run_alphafold.py运行证明。
- 2.3.0 command从sequences目录找FASTA，但声明端口是fasta_paths，需查adapter或修复staging映射。
- benchmark/random_seed/搜索CPU字段未被2.3.0 command消费；data_dir/output_dir硬编码。
- 2.3.2 ensemble_predictions未消费；正常BDA boolean正确序列化为1/空字符串，手工脚本不得将false写成非空字符串。
- 官方AF2无initial_guess CLI；本地包装的代码commit/安装可用性未取得一致性证明。

## 来源与版本

- [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：2026-09-15 BDA声明、command、schema、ports快照；声明不是运行成功证明；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/alphafold2/README.md)：2026-08-30历史QM运行手册；与当前声明不同处需单列；commit `None`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交library的alphafold2参数提取，默认值不是BDA默认值；commit `c77e5d2a8961d1a353632c462914ff0a32a950f6`；读取 2026-09-15。
- [parameter-env](../../../backend_v2/app/compute/scripts.py)：parameter_environment将boolean true/false导出为1/空字符串；字符串不按boolean解释；commit `None`；读取 2026-09-15。
- [upstream-0](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/run_alphafold.py)：run_alphafold.py；上游源码快照，不证明QM安装代码完全相同；commit `c77e5d2a8961d1a353632c462914ff0a32a950f6`；读取 2026-09-15。
- [upstream-1](https://github.com/google-deepmind/alphafold/blob/c77e5d2a8961d1a353632c462914ff0a32a950f6/README.md)：README.md；上游源码快照，不证明QM安装代码完全相同；commit `c77e5d2a8961d1a353632c462914ff0a32a950f6`；读取 2026-09-15。
