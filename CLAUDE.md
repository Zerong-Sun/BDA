# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Interpreter

Use the primary checkout's `backend_v2/.venv` for everything Python. The primary checkout has that environment; auxiliary linked worktrees do not necessarily have their own `backend_v2/.venv`. Resolve the primary checkout through Git's common directory instead of assuming every worktree contains a virtual environment. The **root `.venv` is broken** (missing `jsonschema` and other deps) and the system `python3` is Anaconda 3.11, below this project's `requires-python = ">=3.13"`. Neither will run the test suite correctly.

```bash
BDA_PYTHON_BIN="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/backend_v2/.venv/bin"
"$BDA_PYTHON_BIN/python" -c "import fastapi, jsonschema; print('ok')"
```

## Commands

All commands run from the repo root.

The examples below use `backend_v2/.venv/bin/...` for readability. In an auxiliary worktree, replace that prefix with the resolved `$BDA_PYTHON_BIN/` above.

```bash
backend_v2/.venv/bin/ruff check backend_v2
backend_v2/.venv/bin/mypy --config-file backend_v2/pyproject.toml backend_v2/app backend_v2/scripts
backend_v2/.venv/bin/pytest backend_v2/tests
npm --prefix frontend test
npm --prefix frontend run build
```

Single backend test / single frontend test:

```bash
backend_v2/.venv/bin/pytest backend_v2/tests/test_compute_service.py::test_name -q
```

```bash
npx --prefix frontend vitest run src/lib/api/workflow.test.ts -t "case name"
```

Local stack (frontend on `:8080`, MinIO console on `:9003`, Postgres on `:5433`):

```bash
docker compose up --build
```

Migrations — `alembic.ini` hardcodes `postgresql+psycopg://bda:bda@localhost:5433/bda_v2`, so a local Postgres on 5433 must be up:

```bash
backend_v2/.venv/bin/alembic -c backend_v2/alembic.ini upgrade head
```

Tests marked with `BDA_V2_RUN_DB_TESTS != "1"` skip by default (`test_database_flow.py`, part of `test_candidate_metrics.py`). Set `BDA_V2_RUN_DB_TESTS=1` plus `BDA_V2_DATABASE_URL` to run them. There is no `conftest.py`; tests construct their own fixtures.

Tests that read research working data (receptor structures, job configs, deliverable bundles) are gated on that data being present, via `backend_v2/tests/_research_data.py`. The data is not in git — it lives in the sibling store (see below) — so these run on a machine that has the store and skip on a clone, and a green run means "everything runnable passed". Set `BDA_V2_REQUIRE_RESEARCH_FIXTURES=1` to turn a missing store into a failure instead of a skip.

`mypy` is invoked by CI **without** `--config-file`, from the repo root. The Celery imports carry inline `# type: ignore` comments rather than a config override specifically so behavior is identical either way — keep it that way rather than adding `[[tool.mypy.overrides]]` sections.

## CI gates that fail on drift, not on bugs

Most CI breakage here is a regeneration or registration step that was skipped, not broken logic. After changing backend routes or schemas:

```bash
PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/export_openapi.py backend_v2/openapi.json
npm --prefix frontend run generate:api
```

CI runs both and then `git diff --exit-code`, so an un-regenerated `backend_v2/openapi.json` or `frontend/src/lib/api/generated/` fails the build.

Other gates, each with a script you can run locally:

- **Flow matrix** — every table must be declared in `contracts/v2-flow-matrix.yaml` with its domain, producers, consumers, api_paths, and ui. New table ⇒ new entry. Check with `PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/check_flow_matrix.py contracts/v2-flow-matrix.yaml`.
- **Coverage** — 85% overall, plus 95% on `identity/service.py`, `identity/deps.py`, `compute/service.py`, `artifacts/service.py`, `research/package_import.py`, `research/package_validation.py`, and `migration/`. Thresholds live in `backend_v2/scripts/check_coverage.py`. `research/package_validation.py` additionally needs 95% *branch* coverage. On a machine with no PostgreSQL the DB-gated tests skip and the numbers come out below CI's — `check_coverage.py` says so rather than letting it read as a regression.
- **Slot declarations** — a plugin may declare `cpus > 1` only with a `cpus_evidence` string naming the measurement or upstream thread flag that supports it. The cluster treats a job holding unused cores as a violation, so an unreviewable number is not allowed to sit in the registry. Check with `PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/check_plugin_cpu_declarations.py`.
- **Migration reversibility** — CI runs `alembic check` (model/migration drift) then `alembic downgrade base`. Every migration needs a working downgrade.
- **Retired-runtime grep** — CI greps the tree and fails on `/api/v1`, `submit-to-compute`, `/jobs/.*/sync`, `experiment-results/upload`, `copilot/literature`, `docker.sock`, and `sqlite:///`. These paths are deliberately dead.
- **Frontend transport boundary** — see below.

## Version scope

The repository and released contracts remain **BDA v2 / 2.0.0**. `platform-v3` names the internal restructuring milestone merged in PR #281; it is not a published v3 product or API. Do not rename `/api/v2`, `backend_v2`, `BDA_V2_*`, package versions, or frontend branding on that basis. Autopilot campaigns remain isolated on `codex/autopilot-campaigns-wip-20260829` until their new-baseline gates pass and must not be described here as a mainline capability.

## Backend architecture

FastAPI modular monolith under `backend_v2/app/`, one package per domain (identity, projects, targets, workflows, compute, artifacts, candidates, experiments, campaigns, research, knowledge, journal, literature, intelligence, registry, delivery, copilot, ligands, audit, platform). Each follows the same four-file convention:

| File | Responsibility |
|---|---|
| `api.py` | protocol, dependency injection, `x-permission` declaration |
| `service.py` | domain rules, transaction boundary |
| `repository.py` | persistence only |
| `models.py` / `schemas.py` | SQLAlchemy ORM / external contract — kept separate |

Cross-domain writes go through another domain's service or through an outbox event, never directly into a foreign repository. Copilot orchestrates domain services and owns no domain rules; compute never touches the campaign repository.

**Registering a new module takes three edits**, and forgetting any one produces a confusing failure: add the model import to `app/all_models.py` (Alembic reads metadata from there, so an unregistered model silently produces an empty migration), add the router to the tuple in `app/main.py`, and add the table to the flow matrix.

Conventions that apply everywhere:

- UUID primary keys, UTC timestamps, `version` column for optimistic locking. Legacy rows keep a unique `legacy_id`.
- Mutating endpoints require `If-Match: W/"<version>"`. Missing header ⇒ **428**, stale version ⇒ **412**.
- Lists use opaque cursors. There is no offset/total compatibility layer.
- Errors are `application/problem+json` with `type/title/status/detail/instance/error_code/trace_id`; validation errors add `errors`. Raise `DomainError` from `app/core/problem.py` rather than `HTTPException`.
- A middleware in `main.py` rejects all `/api/v2` writes with 503 when `BDA_V2_WRITES_ENABLED` is false, exempting only `/auth/token` and `/auth/refresh`. Production Helm defaults this to false.
- Settings are prefixed `BDA_V2_`. Production startup refuses to boot on default secrets, SQLite, demo compute, a mounted Docker socket, a missing LLM provider, or unsafe TLS.

### Compute path

Submissions (`POST /workflow-runs/{id}/submissions`) require an `Idempotency-Key`. The API only writes submission + job + attempt + outbox rows and returns 202 — it never calls a compute backend inline, so a Redis outage cannot lose work. The publisher drains the outbox with `FOR UPDATE SKIP LOCKED` onto six Celery queues: `dispatch`, `poll`, `collect`, `maintenance`, `research`, `copilot`.

```text
pending -> dispatching -> queued -> running -> collecting -> succeeded
                                                \-> failed
                         \--------------------------> cancelled
```

Rendered `#BSUB` directives take `-n`, `span[ptile=…]` and the exported `$BDA_CPUS` from one number (`compute/scripts.py:declared_cpus`). They must stay equal: ptile is slots *per host*, so `-n 8` without a span scatters the job across eight machines, and a tool told to start a different number of threads than the scheduler reserved is what draws the cluster's low-utilisation mail.

Docker and LSF adapters both implement `ensure_submitted/status/cancel/collect` and derive deterministic external names and staging keys from the job UUID — on recovery they **query external state before resubmitting**. `collect()` rejects path traversal, verifies schema/size/SHA-256, and creates artifacts, lineage, candidates, and results in one transaction.

### Artifacts

Two-phase, browser-direct: `POST /artifact-uploads` → client computes SHA-256 and PUTs to the presigned URL → `POST /artifact-uploads/{id}/complete`. The API never receives multipart file bodies. MinIO is addressed by two distinct endpoints — `MINIO_ENDPOINT` for server-side I/O and `MINIO_PUBLIC_ENDPOINT` for presigned URLs handed to the browser (the host is signed and cannot be rewritten).

## Frontend architecture

React 19 + TypeScript + Vite, TanStack Query for server state, Zustand for UI state only, React Flow for the workflow graph, Mol* for structures, Tailwind v4.

**The transport boundary is CI-enforced.** Ordinary REST goes through the generated SDK in `src/lib/api/generated/`; `apiRequest` is banned outright, and raw `fetch(` is allowed only in `lib/api/client.ts`, `generatedTransport.ts`, `generated/**`, `artifacts.ts`, `copilot.ts`, `sse.ts`, `researchPackages.ts`, `features/pdb-viewer/structureLoader.ts`, and tests. `sse.ts` is there because the streaming endpoints authenticate with a bearer token and `EventSource` cannot set headers — the alternative was the access token in a query string. Adding a `fetch` elsewhere fails the build.

Static resources use generated types. Dynamic research JSON (Literature, Intelligence) is validated at the boundary with Zod schemas in `src/lib/schemas/`.

- Access token lives in sessionStorage; the refresh token is an HttpOnly cookie JS cannot read. A 401 triggers a **single-flight** refresh — one refresh in flight at a time, original request retried at most once.
- Query keys must include the project/resource UUID. Candidates must not query without a project context, or data leaks between empty projects.
- 409 = state/idempotency conflict, 412 = reload prompt (never overwrite server data), 422 = field errors, 429/5xx = limited backoff on GET/HEAD only.
- Job status comes from the job resource and cursor logs; `/jobs/{id}/events` SSE shortens the gap between a state change and seeing it, but polling is the floor beneath it and a dropped stream is not an error. There is no sync endpoint.
- `npm run dev` proxies `/api` to `http://127.0.0.1:8100` (override with `BDA_V2_PROXY_TARGET`).
- Mol* is excluded from Vite pre-bundling — its circular ESM deps break `registerDefault` otherwise. Several `resolve.alias` entries in `vite.config.ts` redirect CJS-only packages to shims in `src/vendor/`; don't remove them.

## HPC scripts

`qm-scripts/` targets the Qiming cluster, which runs **IBM Spectrum LSF — submit with `bsub`, not `sbatch`**. Job definitions are JSON configs driven through `qm-scripts/library/qm_job.py` (`params` / `validate` / `render` subcommands) rather than hand-written batch scripts. Login nodes are for inspection, light staging, transfer, and submission only — never for running models.

Qiming access is permanent: **the user logs in by typing the password in their own terminal; the agent only reuses a session the user has confirmed.** Do not auto-login, auto-reconnect, probe connectivity in the background, poll in a loop, or handle password prompts. If the session is missing or expired, stop and ask the user to log in by hand. OpenSSH's non-post-quantum key-exchange message is a server-capability warning — do not retry because of it, and do not weaken client security settings to hide it. Passwords must not be stored, echoed, or placed in commands, environment variables, scripts, Git, logs, or reports. Reuse a confirmed session with `ssh -o BatchMode=yes qm …`. Requested cores must match what the binary can actually use: `-n` defaults to 1 and only goes higher with evidence (an MPI build, an explicit thread/worker count), `ptile` equals `-n`, and CPU-only jobs set `"gpus": 0` — the cluster sends low-utilisation inspection mail otherwise, which this project treats as a violation, not a notice to ignore. Full rules are in `docs/QM_CLUSTER_OPERATION_RULES.md`.

## Documentation

`docs/README.md` is the complete categorized index. `docs/refactor/CURRENT_STATE_2026-08-29.md` is the unique current-status entry, and `docs/DATA_CATALOG.md` is the only logical entry for external research output. The two architecture references worth reading before substantial work are `docs/BACKEND_V2.md` and `docs/FRONTEND_V2.md`; both are in Chinese and are more current than this file on domain detail. `docs/archive/` holds retired-runtime material for migration archaeology only — it is not an operational guide.

## Repository hygiene

- `.claude/worktrees/` is excluded via `.git/info/exclude` (not `.gitignore`), so worktrees are invisible to `git status` but real to `git worktree list`.
- A long-lived stash from `codex/recoverprojects` sits at `stash@{0}`. A bare `git stash pop` will detonate it — use a worktree instead.
- **This repository holds code only.** Research data (`research projects/`, `deliverables/`, `fig/`) moved to a sibling store, `../BDA-data` by default; large local-only artifacts (model checkpoints, database dumps) moved to `../BDA-local` and exist in no repository at all. See `docs/refactor/REPO_SPLIT.md`.
- Anything that reads research data must resolve it through `backend_v2/scripts/_data_root.py` (`data_path("deliverables/…")`), never a hardcoded repo-relative path, and honour `BDA_DATA_ROOT`. Resolution first checks filesystem ancestors, then Git's common directory to find the primary checkout's sibling store. This matters for Codex worktrees that live outside the primary checkout's directory tree; both plain `REPO_ROOT.parent` and ancestor walking alone are wrong there.
