# 2026-09-30 已完成方案与历史验收

本批次的 5 份文档采用仓库统一归档格式：历史提示、分隔线、归档前原始字节。正文中的“当前”、日期、测试数量和相对链接均属于原文；现行入口见下表。

| 归档件（原位于 `docs/plans/`） | 归档原因 | 当前入口 |
| --- | --- | --- |
| [BOT_ROOM_PLAN.md](BOT_ROOM_PLAN.md) | 研究室 P0–P4 已交付，移除待实施入口 | [工作区说明](../../BOT_FIRST_WORKSPACE.md) |
| [PROTEIN_DESIGN_FEATURES.md](PROTEIN_DESIGN_FEATURES.md) | 1–7 已实现，8 明确不做，9 已有入口 | [研究工具能力](../../RESEARCH_TOOL_CAPABILITIES.md) |
| [DRUG_LANDSCAPE_AUDIT.md](DRUG_LANDSCAPE_AUDIT.md) | 9 月 15 日验收记录，保留当时缺陷和结果 | [研究工具能力](../../RESEARCH_TOOL_CAPABILITIES.md) |
| [DRUG_LANDSCAPE_PLAN.md](DRUG_LANDSCAPE_PLAN.md) | 阶段已交付；原路径改为剩余工作 | [专利与成药性待办](../../plans/DRUG_LANDSCAPE_PLAN.md) |
| [FRONTEND_USAGE_PLAN.md](FRONTEND_USAGE_PLAN.md) | 已交付交互阶段和原诊断退出待办正文 | [前端待办](../../plans/FRONTEND_USAGE_PLAN.md) |

[manifest.json](manifest.json)的 `documents` 记录原路径、归档路径及替代入口；`original_bytes` / `original_sha256` 校验分隔线后的原文，`archive_bytes` / `archive_sha256` 校验含历史提示的归档文件。[SHA256SUMS](SHA256SUMS)对应完整归档文件，可在本目录执行 `shasum -a 256 -c SHA256SUMS` 校验。原路径标为 `removed` 的文件已从规划区移除，其余原路径保留精简待办。

恢复原文时先校验完整归档，再提取首个 `\n---\n\n` 分隔符之后的字节，核对 `original_bytes` / `original_sha256` 后按 `old_path` 选择恢复位置；不要覆盖现行文档而丢失后续修改。历史相对链接需按原路径解释，当前阅读请使用本页的入口。
