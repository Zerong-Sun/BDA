# BDA v2 Helm chart

Deploys the API, the three Celery worker pools, Beat, the frontend and the migration job.

`BDA_V2_WRITES_ENABLED` defaults to `"false"`. Leave it there until the production
readiness items in [operations](../docs/operations.md) have been signed off.

## Secrets the chart expects

Every pod mounts `values.yaml`'s `existingSecret` (default `bda-v2-secrets`) with
`envFrom`, so each key below becomes an environment variable directly. The chart cannot
validate the contents; a missing key surfaces as a pod that crash-loops on the settings
validator in `app/core/config.py`. Create it before installing:

```bash
kubectl create secret generic bda-v2-secrets \
  --from-literal=BDA_V2_DATABASE_URL='postgresql+psycopg://bda_api_login:APP_PASSWORD@pgbouncer:5432/bda_v2' \
  --from-literal=BDA_V2_REDIS_URL='redis://:PASSWORD@redis:6379/0' \
  --from-literal=BDA_V2_CELERY_BROKER_URL='redis://:PASSWORD@redis:6379/1' \
  --from-literal=BDA_V2_JWT_SECRET='<32+ random characters>' \
  --from-literal=BDA_V2_CORS_ORIGINS='https://bda.example.org' \
  --from-literal=BDA_V2_MINIO_ENDPOINT='minio.internal:9000' \
  --from-literal=BDA_V2_MINIO_ACCESS_KEY='<access key>' \
  --from-literal=BDA_V2_MINIO_SECRET_KEY='<16+ characters>' \
  --from-literal=BDA_V2_MINIO_BUCKET='bda-v2-artifacts' \
  --from-literal=BDA_V2_OIDC_PROVIDERS_JSON='{"campus":{"issuer":"https://idp.example.org","client_id":"bda","redirect_uris":"https://bda.example.org/auth/callback"}}' \
  --from-literal=BDA_V2_LLM_DEFAULT_PROVIDER_REF='file:/var/lib/bda/secrets/default.key' \
  --from-literal=BDA_V2_EXTERNAL_RESEARCH_SOURCES_JSON='{"europe_pmc":{"base_url":"https://www.ebi.ac.uk/europepmc/webservices/rest"}}' \
  --from-literal=BDA_V2_OTEL_ENDPOINT='http://otel-collector:4318'
```

The migration credential is deliberately a second secret mounted only by the ephemeral
Alembic Job. API and worker pods must not be able to read it:

```bash
kubectl create secret generic bda-v2-migration \
  --from-literal=BDA_V2_MAINTENANCE_DATABASE_URL='postgresql+psycopg://bda_migration_login:MIGRATION_PASSWORD@postgres:5432/bda_v2'

kubectl create secret generic bda-v2-worker \
  --from-literal=BDA_V2_DATABASE_URL='postgresql+psycopg://bda_worker_login:WORKER_PASSWORD@pgbouncer:5432/bda_v2'
```

`workerSecret` overrides only `BDA_V2_DATABASE_URL` in worker and Beat pods. The worker
login is `NOBYPASSRLS`, owns no tables, and receives project scope through each operation;
it is not the API login and never receives the migration credential.

The migration Job sets `BDA_V2_MAINTENANCE_DATABASE_ROLE=bda_migrator`. Alembic executes
`SET ROLE bda_migrator` before its first DDL statement, so migrated objects and default
privileges belong to the stable NOLOGIN capability role instead of the rotating login.

| Key | Required | Notes |
| --- | --- | --- |
| `BDA_V2_DATABASE_URL` | always | Must be `postgresql://` or `postgresql+psycopg://`. SQLite is rejected. |
| `BDA_V2_MAINTENANCE_DATABASE_URL` | migration job | Direct PostgreSQL URL from `migrationSecret`. Its username must differ from the application URL. Alembic uses this URL; API/worker pods never receive the secret. |
| `BDA_V2_MAINTENANCE_DATABASE_ROLE` | migration job | Stable NOLOGIN owner role. The chart sets this to `bda_migrator`; the migration login must be a member. |
| `BDA_V2_REDIS_URL` | always | Celery result backend. |
| `BDA_V2_CELERY_BROKER_URL` | always | Use a different database number from the result backend. |
| `BDA_V2_JWT_SECRET` | production | At least 32 characters and must not contain `development`. |
| `BDA_V2_CORS_ORIGINS` | production | Explicit comma-separated allowlist; `*` is rejected. |
| `BDA_V2_MINIO_ENDPOINT` | always | Private service endpoint used for object I/O. |
| `BDA_V2_MINIO_ACCESS_KEY` / `BDA_V2_MINIO_SECRET_KEY` | always | Secret key must be 16+ characters in production. |
| `BDA_V2_MINIO_BUCKET` | always | |
| `BDA_V2_OIDC_PROVIDERS_JSON` | production | Each provider needs `issuer` (https), `client_id` and a comma-separated `redirect_uris` allowlist. |
| `BDA_V2_LLM_DEFAULT_PROVIDER_REF` | production | A `file:` reference inside the BYOK volume. |
| `BDA_V2_EXTERNAL_RESEARCH_SOURCES_JSON` | production | |
| `BDA_V2_OTEL_ENDPOINT` | production | |
| `BDA_V2_DOCKER_TLS_CA` / `_CERT` / `_KEY`, `BDA_V2_DOCKER_HOST` | `computeBackend: docker` | The host must be `tcp://` or `https://`; a local socket is refused in production. |

`BDA_V2_MINIO_PUBLIC_ENDPOINT` is set from `config.minioPublicEndpoint` in `values.yaml`,
not from this secret, because presigned URLs are signed for the browser-facing host.

## Cluster credentials (`computeBackend: lsf`)

The application resolves the SSH credential through a `file:` reference and refuses an
inline value, so the credential must arrive as a mounted file rather than an environment
variable. Create a separate secret and point `lsfCredentials` at it:

```bash
kubectl create secret generic bda-v2-lsf --from-file=password=./lsf-password
```

```yaml
config:
  computeBackend: lsf
  lsf:
    sshHost: cluster.example.internal
    sshUser: bda
    remoteRoot: /work/bda/v2
    queue: normal
lsfCredentials:
  secretName: bda-v2-lsf
  passwordFile: password   # or keyFile: id_ed25519
```

The chart refuses to render with `computeBackend: lsf` until the host, the remote root and
one of `keyFile`/`passwordFile` are supplied. That check exists because the container's own
validator only inspects the environment variable, so a release could previously start
healthy and then fail at the first dispatch with an unresolvable credential path.

Only the `dispatch,poll,collect,maintenance` worker mounts this secret; nothing else needs
a route to the cluster.

## BYOK provider keys

Per-project LLM keys are written by the API (mode `0600`, atomic replace) and read back by
the research and copilot workers. Every pod runs with `readOnlyRootFilesystem: true`, so
they need a real volume, and because the readers are different pods from the writer it has
to be shared rather than per-pod:

```yaml
byokStorage:
  enabled: true
  accessMode: ReadWriteMany
  storageClassName: nfs-client
  size: 1Gi
```

`ReadWriteMany` is the default for that reason. On a cluster without an RWX class, either
supply `existingClaim` pointing at one, or set `replicas.api: 1` and accept that keys
written by the API are only visible to workers scheduled on the same node.

Setting `byokStorage.enabled: false` removes the volume entirely; BYOK then returns
`503 credential_store_unavailable`, which is the honest outcome rather than writing keys to
a location that silently loses them.
