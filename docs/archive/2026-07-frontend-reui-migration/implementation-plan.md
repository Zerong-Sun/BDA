# Frontend REUI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every user-visible component and dashboard in `frontend/` with documented shadcn and ReUI compositions while preserving the BDA v2 behavior contract.

**Architecture:** Establish a root-level registry layer (`components/ui`, `components/reui`) and a semantic application-composition layer (`src/components`, `src/features`). Migrate shared primitives first, then route families in vertical slices, using one ReUI Frame surface throughout and ReUI Data Grid for every table.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Tailwind CSS 4, shadcn aria style, ReUI, TanStack Query/Table, Zustand, Vitest, Testing Library, Playwright.

## Global Constraints

- Preserve all routes, API contracts, query keys, Zustand ownership, ETag/idempotency/upload/SSE behavior, English/Chinese localization, React Flow, and Mol* behavior.
- Use one ReUI `frame` surface across all dashboard screens; do not mix ReUI Frame and shadcn Card surface archetypes.
- Use only ReUI component names, props, variants, and imports returned by MCP APIs or installed examples.
- Use Phosphor icons consistently.
- Do not edit vendored ReUI component internals after installation; adapt via documented props and application compositions.
- All implementation work follows red-green-refactor.
- Test commands set `TMPDIR=/tmp` to avoid the inherited unavailable Windows temporary directory.
- The existing `.git` metadata is read-only. Do not block on commits; record changed files and verification in the SDD ledger.
- Preserve the user's pre-existing changes in `frontend/.gitignore`, `frontend/package.json`, `frontend/src/index.css`, `frontend/tsconfig.json`, `frontend/components.json`, `frontend/components/`, `frontend/lib/`, `frontend/bun.lock`, and `frontend/.opencode/`.
- Third-party native-control exceptions are limited to hidden file inputs and DOM required by React Flow, Mol*, or browser upload APIs.

---

### Task 1: Registry foundation and migration guardrails

**Files:**
- Modify: `frontend/components.json`
- Modify: `frontend/tsconfig.app.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/index.css`
- Modify: `frontend/eslint.config.js`
- Create: `frontend/src/test/reuiMigrationAudit.test.ts`
- Install: `frontend/components/reui/{frame,data-grid,filters,stepper,timeline,badge,alert,autocomplete,sortable,icon-tile,icon-stack}.tsx` and their registry dependencies
- Install: shadcn Button, Input, Textarea, Label, Select, Checkbox, Switch, Tabs, Tooltip, Accordion, Dialog, AlertDialog, Sheet, Drawer, DropdownMenu, Popover, Command, ScrollArea, Separator, Skeleton, Progress, Avatar, Breadcrumb, and Sonner

**Interfaces:**
- Produces: `@/components/ui/*`, `@/components/reui/*`, and `@/lib/utils` imports resolvable by TypeScript, Vite, Vitest, and ESLint.
- Produces: semantic ReUI color tokens `success`, `info`, `warning`, `destructive-foreground`, `invert`, and paired foreground tokens.
- Produces: a foundation audit that validates registry configuration, aliases, tokens, and installed controls. Task 8 expands this same file into the final legacy/raw-UI completion audit.

- [ ] **Step 1: Write the failing alias and migration audit**

Create `src/test/reuiMigrationAudit.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')

describe('REUI migration guardrails', () => {
  it('has one valid @reui registry and root alias', () => {
    const components = JSON.parse(readFileSync(resolve(root, 'components.json'), 'utf8'))
    const tsconfig = JSON.parse(readFileSync(resolve(root, 'tsconfig.app.json'), 'utf8'))
    expect(Object.keys(components.registries)).toEqual(['@reui'])
    expect(tsconfig.compilerOptions.paths['@/*']).toEqual(['./*'])
  })
})
```

- [ ] **Step 2: Run the focused test and verify red**

Run:

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/test/reuiMigrationAudit.test.ts
```

Expected: FAIL because `tsconfig.app.json` has no `@/*` path.

- [ ] **Step 3: Repair registry and aliases**

Keep one `registries` key in `components.json`. Add to `tsconfig.app.json`:

```json
"baseUrl": ".",
"paths": { "@/*": ["./*"] }
```

Add to `vite.config.ts` before the vendor aliases:

```ts
{ find: '@', replacement: vendorAlias('./') },
```

Move `buttonVariants` to `components/ui/button-variants.ts` so Fast Refresh lint sees component-only exports.

- [ ] **Step 4: Install registry components and worked examples**

Dry-run first, then install without overwrite:

```bash
npx shadcn@latest add @reui/frame @reui/data-grid @reui/filters @reui/stepper @reui/timeline @reui/badge @reui/alert @reui/autocomplete @reui/sortable @reui/icon-tile @reui/icon-stack --yes
npx shadcn@latest add @reui/c-data-grid-3 @reui/c-filters-1 @reui/c-stepper-4 @reui/c-timeline-4 @reui/c-autocomplete-4 @reui/c-sortable-1 @reui/c-alert-12 --yes
npx shadcn@latest add button input textarea label select checkbox switch tabs tooltip accordion dialog alert-dialog sheet drawer dropdown-menu popover command scroll-area separator skeleton progress avatar breadcrumb sonner --yes
```

If the package runner cannot reach the registry inside the sandbox, rerun with network approval. Do not use `--overwrite`.

- [ ] **Step 5: Normalize semantic tokens**

Merge the current BDA theme into the shadcn/ReUI token contract in `src/index.css`; map existing warm brand values to `primary`, `accent`, and semantic statuses. Define:

```css
--success: var(--success);
--success-foreground: var(--background);
--info: var(--info);
--info-foreground: var(--background);
--warning: var(--warning);
--warning-foreground: var(--background);
--destructive-foreground: var(--background);
--invert: var(--foreground);
--invert-foreground: var(--background);
```

Use distinct internal BDA variable names if self-referential names conflict.

- [ ] **Step 6: Verify foundation**

Run:

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/test/reuiMigrationAudit.test.ts
./node_modules/.bin/tsc -b
./node_modules/.bin/eslint components lib src/test/reuiMigrationAudit.test.ts
```

Expected: focused test, typecheck, and lint PASS.

---

### Task 2: Shared UI, shell, overlays, and status language

**Files:**
- Create: `frontend/src/components/ui/statusBadge.tsx`
- Create: `frontend/src/components/ui/AppFrame.tsx`
- Modify: `frontend/src/components/ui/{ApiState,AppSettingsDrawer,BackendHealthBanner,Button,Card,CopilotDrawer,Divider,DrawerShell,FAQAccordion,GlossaryTooltip,HelpMenu,Input,InterpretationCard,MetricCard,NextStep,PageHead,PipelineRail,Row,Skeleton,StatusPill,Tabs,Toast,Topbar,UserMenu}.tsx`
- Modify: `frontend/src/components/ui/{Topbar,FAQAccordion,ErrorBoundary}.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/i18n/ErrorBoundaryFallback.tsx`

**Interfaces:**
- Produces: `StatusBadge({ status, label })` with exhaustive typed variants.
- Produces: `AppFrame` around ReUI `Frame`/`FramePanel` for application panels.
- Preserves: existing legacy export names temporarily so domain tasks can migrate independently; every wrapper delegates to registry primitives.

- [ ] **Step 1: Add failing shared-component contract tests**

Extend the shared UI tests:

```tsx
it('renders status through the ReUI badge contract', () => {
  render(<StatusPill tone="success">Ready</StatusPill>)
  expect(screen.getByText('Ready')).toHaveAttribute('data-slot', 'badge')
})

it('closes the settings sheet with Escape', async () => {
  renderWithProviders(<AppSettingsDrawer />)
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run focused tests and verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/components/ui/Topbar.test.tsx src/components/ui/FAQAccordion.test.tsx src/features/stage6VerticalSlice.test.tsx
```

Expected: FAIL because the current components do not expose registry slots/focus behavior.

- [ ] **Step 3: Implement shared registry compositions**

Replace:

- legacy Button/Input/Tabs/Divider/Skeleton with shadcn exports or thin compatibility adapters;
- Card/MetricCard/InterpretationCard/PageHead/NextStep with `AppFrame`;
- StatusPill with ReUI Badge using typed variant maps;
- API and health states with ReUI Alert;
- FAQ with shadcn Accordion in Frame;
- Glossary with Tooltip;
- drawers with Sheet/Drawer;
- user/help menus with DropdownMenu;
- Toast store rendering with Sonner while preserving `useToastStore` call sites until Task 9;
- PipelineRail with controlled ReUI Stepper.

Keep the outer shell:

```tsx
<div className="flex min-h-screen min-w-0 flex-col bg-background text-foreground">
  <Topbar />
  <div className="flex min-h-0 flex-1 overflow-hidden">
    <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
      <Outlet />
    </main>
  </div>
</div>
```

- [ ] **Step 4: Verify shared UI**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/components/ui src/features/stage6VerticalSlice.test.tsx
./node_modules/.bin/tsc -b
```

Expected: PASS.

---

### Task 3: Public routes, guide, projects, and experiments dashboard

**Files:**
- Modify: `frontend/src/app/{Login,Guide,FAQ,Experiments}.tsx`
- Modify: `frontend/src/features/guide/*.tsx`
- Modify: `frontend/src/features/projects/*.tsx`
- Modify: `frontend/src/features/experiments/*.tsx`
- Modify: `frontend/src/app/{Login,FAQ}.test.tsx`
- Modify: `frontend/src/features/guide/guideContent.test.ts`
- Modify: `frontend/src/features/experiments/{WorkflowProgress,TargetStructureOverlay}.test.tsx`

**Interfaces:**
- Consumes: `AppFrame`, registry Button/Input/Select/Dialog/Sheet/Accordion/Stepper/Badge/Alert/IconTile/IconStack.
- Produces: all public, project-selection, and experiment surfaces free of raw controls except hidden file inputs.

- [ ] **Step 1: Add failing route interaction tests**

Add assertions:

```tsx
expect(screen.getByRole('button', { name: /sign in/i })).toHaveAttribute('data-slot', 'button')
expect(screen.getByRole('region', { name: /workflow progress/i })).toContainElement(
  screen.getByRole('tab', { name: /design/i }),
)
```

- [ ] **Step 2: Verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/app/Login.test.tsx src/app/FAQ.test.tsx src/features/experiments/WorkflowProgress.test.tsx
```

- [ ] **Step 3: Migrate public and guide surfaces**

Use Frame for page sections, shadcn form controls for login, Accordion for FAQ, controlled Stepper for guide progress, and Icon Tile/Stack only where the icon communicates an actual workflow step or empty state.

- [ ] **Step 4: Migrate project and experiment surfaces**

Use Frame for project library/active project/overview, Dialog/Sheet for create/manage/structure overlay, Select/Autocomplete based on option-count rules, Badge for status, and Alert/Skeleton/empty states for queries.

- [ ] **Step 5: Verify the route family**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/app/Login.test.tsx src/app/FAQ.test.tsx src/features/guide src/features/experiments
./node_modules/.bin/tsc -b
```

Expected: PASS.

---

### Task 4: Workflow builder dashboard

**Files:**
- Modify: `frontend/src/app/Workflow.tsx`
- Modify: `frontend/src/features/workflow/*.tsx`
- Modify: `frontend/src/features/plugins/ParameterSchemaForm.tsx`
- Modify: `frontend/src/features/jobs/JobStatusDrawer.tsx`
- Modify: `frontend/src/features/workflow/{WorkflowToolbar,workflowMapper}.test.tsx`
- Create: `frontend/src/features/workflow/WorkflowChrome.test.tsx`

**Interfaces:**
- Consumes: Frame, Button, Input, Textarea, Select, Checkbox, Tabs, Sheet, ScrollArea, Badge, Alert, Stepper, Timeline, Sortable.
- Preserves: React Flow node/edge/canvas state and all workflow submission behavior.

- [ ] **Step 1: Write failing chrome tests**

```tsx
it('uses registry controls around the workflow canvas', () => {
  renderWithProviders(<WorkflowToolbar {...props} />)
  expect(screen.getByRole('button', { name: /run/i })).toHaveAttribute('data-slot', 'button')
})

it('renders ordered script assets with sortable semantics', () => {
  renderWithProviders(<ScriptAssetManager {...props} />)
  expect(screen.getByRole('button', { name: /drag/i })).toHaveAttribute('data-slot', 'sortable-item-handle')
})
```

- [ ] **Step 2: Verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/features/workflow/WorkflowChrome.test.tsx src/features/workflow/WorkflowToolbar.test.tsx
```

- [ ] **Step 3: Migrate workflow page chrome**

Keep `WorkflowCanvas`, `WorkflowNode`, and `WorkflowEdge` integration internals. Replace toolbar, context bar, compute strip, sidebar, inspector, node builder, plugin registry, and script asset markup with registry controls inside Frame.

- [ ] **Step 4: Migrate parameter forms and job activity**

Map JSON schema types to shadcn controls. Use Sheet for job detail and ReUI Timeline for logs/status transitions. Preserve numeric bounds, enums, validation, mutation disabling, and retry behavior.

- [ ] **Step 5: Verify workflow**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/app/layer8ProductContract.test.tsx src/features/workflow src/features/plugins
./node_modules/.bin/tsc -b
```

Expected: PASS.

---

### Task 5: Candidates and results data dashboards

**Files:**
- Modify: `frontend/src/app/{Candidates,Results}.tsx`
- Modify: `frontend/src/features/candidates/*.tsx`
- Modify: `frontend/src/features/results/*.tsx`
- Create: `frontend/src/features/candidates/CandidateDataGrid.test.tsx`
- Create: `frontend/src/features/results/ValidationDataGrid.test.tsx`
- Modify: existing candidate/results tests

**Interfaces:**
- Produces: TanStack Table instances passed as `table` to ReUI Data Grid with `recordCount`.
- Produces: ReUI Filters state created only through `createFilter`.
- Preserves: candidate selection, comparison, bulk delivery, validation, upload, download, and structure-viewer behavior.

- [ ] **Step 1: Add failing grid and filter tests**

```tsx
it('sorts and selects candidates through ReUI Data Grid', async () => {
  renderWithProviders(<CandidateTable {...props} />)
  expect(screen.getByRole('table')).toHaveAttribute('data-slot', 'data-grid-table')
  await userEvent.click(screen.getByRole('checkbox', { name: /select candidate/i }))
  expect(onSelect).toHaveBeenCalled()
})

it('creates typed filters with stable ids', async () => {
  render(<CandidateFilters {...props} />)
  await userEvent.click(screen.getByRole('button', { name: /add filter/i }))
  expect(screen.getByTestId('candidate-filters')).toHaveAttribute('data-slot', 'filters')
})
```

- [ ] **Step 2: Verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/features/candidates/CandidateDataGrid.test.tsx src/features/results/ValidationDataGrid.test.tsx
```

- [ ] **Step 3: Implement candidate grid and filters**

Build `useReactTable` with stable candidate row IDs, sorting, selection, and existing pagination state. Render:

```tsx
<DataGrid
  table={table}
  recordCount={recordCount}
  isLoading={isLoading}
  emptyMessage={emptyState}
  tableLayout={{ dense: true, headerSticky: true, columnsResizable: true }}
>
  <DataGridContainer>
    <DataGridTable />
  </DataGridContainer>
  <DataGridPagination />
</DataGrid>
```

Use ReUI Filters fields for status, source, method, and score ranges; translate filter values into the existing query parameters.

- [ ] **Step 4: Implement results grid and panels**

Move validation to the same Data Grid contract. Use one divided/stacked Frame for metrics, Frame for interpretations/delivery/upload, Alert for failures, and layout-matching Skeletons.

- [ ] **Step 5: Verify candidate/results behavior**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/app/layer8ProductContract.test.tsx src/features/candidates src/features/results
./node_modules/.bin/tsc -b
```

Expected: PASS.

---

### Task 6: Research intelligence dashboard

**Files:**
- Modify: `frontend/src/app/Research.tsx`
- Modify: `frontend/src/features/research/*.tsx`
- Create: `frontend/src/features/research/ResearchDataGrids.test.tsx`
- Modify: `frontend/src/app/researchPage.test.tsx`
- Modify: existing research tests

**Interfaces:**
- Consumes: Frame, Tabs, Data Grid, Filters, Autocomplete, Button, Input, Textarea, Select, Dialog, Sheet, Badge, Alert, Timeline, ScrollArea.
- Preserves: evidence provenance, review intent, campaign, knowledge, literature, target-intelligence, Copilot import, markdown, ETag, and conflict behavior.

- [ ] **Step 1: Add failing research surface tests**

```tsx
it('renders research navigation with registry tabs', () => {
  renderWithProviders(<ResearchPage />)
  expect(screen.getByRole('tablist')).toHaveAttribute('data-slot', 'tabs-list')
})

it('renders datasets and targets with ReUI grids', () => {
  renderWithProviders(<ResearchWorkspacePanel />)
  expect(screen.getAllByRole('table')).not.toHaveLength(0)
  for (const table of screen.getAllByRole('table')) {
    expect(table).toHaveAttribute('data-slot', 'data-grid-table')
  }
})
```

- [ ] **Step 2: Verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/app/researchPage.test.tsx src/features/research/ResearchDataGrids.test.tsx
```

- [ ] **Step 3: Migrate research navigation and workspace tables**

Use shadcn Tabs for the five research views. Replace every dataset/target table with a typed ReUI Data Grid. Preserve download, search, assertion filtering, selection, and Copilot context actions.

- [ ] **Step 4: Migrate research panels**

Convert Literature, Knowledge, Target Intelligence, Project Review, Generate Similar Research, Campaign, and Decision Review to Frame compositions and registry form controls. Use Timeline for review/activity history and Badge for review state.

- [ ] **Step 5: Verify research**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/app/researchPage.test.tsx src/features/research
./node_modules/.bin/tsc -b
```

Expected: PASS.

---

### Task 7: Copilot, artifacts, PDB/Mol* controls, and tour

**Files:**
- Modify: `frontend/src/features/copilot/*.tsx`
- Modify: `frontend/src/features/artifacts/*.tsx`
- Modify: `frontend/src/features/pdb-viewer/*.tsx`
- Modify: `frontend/src/features/tour/TourOverlay.tsx`
- Modify: affected existing tests

**Interfaces:**
- Consumes: Frame, Sheet, ScrollArea, Button, Input, Textarea, Select, ToggleGroup, Progress, Alert, Skeleton, Badge, Stepper, Dialog/Popover.
- Preserves: chat streaming, settings, artifact two-stage upload, structure viewing, Mol* lifecycle, and tour preparation/navigation.

- [ ] **Step 1: Add failing registry-boundary assertions**

```tsx
expect(screen.getByRole('textbox', { name: /message/i })).toHaveAttribute('data-slot', 'input')
expect(screen.getByRole('button', { name: /next/i })).toHaveAttribute('data-slot', 'button')
expect(screen.getByRole('dialog')).toHaveAttribute('data-slot', 'dialog-content')
```

- [ ] **Step 2: Verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/features/copilot/CopilotChat.test.tsx src/features/tour/TourOverlay.test.tsx src/features/pdb-viewer
```

- [ ] **Step 3: Migrate Copilot and artifact surfaces**

Use Sheet + ScrollArea for chat, Frame for messages/settings/drafts, registry controls for input/actions, matching Skeletons for streaming/loading, and Alert for recoverable errors. Keep the native hidden file input behind a styled Button/label trigger.

- [ ] **Step 4: Migrate viewer controls and tour**

Keep Mol*/React rendering hosts unchanged. Replace surrounding selectors/actions/states with registry components. Use controlled Stepper plus Dialog/Popover for the tour.

- [ ] **Step 5: Verify secondary domains**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/features/copilot src/features/artifacts src/features/pdb-viewer src/features/tour
./node_modules/.bin/tsc -b
```

Expected: PASS.

---

### Task 8: Remove compatibility UI and close all migration exceptions

**Files:**
- Modify/delete: `frontend/src/components/ui/*`
- Modify: every remaining importer under `frontend/src`
- Modify: `frontend/src/test/reuiMigrationAudit.test.ts`
- Modify: `frontend/eslint.config.js`

**Interfaces:**
- Produces: no duplicate legacy upper-case primitives.
- Produces: no raw application controls/tables outside explicit third-party integration boundaries.
- Produces: imports directly from root registry paths or focused semantic application wrappers.

- [ ] **Step 1: Strengthen the audit to fail on legacy/raw UI**

Add recursive source scanning:

```ts
const forbiddenLegacy = [
  'Button.tsx', 'Card.tsx', 'Divider.tsx', 'DrawerShell.tsx',
  'Input.tsx', 'Skeleton.tsx', 'Tabs.tsx',
]

expect(existingLegacyFiles).toEqual([])
expect(rawTables).toEqual([])
expect(rawControlsOutsideExceptions).toEqual([])
```

The exception allowlist contains only exact hidden-file-input and third-party integration files with a reason string.

- [ ] **Step 2: Run the audit and verify red**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run src/test/reuiMigrationAudit.test.ts
```

Expected: FAIL listing remaining legacy files/raw controls.

- [ ] **Step 3: Migrate remaining imports and delete compatibility files**

Replace all remaining legacy imports, remove unused wrappers, convert raw controls reported by the audit, and keep only semantic application wrappers (`AppFrame`, `StatusBadge`, API/error compositions) that add product meaning.

- [ ] **Step 4: Run static audits**

```bash
rg -n '<table|<button|<input|<select|<textarea' src --glob '*.tsx' --glob '!**/*.test.tsx'
rg -n "components/ui/(Button|Card|Divider|DrawerShell|Input|Skeleton|Tabs)" src
TMPDIR=/tmp ./node_modules/.bin/vitest run src/test/reuiMigrationAudit.test.ts
```

Expected: only allowlisted native integration matches; audit PASS.

---

### Task 9: Full verification, browser QA, and REUI audit

**Files:**
- Modify: `frontend/scripts/browser-vertical-slice.mjs`
- Modify: tests or UI files only for defects reproduced by a failing test
- Create: `.superpowers/sdd/2026-07-26-frontend-reui-migration/final-verification.md`

**Interfaces:**
- Produces: final evidence for build, lint, tests, routes, responsive behavior, accessibility, scrolling, theme, reduced motion, and console cleanliness.

- [ ] **Step 1: Get and apply the REUI audit checklist**

Call `get_audit_checklist` for Data Grid and the general application. Record each security, accessibility, scroll, reuse, density, state, and responsive check in the verification report.

- [ ] **Step 2: Validate documented component usage**

Call `validate_usage` for all installed ReUI items and used props, including:

```json
{
  "components": [
    { "name": "frame", "props": ["variant", "spacing", "stacked", "dense"] },
    { "name": "data-grid", "props": ["table", "recordCount", "isLoading", "emptyMessage", "tableLayout"] },
    { "name": "filters", "props": ["filters", "fields", "onChange"] },
    { "name": "stepper", "props": ["value", "onValueChange"] },
    { "name": "timeline", "props": ["orientation"] },
    { "name": "sortable", "props": ["value", "onValueChange", "getItemValue"] }
  ]
}
```

Fix every undocumented use before continuing.

- [ ] **Step 3: Run the complete automated suite**

```bash
TMPDIR=/tmp ./node_modules/.bin/vitest run --maxWorkers=2
./node_modules/.bin/eslint .
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```

Expected: all PASS with no warnings attributable to application code.

- [ ] **Step 4: Run browser vertical slices**

Start Vite with the existing API/MSW test setup and run:

```bash
TMPDIR=/tmp node scripts/browser-vertical-slice.mjs
```

Cover `/login`, `/guide`, `/experiments`, `/workflow`, `/candidates`, `/results`, `/research`, and `/faq` at 1440×900 and 390×844.

- [ ] **Step 5: Inspect functional and visual gates**

For every route verify:

- no console error;
- no unexpected horizontal overflow;
- visible focus and logical keyboard order;
- Escape dismissal and focus return for every layer;
- light/dark/system theme;
- English/Chinese copy;
- loading, empty, error, disabled, and retry states;
- reduced-motion behavior;
- Data Grid sorting/filtering/selection/pagination;
- all visible controls perform an action.

- [ ] **Step 6: Final review and defect loop**

Dispatch the whole-change reviewer. For every critical or important finding, first add a failing regression test, then fix, rerun the focused suite, and request scoped re-review. Completion requires a clean final review and every design stop criterion satisfied.
