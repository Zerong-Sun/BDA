# BDA Rosetta 多模式插件

这是 BDA 原生 ModelPlugin（`org.bda.rosetta` / `2024.09-bda.1`），不是 Codex 个人市场插件。Rosetta 二进制与数据库由站点提供，本仓库只包含参数、生成器和执行包装层。

- [全部45参数说明](../../../docs/rosetta/PARAMETERS.md)：类型、插件默认、单位、适用模式、真实flag、限制与来源。
- [模式/科学语义](../../../docs/rosetta/SCIENTIFIC_MODES.md)：7模式、原始文档与旧参数库审查。
- `spec.py` 是唯一参数源；`build.py` 同步生成 options.json、BDA manifest与参数文档。`runner.py` 被嵌入manifest，集群无需安装额外BDA脚本。

## 在 BDA 中使用

选择 **Rosetta · 多模式参数工作台 / 2024.09-bda.1**，绑定 `s` 输入端口，再选择 application。界面按模式显示参数说明与默认值。约束、突变、native、MoveMap、XML、残基params等文件绑定 `aux`；参数填这些暂存文件的相对名称。PDB要求单模型并有明确链映射；本版不猜测 mmCIF auth/label 与 Rosetta链字母的对应。

将界面链填写为实际伙伴分组（例如AB_C，必须恰好覆盖所有输入链）。`relax_interface` 是复合物Relax后分析，默认并非只动界面；需要限制受体自由度时提供正确MoveMap。天然和设计采用同模式、权重、约束、采样预算进行比较。

Cartesian DDG 必须提供mut_file和*_cart权重，输入需要与所用截断参数一致的预先Cartesian优化WT；模式不会悄悄先替你优化WT。自定义XML模式需自包含XML，变量name=value与所有%%name%%占位符完全对应；不能把任意XML宣称为预验证协议。内置其余模式无需编写XML。

## 在本地生成配置包，暂不执行

```bash
python3 qm-scripts/plugins/rosetta/runner.py describe
python3 qm-scripts/plugins/rosetta/runner.py generate \
  --config qm-scripts/plugins/rosetta/examples/interface.json \
  --input-dir /absolute/staged-input \
  --output-dir /absolute/new-review-directory \
  --runtime-root /absolute/site-rosetta-install
```

input目录包含`s/*.pdb`和可选`aux/*`。`generate`只验证输入、生成run-plan.json、commands.sh和本次parameter-explanations.md；不需要本地Rosetta二进制。`run`才会调用软件。BDA部署后的正常执行仍走工作流预览/资源检查/QM调度，不能在登录节点直接运行长计算。

每个输入/重复独立目录；重复种子显式递增。原始SCORE所有数值和文本列保留，已知核心能量字段非有限值报错。Relax后的每个PDB再独立IA，记录实际输入哈希；坐标几何来自该保存PDB，不冒充IA未导出的内部packing副本。接触阈值是用户选择的几何定义；角度须显式定义两个CA轴，没有锚点就标未计算。

## 输出与完成条件

- `run-plan.json`、`parameter-explanations.md`、`commands.sh`：配置与解释。
- `execution.json`：实际二进制SHA、逐阶段命令、输入/辅助文件身份、退出/输出检查、未启用指标状态。
- `runs/**`：每输入/重复的PDB、原始.sc/.ddg、日志及可选界面原子距离CSV/JSON。天然参考几何也保留原始坐标哈希。
- `scores.json` / `scores.csv`：保留全部原始列与来源；不同stage不混作同一指标。
- `checksums.json`：所有产物的字节数和SHA；BDA收集器再核对并按端口归档。

进程退出0仍要求相应SCORE行/结构/界面字段。现代DDG要求有限WT和每个突变block的记录，不能仅有一个非空文件；迭代提前终止与物理解释仍需协议审查。未启用packstat时，其原始0不是测量值。不会从这些输出填造MSA、pLDDT、ipTM、Kd或物理kcal/mol结合自由能；不凭文件名猜测候选身份，也不覆盖历史候选数据。

## 开发与发布

```bash
python3 qm-scripts/plugins/rosetta/build.py
python3 qm-scripts/plugins/rosetta/build.py --check
pytest backend_v2/tests/test_rosetta_workbench.py backend_v2/tests/test_plugin_site_runtime.py
```

修改已部署manifest必须发布新plugin_version；不要改旧checksum固定版本。站点安装路径通过site_overrides.runtime_root配置；预览与新作业快照使用同一解析结果。插件软件测试、声明valid、真实Rosetta运行proven与生物功能验证是不同状态。
