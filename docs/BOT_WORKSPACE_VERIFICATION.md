# Bot workspace verification — 2026-09-14

状态：活跃

最后核验：2026-09-14（Asia/Shanghai；追加 iteration 7「研究室 / 决策请求 / 结构位点」的六维审计）

权威范围：Bot 工作区六维审计的缺陷复现与修复核验清单。

数据来源：实际界面路径、现有后端契约、Vitest 与浏览器验收结果。

替代关系：是 [Bot 优先工作区](BOT_FIRST_WORKSPACE.md) 的核验附录，不单独定义产品行为。

Scope: the public-data frontend redesign on `codex/bot-first-science-workspace`.
Audit the user's six dimensions against actual UI paths and existing backend contracts.

## Repair checklist

| ID | Priority | Dimensions | Reproduction / defect | Repair and verification |
| --- | --- | --- | --- | --- |
| F1 | P1 | Requirements, logic | Edit the public project's task brief; the package-specific presentation still masks the saved text. | **Fixed.** Authored prompt takes precedence; imported summary still resolves to the source-backed public brief. |
| F2 | P1 | Logic, boundaries | Viewer/demo users can still start/continue/cancel tasks or save deliverables through some Bot controls. | **Fixed.** Shared UI and command-boundary guard for tasks, continuations, cancellation, chat, deliverable saves and model settings; parameterized viewer/demo tests. |
| F3 | P2 | Logic, boundaries | Switch projects while a run is open; the prior project's run ID remains in the URL. | **Fixed.** Project changes clear run and structure parameters while retaining the selected workspace view. |
| F4 | P2 | Requirements, boundaries | Select structures, visit Bots, then return: comparison and selections reset; duplicate choices can masquerade as a comparison. | **Fixed.** URL-backed A/B selections with distinct fallback, disabled duplicate selection, and Back/reload browser coverage. |
| F5 | P1 | Logic, quality, coverage | Streaming state is local to a mounted chat; remount can enable a second send, while a late reply after reset can overwrite another message. | **Fixed.** Reproduced delayed reply races; shared project request identity blocks duplicate sends and rejects late writes after reset, deletion or sign-out. |
| F6 | P2 | Coverage, runtime | Browser fixtures use three Bots rather than the full backend roster, and never exercise streaming navigation races. | **Fixed.** Isolated FastAPI exporter verified 12 Bots / 5 services; browser consumes those responses and exercises delayed synthetic SSE. |
| F7 | P1 | Logic, boundaries | Start a task, leave the workspace before acceptance; its late callback can navigate back to the old project. | **Fixed.** Detached workspaces refresh the task list without changing the current route; pending-mutation regression test. |

## Six-dimension acceptance

1. **Requirements:** direct project entry, Bot-led work, concise source-backed public content, existing Mol* interactions plus comparison, V2 colors, responsive and reduced-motion behavior.
2. **Logic:** URL/project consistency, user-authored content precedence, task scope/readiness, streamed conversation ownership and accurate progress labels.
3. **Boundaries:** missing projects/models/files, invalid/stale URLs, API failures/retry, viewer/demo mode, project switches, reset/sign-out, narrow screens.
4. **Code quality:** shared rules, explicit types, existing UI components, generated API contracts unchanged, readable fixes without new dependencies.
5. **Coverage:** targeted regression tests for each confirmed defect, complete frontend suite, browser acceptance, public-data gate.
6. **Runtime:** production build and browser interaction with real Mol*; exercise local backend APIs where dependencies permit. Never infer model/compute correctness from a fixture.

## Final evidence

All seven listed defects have regression coverage and are repaired. Runtime
checks use the production frontend bundle. No new dependency, generated API
change or public research-data change is introduced.

| Check | Result |
| --- | --- |
| Frontend regression | **123 files / 718 tests passed** |
| Targeted backend regression | 139 passed: Bot policy, task contracts, agent runs and chat surface |
| Production browser | 15 scenario groups passed with the actual 12-Bot / 5-service FastAPI catalog |
| Existing workflow browser gates | 10/10 passed |
| Workflow / Candidates / Results browser matrix | 3/3 passed |
| TypeScript, production build, bundle gate | Passed; entry 399.3 KiB / 750 KiB budget |
| ESLint | No errors; three existing TanStack Table compiler warnings |
| Python catalog exporter lint | Ruff passed |
| Public-data allowlist / checksums | Passed; one public package and six synthetic fixtures unchanged |
| Patch whitespace | `git diff --check` passed |

The viewer/demo guard is a UX restriction, not the security boundary: the backend
continues enforcing project ACLs. The FastAPI catalog runs in an isolated app
with only test authentication overridden. Backend tests use isolated fixtures;
no production PostgreSQL, live model credentials, external retrieval, compute
queue or production deployment was exercised. The browser's single chat POST
and delayed SSE reply are synthetic. Unsent text remains memory-only; task URLs
and structure selections survive reload, while unsent text does not.

## Reproduce

From the repository root, using the backend development Python environment:

```sh
backend_v2/.venv/bin/python frontend/scripts/export-bot-catalog.py /tmp/bda-bot-catalog.json
backend_v2/.venv/bin/python -m pytest backend_v2/tests/test_copilot_bots.py backend_v2/tests/test_copilot_task_contracts.py backend_v2/tests/test_copilot_agent_runs.py backend_v2/tests/test_copilot_chat_surface.py
python3 scripts/check_public_data.py
```

From `frontend`:

```sh
npm run build
npm run lint
npm test
BDA_BOT_TEST_CATALOG=/tmp/bda-bot-catalog.json npm run test:bot-workspace
node scripts/browser-workflow-gates.mjs
BDA_BROWSER_ROUTES=workflow,candidates,results BDA_BROWSER_APPEARANCES=en-light BDA_BROWSER_STATES=populated npm run test:browser
```

For this review, the isolated Python environment was `/tmp/bda-review-venv` and
browser artifacts are in `/tmp/bda-review-browser`. `report.json` records checks,
uncaught browser errors, unexpected writes, the one synthetic chat POST, and
catalog sizes. English/light and Chinese/dark screenshots were inspected.

Publication target: `bda-public` (`Zerong-Sun/BDA`), branch
`codex/bot-first-science-workspace`. No merge to main or deployment is requested.

---

## Iteration 7 verification — research room, decision requests, hotspot sets

Scope: `claude/bot-interaction-decision-display-fb5506`, stacked on
`codex/bot-first-science-workspace` (8007e022). The work is P0–P4 of
[研究室与结构位点选择规划](plans/BOT_ROOM_PLAN.md); the behaviour it produced is
described in [Bot 优先工作区](BOT_FIRST_WORKSPACE.md) iteration 7.

### Repair checklist

Twelve defects were found by the six-dimension pass over this change and are
repaired. Four are worth reading as more than a list: **F1** would have broken
every fresh deployment, **F2** would have shipped a page no host could drive,
**F3** silently disabled a label, and **F5** would have accepted a wrong residue.

| ID | Priority | Dimensions | Defect | Repair and verification |
| --- | --- | --- | --- | --- |
| G1 | P1 | Logic, runtime | `0065` added `copilot_messages.bot` unconditionally, but `0002_full_domains` builds that table from the **live ORM metadata** — so on any database created after this change the column already exists at revision 0002 and the migration failed with `DuplicateColumn`. Caught by the PostgreSQL upgrade-path test, not by the SQLite suite. | **Fixed.** Guarded by a column inspection, the idiom `0010_copilot_research_generation` already uses on this table. 8/8 upgrade paths pass, including `alembic check` and `downgrade base`. |
| G2 | P1 | Requirements, logic | The MCP Apps page was written from a summary of the extension: it sent `ui/message` as `{message}` and read the tool result from `params.result`. The spec is `{role, content:{type,text}}` and the notification carries the `CallToolResult` **as** its params — so the page would have rendered blank and posted a message no host reads. | **Fixed** against the published spec; both shapes pinned by `test_the_page_speaks_the_shapes_the_extension_defines`. |
| G3 | P1 | Logic | The room read a task's delivery from `outcome["state"]`; `agent_loop.evaluate_delivery` writes `status`. Every task entry would have shown the fallback label. | **Fixed** to read the key the task list already reads; asserted in `test_copilot_room`. |
| G4 | P2 | Boundaries | The room's keyset cursor encoded whatever the driver returned, which on SQLite is a naive instant; compared against `timestamptz` on the next page it would be read in the session's timezone. | **Fixed.** The cursor and the sort both normalise to UTC. |
| G5 | P1 | Boundaries | `bool` is an `int` in Python, so `{"chain": "A", "seq": True}` was accepted as residue 1 — a silently wrong residue in a set a design job would run against. | **Fixed.** Refused with the value in the message; covered by the parametrised rejection test. |
| G6 | P1 | Coverage | The three new route groups had service tests and no HTTP tests: nothing exercised `If-Match`, the 404-not-403 scoping, or the 201/412/428 codes a client branches on. | **Fixed.** `test_room_decision_hotspot_api.py`, 16 cases through `TestClient`. |
| G7 | P2 | Coverage | `structures.service.view` — the one impure step between an artifact and a scene — had no test. | **Fixed.** `test_structure_view_service.py`, 7 cases with object storage stubbed. |
| G8 | P2 | Quality, runtime | `room.ts` beside `Room.tsx` differ only in case; `tsc` refuses the pair on a case-insensitive filesystem and the production build failed. | **Fixed.** Renamed `roomFeed.ts`, with the reason in the module docstring. |
| G9 | P2 | Boundaries | `scrollIntoView` is absent in jsdom and in some embedded browsers; the room's autoscroll threw on mount. | **Fixed** with the repo's existing optional-call idiom. |
| G10 | P3 | Quality | Extracting the citation list left `Badge` and `Link` unimported-but-unused in `CopilotChat`, and the panel imported a key factory it did not use. | **Fixed;** `tsc` and ESLint clean. |
| G11 | P1 | Logic, runtime | The runtime schema pin (`Settings.schema_revision`, compose, Helm, Dockerfile, two workflows, the upgrade-path expectation) was not moved with the new head — twice, once per new migration. | **Fixed** for both; `test_runtime_schema_declarations_match_the_migration_head` passes. |
| G12 | P3 | Coverage | A new test fixture constructed `Artifact(kind=…)`, a field that does not exist. | **Fixed** to `artifact_type` / `content_type`. |

### Contract expectations changed deliberately

Four pinned expectations moved. Each argument is written into the test that
holds it, so the next reader meets the reasoning and not a loosened assertion:

1. a reviewer and a director may hold `request_decision` beside `post_handoff` —
   asking a person to decide is neither repairing what you found nor doing the work;
2. the intent-gate exemption names three tools, all of which write a question
   rather than a research record (`propose_hotspot_set` is **not** among them:
   it writes a domain row, and "pending" is not "changes nothing");
3. `resources/list` returns the app page rather than nothing — a host that
   cannot discover it cannot render it, and the page carries no project data;
4. `planner` gains `structure-interaction` in the served roster.

### Six-dimension acceptance

1. **Requirements.** One room per project carrying speech, handovers, tasks and
   decisions in one order; addressing a member; a question a person answers;
   residues proposed, confirmed and fed to a design job. What is deliberately
   absent: generated bot-to-bot dialogue, and any path from a tool to a
   confirmation.
2. **Logic.** Attribution is derived server-side in every path (`bot` on a
   message, `origin` on a set, `decided_by` on the entry an answer writes); a
   client cannot declare who decided. Ordering is a total keyset; delivery
   labels come from one table shared with the task list.
3. **Boundaries.** Unreadable cursor, question already settled, set already
   ruled on, retired operator, handle naming nobody, empty set, 200-residue
   "highlight", read-only project role, another project's row, missing
   `If-Match`, stale `If-Match`.
4. **Code quality.** Ruff and mypy clean over 281 files; ESLint no errors (three
   standing TanStack warnings); no new runtime dependency; the citation list was
   extracted rather than copied so the room and the chat cannot drift.
5. **Coverage.** 83 new backend test functions across seven files and 35 new
   frontend cases across four; total backend coverage 86.48% against the 85%
   gate; new modules measured at room 100%, `mcp_ui` 100%, `molviewspec` 98.1%,
   `decisions` 97.1%, `hotspots` 94.3%.
6. **Runtime.** The 74-case browser matrix passes with the new endpoints
   stubbed; migrations were exercised against a real PostgreSQL, including a
   full `downgrade base`; OpenAPI and the generated SDK regenerate idempotently.

### Evidence

| Check | Result |
| --- | --- |
| Backend suite | Green, exit 0, 0 failures (107 test files) |
| New backend tests | 83 functions: room 12, decisions 19, hotspots 12, MCP app 9, scene 8, structure view 7, HTTP routes 16 |
| Frontend suite | **129 files / 772 tests passed** |
| New frontend tests | 35 cases: room 14, mentions 9, hotspot panel 8, hotspot parameters 4 |
| Production build + bundle gate | Passed; entry 441.6 KiB / 750 KiB |
| ESLint | No errors; three existing TanStack Table warnings |
| Ruff / mypy | Passed; 281 source files |
| Browser vertical slice | **74/74** |
| Migration upgrade paths (PostgreSQL) | **8/8**, each with `alembic check` and `downgrade base` |
| Coverage gate | 86.48% total (gate 85%) |
| Flow matrix | 83 tables / 218 OpenAPI paths |
| Document inventory | 47 Markdown files, 29 active, OK |
| OpenAPI + generated SDK | Regeneration idempotent |
| Plugin CPU declarations / cluster claims | Passed / skipped (no LSF stages in this change) |

### Known boundaries

- **One DB-gated test fails against the developer stack's live database.**
  `test_package_import_adopts_a_user_project_with_matching_claim_lineage`
  adopts the PD1 project that the running local stack already holds, so the id
  it returns is not the one the test created. On a freshly migrated scratch
  database the file passes 3/3, which is what CI uses. Not caused by this change.
- **`check_plugin_catalog_drift.py` fails locally** on dev-only plugin rows in
  the live database; CI's migration-only database passes. Pre-existing.
- **The room has no browser-matrix case.** The matrix's route list is fixed, and
  adding a route to it is a separate change; the room is covered by unit tests
  and by the HTTP tests, not by a real-browser run.
- **No live-server run of the new endpoints.** The local stack runs the main
  checkout, not this worktree, so the endpoints were exercised through
  `TestClient` rather than through the deployed API.
- **`request_residue_selection` writes a decision request whose options are
  residue sets, but nothing yet turns an answered one into a hotspot set
  automatically.** A person confirms the set; the link between the two is the
  evidence reference, not an automatic write.
