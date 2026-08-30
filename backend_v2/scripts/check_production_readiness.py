from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REQUIRED_VALUES = {
    "BDA_V2_KUBECONFIG",
    "BDA_V2_K8S_NAMESPACE",
    "BDA_V2_IMAGE_REPOSITORY",
    "BDA_V2_INGRESS_HOST",
    "BDA_V2_TLS_SECRET",
    "BDA_V2_DATABASE_URL",
    "BDA_V2_REDIS_URL",
    "BDA_V2_CELERY_BROKER_URL",
    "BDA_V2_MINIO_ENDPOINT",
    "BDA_V2_MINIO_PUBLIC_ENDPOINT",
    "BDA_V2_MINIO_BUCKET",
    "BDA_V2_OTEL_ENDPOINT",
    "BDA_V2_PROMETHEUS_URL",
    "BDA_V2_DOCKER_HOST",
    "BDA_V2_LSF_SSH_HOST",
    "BDA_V2_LSF_QUEUE",
    "BDA_V2_BACKUP_RUNBOOK",
    "BDA_V2_PITR_RUNBOOK",
    "BDA_V2_MAINTENANCE_WINDOW",
    "BDA_V2_CUTOVER_OWNER",
    "BDA_V2_ROLLBACK_OWNER",
    "BDA_V2_MIGRATION_REHEARSAL_REPORT",
    "BDA_V2_PERFORMANCE_REPORT",
    "BDA_V2_DOCKER_SMOKE_REPORT",
    "BDA_V2_LSF_SMOKE_REPORT",
    "BDA_V2_BACKUP_RESTORE_REPORT",
    "BDA_V2_MONITORING_VALIDATION_REPORT",
}
REQUIRED_SECRET_REFS = {
    "BDA_V2_K8S_SECRET",
    "BDA_V2_DOCKER_MTLS_SECRET_REF",
    "BDA_V2_LSF_SSH_SECRET_REF",
    "BDA_V2_OIDC_SECRET_REF",
    "BDA_V2_LLM_SECRET_REF",
}
REQUIRED_FILES = {
    "BDA_V2_KUBECONFIG",
    "BDA_V2_BACKUP_RUNBOOK",
    "BDA_V2_PITR_RUNBOOK",
    "BDA_V2_MIGRATION_REHEARSAL_REPORT",
    "BDA_V2_PERFORMANCE_REPORT",
    "BDA_V2_DOCKER_SMOKE_REPORT",
    "BDA_V2_LSF_SMOKE_REPORT",
    "BDA_V2_BACKUP_RESTORE_REPORT",
    "BDA_V2_MONITORING_VALIDATION_REPORT",
}


def readiness_report(environment: dict[str, str]) -> dict:
    missing = sorted(name for name in REQUIRED_VALUES | REQUIRED_SECRET_REFS if not environment.get(name, "").strip())
    invalid: list[str] = []
    docker_host = environment.get("BDA_V2_DOCKER_HOST", "")
    if docker_host and not docker_host.startswith("tcp://"):
        invalid.append("BDA_V2_DOCKER_HOST must identify the remote mTLS daemon with tcp://")
    if environment.get("BDA_V2_WRITES_ENABLED", "").lower() not in {"false", "0"}:
        invalid.append("BDA_V2_WRITES_ENABLED must remain false before production acceptance")
    for name in sorted(REQUIRED_FILES):
        value = environment.get(name, "").strip()
        if value and not Path(value).expanduser().is_file():
            invalid.append(f"{name} does not identify a readable evidence file")
    return {"ready": not missing and not invalid, "missing": missing, "invalid": invalid}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed until all production cutover inputs are supplied")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    payload = readiness_report(dict(os.environ))
    if args.report:
        args.report.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
