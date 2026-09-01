from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..compute.models import Job, OutboxEvent
from ..core.config import get_settings
from ..core.database import SessionFactory
from ..core.metrics import MISSING_WORKER_QUEUES
from ..registry.models import ComputeNode, ModelPlugin, RegistryServer
from .models import MigrationRun, Operation
from .repository import PlatformRepository
from .schemas_operations import OperationsSummary


def operations_summary(session: Session) -> OperationsSummary:
    def grouped(model, field) -> dict[str, int]:
        return {str(key): int(value) for key, value in session.execute(select(field, func.count()).group_by(field))}

    missing_artifacts = int(
        session.scalar(select(func.count(Artifact.id)).where(Artifact.status.in_(["failed", "missing"]))) or 0
    )
    registry_health: dict[str, int] = {}
    for model, field in (
        (RegistryServer, RegistryServer.health_status),
        (ComputeNode, ComputeNode.health_status),
        (ModelPlugin, ModelPlugin.validation_status),
    ):
        for key, value in grouped(model, field).items():
            registry_health[key] = registry_health.get(key, 0) + value
    latest = session.scalar(select(MigrationRun).order_by(MigrationRun.created_at.desc()).limit(1))
    return OperationsSummary(
        jobs_by_status=grouped(Job, Job.status),
        operations_by_status=grouped(Operation, Operation.status),
        outbox_backlog=int(
            session.scalar(select(func.count(OutboxEvent.id)).where(OutboxEvent.published_at.is_(None))) or 0
        ),
        missing_artifacts=missing_artifacts,
        registry_health=registry_health,
        latest_migration_status=latest.status if latest else None,
    )


def visible_operation(session: Session, operation_id: uuid.UUID) -> Operation | None:
    return session.get(Operation, operation_id)


def dependency_health() -> dict[str, str]:
    checks: dict[str, str] = {}
    settings = get_settings()
    try:
        with SessionFactory() as session:
            repository = PlatformRepository(session)
            repository.ping()
            actual_revision = repository.schema_revision()
            checks["schema_revision"] = "ok" if actual_revision == settings.schema_revision else "mismatch"
            heartbeats = repository.recent_worker_heartbeats(datetime.now(UTC) - timedelta(seconds=90))
            valid_queues = {
                queue
                for heartbeat in heartbeats
                if heartbeat.build_revision == settings.build_revision
                and heartbeat.schema_revision == settings.schema_revision
                for queue in heartbeat.queues
            }
            missing_queues = set(settings.required_worker_queue_list) - valid_queues
            MISSING_WORKER_QUEUES.set(len(missing_queues))
            checks["worker_heartbeats"] = "ok" if not missing_queues else "missing"
        checks["postgresql"] = "ok"
    except Exception:
        MISSING_WORKER_QUEUES.set(len(settings.required_worker_queue_list))
        checks["postgresql"] = "unavailable"
        checks["schema_revision"] = "unavailable"
        checks["worker_heartbeats"] = "unavailable"
    try:
        Redis.from_url(settings.redis_url).ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    try:
        checks["minio"] = "ok" if ObjectStorage().healthy() else "missing"
    except Exception:
        checks["minio"] = "unavailable"
    return checks
