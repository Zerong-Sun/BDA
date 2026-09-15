# Boltz — 功能、参数与使用手册

> 文档快照：2026-09-15；由 build_reference_docs.py 生成。配置/文档覆盖不等于运行验证。

Boltz结构预测与Boltz-2单小分子亲和力头分开说明，同时审计base和YAML限定草稿；现有--affinity映射不符合固定官方CLI。

[统一规范](../../../docs/plugins/STANDARD.md) · [全部插件总览](../../../docs/plugins/INDEX.md) · [结构化解释源](../../../docs/plugins/profiles/boltz.json)

## 版本与实际状态

| 版本 | 启用 | 声明校验 | 登记运行状态 | 当前指纹匹配 |
|---|---|---|---|---|
| 2.x | true | valid | unproven | false |

`proven` 但当前指纹不匹配时，只保留为历史观察。以下模式接入状态来自源码审阅，最终使用前还需验证所选版本。

## 功能模式与配方

### Boltz-1结构预测 (`boltz1_structure`)

蛋白/复合物结构置信度预测。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "model": "boltz1"
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：当前BDA command未传--model，界面选择不保证切换

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### Boltz-2结构预测 (`boltz2_structure`)

蛋白及配体复合物结构预测。BDA 接入：`unverified`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "model": "boltz2",
  "num_samples": 5
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：当前predict_affinity默认true产生非官方--affinity，需修复或验证包装兼容性

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 显式单序列 (`single_sequence`)

在每个蛋白YAML字段中写msa: empty。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_msa_server": false
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 本地MSA (`local_msa`)

YAML指向a3m/带配对key的CSV。BDA 接入：`configuration_only`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_msa_server": false
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 远端MSA (`msa_server`)

由远端服务生成MSA。BDA 接入：`unverified`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "use_msa_server": true
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：结构置信度不是实验结合/活性证据

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### 小分子亲和力头 (`affinity`)

Boltz-2对单个小分子和蛋白目标预测affinity。BDA 接入：`unverified`。

输入：YAML properties: [{affinity: {binder: <ligand_chain_id>}}]; Boltz-2结构及亲和力权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：不支持蛋白-蛋白亲和力；RNA/DNA/cofactor目标预测不可靠；仅一个小分子，最多128个按RDKit RemoveHs后计数的原子；训练范围约56原子内更可靠；BDA predict_affinity→--affinity未匹配官方CLI

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### YAML限定草稿 (`guarded_yaml_draft`)

接受多个已审阅的复合物YAML。BDA 接入：`unverified`。

输入：经核对的分子输入文件及可用模型权重

配置示例片段（不是完整提交请求；按本模式限制判断是否为上游配置）：

```json
{
  "num_samples": 5
}
```

输出检查：逐输入/模型/种子核对输出数量、原始置信度和输入序列SHA；对比实际日志与请求参数，不用成功退出替代科学结果验证

限制：Boltz-authoring-6810138a只修正YAML目录staging；继承原affinity/参数消费缺口

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

## 使用方法

1. 先按模型与版本确认输入实体、链ID、序列SHA、MSA/模板来源；区分预测、设计与亲和力。
2. 从当前BDA快照核对enabled、command和ports；文档中的configuration_only/not_exposed不是可执行能力承诺。
3. 填写对应模式配置，检查参数最终进入命令或结构化输入；数据库/权重需已存在且记录版本。
4. 预览任务脚本和实际输入文件，核对CPU/GPU、布尔false、输出目录及样本总数；本次审计不提交任务。
5. 完成后逐输入/seed/model核对文件、原始指标和失败样本；声明、成功退出、解析成功及科学结论分开记录。

## 参数解释

下列默认值来自该 profile 记录的源，不代替后面的逐版本 BDA 默认表；constraints 中的 library/BDA 分层值优先用于区分来源。`未声明` 不等于 null、0 或推荐值。

### `accelerator`

结构预测执行设备类别，如gpu/cpu；应与调度资源和安装后端一致。

类型：`string`；单位：无量纲/不适用；来源记录默认：`gpu`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --accelerator；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The accelerator to use for prediction. Default is gpu.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `affinity_checkpoint`

Boltz-2独立亲和力模型权重路径，与结构置信度checkpoint分开。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：affinity

生成映射：`官方CLI --affinity_checkpoint；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "An optional checkpoint, will use the provided Boltz-1 model by default.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `affinity_mw_correction`

对亲和力值头启用分子量修正；比较时保持设置一致。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：affinity

生成映射：`官方CLI --affinity_mw_correction；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to add the Molecular Weight correction to the affinity value head.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `api_key_header`

MSA服务器API认证的请求头名称；与basic认证二选一。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --api_key_header；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Custom header key for API key authentication (default: X-API-Key).", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `api_key_value`

MSA服务器API凭据值，属于秘密，不应写入公开示例或结果报告。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --api_key_value；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Custom header value for API key authentication.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `cache`

Boltz缓存目录；catalog记录的get_cache_path是函数默认表达式，不是应创建的字面目录。

类型：`string`；单位：路径；来源记录默认：`get_cache_path`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --cache；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The directory where to download the data and model. Default is ~/.boltz, or $BOLTZ_CACHE if set.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `checkpoint`

结构/置信度模型checkpoint覆盖路径；必须记录hash和模型代次。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --checkpoint；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "An optional checkpoint, will use the provided Boltz-1 model by default.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `devices`

Lightning可使用的设备数量/配置，具体类型以安装版本CLI为准；不等于样本数。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`1`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --devices；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of devices to use for prediction. Default is 1.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `diffusion_samples`

Boltz每个输入生成的结构扩散样本数；BDA的num_samples是当前消费的别名，界面同名字段未被command使用。

类型：`integer`；单位：计数；来源记录默认：`1`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --diffusion_samples；Boltz@2.x: schema声明但command未引用（可能硬编码/未接通），不保证生效；Boltz-authoring-6810138a@2.x-draft.1: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["diffusion_samples"]`。

约束与版本差异：{"bda_variants": [{"default": 1, "enabled": true, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "Boltz", "version": "2.x"}, {"default": 1, "enabled": true, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "The number of diffusion samples to use for prediction. Default is 1.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `diffusion_samples_affinity`

亲和力阶段扩散采样数，与结构阶段diffusion_samples分开。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：affinity

生成映射：`官方CLI --diffusion_samples_affinity；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of diffusion samples to use for affinity prediction. Default is 5.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `input_path`

Boltz YAML/FASTA文件或目录；受体-配体的实体、链ID及MSA需在输入文件定义；guarded draft仅接受YAML。

类型：`string`；单位：路径；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`boltz predict <input_path> 位置参数；Boltz@2.x: 从同名staged port解析，不直接信任字段路径；Boltz-authoring-6810138a@2.x-draft.1: 从同名staged port解析，不直接信任字段路径`；BDA 别名：`["input_path"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz", "version": "2.x"}, {"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "YAML input file or directory.", "library_required": true}

依据：[library](../../../qm-scripts/library/catalog.json), registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `max_msa_seqs`

MSA最大序列数上限；这是截断限制，不是本次实际读取或去重后的深度。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`8192`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --max_msa_seqs；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The maximum number of MSA sequences to use for prediction. Default is 8192.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `max_parallel_samples`

同时处理扩散样本的最大数量，影响显存与速度。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --max_parallel_samples；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The maximum number of samples to predict in parallel. Default is None.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `method`

预测使用的方法条件标签；含义/允许值依固定版本，不能当成随意切换的物理能量方法。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --method；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The method to use for prediction. Default is None.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `model`

Boltz代次boltz1/boltz2；affinity能力仅Boltz-2路径，当前BDAcommand未显式传--model。

类型：`string`；单位：无量纲/不适用；来源记录默认：`boltz2`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --model；Boltz@2.x: schema声明但command未引用（可能硬编码/未接通），不保证生效；Boltz-authoring-6810138a@2.x-draft.1: schema声明但command未引用（可能硬编码/未接通），不保证生效`；BDA 别名：`["model"]`。

约束与版本差异：{"bda_variants": [{"default": "boltz2", "enabled": true, "enum": ["boltz2", "boltz1"], "maximum": null, "minimum": null, "plugin_key": "Boltz", "version": "2.x"}, {"default": "boltz2", "enabled": true, "enum": ["boltz2", "boltz1"], "maximum": null, "minimum": null, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "The model to use for prediction. Default is boltz2.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `msa_pairing_strategy`

多链MSA配对策略；按固定版本支持的选项选择并记录。

类型：`string`；单位：无量纲/不适用；来源记录默认：`greedy`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --msa_pairing_strategy；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Pairing strategy to use. Used only if --use_msa_server is set. Options are 'greedy' and 'complete'", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `msa_server_password`

MSA服务器basic认证密码，禁止写入共享报告或明文示例。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --msa_server_password；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "MSA server password for basic auth. Used only if --use_msa_server is set. Can also be set via BOLTZ_MSA_PASSWORD environment variable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `msa_server_url`

远端MSA服务地址；启用服务会向该服务发送目标序列，需明确数据流。

类型：`string`；单位：无量纲/不适用；来源记录默认：`https://api.colabfold.com`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --msa_server_url；Boltz@2.x: command引用此变量；仍需验证运行日志；Boltz-authoring-6810138a@2.x-draft.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["msa_server_url"]`。

约束与版本差异：{"bda_variants": [{"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz", "version": "2.x"}, {"default": "", "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "MSA server url. Used only if --use_msa_server is set. ", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `msa_server_username`

MSA服务器basic认证用户名；与API key认证不可同时使用。

类型：`string`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --msa_server_username；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "MSA server username for basic auth. Used only if --use_msa_server is set. Can also be set via BOLTZ_MSA_USERNAME environment variable.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `no_kernels`

禁用可选加速内核，供兼容性排查；可能改变性能。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --no_kernels；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to disable the kernels. Default False", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `num_samples`

BDA样本数别名；Boltz映射--diffusion_samples，Chai映射--num-diffn-samples。

类型：`integer`；单位：计数；来源记录默认：`5`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`BDA包装字段；不是同名官方CLI参数；Boltz@2.x: command引用此变量；仍需验证运行日志；Boltz-authoring-6810138a@2.x-draft.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["num_samples"]`。

约束与版本差异：{"bda_variants": [{"default": 5, "enabled": true, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "Boltz", "version": "2.x"}, {"default": 5, "enabled": true, "enum": null, "maximum": 100, "minimum": 1, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "", "library_required": false}

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `num_subsampled_msa`

启用MSA子采样时保留的行数，不能写成全部原始MSA深度。

类型：`integer`；单位：计数；来源记录默认：`1024`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --num_subsampled_msa；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of MSA sequences to subsample. Default is 1024.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `num_workers`

数据加载工作进程数；与设备数和预处理线程数分开。

类型：`integer`；单位：计数；来源记录默认：`2`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --num_workers；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of dataloader workers to use for prediction. Default is 2.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `out_dir`

结果根目录；当前BDA固定映射至BDA_OUTPUT_DIR。

类型：`string`；单位：路径；来源记录默认：`./`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --out_dir；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The path where to save the predictions.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `output_format`

结构输出格式mmcif或pdb；保留链/化学组分信息时优先核对mmCIF。

类型：`string`；单位：无量纲/不适用；来源记录默认：`mmcif`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --output_format；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The output format to use for the predictions. Default is mmcif.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `override`

覆盖已有处理/预测结果，防止参数变更后误复用旧输出；只在隔离作业目录使用。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --override；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to override existing found predictions. Default is False.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `predict_affinity`

BDA历史布尔字段映射--affinity；固定Boltz源码无此开关，正确请求来自YAML properties.affinity.binder，因此不能按此字段承诺得到亲和力。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`true`。

适用模式：affinity

生成映射：`BDA包装字段；不是同名官方CLI参数；Boltz@2.x: command引用此变量；仍需验证运行日志；Boltz-authoring-6810138a@2.x-draft.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["predict_affinity"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz", "version": "2.x"}, {"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "", "library_required": false}

依据：registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `preprocessing_threads`

输入预处理线程数，须与调度申请协调。

类型：`integer`；单位：计数；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --preprocessing_threads；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of threads to use for preprocessing. Default is 1.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `recycling_steps`

Boltz结构回收循环数；不是优化轮次num_cycles，也不是物理时间。

类型：`integer`；单位：计数；来源记录默认：`3`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --recycling_steps；Boltz@2.x: command引用此变量；仍需验证运行日志；Boltz-authoring-6810138a@2.x-draft.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["recycling_steps"]`。

约束与版本差异：{"bda_variants": [{"default": 3, "enabled": true, "enum": null, "maximum": 20, "minimum": 1, "plugin_key": "Boltz", "version": "2.x"}, {"default": 3, "enabled": true, "enum": null, "maximum": 20, "minimum": 1, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "The number of recycling steps to use for prediction. Default is 3.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `sampling_steps`

结构扩散去噪采样步数，不是分子动力学步数。

类型：`integer`；单位：计数；来源记录默认：`200`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --sampling_steps；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of sampling steps to use for prediction. Default is 200.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `sampling_steps_affinity`

亲和力阶段扩散采样步数，与结构阶段独立。

类型：`integer`；单位：计数；来源记录默认：`200`。

适用模式：affinity

生成映射：`官方CLI --sampling_steps_affinity；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The number of sampling steps to use for affinity prediction. Default is 200.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `seed`

推理随机种子；同时记录模型/软件/输入版本，种子不能保证跨硬件完全重现。

类型：`integer`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --seed；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "Seed to use for random number generator. Default is None (no seeding).", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `step_scale`

扩散采样步长缩放，影响探索范围；具体默认可能按模型代次动态设置。

类型：`number`；单位：无量纲/不适用；来源记录默认：`null`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --step_scale；`；BDA 别名：`[]`。

约束与版本差异：{"bda_variants": [], "library_help": "The step size is related to the temperature at which the diffusion process samples the distribution. The lower the higher the diversity among samples (recommended between 1 and 2). Default is 1.638 for Boltz-1 and 1.5 for Boltz-2. If not provided, the default step size will be used.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）

### `subsample_msa`

是否对子采样MSA；与是否提供MSA、最大MSA行数分开。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --subsample_msa；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to subsample the MSA. Default is True.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `use_msa_server`

是否使用远端MMseqs/ColabFold服务生成MSA；false本身不等于已经准备好空MSA或本地MSA。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --use_msa_server；Boltz@2.x: command引用此变量；仍需验证运行日志；Boltz-authoring-6810138a@2.x-draft.1: command引用此变量；仍需验证运行日志`；BDA 别名：`["use_msa_server"]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [{"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz", "version": "2.x"}, {"default": true, "enabled": true, "enum": null, "maximum": null, "minimum": null, "plugin_key": "Boltz-authoring-6810138a", "version": "2.x-draft.1"}], "library_help": "Whether to use the MMSeqs2 server for MSA generation. Default is False.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `use_potentials`

启用Boltz推理势/约束引导，需在输入中提供兼容信息；不是计算结合自由能。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --use_potentials；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to use potentials for steering. Default is False.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `write_embeddings`

导出Boltz中间表示供分析，不是亲和力。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --write_embeddings；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": " to dump the s and z embeddings into a npz file. Default is False.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `write_full_pae`

保存完整PAE矩阵，便于按链/界面分析预测相对位置误差。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --write_full_pae；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to dump the pae into a npz file. Default is True.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

### `write_full_pde`

保存完整预测距离误差PDE矩阵，与PAE定义不同。

类型：`boolean`；单位：无量纲/不适用；来源记录默认：`false`。

适用模式：boltz1_structure, boltz2_structure, single_sequence, local_msa, msa_server, affinity, guarded_yaml_draft

生成映射：`官方CLI --write_full_pde；`；BDA 别名：`[]`。

约束与版本差异：{"bda_environment": "true→1, false→空字符串；${flag:+--flag}与正常BDA布尔值兼容", "bda_variants": [], "library_help": "Whether to dump the pde into a npz file. Default is False.", "library_required": false}

依据：[library](../../../qm-scripts/library/catalog.json), upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, [parameter-env](../../../backend_v2/app/compute/scripts.py)

## 当前 BDA 输入默认与生成声明

每版表格是注册快照。是否实际传入请结合上面的 mapping/gaps；命令中未直接出现的键也可能经 adapter 消费，因此不通过简单字符串检索判定失效。

### 版本 `2.x`

| BDA key | 类型 | 表单默认 | 允许值/约束 |
|---|---|---|---|
| input_path | artifact_ref |  | {} |
| model | enum | boltz2 | {"options": ["boltz2", "boltz1"]} |
| use_msa_server | boolean | true | {} |
| msa_server_url | string |  | {} |
| predict_affinity | boolean | true | {} |
| num_samples | integer | 5 | {} |
| recycling_steps | integer | 3 | {} |
| diffusion_samples | integer | 1 | {} |

**input_ports**

```json
[
  {
    "name": "input_path",
    "kind": "protein_sequence",
    "accepts": [
      "sequence_set",
      "sequence"
    ],
    "content_types": [],
    "required": true,
    "multiple": false,
    "description": "Input YAML/path. Boltz YAML file or directory. (from field 'input_path')"
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
    "description": "Predicted complex structures."
  },
  {
    "name": "affinity_metrics",
    "kind": "tabular",
    "artifact_type": "score_table",
    "filename_glob": "*",
    "description": "Boltz affinity and binder-probability outputs."
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
      "help": "Predicted complex structures."
    },
    {
      "name": "affinity_metrics",
      "artifact_types": [
        "score_table"
      ],
      "required": false,
      "many": false,
      "help": "Boltz affinity and binder-probability outputs."
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
  "cpus_evidence": "Measured: job 4167148 reported CPU PEAK 1.00 and 68.68% average efficiency on one slot. `boltz predict` drives the GPU; the command passes neither --num_workers nor --preprocessing_threads (D061)."
}
```

命令摘要 SHA-256：`e17353ffc1cdbbe9424818fc3145881b395fe5c825136f59f465262158d38aea`。

命令文本中出现的 flags（文本清单，不保证所有条件分支执行）：`["--diffusion_samples", "--msa_server_url", "--out_dir", "--recycling_steps", "-maxdepth", "-type", "-z"]`。

命令文本引用的变量（含包装器局部变量，不全是用户参数）：`["BDA_INPUT_DIR", "BDA_OUTPUT_DIR", "input_path", "msa_server_url", "num_samples", "predict_affinity", "recycling_steps", "use_msa_server"]`。

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
| predicted_structure / complex | 预测原子坐标及链/残基映射 | Å | 坐标是假说；保留精确输入实体、模型与seed；不能推断实验结合。 | upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| pLDDT | 局部结构置信度 | 通常0–100；Boltz/Protein-Hunter原始汇总常0–1 | 逐文件核对尺度，不是概率或亲和力。 | upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| pTM / ipTM | 整体折叠/多链相对构象置信度 | 0–1 | 单体没有真实跨链接口ipTM；不要将零占位或对角线当结合分数。 | upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| PAE | 对齐后的相对位置预测误差矩阵 | Å | 保留链映射、非对角块和聚合定义；不能单独证明结合位点。 | upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| affinity_pred_value | Boltz-2亲和力回归头 | log10(IC50/μM) | 值越低预测越强；用于活性小分子间比较，不是Kd、ΔG或蛋白-蛋白亲和力。 | upstream-2（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| affinity_probability_binary | 小分子结合/非结合二分类头 | 0–1 | 用于区分binder与decoy，与回归头目标不同；必须有真实affinity JSON。 | upstream-2（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |
| PDE | 模型预测距离误差 | Å | 与PAE不同；write_full_pde控制完整矩阵。 | upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）, registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`） |

保留所有额外原始列；动态 XML/模型/配置新增字段须附定义、单位、版本和来源，未解释前不纳入筛选。

## 已知缺口与后续验收

- BDA base/draft将predict_affinity映射--affinity，但固定官方src/boltz/main.py没有该flag；官方从YAML properties.affinity指定。
- model与diffusion_samples字段未被BDA command消费；num_samples才映射--diffusion_samples。
- base input_path端口被标protein_sequence且允许sequence_set，但command假设可直接交给boltz；草稿强制YAML修复了输入限制，却未修复affinity开关。
- 正常BDA renderer将boolean false导出为空字符串，可正确省略flag；手工脚本若写字符串false则会错误启用。
- 当前output ports使用*泛匹配，不保证完整PAE/PDE/affinity文件真实存在；要逐文件核验。

## 易错点

- pLDDT/ipTM/RMSD不等于ΔG/ΔΔG/Kd或生物活性。
- template、initial_guess、空MSA和真实MSA是不同证据条件；不能混成独立交叉验证。
- 未消费的UI参数不可写入报告为已执行条件；本地catalog默认、BDA默认、命令回退和安装默认要区分。
- BDA base/draft将predict_affinity映射--affinity，但固定官方src/boltz/main.py没有该flag；官方从YAML properties.affinity指定。
- model与diffusion_samples字段未被BDA command消费；num_samples才映射--diffusion_samples。
- base input_path端口被标protein_sequence且允许sequence_set，但command假设可直接交给boltz；草稿强制YAML修复了输入限制，却未修复affinity开关。
- 正常BDA renderer将boolean false导出为空字符串，可正确省略flag；手工脚本若写字符串false则会错误启用。
- 当前output ports使用*泛匹配，不保证完整PAE/PDE/affinity文件真实存在；要逐文件核验。

## 来源与版本

- registry（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：2026-09-15 BDA声明、command、schema、ports快照；声明不是运行成功证明；commit `None`；读取 2026-09-15。
- [runbook](../../../qm-scripts/plugins/boltz/README.md)：2026-08-30历史QM运行手册；与当前声明不同处需单列；commit `None`；读取 2026-09-15。
- [library](../../../qm-scripts/library/catalog.json)：手工提交library的boltz参数提取，默认值不是BDA默认值；commit `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc`；读取 2026-09-15。
- [parameter-env](../../../backend_v2/app/compute/scripts.py)：parameter_environment将boolean true/false导出为1/空字符串；字符串不按boolean解释；commit `None`；读取 2026-09-15。
- upstream-0（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：src/boltz/main.py；上游源码快照，不证明QM安装代码完全相同；commit `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc`；读取 2026-09-15。
- upstream-1（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：README.md；上游源码快照，不证明QM安装代码完全相同；commit `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc`；读取 2026-09-15。
- upstream-2（私有审计快照，SHA-256 `c08339c22854cce7f1735573212d2beda76cc71340311d7f9e848d9cd30074a4`）：docs/prediction.md；上游源码快照，不证明QM安装代码完全相同；commit `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc`；读取 2026-09-15。
