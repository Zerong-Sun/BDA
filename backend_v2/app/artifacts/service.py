from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.config import get_settings
from ..core.metrics import ARTIFACT_CHECKSUM_FAILURES
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from .models import Artifact, ArtifactLineageEdge, ArtifactUpload
from .repository import ArtifactRepository
from .schemas import UploadComplete, UploadCreate
from .storage import ObjectStorage


def _validate_artifact_content(filename: str, content_type: str, body: bytes) -> None:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix in {"pdb", "ent"}:
        text = body.decode("utf-8", errors="strict")
        if not any(line.startswith(("ATOM  ", "HETATM", "MODEL ")) for line in text.splitlines()):
            raise ValueError("pdb_records_missing")
    elif suffix in {"cif", "mmcif"}:
        text = body.decode("utf-8", errors="strict")
        if "data_" not in text[:4096]:
            raise ValueError("mmcif_header_missing")
    elif suffix in {"fa", "fasta", "faa"}:
        if not body.decode("utf-8", errors="strict").lstrip().startswith(">"):
            raise ValueError("fasta_header_missing")
    elif suffix == "json" or content_type == "application/json":
        json.loads(body.decode("utf-8"))
    elif suffix == "csv" or content_type == "text/csv":
        rows = csv.reader(io.StringIO(body.decode("utf-8-sig")))
        if not next(rows, None):
            raise ValueError("csv_header_missing")
    elif suffix in {"zip", "xlsx"}:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if not archive.namelist():
                raise ValueError("archive_empty")
    elif suffix == "pdf" and not body.startswith(b"%PDF-"):
        raise ValueError("pdf_header_invalid")


def create_upload(session: Session, project: Project, payload: UploadCreate, user: User) -> tuple[ArtifactUpload, str]:
    settings = get_settings()
    upload = ArtifactUpload(
        project_id=project.id,
        created_by=user.id,
        filename=payload.filename,
        artifact_type=payload.artifact_type,
        content_type=payload.content_type,
        object_key=f"staging/{uuid.uuid4().hex}",
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.upload_url_ttl_seconds),
    )
    session.add(upload)
    session.flush()
    url = ObjectStorage().upload_url(upload.object_key)
    record_audit(
        session,
        action="artifact.upload.create",
        entity_type="artifact_upload",
        entity_id=upload.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return upload, url


def complete_upload(
    session: Session,
    upload: ArtifactUpload,
    payload: UploadComplete,
    project: Project,
    user: User,
) -> Artifact:
    repo = ArtifactRepository(session)
    existing = repo.artifact_for_upload(upload.id)
    if existing:
        return existing
    expires_at = upload.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if upload.status != "uploading" or expires_at <= datetime.now(UTC):
        raise DomainError("upload_expired", "Artifact upload is no longer active", status_code=409)
    upload_id = upload.id
    object_key = upload.object_key
    filename, content_type, project_id = upload.filename, upload.content_type, project.id
    session.commit()  # release the request connection before object I/O
    storage = ObjectStorage()

    def mark_failed(code: str) -> None:
        failed = repo.upload(upload_id, for_update=True)
        if failed and failed.status == "uploading":
            failed.status = "failed"
            failed.error = code
            failed.version += 1
        session.commit()

    # Hash, validate and persist one bounded snapshot: a still-valid PUT URL can
    # overwrite staging at any time, so a later copy cannot be trusted to match it.
    try:
        body = storage.read_bytes(object_key, max_bytes=get_settings().max_upload_bytes)
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc) == "object_too_large":
            mark_failed("file_too_large")
            raise DomainError("file_too_large", "Uploaded object exceeds the size limit", status_code=413) from exc
        mark_failed("upload_object_missing")
        raise DomainError("upload_object_missing", "Uploaded object could not be inspected", status_code=409) from exc
    size, checksum = len(body), hashlib.sha256(body).hexdigest()
    if checksum.lower() != payload.checksum_sha256.lower():
        ARTIFACT_CHECKSUM_FAILURES.labels("upload").inc()
        mark_failed("checksum_mismatch")
        raise DomainError("checksum_mismatch", "Uploaded object checksum does not match", status_code=409)
    try:
        _validate_artifact_content(filename, content_type, body)
    except Exception as exc:
        mark_failed("artifact_format_invalid")
        raise DomainError(
            "artifact_format_invalid", "Uploaded object does not match its declared format", status_code=422
        ) from exc
    target_key = f"projects/{project_id}/sha256/{checksum}"
    storage.put_bytes(target_key, body, content_type)
    # Retain staging until the orphan reconciler removes it. Deleting before the
    # database commit would make a rolled-back completion impossible to retry.
    refreshed_upload = repo.upload(upload_id, for_update=True)
    if refreshed_upload is None:
        raise DomainError("upload_not_found", "Artifact upload disappeared during completion", status_code=409)
    upload = refreshed_upload
    existing = repo.artifact_for_upload(upload.id)
    if existing:
        return existing
    if upload.status != "uploading":
        raise DomainError("upload_expired", "Artifact upload is no longer active", status_code=409)
    edges_seen: set[tuple[uuid.UUID, str]] = set()
    for edge in payload.lineage_edges:
        pair = (edge.parent_artifact_id, edge.relation)
        if pair in edges_seen:
            raise DomainError("lineage_duplicate", "A lineage parent and relation cannot be repeated", status_code=422)
        edges_seen.add(pair)
    artifact = Artifact(
        project_id=project.id,
        upload_id=upload.id,
        created_by=user.id,
        artifact_type=upload.artifact_type,
        filename=upload.filename,
        content_type=upload.content_type,
        object_key=target_key,
        size_bytes=size,
        checksum_sha256=checksum,
        lineage=payload.lineage,
    )
    session.add(artifact)
    session.flush()
    for edge in payload.lineage_edges:
        parent = repo.artifact(edge.parent_artifact_id)
        if parent is None or parent.project_id != project.id:
            raise DomainError(
                "lineage_parent_invalid",
                "A lineage parent does not exist in the upload project",
                status_code=422,
            )
        if parent.id == artifact.id:
            raise DomainError("lineage_cycle", "An artifact cannot derive from itself", status_code=422)
        session.add(
            ArtifactLineageEdge(
                project_id=project.id,
                parent_artifact_id=parent.id,
                child_artifact_id=artifact.id,
                relation=edge.relation,
                details=edge.details,
            )
        )
    upload.status = "available"
    upload.version += 1
    record_audit(
        session,
        action="artifact.upload.complete",
        entity_type="artifact",
        entity_id=artifact.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={"checksum_sha256": checksum, "size_bytes": size},
    )
    return artifact
