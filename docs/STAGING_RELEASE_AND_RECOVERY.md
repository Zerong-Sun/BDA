# Staging release and recovery evidence

BDA is not production-ready. The staging workflow always deploys with
`BDA_V2_WRITES_ENABLED=false`; there is deliberately no production deployment job.

## Release path

Run **Staging release** manually. The supply-chain job builds SHA-tagged backend and
frontend images, records their immutable digests, generates SPDX SBOMs, blocks on high
or critical vulnerabilities, creates GitHub/Sigstore provenance attestations, and
keyless-signs both images. Selecting `deploy=true` requires the protected `staging`
environment and its Kubernetes/LSF variables. Helm uses image digests, runs Alembic as
a pre-upgrade migration job, waits for `/api/v2/health/ready`, and rolls back a failed
release.

## Required recovery rehearsal

Create one evidence directory outside the repository for each exercise. Store:

- PostgreSQL custom-format backup, WAL/PITR target time, source and restored Alembic
  revisions, table counts and critical row counts;
- MinIO bucket version listing, object/version/checksum manifest, restore selection and
  post-restore checksum report;
- API and every worker build/schema heartbeat, read-only smoke output, injected failure
  observations, alert screenshots or exported alert events;
- prior and candidate Helm revisions, image digests, SBOM/attestation verification, and
  rollback output.

The rehearsal is accepted only when a separate PostgreSQL instance and a separate MinIO
bucket are restored, checksums match, `0045 -> head` succeeds on a clone, an empty database
survives the complete upgrade/downgrade round trip, and Redis/MinIO/worker/LSF failures make
readiness fail and generate the expected alerts. Never use application downgrade as the
production rollback mechanism: roll back code and restore the backup/PITR snapshot.

Production writes may be enabled only after the evidence is reviewed and signed off.
