# Bot-first science workspace

状态：活跃

最后核验：2026-09-14（Asia/Shanghai）

权威范围：Bot 优先工作区的诊断、设计、实现清单与验收记录。

数据来源：`codex/bot-first-science-workspace` 分支的前端代码、浏览器验收脚本与公开 PD1 演示包。

替代关系：不取代 [前端架构与 API 契约](FRONTEND_V2.md)；Bot 名册与职责边界以 [Copilot Bot Roster](COPILOT_BOT_ROSTER.md) 为准。

Status: implemented and reviewed · 2026-09-14

Branch: `codex/bot-first-science-workspace`

## Diagnosis and design

The project library's Open action only selects a project. Research lives behind
a second action. The home page mixes portfolio browsing with target preparation,
workflow metrics and assistant onboarding. Decorative structure previews do not
communicate project purpose. The goal tree is independent of imported research
briefs, so imported projects appear to have no objective. Long reviews repeat the
reference catalog before readers reach individual evidence records.

The new hierarchy is **Projects → project brief / Bots → evidence, structures,
plans and decisions**. Projects remain the scope of every conversation and task.
Bots have a full page, a real server-provided roster, task deliverables and a
handoff record. Existing execution checks and scientific provenance remain.

Visual direction follows the supplied Bigo V2: bone #F3F0E8, ink #171A16,
lime #D3ED70, coral/cyan supporting accents, fine rules, restrained corners,
readable metadata and motion only for interaction or actual activity. Dark mode
uses the same hierarchy. No arbitrary generated project illustrations.

References consulted on 2026-09-14:

- [Grok Bot design, 2026-09-03](https://x.ai/news/designing-grok-bot): persistent
  roster, identity and state, progressively revealed activity.
- [Linear Agent](https://linear.app/changelog/2026-03-24-introducing-linear-agent):
  project context and inspectable outcomes.
- [Notion Agents](https://www.notion.com/product/agents): goal-based assignment,
  visible responsibilities and scoped permissions.
- User-supplied **Bigo.bio visual system V2**, dated 2026-09-14.

These inform interaction choices; no external artwork or product code is copied.

## Implementation and acceptance

1. [x] Align shared colors, surfaces, typography and responsive navigation.
2. [x] Replace portfolio illustrations with readable project rows, concise
   objectives, source-backed counts, search/reset and direct Open navigation.
3. [x] Introduce a full-page Bot workspace using the existing roster, chat,
   durable task API and actual handoff records. Preserve project scoping.
4. [x] Present the public PD1 package as a client-readable brief: objective,
   questions, deliverables, provenance. For other projects use stored content;
   never invent completed goals, experimental results or agent activity.
5. [x] Reduce repeated research prose, keep full source documents accessible,
   and add an interactive structure comparison workspace.
6. [x] Run meaningful regression tests, type checking, lint, production build
   and browser adversarial checks; inspect light/dark and Chinese/English
   layouts, keyboard navigation, narrow widths, empty/error/read-only states.
7. [x] Fix findings, document verification and limitations, commit changes.

## Public content scope

The approved public package contains one project (PD1), twelve references and
four source structures. The private overlay is outside this content pass.
Presentation changes retain the versioned source data and all citations. Brief
questions derived from the package are labelled as brief content, not persisted
goal records. Missing data is explicit and recoverable. Dataset publication,
live compute, production deployment and private-data synchronization are not
needed for this frontend branch.

## Verification record

- Production build and TypeScript: passed. Entry chunk 395.2 KiB, below the 750 KiB gate.
- ESLint: no errors; three pre-existing TanStack Table compiler warnings remain in laboratory components.
- Vitest: 122 files / 691 tests passed.
- Bot workspace browser acceptance: seven scenario groups, including direct Open and Back, brief content, two real Mol* viewers with synthetic PDB fixtures, unsent source-scoped Bot drafts, roster selection, keyboard tabs, read-only controls, empty projects and roster retry. No backend mutations or uncaught browser errors.
- Responsive checks: Bot page at 320/390/768/1024/1440/1920/2560px; Chinese brief at 320/390/768/1024/1440px; project list at 320/390/768px; structure comparison at 390px. Light English and dark Chinese screenshots inspected.
- Existing workflow browser gates: 10/10 passed, including graph editing, preview, source selection, versioned release and mobile layout.
- Existing production browser matrix: Workflow, Candidates and Results, desktop English/light: 3/3 passed.
- `git diff --check`: passed. The approved public JSON package and synthetic fixtures are unchanged; no private research files were added.
- Public data allowlist: passed, including checksums for the six synthetic fixtures. The feature branch is based directly on public main `fa7520be`, with no private overlay history.

Adversarial findings resolved:

| Finding | Repair |
| --- | --- |
| Open only selected a project | Link directly to the project's goals route; URL is the source of project context |
| Imported brief and saved goal tree disconnected | Show the source-derived public brief above editable saved questions; label the distinction |
| Global unsent draft and entity IDs survived a project switch | Clear transient context when project changes; retain per-project conversation history |
| Viewer/demo users could operate goal editing controls | Disable creation, deletion, status and link edits; guard submit; show retryable API failures |
| Dark/light semantic badges lacked contrast | Set legible light-theme status foregrounds and preserve dark-theme semantic colors |
| Small-screen header and Bot tabs overflowed | Wrap header actions, constrain project label, wrap tabs and reflow workspace columns |
| Task view could unexpectedly consume a structure discussion draft | Keep task and conversation surfaces separate while retaining the unsent draft |
| Full reviews and method documents buried actionable content | Default to concise brief and evidence records, with full source documents expandable |

## Reproduce

From `frontend`:

```sh
npm ci
npm run build
npm run lint
npm test
npm run test:bot-workspace
node scripts/browser-workflow-gates.mjs
BDA_BROWSER_ROUTES=workflow,candidates,results BDA_BROWSER_APPEARANCES=en-light BDA_BROWSER_STATES=populated npm run test:browser
```

The Bot test starts a production preview on port 4188; set `BDA_BOT_TEST_ORIGIN`
to use an existing server. Screenshots and the JSON result are written to
`/tmp/bda-bot-workspace` by default, configurable with `BDA_BOT_TEST_OUTPUT`.
The browser API and structures are explicitly synthetic QA fixtures. Real model
credentials, external retrieval, persisted database writes and production
compute were not invoked by these checks.

## Presentation boundaries

The public PD1 brief is an editorial reading of the existing package objective,
questions and scope. It does not create or mark database goals complete.
Other projects display their stored objective/summary. The Bot roster and
handoff record use the existing server APIs; avatars do not invent activity.
Structure comparison presents independent cameras, not computed alignment.
Advanced workflows and the contextual drawer remain reachable. No production
deployment or private project content migration is included in this branch.

## Iteration 2 — continuous research navigation

The second review followed a complete user journey: open a public question,
prepare a Bot conversation, inspect project materials, and return to a task's
deliverable. The implementation addresses the breaks found along that path:

- Every source-derived public brief question has a **Discuss with a Bot** action.
  It prepares an editable draft with source-citation requirements, resets stale
  source selections, and uses auto-match. Navigation does not invoke a model.
- Conversation input, source selections and full-page task drafts are scoped to
  the project. Switching tabs or visiting project materials preserves them.
  These are memory-only drafts: page reload clears unsent work, while the task
  detail URL survives reload. Project deletion and sign-out clear draft state.
- Task details use `/bots?project=…&view=tasks&run=…`. Opening, browser Back,
  reloading, and returning from project materials all resolve the same task.
  A run must belong to the current project before its transcript is requested
  or its delivery actions are rendered.
- Failed service, readiness, task-list and task-detail reads offer local retry.
  An unavailable suggested service has an explicit fallback. Turn and budget
  limits validate the server's integer ranges before enabling task start.
- Chat waits for project resolution before showing its composer or sending an
  initial question. A response finishing after a project switch only clears
  source context in its originating project.
- The pipeline now marks the actual page as **You are here** and separately
  labels the project's progress. Previously Research could be selected while
  Results incorrectly carried the location caption.

The browser suite now includes eleven scenario groups. New checks cover an
unsent brief-question handoff, draft round trips, durable task links, and task
retry. Browser fixtures remain explicitly synthetic; no model, database write,
external retrieval or compute was invoked. The new brief and task-delivery
screenshots are included in the existing `/tmp/bda-bot-workspace` output.

Final validation for iteration 2:

- Full Vitest regression: **122 files / 700 tests passed**.
- Production TypeScript/build and bundle gate passed (entry 397.8 KiB).
- ESLint passed with the same three existing TanStack Table warnings, no errors.
- Browser acceptance: **11/11 scenario groups passed**, including responsive
  layouts, project-location captions, real Mol* fixture rendering and task retry.
- Public-data allowlist/checksums and `git diff --check` passed. Public source
  package data and model/backend contracts are unchanged.

## Six-dimension audit

The follow-up [verification and repair checklist](BOT_WORKSPACE_VERIFICATION.md)
records requirements, logic, boundary cases, code quality, test coverage and
runtime evidence, including streaming races and the full backend Bot catalog.

## Iteration 3 — tasks are assigned to an owner

Branch: `claude/bot-task-assignment`, from `codex/bot-first-science-workspace`.

The task composer asked the person to pick a *service* (brief, literature,
planning, execution, interpretation) — a split by function that ran parallel to
the Bot roster, so a task had no operator answering for it. The composer now
asks **who should own this**:

- The roster declares ownership. Each recipe in `task_contracts.SERVICES` has
  exactly one producing owner (`BotSpec.task_service`), checked at import; see
  [Guided task ownership](COPILOT_BOT_ROSTER.md#guided-task-ownership).
  `/copilot/bots` serves `task_service` and `task_write_tools`.
- The client sends `bot` with the owner's `service_kind`. The server refuses a
  recipe started under a bot that does not own it (`copilot_task_owner_mismatch`),
  because `bot ∩ recipe` would otherwise silently strip the operator's own tools.
- Only writes the owner can be granted are offered. The Research page's literature
  task therefore no longer asks to save notes: note authoring belongs to Archivist.
- A goal suggests an owner (a named trigger first, then the keyword guess); the
  person can reassign it. Reviewers and the director are never offered as owners.
- Tasks are listed under their owner in roster order; runs started without an
  owner are grouped last. A task's detail shows its owner.
- A roster failure is explained once in the composer and recovers through Retry.

Operators without a recipe (Scout, Structuralist, Medic, Archivist, Conductor,
Steward, Auditor) keep working through conversation, handoffs and delegation.
Per-bot pages, a decision inbox and role-based navigation are later steps.

## Iteration 4 — a responsibility page per Bot

Branch: `claude/bot-role-pages`, stacked on iteration 3.

Choosing someone in the roster used to change the conversation's scope and
nothing else, so the roster read as a setting. Each operator now has a page at
`/bots/:botId?project=…`:

- **Mandate and refusals** — the charter the operator works under.
- **Guided tasks** — the recipe it owns and an *Assign a task* action that only
  prepares the composer with this owner (plan, writes and budget are still
  reviewed there). Operators without a recipe offer a scoped conversation.
- **Tasks it holds** — runs whose `bot` is this operator, delegated child runs
  marked, each opening inline at a durable `run=` URL.
- **Handoffs** — records received and sent, using the Chain view's cards.
- **Works with** — hands off to, reviewed by, reviews and directs, each linking to
  that operator's page; **Workbenches** link to the pages its work lives on
  (`features/copilot/bots/workbenches.ts`, the one frontend-owned mapping).
- **Conversation** — the chat, scoped to this operator on entry.

The roster is shared by the overview and every Bot page; named operators are
links (`aria-current="page"`), Auto-match stays an action. The overview keeps
Tasks, auto-match Conversation and Handoffs; a Bot-scoped chat there links to its
page or switches back to auto-match. Owner headings in the task list link to the
owner's page. No backend or API change.

## Iteration 5 — what waits on a person, and navigation by role

Branch: `claude/decision-inbox`, stacked on the six-operator roster.

Bots prepare, draft and claim; a few things only a person may settle, and they
were spread over the task list, the workflow inspector, the literature panel and
the handoff record. `/inbox` (**待我决定 / Decisions**) gathers them per project
and links to where each decision is made. It decides nothing itself and adds no
endpoint:

- **Needs your input** — top-level tasks whose delivery is `needs_input` or
  `blocked`, opening at the owner's page (`/bots/:owner?run=…`); runs recorded
  under a retired id open at the operator that absorbed it.
- **Ready for your review** — `completed`, `partial` or `review_required`
  deliveries, newest first, capped with a link to the full task list.
- **Compute drafts to confirm** — drafts still in `draft`, linking to Workflow,
  with the reminder that Auditor can check declared resources first.
- **Literature claims to review** — the count of `pending` extracted claims,
  linking to Research → Literature & evidence.
- **Claims without evidence** — handovers carrying an `unsupported` claim,
  linking to the recipient's page.

Each source loads, fails and retries on its own; the all-clear message appears
only when every source has been read. Live runs and delegated child runs are
excluded, because a child reports through its parent.

The main navigation now reads by who acts: **Projects · Decisions · Research
team · Research**. Workflow, Candidates, Lab, Results and Timeline sit under a
**Workbenches** menu on desktop; on small screens every route remains a link.
The Bots overview is titled **Research team**. There is no count badge in the
top bar, so no route issues extra requests on arrival.
