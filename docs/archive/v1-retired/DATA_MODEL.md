# BDA Data Model (summary)

Runtime schema is defined in:

- [`backend/db/schema.sql`](../backend/db/schema.sql) — core tables
- [`backend/db/schema_extended.sql`](../backend/db/schema_extended.sql) — research, campaigns, literature
- [`backend/scripts/init_db.py`](../backend/scripts/init_db.py) — additive SQLite migrations at startup

PostgreSQL migrations under [`alembic/`](../alembic/) are reserved for a future deployment mode and are **not** applied by the API today.

## Primary entities

| Entity | Table | Notes |
|--------|-------|-------|
| Project | `projects` | Root aggregate; links to design tasks and members |
| Candidate | `candidates` | Ranked designs with structure paths and decisions |
| Workflow run | `workflow_runs` | DAG execution instance |
| Job | `jobs` | Compute unit tied to a workflow node |
| Artifact | `artifacts` | Registered files with `artifact://` storage URIs |
| Campaign | `campaigns` | Multi-round evaluation loop |

See seed data in [`backend/db/seed_demo.sql`](../backend/db/seed_demo.sql) for a worked example.
