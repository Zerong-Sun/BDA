# Staging release and recovery evidence

状态：活跃

最后核验：2026-08-30（Asia/Shanghai；staging 发布与恢复演练基线）

权威范围：公开 BDA 的可复现 staging 发布、回滚与恢复证据要求。

数据来源：仓库内 staging workflow、Helm 配置、健康检查与恢复演练流程。

替代关系：取代非版本化的发布备忘；真实基础设施验收记录仍应保存在私有证据库。

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
