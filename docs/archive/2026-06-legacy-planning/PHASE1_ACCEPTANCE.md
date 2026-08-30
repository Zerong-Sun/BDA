# BDA Phase 1 + P1 Acceptance Checklist

## Experiments (FRD §5.1)

- [x] Overview cards: active project, BLI positives, compute access, next action
- [x] Agent workspace: plan route / adjust workflow / interpret lab results
- [x] Project cards from API with PD-1 naming
- [x] Copilot hero with loop links

## Workflow (FRD §5.2)

- [x] Registry-driven NodeBuilder from `/model-plugins`
- [x] Compute status strip
- [x] Plugin registry panel
- [x] Workflow canvas loads API nodes with layered layout
- [x] Draft workflow CRUD + layout persistence endpoints
- [x] Completed run read-only
- [x] Collapsible target intake with lazy Mol*

## Candidates (FRD §5.3)

- [x] Funnel strip
- [x] Extended columns (Pred Kd, solubility, clash, buried SASA)
- [x] Pagination
- [x] Candidate explanation via `/copilot/candidate-explanation`
- [x] Link to Results

## Results (FRD §5.4)

- [x] Metric cards from `/results-summary`
- [x] Demo disclaimer band
- [x] Experiment upload refreshes summary path
- [x] Delivery package downloads (artifact links + ZIP)
- [x] Round-two brief from delivery constraints

## Cross-cutting

- [x] URL project context `?project=`
- [x] Topbar project switcher
- [x] Loop stepper navigation
- [x] Copilot uses backend rule engine
- [x] Zod API parsing on core endpoints
- [x] en/zh static UI strings
- [x] Backend pytest contract tests
- [x] Frontend vitest for mapper/i18n

## Out of scope (P2)

- [ ] DeepSeek / LLM tool calling
- [ ] Real GPU/CPU worker execution
- [ ] Auth / multi-tenant / presentation mode
