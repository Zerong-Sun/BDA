# Verification

CI runs Ruff, mypy, PostgreSQL-backed pytest, Alembic upgrade/check/downgrade,
OpenAPI/generated-TypeScript drift checks, dependency audit and
repository/container scanning. It enforces 85% overall coverage and 95% for
identity, authorization, compute state transitions, artifact completion and
migration primitives. Run the v2 checks locally:

```bash
backend_v2/.venv/bin/ruff check backend_v2
backend_v2/.venv/bin/mypy --config-file backend_v2/pyproject.toml backend_v2/app backend_v2/scripts
backend_v2/.venv/bin/pytest backend_v2/tests --cov=backend_v2/app \
  --cov-report=json:backend_v2/coverage.json
backend_v2/.venv/bin/python backend_v2/scripts/check_coverage.py backend_v2/coverage.json
backend_v2/.venv/bin/pytest backend_v2/tests/test_research_package_validation.py \
  --cov=backend_v2.app.research.package_validation --cov-branch --cov-fail-under=95
```

Database tests require a migrated PostgreSQL database and
`BDA_V2_RUN_DB_TESTS=1`. Docker adapter integration tests require a Docker
daemon; LSF smoke tests require a designated non-production queue. Neither is
silently replaced with demo compute in production.

The local suite covers outbox replay, deterministic adapter submission,
manifest path/checksum validation, timeout/cancel races, worker recovery,
two-stage upload failures and the complete domain API contract. Production
cutover still requires the same tests against the supplied Kubernetes,
remote-Docker and LSF environments. Local performance, SSE, Redis/MinIO outage
and migration evidence is recorded in `docs/V2_LOCAL_ACCEPTANCE.md`; it is not a
substitute for signed production-environment evidence.
