# AlphaFold 3 — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

以结构化JSON预测多分子体系；支持独立数据准备、MSA/模板及推理阶段，但BDA当前命令没有连接全部界面开关。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/alphafold3.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 3.0 | true | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### AF3单蛋白 (`monomer`)

输入JSON含单个protein实体。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "num_diffusion_samples": 1
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### AF3复合物 (`complex`)

JSON定义蛋白/核酸/配体及成键关系。BDA 接入：`declared`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "num_diffusion_samples": 1
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### 仅数据准备 (`data_pipeline`)

生成MSA和模板。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "run_data_pipeline": true,
  "run_inference": false
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：官方能力存在，但当前BDA command未传这两个开关

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### 预处理输入推理 (`inference_prepared`)

复用完整_data.json。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "run_data_pipeline": false,
  "run_inference": true
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：当前BDA command未传此阶段选择

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### 显式空MSA对照 (`empty_msa`)

JSON protein unpairedMsa/pairedMsa均为空字符串，templates为空列表。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：必须在输入JSON声明；缺省/null与空字符串含义不同；无同源MSA输入不意味着特征中不存在query行

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### 给定模板对照 (`templates`)

输入protein.templates提供mmCIF和query/template indices。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：templates是模板特征，不等同AF2 initial_guess或固定坐标约束

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

## 使用方法

1. 先按模型与版本确认输入实体、链ID、序列SHA、MSA/模板来源；区分预测、设计与亲和力。
2. 从当前BDA快照核对enabled、command和ports；文档中的configuration_only/not_exposed不是可执行能力承诺。
3. 填写对应模式配置，检查参数最终进入命令或结构化输入；数据库/权重需已存在且记录版本。
4. 预览任务脚本和实际输入文件，核对CPU/GPU、布尔false、输出目录及样本总数；本次审计不提交任务。
5. 完成后逐输入/seed/model核对文件、原始指标和失败样本；声明、成功退出、解析成功及科学结论分开记录。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `buckets`

递增的token编译桶大小列表；决定JAX编译复用及内存，不是序列长度筛选分数。

类型：`list`；单位：无量纲/不适用；来源记录默认：`["256", "512", "768", "1024", "1280", "1536", "2048", "2560", "3072", "3584", "4096", "4608", "5120"]`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --buckets；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Strictly increasing order of token sizes for which to cache compilations. For any input with more tokens than the largest bucket size, a new bucket is created for exactly that number of tokens.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `compress_large_output_files`

以zstandard压缩大mmCIF及confidence JSON；收集器需识别相应后缀。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --compress_large_output_files；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "If True, compresses the output mmCIF and confidences JSON files (the two largest files) using zstandard. Note that embeddings and distogram, if saved, are already stored in a compressed format.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `conformer_max_iterations`

覆盖RDKit小分子初始构象搜索的最大迭代次数。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --conformer_max_iterations；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Optional override for maximum number of iterations to run for RDKit conformer search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `db_dir`

AF3数据库查找目录列表；可多个目录按序搜索，${DB_DIR}由工具解析，不是用户HOME。

类型：`list`；单位：路径；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --db_dir；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["db_dir"]`。

约束与版本差异：{"bda_variants": [{"default": "/root/public_databases", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Path to the directory containing the databases. Can be specified multiple times to search multiple directories in order.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `fix_standalone_glycans`

改变未成键糖配体离去原子的处理；启用会偏离AF3原训练/评估处理方式。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --fix_standalone_glycans；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "AlphaFold 3 model training and evaluation filtered out leaving atoms from glycan ligands even if they were not bonded to anything (\"standalone\" glycans). Setting this flag to True fixes this undesirable behavior, but moves away from the regime where AlphaFold 3 was trained and evaluated.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `flash_attention_implementation`

注意力实现triton/cudnn/xla；固定源码默认triton，triton/cudnn要求Ampere或更新GPU，xla为兼容路径；catalog漏取了此默认值。

类型：`string`；单位：无量纲/不适用；来源记录默认：`triton`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --flash_attention_implementation；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "default_source": "固定上游run_alphafold.py，纠正catalog提取漏值", "library_extracted_default": null, "library_help": "", "library_required": false, "upstream_enum": ["triton", "cudnn", "xla"]}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `force_output_dir`

允许使用已存在非空输出目录；适用于分开的预处理/推理复用，需防混入旧结果。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --force_output_dir；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to force the output directory to be used even if it already exists and is non-empty. Useful to set this to True to run the data pipeline and the inference separately, but use the same output directory.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `gpu_device`

可见GPU中的零起始设备编号；CUDA_VISIBLE_DEVICES已过滤时按过滤后的索引解释。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`0`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --gpu_device；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Optional override for the GPU device to use for inference, uses zero-based indexing. Defaults to the 0th GPU on the system. Useful on multi-GPU systems to pin each run to a specific GPU. Note that if GPUs are already pre-filtered by the environment (e.g. by using CUDA_VISIBLE_DEVICES), this flag refers to the GPU index after the filtering has been done.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `hmmalign_binary_path`

hmmalign搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --hmmalign_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Hmmalign binary.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `hmmbuild_binary_path`

hmmbuild搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --hmmbuild_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Hmmbuild binary.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `hmmsearch_binary_path`

hmmsearch搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --hmmsearch_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Hmmsearch binary.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `input_dir`

包含多个AF3输入JSON的目录，与单个json_path路径形式区分。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --input_dir；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the directory containing input JSON files.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `jackhmmer_binary_path`

jackhmmer搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --jackhmmer_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Jackhmmer binary.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `jackhmmer_max_parallel_shards`

分片数据库同时启动的Jackhmmer任务数；未指定可能每个分片一个进程，须纳入CPU总预算。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --jackhmmer_max_parallel_shards；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Maximum number of shards to search against in parallel. If unset, one Jackhmmer instance will be run per shard. Only applicable if the database is sharded.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `jackhmmer_n_cpu`

jackhmmer搜索线程数；未指定时上游可按min(cpu_count,8)选择，需与LSF分配协调。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --jackhmmer_n_cpu；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Number of CPUs to use for Jackhmmer. Defaults to min(cpu_count, 8). Going above 8 CPUs provides very little additional speedup.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `jax_compilation_cache_dir`

持久化JAX编译缓存目录；记录版本和硬件，缓存不代表预测结果。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --jax_compilation_cache_dir；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to a directory for the JAX compilation cache.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `json_path`

完整AF3输入JSON；其中分子实体、modelSeeds、MSA和模板定义才决定复合物内容。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --json_path；AlphaFold 3@3.0: 从同名staged port解析，不直接信任字段路径`；BDA 别名：`["json_path"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Path to the input JSON file.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `max_template_date`

模板发布日期上限，格式YYYY-MM-DD；用于限制结构信息泄漏。AF3还会据此限制CCD参考构象回退。

类型：`string`；单位：无量纲/不适用；来源记录默认：`2021-09-30`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --max_template_date；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Maximum template release date to consider. Format: YYYY-MM-DD. All templates released after this date will be ignored. Controls also whether to allow use of model coordinates for a chemical component from the CCD if RDKit conformer generation fails and the component does not have ideal coordinates set. Only for components that have been released before this date the model coordinates can be used as a fallback.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `mgnify_database_path`

mgnify数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/mgy_clusters_2022_05.fa`。

适用模式：data_pipeline

生成映射：`官方CLI --mgnify_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Mgnify database path, used for protein MSA search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `mgnify_z_value`

mgnify数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`integer`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --mgnify_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in number of sequences for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `model_dir`

AF3模型权重目录；固定上游commit不证明本地checkpoint相同。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --model_dir；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["model_dir"]`。

约束与版本差异：{"bda_variants": [{"default": "/root/models", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Path to the model to use for inference.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `model_seeds`

官方AF3字段是输入JSON modelSeeds。BDA序列adapter会读取list[int]，但当前UI声明string，逗号字符串会回退[1]；显式JSON优先且不被此参数覆盖。

类型：`string`；单位：无量纲/不适用；来源记录默认：`1`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`sequences adapter: list[int]→fold_input.json.modelSeeds；UI string类型不兼容会回退[1]；显式JSON不改写`；BDA 别名：`["model_seeds"]`。

约束与版本差异：{"bda_variants": [{"default": "1", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [af3-adapter](../../../backend_v2/app/compute/input_adapters/af3_fold_input.py)

### `nhmmer_binary_path`

nhmmer搜索/比对程序的可执行文件路径；须检查版本与执行权限。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --nhmmer_binary_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Path to the Nhmmer binary.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `nhmmer_max_parallel_shards`

分片RNA数据库同时运行的Nhmmer任务数，控制搜索并发资源。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --nhmmer_max_parallel_shards；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Maximum number of shards to search against in parallel. If unset, one Nhmmer instance will be run per shard. Only applicable if the database is sharded.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `nhmmer_n_cpu`

nhmmer搜索线程数；未指定时上游可按min(cpu_count,8)选择，需与LSF分配协调。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --nhmmer_n_cpu；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Number of CPUs to use for Nhmmer. Defaults to min(cpu_count, 8). Going above 8 CPUs provides very little additional speedup.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `non_commercial_ack`

BDA记录的权重许可确认字段，不是官方模型CLI参数；不能据此推断任意商业用途已获许可。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`BDA包装字段；不是同名官方CLI参数；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["non_commercial_ack"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": false, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "", "library_required": false}

依据：[registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `ntrna_database_path`

ntrna数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/nt_rna_2023_02_23_clust_seq_id_90_cov_80_rep_seq.fasta`。

适用模式：data_pipeline

生成映射：`官方CLI --ntrna_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "NT-RNA database path, used for RNA MSA search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `ntrna_z_value`

ntrna数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`number`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --ntrna_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in megabases for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `num_diffusion_samples`

每个随机种子的扩散结构样本数；每个seed/sample需有独立输出与置信度。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --num_diffusion_samples；AlphaFold 3@3.0: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_diffusion_samples"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Number of diffusion samples to generate.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `num_recycles`

结构推理循环次数；不是MD时间步，也不是MSA深度。

类型：`integer`；单位：计数；来源记录默认：`10`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --num_recycles；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["num_recycles"]`。

约束与版本差异：{"bda_variants": [{"default": 10, "enabled": true, "enum": null, "maximum": 48, "minimum": 1, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Number of recycles to use during inference.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `num_seeds`

由输入JSON单个种子展开连续种子数；启用时输入必须只有一个modelSeeds起始值。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --num_seeds；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Number of seeds to use for inference. If set, only a single seed must be provided in the input JSON. AlphaFold 3 will then generate random seeds in sequence, starting from the single seed specified in the input JSON. The full input JSON produced by AlphaFold 3 will include the generated random seeds. If not set, AlphaFold 3 will use the seeds as provided in the input JSON.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `output_dir`

输出目录；BDA通常以作业隔离的BDA_OUTPUT_DIR接管，不能假定界面值决定实际路径。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --output_dir；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["output_dir"]`。

约束与版本差异：{"bda_variants": [{"default": "outputs/alphafold3", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Path to a directory where the results will be saved.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `pdb_database_path`

pdb数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/mmcif_files`。

适用模式：data_pipeline

生成映射：`官方CLI --pdb_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "PDB database directory with mmCIF files path, used for template search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `resolve_msa_overlaps`

处理AF3 paired/unpaired MSA之间的重叠行；会影响有效特征，不能只比较原始行数。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --resolve_msa_overlaps；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to deduplicate unpaired MSA against paired MSA. The default behaviour matches the method described in the AlphaFold 3 paper. Set this to false if providing custom paired MSA using the unpaired MSA field to keep it exactly as is as deduplication against the paired MSA could break the manually crafted pairing between MSA sequences.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `rfam_database_path`

rfam数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/rfam_14_9_clust_seq_id_90_cov_80_rep_seq.fasta`。

适用模式：data_pipeline

生成映射：`官方CLI --rfam_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Rfam database path, used for RNA MSA search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `rfam_z_value`

rfam数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`number`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --rfam_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in megabases for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `rna_central_database_path`

rna_central数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/rnacentral_active_seq_id_90_cov_80_linclust.fasta`。

适用模式：data_pipeline

生成映射：`官方CLI --rna_central_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "RNAcentral database path, used for RNA MSA search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `rna_central_z_value`

rna_central数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`number`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --rna_central_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in megabases for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `run_data_pipeline`

是否运行遗传MSA/模板搜索；false时必须提供足够完整的预处理输入，不能当成自动填充MSA。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --run_data_pipeline；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["run_data_pipeline"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Whether to run the data pipeline on the fold inputs.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `run_inference`

是否运行结构推理；false可做CPU预处理，但当前BDA命令是否传递此开关须另核。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：monomer, complex, data_pipeline, inference_prepared, empty_msa, templates

生成映射：`官方CLI --run_inference；AlphaFold 3@3.0: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["run_inference"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "AlphaFold 3", "version": "3.0"}], "library_help": "Whether to run inference on the fold inputs.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `save_distogram`

保存模型距离分布输出；不是坐标距离实测值。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --save_distogram；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to save the final distogram in the output. Note that the distogram is a large float16 array: num_tokens * num_tokens * 64.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `save_embeddings`

保存模型embedding特征，供后处理；不是亲和力测量。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：monomer, complex, inference_prepared, empty_msa, templates

生成映射：`官方CLI --save_embeddings；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to save the final trunk single and pair embeddings in the output. Note that the embeddings are large float16 arrays: num_tokens * 384 + num_tokens * num_tokens * 128.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `seqres_database_path`

seqres数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/pdb_seqres_2022_09_28.fasta`。

适用模式：data_pipeline

生成映射：`官方CLI --seqres_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "PDB sequence database path, used for template search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `small_bfd_database_path`

small_bfd数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/bfd-first_non_consensus_sequences.fasta`。

适用模式：data_pipeline

生成映射：`官方CLI --small_bfd_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Small BFD database path, used for protein MSA search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `small_bfd_z_value`

small_bfd数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`integer`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --small_bfd_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in number of sequences for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `uniprot_cluster_annot_database_path`

uniprot_cluster_annot数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/uniprot_all_2021_04.fa`。

适用模式：data_pipeline

生成映射：`官方CLI --uniprot_cluster_annot_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "UniProt database path, used for protein paired MSA search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `uniprot_cluster_annot_z_value`

uniprot_cluster_annot数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`integer`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --uniprot_cluster_annot_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in number of sequences for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `uniref90_database_path`

uniref90数据库文件/索引路径；核对对应版本、发布日期及工具要求，不能用目录名替代特定文件。

类型：`string`；单位：路径；来源记录默认：`${DB_DIR}/uniref90_2022_05.fa`。

适用模式：data_pipeline

生成映射：`官方CLI --uniref90_database_path；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "UniRef90 database path, used for MSA search. The MSA obtained by searching it is used to construct the profile for template search.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

### `uniref90_z_value`

uniref90数据库规模，用于分片搜索E-value计算；蛋白数据库按序列数，RNA数据库按百万碱基，不能填成分片数。

类型：`integer`；单位：序列数（蛋白）/百万碱基（RNA）；来源记录默认：`null`。

适用模式：data_pipeline

生成映射：`官方CLI --uniref90_z_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The Z-value representing the database size in number of sequences for E-value calculation. Must be set for sharded databases.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `3.0`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| json_path | artifact_ref |  | {} |
| model_dir | string | /root/models | {} |
| output_dir | string | outputs/alphafold3 | {} |
| db_dir | string | /root/public_databases | {} |
| run_data_pipeline | boolean | true | {} |
| run_inference | boolean | true | {} |
| model_seeds | string | 1 | {} |
| num_recycles | integer | 10 | {} |
| non_commercial_ack | boolean | false | {} |
| num_diffusion_samples | integer | 1 | {} |

**input_ports**

```json
[
  {
    "name": "json_path",
    "kind": "params",
    "accepts": [],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Input JSON. Path to AlphaFold 3 fold_input.json. (from field 'json_path')",
    "exclusive_group": "af3_input_source"
  },
  {
    "name": "sequences",
    "kind": "protein_sequence",
    "accepts": [
      "sequence_set",
      "sequence"
    ],
    "content_types": [],
    "required": false,
    "multiple": true,
    "description": "Sequences to fold. Converted into fold_input.json by the af3_fold_input adapter, so this can be wired from an upstream design node.",
    "exclusive_group": "af3_input_source"
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
    "filename_glob": "*_model.cif*",
    "description": "Predicted complex, mmCIF (sometimes gzipped)."
  },
  {
    "name": "confidence_json",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*summary_confidences.json",
    "description": "Per-prediction ipTM/pTM and chain-pair confidences."
  },
  {
    "name": "run_manifest",
    "kind": "params",
    "artifact_type": "manifest",
    "filename_glob": "*_data.json",
    "description": "The resolved fold input AF3 echoes back for the run."
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
      "help": "All-atom predicted structures."
    },
    {
      "name": "confidence_json",
      "artifact_types": [
        "score_table"
      ],
      "required": true,
      "many": false,
      "help": "Ranking/confidence outputs."
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
  "cpus": 8,
  "walltime_minutes": 1440,
  "cpus_evidence": "Upstream exposes --jackhmmer_n_cpu and --nhmmer_n_cpu with a default of 8, and the hand-written control job 4186532 reserved -n 8 to match --jackhmmer_n_cpu. 16 matched nothing."
}
```

命令摘要 SHA-256：`9ebb28092d70ac31cd55ab4f8f6a9cf592d9f774cf919f4c2909dfc641239459`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--db_dir", "--json_path", "--model_dir", "--num_diffusion_samples", "--output_dir", "-maxdepth", "-type", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "json_path", "num_diffusion_samples"]`。

输入适配器：`af3_fold_input`；输出解析器：`null`。

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
| predicted_structure / complex | 预测原子坐标及链/残基映射 | Å | 坐标是假说；保留精确输入实体、模型与seed；不能推断实验结合。 | [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pLDDT | 局部结构置信度 | 通常0–100；Boltz/Protein-Hunter原始汇总常0–1 | 逐文件核对尺度，不是概率或亲和力。 | [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| pTM / ipTM | 整体折叠/多链相对构象置信度 | 0–1 | 单体没有真实跨链接口ipTM；不要将零占位或对角线当结合分数。 | [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| PAE | 对齐后的相对位置预测误差矩阵 | Å | 保留链映射、非对角块和聚合定义；不能单独证明结合位点。 | [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| *_data.json | 完整已解析输入，含MSA/模板与seed | 结构化JSON | 空字符串、null、缺省不同；保存原始/去重/非query行数，Neff需另算。 | [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |
| ranking_score | AF3内部模型排序综合分数 | 模型定义分数 | 含置信度、无序及碰撞项；不是能量。 | [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py), [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json) |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- run_data_pipeline/run_inference/num_recycles未出现在BDA command；model_seeds另有adapter但UI string与adapter list[int]不匹配，字符串会回退默认[1]。
- model_dir/db_dir/output_dir由命令硬编码，UI默认/root路径不是真实执行路径。
- AF3上游固定commit与QM v3.0.1安装未做源码一致性验证；部分library参数可能不在已装版本。
- MSA/templates的JSON字段未被平铺UI完整暴露；必须审阅真实输入JSON和_data.json。
- 模型权重许可限制需按实际获得条款处理；本次文档审计不构成许可授权。

## 易错点

- pLDDT/ipTM/RMSD不等于ΔG/ΔΔG/Kd或生物活性。
- template、initial_guess、空MSA和真实MSA是不同证据条件；不能混成独立交叉验证。
- 未消费的UI参数不可写入报告为已执行条件；本地catalog默认、BDA默认、命令回退和安装默认要区分。
- run_data_pipeline/run_inference/num_recycles未出现在BDA command；model_seeds另有adapter但UI string与adapter list[int]不匹配，字符串会回退默认[1]。
- model_dir/db_dir/output_dir由命令硬编码，UI默认/root路径不是真实执行路径。
- AF3上游固定commit与QM v3.0.1安装未做源码一致性验证；部分library参数可能不在已装版本。
- MSA/templates的JSON字段未被平铺UI完整暴露；必须审阅真实输入JSON和_data.json。
- 模型权重许可限制需按实际获得条款处理；本次文档审计不构成许可授权。

## 来源与版本

- [registry](../../../private/datasets/plugin-docs-audit-20260915/snapshots/live-registry.json)：2026-09-15 BDA声明、command、schema、ports快照；声明不是运行成功证明；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/alphafold3/README.md)：2026-08-30历史QM运行手册；与当前声明不同处需单列；commit `None`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交library的alphafold3参数提取，默认值不是BDA默认值；commit `b2f3d45fbfcacc5183bd5345d15df93571b8437f`；读取 2026-09-15。
- [parameter-env](../../../backend_v2/app/compute/scripts.py)：parameter_environment将boolean true/false导出为1/空字符串；字符串不按boolean解释；commit `None`；读取 2026-09-15。
- [af3-adapter](../../../backend_v2/app/compute/input_adapters/af3_fold_input.py)：FASTA转AF3 JSON；list[int]种子、显式JSON优先及蛋白实体限制；commit `None`；读取 2026-09-15。
- [upstream-0](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/run_alphafold.py)：run_alphafold.py；上游源码快照，不证明QM安装代码完全相同；commit `b2f3d45fbfcacc5183bd5345d15df93571b8437f`；读取 2026-09-15。
- [upstream-1](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/README.md)：README.md；上游源码快照，不证明QM安装代码完全相同；commit `b2f3d45fbfcacc5183bd5345d15df93571b8437f`；读取 2026-09-15。
- [upstream-2](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/docs/input.md)：docs/input.md；上游源码快照，不证明QM安装代码完全相同；commit `b2f3d45fbfcacc5183bd5345d15df93571b8437f`；读取 2026-09-15。
- [upstream-3](https://github.com/google-deepmind/alphafold3/blob/b2f3d45fbfcacc5183bd5345d15df93571b8437f/docs/output.md)：docs/output.md；上游源码快照，不证明QM安装代码完全相同；commit `b2f3d45fbfcacc5183bd5345d15df93571b8437f`；读取 2026-09-15。
