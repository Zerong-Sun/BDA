# BDA Workbench v2

BDA Workbench is a traceable protein-design workspace built on a FastAPI modular monolith, PostgreSQL, Redis/Celery, MinIO, and a React frontend. The active API contract is `/api/v2`; the retired runtime is not deployed from this repository.

中文说明见 [README.zh-CN.md](README.zh-CN.md).

This public repository is the single source of truth for BDA software. The
private `BDA-demo` repository follows explicit BDA release tags and adds only
private research data and deployment configuration; software changes originate
here and flow one way through reviewed synchronization PRs.

## PD1 demo

The only bundled dataset is `pd1-demo-v1`: one PD1 project, 12 public-source
metadata records, four evidence relations, and six checksummed `DEMO` PDB
fixtures for three fictional candidates. All candidate IDs, metrics, and fixture
structures are precomputed synthetic UI/migration material—not a model run,
experimental result, medical claim, or scientific conclusion. See the
[data card](examples/migration-fixtures/pd1/DATA_CARD.md).

## Capabilities

- Organizations, projects, multiple targets, and a project primary target
- Editable workflow graphs with ETag concurrency control and immutable runtime snapshots
- Asynchronous Docker/LSF jobs through transactional outbox and Celery queues
- Two-phase browser uploads, checksums, artifact lineage, candidates, experiments, and delivery packages
- Campaign rounds, literature claims/evidence/relations, Target Intelligence, knowledge, Registry, and Copilot
- Local accounts and OIDC, project authorization, audit logs, Problem Details, cursor pagination, SSE, metrics, and tracing

## Quick start

Copy `.env.example` to `.env`, replace every secret, then run:

```bash
docker compose up --build
```

Open `http://localhost:8080`. API health endpoints are `http://localhost:8080/api/v2/health/live` and `/api/v2/health/ready`. The MinIO console is bound locally on port `9003`.

Production Helm defaults to `BDA_V2_WRITES_ENABLED=false`. Do not enable writes until database/object-store backups, migration reconciliation, remote Docker and LSF smoke tests, OIDC/provider secrets, performance tests, monitoring, and rollback ownership have passed.

This alpha provides a reproducible staging baseline; it is not production-ready
and does not claim that real Kubernetes, LSF, OIDC, TLS, PITR, alerting, or
restore acceptance has completed.

## Development checks

```bash
backend_v2/.venv/bin/ruff check backend_v2
backend_v2/.venv/bin/mypy --config-file backend_v2/pyproject.toml backend_v2/app backend_v2/scripts
backend_v2/.venv/bin/pytest backend_v2/tests
npm --prefix frontend test
npm --prefix frontend run build
```

## Documentation

- [Backend v2 guide](docs/BACKEND_V2.md)
- [Frontend v2 guide](docs/FRONTEND_V2.md)
- [Local v2 acceptance evidence](docs/V2_LOCAL_ACCEPTANCE.md)
- [Backend package](backend_v2/README.md)
- [Frontend package](frontend/README.md)

Historical runtime documentation is retained only under `docs/archive/` for migration archaeology. It is not an operational guide.

## Licenses

Software is licensed under [Apache-2.0](LICENSE). The PD1 demo data is separately
licensed under [CC BY 4.0](DATA_LICENSE.md). Contributions and public data changes
must follow [CONTRIBUTING.md](CONTRIBUTING.md) and [DATA_POLICY.md](DATA_POLICY.md).
