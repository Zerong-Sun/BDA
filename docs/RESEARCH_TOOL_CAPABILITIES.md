# 研究工具能力与输入要求

状态：活跃

最后核验：2026-09-30（仓库实现核对；未重新验证外部账号或集群）

权威范围：蛋白质、专利与成药性工具的现有能力、输入和限制。

数据来源：[工具注册](../backend_v2/app/copilot/tools.py)、[序列服务](../backend_v2/app/sequences/service.py)、[结构服务](../backend_v2/app/structures/service.py)、[成药性服务](../backend_v2/app/intelligence/druggability_service.py)、[专利入口](../backend_v2/app/literature/api.py)。

替代关系：已完成能力从[历史方案](archive/2026-09-30/README.md)移入本文；任务授权仍以 [Copilot 服务指南](COPILOT_SERVICE_GUIDE.md)为准。

## 蛋白质与结构

| 任务 | 入口与输入 | 结果与限制 |
| --- | --- | --- |
| 序列分析 | `analyse_sequence`；项目内 candidate、target 或 protein ID | 返回位点和理化测量，不回传序列明文。 |
| 界面测量 | `measure_structure_interface`；结构 artifact ID | 返回 SASA/BSA、氢键、盐桥等测量；不据此宣告设计成功。 |
| 结构叠合 | `compare_structures`；结构 artifact ID | 按作者编号匹配 CA，报告拟合前后 RMSD。 |
| AlphaFold 3 结果 | 作业结果采集 | 按 seed 解析指标；解析器可用不证明某次集群作业已成功。 |
| 候选分诊 | `triage_candidates`；候选与路线阈值 | 按阈值区分通过、不通过和缺数据。 |
| 密码子优化 | HTTP 入口 `/projects/{id}/codon-optimisations`；蛋白记录与宿主 | 返回 DNA，验证可翻译回原蛋白；不作为会记录输出的 Copilot 工具。 |
| 保守性分析 | `analyse_conservation`；比对 artifact 或可唯一匹配的 target | 支持上传 FASTA/A3M/Stockholm，以及 AF3 采集的真实比对；返回位点统计，不补造 MSA。 |

AF3 从已采集的 `*_data.json` 提取内嵌 `unpairedMsa`/`pairedMsa`，生成逐链 A3M。源文件须通过 SHA-256 校验，查询行须匹配链序列；派生制品保留源制品、哈希、job、attempt、链和比对类型。没有比对时保留原始输出并标记不可用；多份匹配时要求指定 artifact。`protein_msa` 端口只影响新快照，旧作业快照不被重写。

MCP 的工具与权限来自同一注册表。项目资源可按引用读取，但不枚举实体，也不增加明文序列资源。作业查询复用已授权的只读工具；提交仍需计算草稿、人工确认和提交接口。详见 [MCP 契约](MCP_CAPABILITY_SURFACE.md)。

## 专利与成药性

| 任务 | 入口与前提 | 产物 |
| --- | --- | --- |
| 专利检索 | 明确请求 `start_patent_search`；Europe PMC 或已配置的 EPO OPS | 保存专利文档、查询、来源、时间与检索追踪；支持按局过滤。 |
| 专利格局 | `summarise_patent_landscape` 或项目专利页面 | 汇总本项目已保存记录，区分公开文本与专利族；显示缺失和截断。 |
| 同族、法律事件和权利要求 | 项目已保存专利；EPO OPS 凭据 | 异步采集、保存原始 XML 制品及来源追踪；权利要求支持字面搜索。法律事件按国家展示，不汇总成有效性结论。 |
| 成药性证据 | `start_druggability_assessment`；有 UniProt 标识的靶点，可选 `candidate_id` | Open Targets 证据、临床阶段、安全性、项目已保存文献和候选序列测量；`get_druggability_assessment` 读取结果。 |
| 竞争格局 | 成药性报告 | 临床登记年度趋势、申办方构成、已保存专利年份趋势；不输出市场规模或成药概率。 |

成药性评估在排队时冻结候选测量和序列摘要，避免后续编辑改变该次评估。缺失的临床阶段数据保持未知；PHASE3 与 PHASE4 均取得后才计算晚期试验总数。申办方统计按 NCT ID 去重，最多读取 100 页、每页 1,000 条；失败、循环游标或到达上限均标记不完整。登记数不能等同研发项目数，保存文献也不等于已读或支持结论。

EPO OPS 需要 `BDA_V2_EPO_OPS_CREDENTIAL_REF` 指向凭据文件；缺凭据时拒绝排队。部署还需核验账号配额和目标文献的覆盖范围。真实来源的可达性不由历史验收保证，失败和无命中必须区分。[剩余工作](plans/DRUG_LANDSCAPE_PLAN.md)保留按适应症拆分和部署验收条件。
