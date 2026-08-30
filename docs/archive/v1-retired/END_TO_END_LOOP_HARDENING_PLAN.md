# End-to-End Loop Hardening Plan

This is the current source-of-truth staged plan for hardening BDA Workbench into a truthful, supported AI protein/biomaterial-design workflow.

The plan intentionally separates implemented vertical-slice work from paused expansion. Do not resume Stage 7 items until the Stage 6 sweet-protein vertical slice is manually accepted.

## MVP decisions

| Decision area | Current decision |
|---------------|------------------|
| MVP scope | Broader protein/biomaterial workflows, with only one acceptance-tested vertical slice at a time. |
| First supported route | Sweet protein redesign: curated Monellin/Brazzein target evidence → automatic structure preparation → RFdiffusion → ProteinMPNN → fold prediction → Rosetta/interface scoring → candidate/result interpretation. |
| Compute truth | Every model used by the supported route must be proven installed, licensed, and runnable in the current installation before it is presented as executable. In this Codex environment on 2026-07-13, only repo-local synthetic stub runners were found and smoke-run successfully; real RFdiffusion, ProteinMPNN, AlphaFold, Rosetta, Docker, and LSF CLIs were not installed locally. |
| Execution model | Automatic DAG orchestration: once a run is submitted, newly ready downstream nodes should schedule from completed upstream artifacts without manual resubmission. |
| Target gate | Target readiness follows found evidence/readiness rules: project review evidence, target identity, prepared structure revision, warnings, checksum, and human approval must be server-verifiable before execution. |
| Structure policy | Structure preparation operations are automatic transforms with recorded options, warnings, chain/residue mapping, checksum, and approval state. Users approve/reject the prepared revision; they should not hand-edit hidden state. |
| Research authority | The canonical dossier is the Project Review. Target Intelligence and Literature Claims are evidence producers feeding Project Review, not competing sources of truth. |
| Copilot authority | Copilot may mutate only after server-verifiable confirmation: authenticated user, project scope, readiness/preflight pass, explicit confirmation token/action, and auditable mutation result. |
| Fixture policy | Synthetic workflows must not live in production product databases as ordinary scientific records. They are allowed only in development/demo/test databases or explicitly watermarked example/release storage. |
| Scientific thresholds | Score definitions, decision thresholds, and assay acceptance criteria must be database-backed from reviewed literature/project policy before they can drive ranking or interpretation gates. |
| Deployment scope | LSF is an adapter integration owned by each installation. The core platform records adapter capability and job state, but site-specific queues, modules, licenses, and wrapper paths are installation responsibilities. |
| Examples and delivery packages | Full example delivery packages move to object/release storage; the product database stores metadata, release pointers, provenance, and verification status rather than bulky package contents. |

## Supported product path

The supported sweet-protein path is:

1. create or select a research project;
2. confirm the Project Review dossier as the canonical research authority;
3. confirm target identity and structure readiness for Monellin/Brazzein-style sweet-protein scaffolds;
4. automatically prepare the structure and approve the design-ready revision;
5. create the schema-valid sweet-protein route using registered plugin ports;
6. submit only after preflight verifies required inputs, executable availability, license/site adapter readiness, and fixture policy;
7. orchestrate the DAG automatically through RFdiffusion, ProteinMPNN, fold prediction, and scoring;
8. collect candidates/results with lineage and provenance;
9. interpret only verified or explicitly caveated evidence;
10. recover from expected failures without mistaking fixtures for real scientific execution.

## Stage status summary

| Stage | Status | Current evidence | Remaining gate |
|-------|--------|------------------|----------------|
| Stage 0 — truthful baseline | Implemented for supported path | Capability profile and synthetic execution classification are surfaced by backend capability services; fixture outputs are watermarked/blocked from normal interpretation paths. | Continue to keep demo-only content out of default product entry points. |
| Stage 1 — secure and stabilize contracts | Implemented | Project/user scoping, repository validation, mutation retry controls, and full backend/frontend test/lint commands are green. | Keep CI wired to the canonical commands below. |
| Stage 2 — target and structure gate | Implemented | Target identity confirmation, target readiness, versioned structure preparation, approval, and readiness-gated navigation are implemented. | Manual smoke with a real user-supplied target structure. |
| Stage 3 — one executable workflow plan | Implemented for the sweet-protein route contract | Route application now derives named workflow ports from registered plugin schemas and hard preflight blocks unready projects/runs. | Live installed compute still needs the site-owned RFdiffusion/ProteinMPNN/fold/score checks. |
| Stage 4 — workflow orchestration and lineage | Partially implemented; external E2E blocked | Job submission, manifests, artifact collection, synthetic classification, lineage-preserving candidate collection, and local/LSF tests are in place. | Real RFdiffusion job on `qm` must be run from campus/VPN using the runbook. |
| Stage 5 — candidate and result truthfulness | Implemented for displayed vertical slice | Candidate metric labels, provenance overlays, delivery-package verified-artifact gating, and result caveats are present. | Expand metric provenance only when new models add real output schemas. |
| Stage 6 — focused UX and visualization | Implemented for supported path | Readiness-derived progress, mobile navigation, target/candidate overlays, Mol* lazy loading, vertical-slice UI tests, failure recovery tests, and a real Chromium browser smoke are present. | Product-owner acceptance on the sweet-protein path; real-device manual smoke remains useful but is no longer the only browser gate. |
| Stage 7 — selectively resume expansion | Paused by design | Stage 7 remains documented but intentionally not started. | Product owner must accept the sweet-protein vertical slice first. |

## Stage 0 — truthful baseline

Goal: no UI or API implies real scientific execution where only fixtures exist.

Implemented controls:

- Execution modes are classified as unavailable, synthetic fixture, local, external adapter, or remote LSF.
- Synthetic outputs carry execution metadata so downstream artifact/candidate handling can treat them differently.
- Default seeded projects no longer include unrelated cannabinoid demo content.
- Fixture/demo workflows are allowed in development seed databases only when visibly watermarked; production product databases should store real records or explicit release/example pointers.
- Backend health/capability state is available to the frontend instead of relying on optimistic UI claims.

Evidence:

- `backend/app/services/platform_capabilities.py`
- `backend/app/services/job_artifacts.py`
- `backend/db/seed_demo.sql`
- `frontend/src/components/ui/AppSettingsDrawer.tsx`

## Stage 1 — secure and stabilize contracts

Goal: canonical tests/lint are green and authorization regression tests pass.

Implemented controls:

- Repository table/order/id validation blocks unsafe dynamic repository access.
- Project-scoped APIs and candidate/artifact access checks have regression coverage.
- React Query mutations do not inherit automatic retry behavior.
- Test database setup uses isolated test DB paths and closes pools correctly.
- Frontend lint now passes with zero warnings.

Evidence:

- `backend/app/repositories/base.py`
- `backend/tests/test_rbac_writes.py`
- `backend/tests/conftest.py`
- `frontend/src/App.tsx`
- `frontend/src/test/renderWithProviders.tsx`

## Stage 2 — target and structure gate

Goal: the platform can prove that an approved design-ready structure exists.

Implemented controls:

- Target identity confirmation records accession, organism, construct, and identity state.
- Structure upload, preparation, revision, approval, checksum/report metadata, and readiness are explicit.
- Workflow entry points are readiness-gated rather than page-history-gated.
- Local preview and persisted artifact paths are visually distinct.

Evidence:

- `backend/app/services/target_readiness.py`
- `backend/app/services/project_service.py`
- `backend/app/routers/core.py`
- `frontend/src/features/experiments/ActiveProjectPanel.tsx`
- `frontend/src/features/experiments/WorkflowProgress.tsx`
- `backend/tests/test_target_readiness.py`

## Stage 3 — one executable workflow plan

Goal: a plan cannot be submitted unless every required input and executable is verified.

Implemented controls:

- The first supported route is `sweet_protein_design_route`.
- The supported route uses registered plugin IDs and versions from the registry.
- Route application creates workflow graph edges by matching named plugin output/input ports and artifact types.
- Generic `output`/`input` route edges are no longer produced by the route planner.
- Hard preflight reports actionable blockers before execution.

Evidence:

- `backend/app/services/route_planner.py`
- `backend/app/services/workflow_preflight.py`
- `backend/app/plugins/defaults.py`
- `backend/tests/test_route_planner.py`
- `backend/tests/test_workflow.py`

## Stage 4 — workflow orchestration and lineage

Goal: one submission completes or fails the full route without manual resubmission, with traceable lineage.

Implemented controls:

- Job manifests include project, workflow run, node, plugin, input ports, parameters, and execution classification.
- Artifact collection preserves candidate IDs and source metadata.
- Missing manifests/outputs fail safely instead of silently becoming results.
- Local and LSF adapter paths have regression tests and an RFdiffusion runbook.

Blocked gate:

- Live `qm` RFdiffusion E2E is still blocked from the current environment. Do not mark Stage 4 externally complete until the sweet-protein runbook records real `job_id` values, LSF `external_id` values, and collected outputs.

Evidence:

- `backend/app/services/job_service.py`
- `backend/app/services/job_artifacts.py`
- `backend/app/compute/factory.py`
- `backend/tests/test_compute_e2e.py`
- `backend/tests/test_remote_lsf_adapter.py`
- `docs/CLUSTER_E2E_RFDIFFUSION.md`

## Stage 5 — candidate and result truthfulness

Goal: every displayed value is traceable back to its source.

Implemented controls:

- Candidate metrics use explicit labels, directionality, and caveats.
- Score definitions, decision thresholds, and assay acceptance criteria must come from reviewed literature/project policy tables before they are used as gates.
- Candidate overlay links metrics to model/ranking/scoring provenance categories.
- Result and delivery surfaces avoid generating packages when verified artifacts are absent.
- Copilot streaming shows tool/status provenance instead of generic “thinking” only.

Evidence:

- `frontend/src/features/candidates/CandidateStructureOverlay.tsx`
- `frontend/src/features/results/DeliveryPackage.tsx`
- `frontend/src/features/copilot/CopilotChat.tsx`
- `frontend/src/lib/api/copilot.ts`
- `frontend/src/features/results/DeliveryPackage.test.tsx`
- `frontend/src/features/copilot/CopilotChat.test.tsx`

## Stage 6 — focused UX and visualization

Goal: a non-expert can complete the supported path and recover from expected failures.

Implemented controls:

- Progress is derived from target readiness, not page artifacts.
- Mobile navigation and button semantics are accessible.
- Target and candidate visual overlays expose chain roles, missing hotspot/contact evidence, readiness, and provenance.
- Mol* is lazy-loaded through direct lazy viewer imports; runtime barrel imports were removed.
- Vertical-slice UI tests cover readiness recovery, visualization explanation, retry behavior, and upload persistence semantics.
- A Playwright-backed Chromium smoke runs the built app through Experiments → Target intelligence recovery → blocked Workflow submit → mobile Candidates navigation → Results evidence/delivery gating with mocked APIs.

Evidence:

- `frontend/src/features/experiments/WorkflowProgress.tsx`
- `frontend/src/components/ui/Topbar.tsx`
- `frontend/src/features/experiments/TargetStructureOverlay.tsx`
- `frontend/src/features/candidates/CandidateStructureOverlay.tsx`
- `frontend/src/features/stage6VerticalSlice.test.tsx`
- `frontend/scripts/browser-vertical-slice.mjs`
- `.github/workflows/ci.yml`

## Stage 7 — selectively resume expansion

Stage 7 is intentionally paused.

Do not resume these until the supported path is accepted:

- additional workflow routes;
- additional model plugins;
- campaign automation;
- mutating Copilot tools;
- literature subscription automation;
- PostgreSQL migration;
- advanced collaboration/organization features.

Required entry criteria:

1. Stage 6 automated UI and browser smoke pass for the sweet-protein path, followed by product-owner acceptance.
2. Live sweet-protein RFdiffusion/ProteinMPNN/fold/score compute runbook is completed or explicitly deferred by the product owner.
3. Product owner chooses which Stage 7 expansion has priority and accepts the added operational risk.

## Compute truth snapshot — 2026-07-13

Current Codex environment results:

| Executable / runner | Status today | Interpretation |
|---------------------|--------------|----------------|
| `docker/models/rfdiffusion/run.py` | Smoke-run passed | Synthetic local stub only; not a licensed/scientific RFdiffusion executable. |
| `docker/models/proteinmpnn/run.py` | Smoke-run passed | Synthetic local stub only; not a licensed/scientific ProteinMPNN executable. |
| `docker/models/alphafold2/run.py` | Smoke-run passed | Synthetic local stub only; not a licensed/scientific AlphaFold executable. |
| `docker/models/rosetta/run.py` | Smoke-run passed | Synthetic local stub only; not a licensed/scientific Rosetta executable. |
| `rfdiffusion`, `run_inference.py` | Not found | Real RFdiffusion execution not locally verified. |
| `protein_mpnn_run.py` | Not found | Real ProteinMPNN execution not locally verified. |
| `run_alphafold.py` | Not found | Real AlphaFold execution not locally verified. |
| `rosetta_scripts.default.linuxgccrelease` | Not found | Real Rosetta execution/licensing not locally verified. |
| `docker` | Not found | Docker adapter cannot be verified in this environment. |
| `bsub`, `bjobs` | Not found locally | LSF must be verified through the installation-owned adapter/SSH environment. |

Product implication: only synthetic local runner behavior is proven here. A production installation must run the site-owned executable/license checks before the sweet-protein route can be marked executable.

## Canonical verification commands

Run from the repository root unless noted:

```bash
cd backend && ../.venv/bin/python -m pytest tests -q
cd frontend && npm run lint
cd frontend && npm test -- --run
cd frontend && npm run build
cd frontend && npm run test:browser
```

The browser smoke requires Chromium once per environment:

```bash
cd frontend && npx playwright install chromium
```

Known external verification:

```bash
docs/CLUSTER_E2E_RFDIFFUSION.md
```

Use that runbook only from an environment that can reach `qm`.
