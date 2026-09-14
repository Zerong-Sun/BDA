# 蛋白质设计能力清单：已交付与未交付

状态（2026-09-15）：第 1–6 项已实现；第 7 项已实现（输入限于人工上传的比对文件，见下）；第 8–9 项未开始。

这份清单回答的是"做蛋白设计时，平台还缺什么"。它不是路线图承诺，只记录每一项的当前状态、落在哪个模块、以及为什么这么做——尤其是那些**故意不做成工具**或**故意不存表**的决定。

| # | 能力 | 状态 | 落点 |
| --- | --- | --- | --- |
| 1 | 序列级分析（糖基化位点、脱酰胺、异构化、氧化与游离半胱氨酸、疏水斑块、pI/电荷/消光系数） | 已实现 | `app/sequences/{kernels,service}.py`；copilot 工具 `analyse_sequence` |
| 2 | 界面测量（SASA/BSA、氢键、盐桥、疏水比例） | 已实现 | `app/structures/kernels.py: interface()`；工具 `measure_structure_interface` |
| 3 | 结构叠合（按作者编号配对 CA、拟合前后 RMSD） | 已实现 | `app/structures/kernels.py: superpose()`；工具 `compare_structures` |
| 4 | AlphaFold3 输出解析（每个 seed 一行指标） | 已实现 | `app/compute/parsers/alphafold3.py`；迁移 `0068` |
| 5 | 候选分诊（阈值判定，三态 pass/fail/missing） | 已实现 | `app/candidates/triage.py`；工具 `triage_candidates` |
| 6 | 密码子优化与构建体设计 | 已实现 | `app/sequences/{codon,codon_usage,schemas,api}.py`；`scripts/build_codon_usage.py`；仅 HTTP |
| 7 | 保守性分析（从比对计算每个位点的保守度，标注不可动残基） | 已实现（输入限于已上传的比对文件） | `app/sequences/conservation.py`；工具 `analyse_conservation` |
| 8 | 序列/结构资源 MCP（把项目的序列与结构以 MCP resource 暴露给外部模型） | 未开始 | 预计 `app/copilot/mcp*.py` |
| 9 | 集群作业 MCP（在授权会话内查询与提交集群作业） | 未开始 | 预计 `app/copilot/mcp*.py` + `app/compute/` |

## 两条贯穿始终的规则

**明文序列只有一份。** `wetlab.models.Protein.sequence` 是唯一的明文副本，`ProteinRead` 对外只给摘要。因此第 1 项的工具只收 id、不收序列，也不回传残基；第 6 项返回 DNA，所以它**不做成 copilot 工具**——工具调用的结果会写进 `copilot_messages.tool_calls`，那等于在对话记录里留下第二份构建体明文。它只走 HTTP，交给发起请求的登录用户。

**只报测量，不报结论。** 第 1、2、3、6 项都只给数字与位置，不说"这个设计可行"。是否可接受是人对一次未做的实验下的判断，不是这些函数能替人下的。第 5 项的分诊是例外，也只是把人给的阈值套上去，并且区分"不满足"与"没有这项数据"。

## 第 7 项：输入从哪里来，以及它现在到哪一步

动手前先查了来源，结论是**平台目前不产出 MSA**：`msa` 只作为端口语义类型存在于
`registry/ports.py` 与工作流连线规则里，`qm-scripts/plugins/registry.json` 中没有任何插件声明
MSA 输出，AlphaFold3 插件也只把 MSA 当作运行中的一个阶段。所以"从流程产出的 MSA 算保守性"
会是一个没有输入的功能。

已实现的是另一半：**对项目里已上传的比对文件**（FASTA / a3m / Stockholm）按 artifact id 计算，
走 `analyse_conservation` 工具。这条路今天就能用——比对文件通过普通的 artifact 上传进来即可。
三个判断见 [Copilot bot 名册](../COPILOT_BOT_ROSTER.md) 的 `sequence-analysis` 一节：
默认 Henikoff 加权、gap 单独报、结果里不含查询序列。

**仍未做**：让 AlphaFold3 流程把它算出的 MSA 落成 artifact（需要改插件的 output port 与 collect
解析），以及按 target 自动找到对应比对。在那之前，这项能力要求人先上传比对文件。
