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
| 8 | 序列/结构资源 MCP（把项目的序列与结构以 MCP resource 暴露给外部模型） | **不做**（见下） | 现状：`app/copilot/mcp.py: resource_listing/read_resource` |
| 9 | 集群作业 MCP（在授权会话内查询集群作业） | 已具备，无需新增 | 现有注册表工具经同一个 MCP transport 暴露 |

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

## 第 8 项为什么不做

原始设想是"把项目的序列与结构做成 MCP resource"。查过现状后结论是**不做**，两条理由都写在现有代码里：

1. `mcp.py: resource_listing()` 只返回 UI 页面，并且注明了原因——把项目实体逐条列出来，等于开出
   第二个**没有能力门**的读取面。现在的设计是：资源**可寻址、不可枚举**，
   `resources/read` 认 `bda://{research|project|literature}/{kind}/{id}`，并在读之前检查
   `research-read` / `project-read`。artifact 已经在 `PROJECT_ROUTES` 里（`/api/v2/artifacts/{id}`）。
2. 序列资源会直接违反贯穿本清单的那条规则：`Protein.sequence` 是唯一的明文副本。把残基做成
   resource 内容，等于给外部模型发一份明文。

外部模型需要结构时，已有路径是**工具**：`render_structure_view`、`measure_structure_interface`、
`compare_structures` 按 artifact id 在服务端算完再回结果，而不是把坐标整体交出去。

## 第 9 项为什么不用新增

"集群作业 MCP"在这套架构里不需要是新东西：MCP 是注册表的第二个传输层，
`mcp.available_tools` 直接从 `REGISTRY.all()` 里选，所以作业相关工具天然在 MCP 上可见——
`get_compute_status`（project-read / failure-diagnosis）、`diagnose_compute_failure`（failure-diagnosis）、
`review_compute_declaration`（review-audit）都是只读工具，一个授权会话有对应 capability 就能调。
再写一套 MCP 专用作业工具，就是 `registry.py` 开篇要消灭的"第四处声明"。

两条边界是有意保留的，并由测试钉住（`tests/test_copilot_mcp.py`）：
未绑定 run 的会话**拿不到** `create_compute_draft`——草稿会占集群时间，而没有 run 的会话没有授权依据；
`await_compute_job` 需要挂起一次 run，MCP 客户端不能挂起，所以它从不出现在 MCP 列表里。
**提交作业本身不是工具**：它花钱，走 draft → 人确认 → 提交这条既有路径。
