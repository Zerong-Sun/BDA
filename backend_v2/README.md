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
