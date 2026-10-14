# 版本化仪器分析、Bot 证据与结构复核

状态：2.6 开发分支已实现的软件工作流；不代表 assay 或功能验证通过。

最后核验：2026-10-14。

权威范围：BLI 版本化分析、Bot 证据入口、结果与候选指标、结构残基身份及公开软件复现步骤；产品/API 版本仍为 BDA v2。

数据来源：[仪器分析与请求契约](../backend_v2/app/wetlab/analysis.py)、[仪器请求 schema](../backend_v2/app/wetlab/schemas.py)、[QC 审阅](../backend_v2/app/experiments/service.py)、[结果摘要](../backend_v2/app/delivery/service.py)、[结构残基工具](../backend_v2/app/copilot/structure_tools.py)、[Bot 职责](../backend_v2/app/copilot/bots.py)、[证据入口](../frontend/src/features/copilot/ToolEvidence.tsx)及下列合成数据测试。

替代关系：补充[仪器质控](WETLAB_QUALITY_CONTROL.md)、[Copilot 服务指南](COPILOT_SERVICE_GUIDE.md)和[MCP 契约](MCP_CAPABILITY_SURFACE.md)；本文说明新增版本与跨页证据路径，不替代实验原始记录、仪器操作规程或人工科研审核。

## 从源文件到可审阅结果

1. 在当前项目上传原始仪器文件。分析先核验文件长度与 SHA-256；原文件不被重写。BLI 支持既有 ForteBio CSV 与 `Time/Data/Fit` 三列一组的动力学导出。`Data` 是观测响应，`Fit` 是仪器拟合曲线；仪器导出的 KObs/KOff 也须单独标注来源。
2. 先预览并确认传感器—样品映射、浓度单位、绝对时间轴上的结合/解离切换点、参比及排除的传感器。三列导出的实测曲线重拟合需要显式相界；缺少信息不会自动生成一个已验证的 KD。原始曲线、参比处理曲线、仪器拟合和本次分析拟合分别显示。
3. 选择方法。`measured_global` 对观测曲线拟合；`instrument_kobs` 使用仪器动力学参数，不运行实测曲线拟合，也不把参比/基线处理冒充为已作用于仪器参数。默认基线为 `initial_point`；`fitted_offset` 是显式选择。仪器参数拟合得好不等于独立重拟合或可靠置信区间；查看残差、方法差异、假设与 QC 限制。
4. 明确请求保存后才产生新实验结果。改变映射、参比、排除项或拟合设置，应保存新版本；使用 `supersedes_result_id` 时必须填写修正说明。旧结果、处理条件和原始来源保留，不能把敏感性分析描述为覆盖原始数据。
5. 在已保存结果中审阅。新结果的 QC 为 `pending`，assay 状态为 `unknown`。接受/拒绝需理由、当前版本与实验权限；过期版本要求重新读取。QC 接受不自动设置 assay pass，也不证明结合功能或生物学有效性。

保存的 BLI 结果包含源文件摘要、处理条件、方法/QC、版本关联和用于绘图的抽样点快照；完整原始观测仍在源文件。Bot 的项目上下文只携带各绘图数组的准确点数及结果/来源引用，避免把大量浮点坐标填入对话。该压缩不改变数据库或 API 中的快照，点数也不代表独立实验重复数。

## Results、Candidates 与讨论报告

| 入口 | 用途与状态含义 |
| --- | --- |
| Lab / Results 的已保存仪器结果 | 查看各次分析、源文件、图、处理条件与 QC；待审或被拒结果仍是可追溯记录 |
| Candidates | 关联到候选且 QC 被接受的仪器结果才投影为候选实测指标；预测指标独立保留。后续拒绝移除相应派生指标，不删除原始结果 |
| Results 的 Best reviewed KD | 比较有限、严格为正且单位可换算的浓度。BLI/仪器 QC 记录必须被接受；明确 assay fail 排除。无仪器审核信息的历史手工 KD 必须为 pass。返回被选记录的原值、单位与 ID；这不是功能验证或自动选定主分析 |
| Bot 工具证据卡 | 按返回的身份打开来源、结构残基、已保存分析、候选或讨论报告。预览不等于保存，模型说“完成”不代替实际记录 |

Planner 负责结构证据与方案，Analyst 负责仪器结果与归档，Auditor 复核结论；Conductor 的委派受项目能力和任务授权限制。跨页写入必须在用户授权范围内。保存讨论报告使用知识草案，入口位于 Research 的方法/知识记录；报告应链接具体实验结果、源制品和工具证据，写明方法、处理条件、审核状态与限制。没有返回报告记录 ID 的普通回答不能称为“已保存报告”。接受某个仪器参数或参比敏感性版本必须有明确审核，不会因它的数值更小或版本更新而自动接受。

## 结构身份与科学表述

先用 `analyse_structure` 确认制品、作者链 ID、编号与置信度来源，再用 `list_structure_residues`、接触/界面/位点工具读取证据；读完结果后再调用 `render_structure_view`。LYS/ARG 的“正电”是近中性 pH 下的侧链分类，HIS 的电荷取决于质子化，不是固定正电；这不是 pKa 或静电计算。

保留作者链、残基编号和插入码，例如 `A:52` 与 `A:52A` 是不同身份。查看器与报告均使用完整身份；位点编号有歧义时须显式给出插入码。当前 hotspot/design 写入不支持非空插入码，会明确拒绝，不能直接删码后改指另一残基。

预测坐标上的接触应称“预测结构坐标计算的几何接触/距离”，不要称“实测几何”或“实验测得”。接触、埋藏面积与邻近残基仅支持几何界面候选；没有独立实验依据不能称功能位点或已验证热点。B-factor 只有在来源明确声明时才解释为 pLDDT，未知来源保持未知。

## 可复现的软件验证

使用隔离测试库和仓库内合成数据，不需要私有数据、外部仪器或计算作业。按 [CLAUDE.md](../CLAUDE.md) 选择主 checkout 的 Python 环境，在仓库根目录执行：

```bash
BDA_PYTHON_BIN="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/backend_v2/.venv/bin"
"$BDA_PYTHON_BIN/pytest" backend_v2/tests/test_bli_triplet_provenance.py backend_v2/tests/test_copilot_instrument_boundary.py backend_v2/tests/test_delivery_result_summary.py backend_v2/tests/test_copilot_project_context.py backend_v2/tests/test_copilot_structure_evidence.py backend_v2/tests/test_structure_residues.py
npx --prefix frontend vitest run --root frontend src/features/copilot/ToolEvidence.test.tsx src/features/lab/instrumentAnalysis.test.tsx src/features/pdb-viewer/structureResidueIdentity.test.ts src/features/results/ResultsMetrics.test.tsx
```

人工走查可使用测试生成的合成文件：预览 → 明确保存 → 改参另存 → 拒绝/接受 → 从证据卡回到原结果，核对源文件未变、版本与处理条件可见、待审结果没有进入 Best reviewed KD。结构走查应同时选择带/不带插入码的残基，并验证没有把预测几何写成实验结论。上述步骤验证软件契约；真实 assay 的方法适用性与复现性需另行审核。
