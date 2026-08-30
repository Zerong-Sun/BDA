# BDA v2 operations

## Local development

Copy `.env.example` (repository root, the only environment template) to `.env`, replace
every secret, then run:

```bash
docker compose up --build
```

```bash
docker compose exec api-v2 python -m backend_v2.scripts.bootstrap_admin --username admin
```

`bootstrap_admin` is intentionally idempotent: rerunning it resets the named user's
password, restores the `admin` role, enables the account, and ensures ownership of the
bootstrap organization. Keep the password in a secret manager or an ignored, mode-`600`
local environment file; never commit it.

The stack is served through nginx at `http://localhost:8080`, so the API is
`http://localhost:8080/api/v2`. API, worker and Beat run as separate processes. The
retired v1 runtime is not deployed from this repository.

For a host Python environment, where uvicorn binds its own port directly:

```bash
python3.13 -m venv backend_v2/.venv
```

```bash
backend_v2/.venv/bin/pip install -e './backend_v2[dev]'
```

```bash
backend_v2/.venv/bin/alembic -c backend_v2/alembic.ini upgrade head
```

```bash
backend_v2/.venv/bin/uvicorn backend_v2.app.main:app --port 8200
```

## Required production configuration

The application refuses production startup with SQLite, a demo compute backend, weak
JWT/MinIO secrets, wildcard or empty CORS, a plaintext OIDC issuer, or an OIDC provider
with no `redirect_uris` allowlist.

The full list of keys the Kubernetes secret must carry, and the separate mounted volumes
the LSF credential and the BYOK provider keys require, are documented in
[the chart README](../helm/README.md). Those two are files rather than environment
variables on purpose, and the chart refuses to render an LSF release without them.

Use `/api/v2/health/live` for process liveness and `/api/v2/health/ready` for
PostgreSQL, Redis and MinIO readiness. Prometheus metrics are exposed at
`/internal/metrics`.

## Migration rehearsal

Always use a filesystem snapshot/copy of SQLite and artifacts. The source is
opened read-only and IDs are deterministically mapped, so rehearsals are
idempotent.

```bash
backend_v2/.venv/bin/python -m backend_v2.scripts.migrate_v1 \
  --sqlite /snapshot/bda.sqlite3 \
  --artifact-root /snapshot/backend/artifacts \
  --artifact-root /snapshot/deliverables \
  --report /reports/bda-v2-migration-1.json \
  --rehearsal 1
```

Use `--skip-files` for inventory-only rehearsals. The JSON report accounts for
every source-table row as migrated, deferred or rejected and includes the full
legacy-to-v2 ID map, checksum counts and explicit rejection reasons. A rehearsal
is not acceptable while any unexpected rejection remains. No deferred or
unexplained rows are accepted. Run the same snapshot at least three times and
validate them with the machine gate:

```bash
backend_v2/.venv/bin/python backend_v2/scripts/check_migration_rehearsals.py \
  /reports/bda-v2-migration-1.json \
  /reports/bda-v2-migration-2.json \
  /reports/bda-v2-migration-3.json
```

Source fingerprint, table counts, ID-map digest and every file checksum must be identical.

## Production deployment gate

Keep `BDA_V2_WRITES_ENABLED=false`, populate the deployment inventory and run:

```bash
backend_v2/.venv/bin/python backend_v2/scripts/check_production_readiness.py \
  --report /reports/production-readiness.json
```

The gate requires kubeconfig/namespace, immutable image repository, DNS/TLS,
PostgreSQL/Redis/MinIO, backup and PITR runbooks, OTLP/Prometheus, Docker mTLS,
LSF SSH/queue, OIDC/LLM secret references, the maintenance window, named
cutover/rollback owners, and readable migration/performance/Docker/LSF/backup/
monitoring evidence reports. A failed gate prohibits real deployment and cutover.

## Final cutover

This section describes the one-time migration off the retired v1 runtime. It is retained
because the migration tooling and the rollback path are still shipped; it does not
describe a system this repository deploys.

1. Put v1 into read-only mode and block background writers.
2. Snapshot SQLite plus WAL, the artifact tree and configuration; verify the backup.
3. Run Alembic and the final migration without `--skip-files`.
4. Require zero unexplained rows, zero foreign-key errors and checksum agreement for every migratable file.
5. Run API/RBAC/job smoke tests and scientific sample reconciliation.
6. Switch the gateway/frontend to `/api/v2`; only then enable v2 writes.
7. Keep v1 read-only for one release cycle, then retire it.

Before v2 writes open, rollback means restoring v1 routing and the frozen v1
snapshot. After writes open, recovery uses PostgreSQL PITR plus MinIO versioning
and backups; there is no reverse synchronization.
