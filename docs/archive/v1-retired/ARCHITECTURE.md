# BDA Workbench Architecture

## Overview

BDA is a full-stack protein binder design automation platform:

- **Frontend**: React 19 + Vite + TanStack Query + Zustand
- **Backend**: FastAPI + SQLite + Celery + Redis
- **Compute**: `demo`, `local`, `docker`, and `remote_lsf` adapters
- **Storage**: Local filesystem under `backend/artifacts/` or MinIO
- **Auth**: JWT Bearer + RBAC (`admin` / `researcher` / `viewer`)
- **Monitoring**: Prometheus + Grafana (metrics token or admin JWT)

## API

All endpoints are under `/api/v1/`. OpenAPI docs at `/api/docs` (disabled in production by default).

### Core groups

| Prefix | Description |
|--------|-------------|
| `/auth` | Login, token refresh, user management |
| `/projects` | Project CRUD, overview, candidates, results, local index |
| `/workflow-runs` | Workflow graph CRUD, validation, layout (`core`, `workflow_mgmt`, `compute`, `jobs`) |
| `/files` | Artifact upload/download, delivery packages |
| `/experiments` | Experiment result import |
| `/registry` | Model/method plugins, compute nodes, script assets |
| `/copilot` | Chat, config, knowledge, literature, target intelligence, cluster drafts |
| `/campaigns` | Multi-round closed-loop R&D |
| `/jobs` | Compute job lifecycle and sync |
| `/admin` | Audit logs, health detail |
| `/metrics` | Prometheus scrape (metrics token or admin JWT) |

## Data and migrations

Runtime schema is applied by `backend/scripts/init_db.py` using `backend/db/schema.sql`, `schema_extended.sql`, and inline `ALTER` migrations. Alembic versions under `alembic/versions/` are reserved for a future PostgreSQL cutover and are **not** applied automatically at runtime.

## Deployment

```bash
cp .env.example .env
docker compose up -d
```

Access via `http://localhost:8080` (nginx) or `http://localhost:5173` (dev frontend).

| Service | Role |
|---------|------|
| `nginx` | Unified entry point |
| `api` | FastAPI backend |
| `frontend` | React SPA |
| `worker` | Celery worker (job polling, output collection) |
| `beat` | Celery beat (literature subscription scans) |
| `redis` | Queue / cache |
| `minio` | Optional artifact object storage |
| `prometheus` | Metrics scrape |
| `grafana` | Dashboards |

Set `BDA_ADMIN_PASSWORD` before first init in non-development environments. For local seeding only, `BDA_ALLOW_DEFAULT_ADMIN=true` enables the legacy `admin123` fallback.

Artifact volumes mount `./backend/artifacts` to `/app/backend/artifacts` in API and worker containers.

## Model plugins

Container images in `docker/models/`:

- `bda/proteinmpnn:1.0.0`
- `bda/rfdiffusion:1.1.0`
- `bda/alphafold2:2.3.0`
- `bda/rosetta:2024.09`

Build: `docker build -t bda/proteinmpnn:1.0.0 docker/models/proteinmpnn`

Set `BDA_COMPUTE_MODE=local` to run built-in stub runners without Docker, or `BDA_COMPUTE_MODE=docker` / `remote_lsf` for real execution.
