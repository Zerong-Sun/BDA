# Other projects display review — 2026-10-19

状态：已核验记录

最后核验：2026-10-19

权威范围：本记录所列前端行为、修复与验收范围；不代表 main 已合并或科学结论已验证。

数据来源：对应提交、自动化测试及本地浏览器验收；私有运行证据保存在仓库外。

替代关系：补充近期更新与前端验收记录，不替代运行时状态及原始项目报告。

## Scope and finding

Read-only browser inspection covered the remaining 11 projects: protein nanocages, flavor proteins, archived PD-1/PD-L1, INSR rescue, pain modulation, biocontrol archive, contaminant degradation, Botrytis archive, CD3 binders, enzyme scaffold repair and cannabinoid recognition.

Legacy nanocage, flavor and enzyme reports use ordinary paragraphs instead of level-two section headings. Their saved conclusions were hidden behind a misleading empty-results message. The overview now shows verbatim opening paragraphs, keeps label/list pairs together and exposes explicitly authored next-stage paragraphs or input lists. A saved pause instruction takes precedence over historical next-stage suggestions. The full report remains collapsed and available. No new scientific conclusions, translations, review approvals or source records are generated.

## Validation

- 33 desktop page inspections and 33 mobile inspections at 390 px: no horizontal overflow.
- 285 real project-scoped link clicks across results, team and workflow pages: all retained expected project and route parameters.
- All 11 workspace identities, displayed report titles and finding-review counts matched their saved API records.
- All 34 conversations represented in the 11 rooms belonged to the requested project; room pages were fully retrieved with no next cursor.
- Botrytis has only a source index and no standalone results report or primary target. Its primary-target API returns 404; the structure page correctly renders its empty state. This is recorded separately from navigation failures.
- 25 focused tests passed, including missing reports, index-only archives, citations, legacy prose, input lists, pause precedence and code/table exclusion. Production build and bundle gate passed; changed files passed lint.
- Browser application writes were blocked; none were attempted. Authentication was allowed. No DeepSeek or other model calls were made.

## Boundaries

This verifies display, provenance and navigation, not the scientific accuracy of the saved reports or completion of outstanding scientific reviews. Private browser evidence stays outside Git. Main merge and PR approval follow-up remain paused.

## Latest-record follow-up

All 13 selectable projects were checked in both visit orders (26 selector transitions). Saved report identity, latest progress source, next-step text and review counts stayed consistent with each project's baseline. Project-scoped links retained the destination ID, report details reset to collapsed, and no page errors were observed. Three projects had newer progress notes; their summaries used those notes without reviving the older report's instructions. The existing paused project retained its authored hold.

Two presentation omissions were found and fixed: an authored “当前准备判定” section now appears with advancement conditions, and an archive-only index can show its maintenance instructions with an explicit archive-index source label. The index still does not count as a scientific results report. Three regression cases cover these paths; the complete frontend suite passed 1,364 tests. Private browser evidence and saved-record snapshots remain outside Git; no model calls or research submissions were made.
