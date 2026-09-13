# Bot workspace verification — 2026-09-14

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
