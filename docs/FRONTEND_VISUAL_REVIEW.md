# Frontend visual review — 2026-09-14

状态：活跃

最后核验：2026-09-14（Asia/Shanghai）

权威范围：Bot 优先工作区的视觉层级复审与修复清单。

数据来源：渲染后的生产页面截图与本地 Bigo V2 视觉系统。

替代关系：是 [Bot 优先工作区](BOT_FIRST_WORKSPACE.md) 的视觉附录，不取代 [前端架构与 API 契约](FRONTEND_V2.md)。

The functional Bot-first workspace was clearer than the original, but its visual
hierarchy still resembled an administrative form. This follow-up reviews the
rendered production pages and adapts the local Bigo V2 system to an application.

## Repair checklist

| ID | Observed problem | Repair |
| --- | --- | --- |
| V1 | Oversized landing headline and team block push projects below the first screen. Duplicate creation actions compete. | Compact welcome, smaller type scale, concise team overview, single library creation entry. |
| V2 | Topbar is a dense row of outlined controls. Navigation lacks hierarchy. | Brand mark, quieter utility controls, icon/text navigation with underline selection and larger targets. |
| V3 | Tiny library heading; raw `all`/`recent` filter values; disconnected project actions. Sorting says created but uses updated time. | Strong title and real project count, localized labels and accurate updated-time wording, consistent controls, meaningful material icons and grouped actions. |
| V4 | Bot tasks resemble a parameter form. Input is weak; five service buttons leave an accidental orphan. | Prominent composer with integrated continuation, semantic service icons, balanced odd-count grid and distinct deliveries. |
| V5 | Roster repeats internal IDs and consumes the mobile screen. | Human-facing names, server descriptions on hover, compact desktop roster and horizontal mobile selector. |
| V6 | Project context, navigation and questions have little visual distinction. | Separate objective surface, material navigation label and readable question typography. |
| V7 | Chinese welcome uses the English project name; control sizing/focus is inconsistent; mobile user-menu trigger has no accessible name. | Project localization, named user menu, aligned corners/touch targets/focus and retained reduced-motion behavior. |
| V8 | Mobile screenshot review finds a three-row toolbar and another repeated project-name row. | Compact utility menu, two-row header, management shortcut next to the project selector, compact mobile team preview. Settings/tour have command regression tests; menu items and last Bot have browser keyboard coverage. |

## Validation plan

- Build and lint; run affected frontend regressions.
- Exercise the real 12-Bot / 5-service catalog with the deterministic production
  browser harness. No live model, compute or research-data writes.
- Inspect English/light and Chinese/dark screenshots, including mobile; check
  overflow through 2560px, keyboard navigation and task paths.
- Verify localized filters/context and preserve public provenance, permissions
  and interactive Mol* comparison.

## Final verification

All eight checklist items are repaired. Desktop English/light and Chinese/dark
pages and the mobile variants were inspected after the last visual adjustment.
The screenshots also informed a second pass that reduced composer whitespace,
grouped the library help action, and removed redundant mobile context.

| Dimension | Evidence |
| --- | --- |
| Requirement completeness | Projects, Bot collaboration, source-backed brief and Mol* comparison retain their existing paths. Project rows use meaningful metadata rather than arbitrary illustrations. |
| Logic | Localized filter values survive selection; sorting text matches updated-time order; utility actions open the intended state. |
| Boundaries | 320–2560px overflow checks, Chinese dark mode, keyboard access to the last mobile Bot, empty/error/read-only states and existing streaming/navigation races. |
| Code quality | Existing registry components and icon library; no new dependencies; scoped component styling, unchanged API/scientific data contracts. |
| Test coverage | **123 files / 720 frontend tests passed**; two additional utility-menu command cases. |
| Actual runtime | **16 production-browser scenario groups passed**, with the real FastAPI catalog of 12 Bots / 5 services and real Mol* rendering of labeled synthetic fixtures. Existing workflow browser gates: **10/10 passed**. |

TypeScript/build/bundle gate passed (entry **424.9 KiB**, limit 750 KiB).
ESLint has zero errors and the same three existing TanStack Table compiler
warnings. The public-data allowlist/checksum gate and `git diff --check` passed.

The browser uses deterministic API responses and one synthetic SSE chat reply;
it verifies the production frontend bundle, not a live model or deployed system.
No production service invocation or research-data edit is part of this change.

## Reproduce and inspect

From `frontend`, after exporting the backend catalog as documented in
`BOT_WORKSPACE_VERIFICATION.md`:

```sh
npm run build
npm test
npm run lint
BDA_BOT_TEST_CATALOG=/tmp/bda-review-catalog.json BDA_BOT_TEST_OUTPUT=/tmp/bda-visual-review npm run test:bot-workspace
node scripts/browser-workflow-gates.mjs
```

Browser images/report are generated under `/tmp/bda-visual-review`; the final
selected images are also retained locally in the ignored directory
`.superpowers/sdd/bot-visual-review/browser-artifacts/`. They include project and
Bot pages in both themes/languages, mobile layouts and the compact utility menu.

Publication target remains `bda-public`, branch
`codex/bot-first-science-workspace`; this change does not merge or deploy main.

## Local review of the role-based workspace — 2026-09-14

Reviewed in the in-app browser against a synthetic local API (harness fixtures,
the real six-operator catalog, synthetic tasks, a handoff with an unsupported
claim, pending claims and a compute draft) at 1440×900 and 390×844, light and
dark. No credentials, model calls or database writes were involved.

| ID | Finding | Repair |
| --- | --- | --- |
| R1 | Projects and Research logged a Base UI error on every visit: `Disclosure` and three accordions passed a new `defaultValue` array each render, which Base UI reads as a changed default | Stable module-level default arrays; the target-preparation panel decides its default once, on arrival |
| R2 | A new page opened at the previous page's scroll depth; on mobile Decisions opened half way down | Reset both the document and `<main>` scroll on route change |
| R3 | The Copilot drawer opened as a modal over every fresh session, covering the page that loaded | Closed by default; the top bar button opens it |
| R4 | Drawer model settings were offered to every role, unlike the Research team page | Shown only to project admins and owners |
| R5 | Drawer surfaces were named by function (Tasks / Chat / Chain / Agent runs / MCP) and Agent runs repeated Tasks | Tasks & deliverables / Conversation / Bot handoffs / External access; the duplicate run list is removed; a handoff to a retired id selects its successor |
| R6 | "Open Bot workspace", "Work with Bots" and "Bot workspace views" contradicted the Research team navigation | Renamed to the research team everywhere |
| R7 | The Projects team card showed `director` (not an operator) and generic steps | Shows the five working operators and their responsibilities |
| R8 | With five task owners the first spanned the grid and read as a heading | Removed the odd-count full-width rule |
| R9 | Research showed "Copilot: <tab>" beside the team link, an unclear second entry point | "Ask about <tab>", stating what it does |
| R10 | Compute drafts showed the raw backend id `lsf` | Named in words (LSF cluster) |
| R11 | Research team repeated its page title as the roster heading | Roster heading is Team members |
