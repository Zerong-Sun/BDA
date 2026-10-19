"""Frozen, project-scoped research delivery with RO-Crate 1.1 metadata.

No presigned URLs or storage credentials are exported. Metrics retain their
evidence kind; experiment records are separate. No redistribution licence is granted.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..candidates.models import Candidate, CandidateMetric
from ..core.problem import DomainError
from ..experiments.models import ExperimentResult

MAX_RECORDS = 10_000
MAX_BYTES = 100 * 1024 * 1024


def _json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def _record(row: Any, fields: str) -> dict:
    result = {}
    for field in fields.split():
        value = getattr(row, field)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()
        result[field] = value
    return result


def _bounded(session: Session, query: Any) -> list:
    rows = list(session.scalars(query.limit(MAX_RECORDS + 1)))
    if len(rows) > MAX_RECORDS:
        raise DomainError("delivery_selection_too_large", "Choose a smaller delivery selection", status_code=422)
    return rows


def snapshot_selection(
    session: Session, project_id: uuid.UUID, selection: dict, *, allow_locked_transaction: bool = False,
) -> dict:
    """Freeze committed PostgreSQL rows in one independent, permission-preserving snapshot.

    The caller's transaction is never committed, rolled back or flushed. A normal
    request must have performed reads only. The legacy delivery worker may opt in
    after locking its package, provided it has made no project-data writes: that
    internal path also exports committed data only. SQLite keeps the caller's
    transaction for isolated unit-test fixtures; it is not a production backend.
    """
    if session.get_bind().dialect.name != "postgresql":
        return _collect_snapshot(session, project_id, selection)
    if session.new or session.dirty or session.deleted:
        raise DomainError("delivery_uncommitted_changes",
                          "Commit project changes before requesting a frozen delivery", status_code=409)
    source = session.connection()
    context = source.execute(text("""
        SELECT current_user AS role,
               current_setting('search_path') AS search_path,
               current_setting('bda.user_id', true) AS user_id,
               current_setting('bda.is_global_admin', true) AS is_global_admin,
               current_setting('bda.worker_project_id', true) AS worker_project_id,
               txid_current_if_assigned() AS transaction_id
    """)).mappings().one()
    if context["transaction_id"] is not None and not allow_locked_transaction:
        raise DomainError("delivery_uncommitted_changes",
                          "Request delivery in a separate transaction after committing project changes; "
                          "the current transaction has written or locked rows", status_code=409)
    # Always open another pooled connection: changing isolation on the existing
    # transaction would either fail or invalidate the caller's unit of work.
    with source.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            role = connection.dialect.identifier_preparer.quote_identifier(context["role"])
            connection.exec_driver_sql(f"SET LOCAL ROLE {role}")
            # Copy effective database context, including SET LOCAL overrides and
            # worker fences, rather than relying on session.info or ambient auth.
            connection.execute(text("""
                SELECT set_config('search_path', :search_path, true),
                       set_config('bda.user_id', :user_id, true),
                       set_config('bda.is_global_admin', :is_global_admin, true),
                       set_config('bda.worker_project_id', :worker_project_id, true)
            """), {key: context[key] or "" for key in (
                "search_path", "user_id", "is_global_admin", "worker_project_id",
            )})
            with Session(bind=connection, autoflush=False) as reader:
                snapshot = _collect_snapshot(reader, project_id, selection)
            snapshot["consistency"] = "postgresql-repeatable-read-committed"
            return snapshot


def _collect_snapshot(session: Session, project_id: uuid.UUID, selection: dict) -> dict:
    """Collect bounded records using the caller's already-established read view."""
    try:
        selected = {uuid.UUID(str(value)) for value in selection.get("candidate_ids", [])}
    except (TypeError, ValueError) as exc:
        raise DomainError("delivery_invalid_selection", "Candidate IDs must be UUIDs", status_code=422) from exc
    query = select(Candidate).where(Candidate.project_id == project_id).order_by(Candidate.id)
    if selected:
        query = query.where(Candidate.id.in_(selected))
    candidates = _bounded(session, query)
    ids = [row.id for row in candidates]
    if selected and selected != set(ids):
        raise DomainError("delivery_invalid_selection", "Some candidates are unavailable in this project", status_code=422)
    metrics = _bounded(session, select(CandidateMetric).where(CandidateMetric.candidate_id.in_(ids)).order_by(CandidateMetric.id)) if ids else []
    results = []
    if selection.get("include_experiment_results", True):
        result_query = select(ExperimentResult).where(ExperimentResult.project_id == project_id).order_by(ExperimentResult.id)
        if selected:
            result_query = result_query.where(ExperimentResult.candidate_id.in_(ids))
        results = _bounded(session, result_query)
    artifact_ids = {artifact_id for row in candidates for artifact_id in (row.structure_artifact_id, row.complex_artifact_id) if artifact_id}
    artifact_ids.update(row.source_artifact_id for row in results if row.source_artifact_id)
    artifacts = _bounded(session, select(Artifact).where(Artifact.id.in_(artifact_ids), Artifact.project_id == project_id,
                                                       Artifact.status == "available", Artifact.deleted_at.is_(None)).order_by(Artifact.id)) if artifact_ids else []
    if artifact_ids != {row.id for row in artifacts}:
        raise DomainError("delivery_source_unavailable", "A referenced source file is unavailable in this project", status_code=409)
    snapshot = {
        "schema_version": "2", "project_id": str(project_id), "frozen_at": datetime.now(UTC).isoformat(),
        "candidates": [_record(row, "id version candidate_key name candidate_kind status rank score scores properties structure_artifact_id complex_artifact_id source_job_id") for row in candidates],
        "metrics": [_record(row, "id version candidate_id metric_key value method model_variant evidence_kind assessor condition unit context source_job_id source_experiment_result_id") for row in metrics],
        "experiment_results": [_record(row, "id version candidate_id candidate_ref source_artifact_id batch_key experiment_type pass_status value unit conclusion failure_reason result_metadata created_at") for row in results],
        "artifacts": [_record(row, "id version artifact_type filename content_type size_bytes checksum_sha256") for row in artifacts],
    }
    expected_bytes = sum(row.size_bytes for row in artifacts) + len(_json(snapshot))
    if expected_bytes > MAX_BYTES:
        raise DomainError("delivery_selection_too_large", "Delivery is limited to 100 MiB of uncompressed content; choose fewer candidates", status_code=422)
    return snapshot


def assemble_bundle(session: Session, storage: ObjectStorage, package_id: uuid.UUID, name: str, snapshot: dict, selection: dict) -> tuple[bytes, dict]:
    """Verify all source bytes before exposing an available package."""
    project_id = uuid.UUID(snapshot["project_id"])
    files: dict[str, bytes] = {
        "candidates.json": _json(snapshot["candidates"]),
        "candidate-metrics.json": _json(snapshot["metrics"]),
        "experiment-results.json": _json(snapshot["experiment_results"]),
    }
    total = sum(map(len, files.values()))
    descriptions = []
    for frozen in snapshot["artifacts"]:
        artifact = session.scalar(select(Artifact).where(Artifact.id == uuid.UUID(frozen["id"]), Artifact.project_id == project_id,
                                                        Artifact.status == "available", Artifact.deleted_at.is_(None)))
        if artifact is None or artifact.checksum_sha256 != frozen["checksum_sha256"] or artifact.size_bytes != frozen["size_bytes"]:
            raise DomainError("delivery_source_changed", "A frozen source file is no longer available with its original content", status_code=409)
        if frozen["size_bytes"] < 0 or total + frozen["size_bytes"] > MAX_BYTES:
            raise DomainError("delivery_selection_too_large", "Delivery exceeds its content limit", status_code=422)
        content = storage.read_bytes(artifact.object_key, max_bytes=frozen["size_bytes"])
        if len(content) != frozen["size_bytes"] or hashlib.sha256(content).hexdigest() != frozen["checksum_sha256"]:
            raise DomainError("delivery_checksum_mismatch", "A source file did not match its frozen checksum", status_code=409)
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", frozen["filename"]).strip(".")[:160] or "artifact"
        path = f"artifacts/{frozen['id']}/{filename}"
        files[path] = content
        total += len(content)
        descriptions.append({"@id": path, "@type": "File", "name": frozen["filename"], "encodingFormat": frozen["content_type"],
                             "contentSize": str(len(content)), "identifier": f"urn:uuid:{frozen['id']}"})
    manifest = {
        "schema_version": "2", "package_id": str(package_id), "project_id": str(project_id), "frozen_at": snapshot["frozen_at"],
        "consistency": snapshot.get("consistency", "caller-transaction"),
        "selection": {key: value for key, value in selection.items() if key != "_snapshot"},
        "record_counts": {key: len(snapshot[key]) for key in ("candidates", "metrics", "experiment_results", "artifacts")},
        "artifacts": snapshot["artifacts"],
        "files": [{"path": path, "size_bytes": len(data), "checksum_sha256": hashlib.sha256(data).hexdigest()} for path, data in files.items()],
        "limitations": ["Model predictions and measurements are separate records; scores do not establish experimental success.",
                        "Export does not grant redistribution rights. Review source and project licences before sharing.",
                        "This is a frozen selected-data export, not a full database or executable environment backup."],
    }
    files["manifest.json"] = _json(manifest)
    for path in ("candidates.json", "candidate-metrics.json", "experiment-results.json", "manifest.json"):
        descriptions.append({"@id": path, "@type": "File", "encodingFormat": "application/json", "contentSize": str(len(files[path]))})
    crate = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}, "about": {"@id": "./"}},
        {"@id": "./", "@type": "Dataset", "name": name, "identifier": f"urn:uuid:{package_id}",
         "description": "Frozen BDA candidate, metric and experiment selection with verified source files.",
         "datePublished": snapshot["frozen_at"], "license": "No redistribution licence is granted by this export; source and project rights apply.",
         "hasPart": [{"@id": item["@id"]} for item in descriptions]}, *descriptions,
    ]}
    files["ro-crate-metadata.json"] = _json(crate)
    if sum(map(len, files.values())) > MAX_BYTES:
        raise DomainError("delivery_selection_too_large", "Delivery exceeds its content limit including metadata", status_code=422)
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            entry = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content)
    return body.getvalue(), manifest["record_counts"]
