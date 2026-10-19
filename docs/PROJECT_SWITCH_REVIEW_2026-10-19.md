# Project switching review — 2026-10-19

状态：已核验记录

最后核验：2026-10-19

权威范围：本记录所列前端行为、修复与验收范围；不代表 main 已合并或科学结论已验证。

数据来源：对应提交、自动化测试及本地浏览器验收；私有运行证据保存在仓库外。

替代关系：补充近期更新与前端验收记录，不替代运行时状态及原始项目报告。

## Findings and changes

- While a destination workflow was still loading, its page could briefly offer a blank workflow/route planner. The page now waits for current-run, linked-run ownership and graph loading before presenting the workspace. No creation or planning call is made by loading the page.
- Research pages now explicitly remount their temporary state by project, matching the team/workflow components. The application shell already isolates project pages; this local boundary also protects the research component when embedded independently. An initially suspected evidence-search leak was a test timing artifact: once the selector update settled, the old deployed shell cleared it. This was not a confirmed cross-project data leak.

## Verification

- Chromium used the actual selector for 78 checks across 13 projects, three surfaces and both visit orders. Reports, latest team messages and workflow card/node snapshots matched each project's own cached baseline. Project-scoped links retained the selected project.
- Delayed destination requests showed loading without old content. Releasing old-project requests after switching did not change destination team messages, report or existing workflow graph.
- A typed, unsent team draft did not carry to another project. Back/forward restored the matching project/run, selector changes removed old run/node parameters, and a foreign workflow link was rejected in favor of the current project's run.
- 49 focused/regression tests passed across seven files, covering research state, workflow loading, late responses, ownership checks, team and project lifecycle behavior. Production build and changed-file lint passed.
- No browser page errors or application writes were observed. Authentication was permitted; model calls and research submissions were prohibited throughout. Test drafts were confined to the isolated browser.

Private browser evidence and deployment backups remain outside Git. This is a frontend state/navigation verification, not a scientific validation. Main merge remains paused.

## CI loading-state follow-up

- The full browser matrix caught a missing canvas skeleton in the new project-loading guard. The guard correctly withheld the old workflow, but returned only a status line. It now renders a busy, accessible canvas placeholder until the current project has loaded.
- The workflow regression asserts that the skeleton is visible while the current run is pending, disappears when the run arrives, and never exposes creation/planning controls or calls during loading. The existing 21 workflow journey checks pass.
