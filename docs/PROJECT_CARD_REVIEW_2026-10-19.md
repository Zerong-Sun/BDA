# Project card presentation review — 2026-10-19

状态：已核验记录

最后核验：2026-10-19

权威范围：本记录所列前端行为、修复与验收范围；不代表 main 已合并或科学结论已验证。

数据来源：对应提交、自动化测试及本地浏览器验收；私有运行证据保存在仓库外。

替代关系：补充近期更新与前端验收记录，不替代运行时状态及原始项目报告。

## Scope

Unify project results, research team and workflow cards around saved results, review state and the next action. Keep every destination scoped to the selected project. No model requests or research submissions were used for validation.

## Changes

- Project results: put results and report/review first, next actions second, followed by source materials and original objectives/questions. Place report/progress buttons beside their respective records and preserve source dates and incomplete-review notices.
- Research team: keep the latest conclusion and review visible; move related actions below the answer. Collapse project background by default and remove the redundant methods shortcut.
- Workflow: show route/status, evidence/review and next step in consistent cards. Keep methods, prior learning forms and feedback details collapsed, with missing review state and pending counts visible.
- Use shared responsive card/action styles, keyboard focus and reduced-motion support. Preserve execution gates, full records and explicit scientific uncertainty.

## Verification

- Frontend full suite: 200 files, 1,341 tests passed. After the last report-button and feedback-collapse adjustments, both affected suites passed again (17 tests).
- TypeScript/Vite production build and bundle gate passed; entry bundle 517.9 KiB.
- Lint: zero errors; four existing React Table compiler warnings.
- Chromium against the real local API: 49 navigation/state/layout checks covering sweet, PD-L1 design and archived PD-1/PD-L1 records. Results, task details, evidence, review queue, review records, material links and workflows retained their project IDs.
- Archived PD-1/PD-L1 objectives/questions were populated from saved records; full report opened on demand. All three pages fit a 390 px viewport without horizontal overflow.
- No browser page/API errors; no blocked application writes during these read-only checks. Auth token operations were permitted; model/research submissions were not.

## Limits

This validates presentation and navigation, not scientific correctness or completion of pending reviews. Main merge and PR approval follow-up remain paused at the user's request. Private data, screenshots, database backups and browser traces stay outside the public repository.
