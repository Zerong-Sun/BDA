# BDA v2 architecture

`backend_v2` is the only backend this repository deploys, and `/api/v2` is the only API
contract. It is a modular monolith: it imports no v1 code and shares no database with the
retired v1 runtime, which survives only as migration tooling.

## Boundaries

- `identity`: local/OIDC identity, rotating refresh sessions, organizations and roles.
- `projects`, `targets`, `workflows`: project-scoped domain resources.
- `compute`: submissions, jobs, state machine, transactional outbox and compute adapters.
- `artifacts`: two-phase MinIO uploads, checksums, lineage and reconciliation.
- `experiments`: typed experiment-result ingestion.
- `audit`: transaction-local immutable change records.
- `platform`: liveness/readiness and operational endpoints.

Routes call services; services own transactions and domain rules; repositories
perform persistence only. PostgreSQL is the business system of record, Redis is
only the Celery transport, and MinIO is the authoritative file store.

## Compute lifecycle

Submission inserts jobs and outbox records in one PostgreSQL transaction. DAG
roots are dispatched first. A node becomes dispatchable only after all parents
succeed; failed/cancelled parents deterministically fail descendants with
`upstream_failed`.

The state machine is:

`pending → dispatching → queued → running → collecting → succeeded`

Failure and cancellation are terminal side paths. Docker and LSF adapters use a
stable job name derived from the v2 job UUID and attempt number, so replay after
a worker crash discovers the existing external job. Database sessions are
closed before Docker/SSH/LSF calls and reopened to persist the external ID.

## API contract

All endpoints are under `/api/v2`. Resource operations use typed Pydantic
responses; errors are `application/problem+json`. Writes carry an
`x-permission` OpenAPI extension checked by contract tests. Lists use opaque
cursors, mutable resources use ETag/`If-Match`, and submissions require an
`Idempotency-Key`.

SSE job events authenticate with a short database session, then open a new
short session for each poll. No connection is held for the stream lifetime.

## Domain coverage

All business domains are implemented in v2 and served under `/api/v2`: identity,
projects, targets, workflows, compute, artifacts, candidates, experiments, campaigns,
research, knowledge, literature, intelligence, registry, delivery, copilot, audit and
platform. Nothing is deferred to v1, and v2 neither proxies nor writes any v1 table.

`backend_v2/openapi.json` is the authoritative list of what is exposed; CI fails on drift
between it and the routers.
