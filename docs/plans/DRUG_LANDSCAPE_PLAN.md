# 专利、成药性与竞争格局：剩余工作

核验日期：2026-09-30。P1–P4 已实现；现有入口与限制见[研究工具能力](../RESEARCH_TOOL_CAPABILITIES.md)。[原方案](../archive/2026-09-30/DRUG_LANDSCAPE_PLAN.md)及[2026-09-15 验收](../archive/2026-09-30/DRUG_LANDSCAPE_AUDIT.md)留作历史证据。

## 未完成

| 工作 | 完成条件 |
| --- | --- |
| 按适应症拆分临床与竞争格局 | 明确适应症筛选、去重口径与来源覆盖，并在报告中显示缺失和截断。当前按靶点/检索词汇总。 |
| EPO 真实账号及部署验收 | 在目标部署验证凭据、配额、原文覆盖和失败恢复，并保存回执。代码与离线测试通过不等于账号或部署可用。 |

市场规模、价格、销售额和份额尚无接入的可审计来源。接入前不生成数字，也不将此项当作已有能力。专利法律事件不自动解释为有效性、侵权或 FTO 结论。

## 已完成，不再列为待办

- 指定 `candidate_id` 的成药性评估在排队时冻结序列摘要与测量。
- ClinicalTrials.gov 申办方统计按 NCT ID 去重，最多 100 页、每页 1,000 条；失败或到达上限时标记不完整。
- EPO 权利要求提取、字面搜索、同族预览、法律事件 REST 入口及 Helm Secret 引用。

实现依据：[成药性服务](../../backend_v2/app/intelligence/druggability_service.py)、[临床统计](../../backend_v2/app/intelligence/druggability.py)、[专利入口](../../backend_v2/app/literature/api.py)；工程核验见[9 月 16 日整合记录](../CONSOLIDATION_REVIEW_2026-09-16.md)。
