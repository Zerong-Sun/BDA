# BDA Backend v2

`backend_v2/` is the production backend package (version 2.0.0): FastAPI API, Celery workers/Beat, SQLAlchemy 2 models, Alembic migrations, migration tooling, Docker image, and Helm chart.

```bash
python3.13 -m venv backend_v2/.venv
backend_v2/.venv/bin/pip install -e './backend_v2[dev]'
cp .env.example .env
alembic -c backend_v2/alembic.ini upgrade head
uvicorn backend_v2.app.main:app --port 8200
```

Run workers separately with queues `dispatch,poll,collect,maintenance`, `research`, and `copilot`; run Beat as one independent process. SQLite and host Docker sockets are not supported production data paths.

See [docs/BACKEND_V2.md](../docs/BACKEND_V2.md) for architecture, configuration, migration, deployment, monitoring, and incident handling.

Notes that sit next to the code they describe:

- [docs/architecture.md](docs/architecture.md) — module boundaries and why this stays one deployment unit.
- [docs/operations.md](docs/operations.md) — local stack, workers, admin bootstrap, v1 migration.
- [docs/testing.md](docs/testing.md) — what CI runs and how to run it locally.
- [scripts/README.md](scripts/README.md) — every operational, gate, and one-shot script in `scripts/`.

Domains are registered in one place: `app/module_registry.py`. `all_models.py`, `main.py` and `core/celery_app.py` all read their model, router and task lists from it, so adding a domain is one edit there plus a row in `contracts/v2-flow-matrix.yaml`.
