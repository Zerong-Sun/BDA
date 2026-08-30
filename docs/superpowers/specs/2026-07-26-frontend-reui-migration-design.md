# Frontend REUI Migration Design

**Date:** 2026-07-26
**Status:** Approved for autonomous implementation by the user's hands-off directive
**Scope:** `frontend/`

## 1. Objective

Rewrite every user-visible frontend component and dashboard surface with shadcn and ReUI building blocks while preserving the existing BDA v2 product behavior, API contracts, routing, state ownership, accessibility, localization, and scientific-data semantics.

The migration is complete only when:

1. Every route and global overlay uses the new shared component system.
2. Every reusable component under `frontend/src/components/ui` is replaced by, delegates to, or is removed in favor of shadcn/ReUI primitives.
3. Every raw data table is migrated to ReUI Data Grid.
4. Dashboard panels use one consistent ReUI Frame surface.
5. Raw interactive controls are replaced by documented shadcn/ReUI controls except where a third-party integration requires native elements.
6. Existing workflows still function and all automated checks pass.
7. Browser smoke tests pass across the authenticated route family and public routes.

## 2. Existing Product Contract

The migration must preserve these application contracts:

- React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, Zustand, React Flow, Mol*, and Zod remain the platform.
- The route set remains `/login`, `/guide`, `/experiments`, `/workflow`, `/candidates`, `/results`, `/research`, and `/faq`.
- Authentication, API retries, Problem Details handling, cursor pagination, ETags, idempotency keys, upload sessions, SSE, and project scoping remain unchanged.
- TanStack Query continues to own server state; Zustand continues to own UI preferences and active context only.
- English and Chinese localization remains supported.
- Scientific predictions, LLM summaries, evidence, validation results, and human review decisions remain visually and semantically distinguishable.
- React Flow and Mol* retain ownership of their specialized canvas/viewer internals, but all surrounding controls, panels, states, and overlays migrate.

## 3. Design Direction

The visual register is **calm, dense, operational scientific tooling**.

- Use ReUI Frame as the single dashboard surface archetype.
- Use compact spacing for controls and data, with larger gaps only between task groups.
- Preserve one focal task per panel and keep supporting metadata visually subordinate.
- Use semantic theme tokens only; do not add raw product colors in component markup.
- Preserve the existing warm BDA identity through semantic tokens rather than bespoke per-component styling.
- Use Phosphor icons consistently because `components.json` selects `phosphor`.
- Keep motion restrained to 200–300 ms state transitions and respect reduced motion.
- Reflow multi-column layouts on smaller screens; do not merely compress desktop layouts.

## 4. Chosen Architecture

### 4.1 Migration strategy

Use a primitive-first, vertical-slice migration.

1. Repair and validate the shadcn/REUI foundation.
2. Install documented ReUI primitives and selected worked examples.
3. Replace the shared UI layer.
4. Migrate route families one domain at a time.
5. Remove legacy primitives and raw controls.
6. Audit the whole application and run functional browser verification.

This approach is selected over:

- **Big-bang page rewrite:** faster to sketch but too risky for a large, behavior-rich scientific application.
- **Compatibility wrappers only:** lower initial churn but would leave hand-built tables, raw controls, and inconsistent dashboards, failing the stop criteria.

### 4.2 Source layout

Registry-installed shadcn primitives live in `frontend/components/ui`.
Registry-installed ReUI primitives live in `frontend/components/reui`.
Application compositions remain in `frontend/src/components` and `frontend/src/features`.

The `@/*` alias resolves from the frontend root so registry code and application code use one import convention. Existing lower-case registry filenames remain canonical; duplicate legacy upper-case primitives are migrated and removed.

### 4.3 Surface contract

All dashboard content uses:

```tsx
<Frame>
  <FramePanel>
    <FrameHeader>
      <FrameTitle />
      <FrameDescription />
    </FrameHeader>
    <div className="p-5">{content}</div>
    <FrameFooter>{actions}</FrameFooter>
  </FramePanel>
</Frame>
```

`Frame` may be `stacked` for related panels and `dense` for data-heavy views. Route pages may compose multiple frames, but they must not mix Frame and Card surface archetypes.

## 5. Registry Components

Install and adapt these ReUI components using their documented APIs:

- `frame`: dashboard and tool-panel structure.
- `data-grid`: all tabular data, sorting, selection, pagination, loading, and empty states.
- `filters`: advanced candidate and research filters.
- `stepper`: pipeline, experiment, guide, and tour progress.
- `timeline`: job logs, workflow status, and review activity.
- `autocomplete`: searchable project, target, model, and knowledge selection when the option set is dynamic or exceeds 20 entries; smaller fixed sets use Select.
- `sortable`: script assets and user-ordered workflow resources.
- `badge`: statuses and compact metadata.
- `alert`: recoverable errors, warnings, health, and API states.
- `icon-tile` and `icon-stack`: list-row media and purposeful empty states.

Selected worked compositions:

- `c-data-grid-3` for dense tables.
- `c-filters-1` for typed multi-field filters.
- `c-stepper-4` for controlled workflow progress.
- `c-timeline-4` for operational activity.
- `c-autocomplete-4` for labeled search selection.
- `c-sortable-1` for ordered resource rows.
- `c-alert-12` for alerts inside Frame.

Generic controls come from shadcn: Button, Input, Textarea, Label, Select, Checkbox, Switch, Tabs, Tooltip, Accordion, Dialog, AlertDialog, Sheet, Drawer, DropdownMenu, Popover, Command, ScrollArea, Separator, Skeleton, Progress, Avatar, Breadcrumb, and Sonner.

## 6. Shared UI Replacement

The legacy shared UI layer is replaced as follows:

| Legacy component | New implementation |
| --- | --- |
| `Button` | shadcn Button |
| `Input` | shadcn Input/Textarea/Label |
| `Card`, `MetricCard`, `InterpretationCard` | ReUI Frame compositions |
| `StatusPill` | ReUI Badge with typed status mapping |
| `ApiState`, `BackendHealthBanner` | ReUI Alert inside Frame |
| `Skeleton` variants | shadcn Skeleton matching final layout |
| `Tabs` | shadcn Tabs |
| `DrawerShell`, app/copilot/job drawers | shadcn Sheet or Drawer |
| `FAQAccordion` | shadcn Accordion inside Frame |
| `GlossaryTooltip` | shadcn Tooltip |
| `Divider` | shadcn Separator |
| `Toast` | Sonner |
| `PageHead`, `NextStep`, `Row` | focused application compositions using Frame, Stepper, Button, and semantic layout |
| `Topbar`, `UserMenu`, `HelpMenu` | shadcn navigation, dropdown, command, and avatar primitives |
| `PipelineRail` | controlled ReUI Stepper |

Application-specific wrappers may remain only when they provide product semantics, localization, typed status mapping, or a stable integration boundary. They must compose registry primitives rather than reproduce them.

## 7. Route and Domain Design

### 7.1 Application shell and public routes

- `AppShell` becomes a min-height, min-width-safe flex shell with shadcn navigation and a Frame-based content region.
- Topbar project switching uses Select or Autocomplete, and menus use DropdownMenu.
- Settings, Copilot, job status, candidate detail, and management panels use Sheet/Drawer with correct focus trapping and Escape behavior.
- Login uses shadcn form controls, Alert, Button, and Frame.
- Guide and FAQ use Frame, Stepper, Accordion, and purposeful Icon Tile/Stack media.

### 7.2 Experiments

- Project library becomes a dense Frame list/data surface with shadcn controls.
- Overview metrics become one divided or stacked Frame, not an equal-weight card wall.
- Active project, project creation, management, and target overlay use Frame, Dialog/Sheet, Badge, Alert, and form primitives.
- Workflow progress becomes a controlled ReUI Stepper.

### 7.3 Workflow

- Preserve React Flow as the canvas engine.
- Toolbar, context bar, compute strip, resource sidebar, inspector, node builder, registry panel, and script manager use shadcn controls inside Frame.
- Workflow state and pipeline progress use Stepper and Badge.
- Job and compute activity use Timeline.
- Script/resource ordering uses Sortable where ordering is user-controlled.
- Native text inputs remain only inside React Flow/Mol* if required by those libraries.

### 7.4 Candidates

- Candidate filters use ReUI Filters with `createFilter`.
- Candidate table uses TanStack `useReactTable` passed to ReUI Data Grid with record count, sorting, selection, pagination, sticky header, dense layout, and accessible row actions.
- Candidate detail and structure overlay use Sheet/Dialog and Frame.
- Score summaries use structured Frame sections and Progress, not ad hoc bars.

### 7.5 Results

- Validation table uses ReUI Data Grid.
- Results metrics use a single divided/stacked Frame.
- Upload and delivery actions use shadcn form/file controls, Button, Alert, and Frame.
- Interpretations use Frame with explicit provenance/limitation bands.

### 7.6 Research

- Research navigation uses shadcn Tabs.
- Dataset and target tables use ReUI Data Grid.
- Research search and structured filters use Autocomplete, Filters, Select, and Input.
- Literature, knowledge, target intelligence, review, campaign, decision, and generated-research panels use Frame.
- Review history and long-running activity use Timeline.
- Inline review actions use Buttons and Badge variants; no raw color-coded text buttons.
- Markdown remains rendered through the existing safe React Markdown path.

### 7.7 Copilot, artifacts, plugins, viewers, and tours

- Copilot messages, settings, draft clusters, and actions use Frame, Alert, Button, Input, Textarea, ScrollArea, Skeleton, and Sheet.
- Artifact browsing/upload uses Frame, Alert, Button, Progress, and ScrollArea.
- Parameter schema controls use shadcn form primitives selected from the schema type.
- Mol*/PDB surrounding controls use Select, Button, ToggleGroup, Alert, Skeleton, and Frame.
- Tour UI uses Dialog/Popover and controlled Stepper.

## 8. Data and State Flow

- Registry components receive existing typed domain data; no API schemas change.
- Data Grid instances are created at the feature boundary with `useReactTable`.
- ReUI Filters state is translated into existing query/filter parameters without duplicating server state.
- Controlled Stepper values derive from existing route/workflow/job state.
- Sheet/Dialog open state remains local to its feature unless another route-level component already consumes it; globally shared Copilot, settings, and tour state remains in the existing Zustand store.
- Status-to-Badge mapping is centralized and exhaustive by domain union type.
- Loading, error, and empty states derive directly from query/mutation state.

## 9. Error, Loading, and Empty States

Every asynchronous surface must provide:

- A layout-matching Skeleton while loading.
- A ReUI Alert with `role="status"` or `aria-live` and a retry action on recoverable failure.
- A purposeful empty state using existing Frame structure, concise copy, Icon Stack/Tile, and the primary next action.
- Disabled and pending states on mutation controls.
- Visible 409/412/422 semantics where already provided by the application contract.

No centered generic spinner is accepted as the sole loading treatment.

## 10. Accessibility and Responsive Contract

- All controls are keyboard reachable with visible focus rings.
- Dialogs, sheets, dropdowns, and popovers use registry focus management.
- Every icon-only/numeric action has an accessible label.
- Decorative icons are hidden from assistive technology.
- Non-submit buttons explicitly use `type="button"`.
- Table selection has accessible labels and does not rely on row color alone.
- Scroll containers own `overflow-auto` and sit inside a complete `min-h-0` flex chain.
- Layouts reflow at narrow widths; shrinking containers use `min-w-0`, and long single-line labels truncate.
- Reduced-motion preferences remove non-essential transitions.

## 11. Testing Strategy

All behavior changes follow red-green-refactor:

1. Add or update a focused test that expresses the registry-based behavior.
2. Run it and confirm it fails for the expected missing migration.
3. Implement the smallest passing composition.
4. Run the focused test and affected suite.
5. Refactor while green.

Required verification:

- Existing Vitest suite.
- New shared primitive contract tests.
- Route vertical-slice tests for public and authenticated pages.
- Data Grid interaction tests for sorting, selection, filtering, pagination, empty, loading, and retry states.
- Drawer/dialog focus and dismissal tests.
- TypeScript build, ESLint, production Vite build.
- Browser smoke flow for login and every route, at desktop and mobile widths.
- Console error, horizontal overflow, focus order, reduced-motion, and theme checks.

## 12. Migration Audit and Stop Criteria

The final audit fails if any of the following remain without a documented third-party exception:

- A legacy upper-case primitive in `src/components/ui`.
- A raw `<table>`.
- Raw `<button>`, `<input>`, `<select>`, or `<textarea>` in application feature/page code.
- A hand-built dialog/drawer/menu/accordion/tab/tooltip.
- A dashboard card that is not a Frame composition.
- Raw status color utilities instead of Badge/Alert semantic variants.
- A loading-only spinner where a layout skeleton is possible.
- Missing empty/error/retry behavior.
- An undocumented ReUI prop or fabricated registry item.
- An accessibility, scrolling, responsive, theme, or reduced-motion regression.

Third-party exceptions are limited to hidden file inputs and DOM required internally by React Flow, Mol*, or browser upload APIs. Each exception must be adjacent to the integration boundary and must not duplicate a registry control.

The goal is complete when the audit is clean, all automated checks pass, browser flows function, and the final task review finds no load-bearing issue.
