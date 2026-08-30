# Repository Structure

```
BDA/
├── backend/app/          # FastAPI application
│   ├── routers/          # HTTP endpoints (copilot split into routers/copilot/*)
│   ├── repositories/     # SQLite data access (projects, candidates, workflows, …)
│   ├── services/         # Business logic (jobs, artifacts, copilot config, …)
│   ├── copilot/          # Copilot runtime, tools, cluster drafts
│   └── compute/          # Compute adapter factory (demo, docker, LSF)
├── frontend/src/
│   ├── app/              # Route-level pages
│   └── features/         # Domain UI modules (workflow, candidates, research, …)
├── backend/db/           # SQLite schema and seeds
├── alembic/              # Reserved PostgreSQL migrations (not used at runtime)
├── docker-compose.yml    # Redis, MinIO, API, worker, frontend stack
└── docs/                 # Architecture and integration guides
```

Domain repositories are split under [`backend/app/repositories/`](../backend/app/repositories/):

- `projects_repo.py` — projects, delivery packages, results summaries
- `candidates_repo.py` — candidates and experiment results
- `workflows_repo.py` — workflow runs, nodes, edges
- `catalog.py` — backward-compatible re-export facade
