"""Target structure import and preparation.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import uuid

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.config import get_settings
from ..core.database import SessionFactory, session_scope
from ..projects.models import Project

settings = get_settings()


@celery_app.task(name="bda_v2.target_structure_import")


def target_structure_import(target_id: str, payload: dict) -> dict:
    import httpx

    from ..targets.models import Target

    parsed = uuid.UUID(target_id)
    with SessionFactory() as session:
        target = session.get(Target, parsed)
        if target is None:
            return {"target_id": target_id, "status": "missing"}
        project = session.get(Project, target.project_id)
        if project is None:
            return {"target_id": target_id, "status": "missing"}
        project_id, created_by = project.id, project.owner_id
    if payload.get("source") == "artifact":
        artifact_id = uuid.UUID(str(payload["artifact_id"]))
        with session_scope() as session:
            target = session.get(Target, parsed)
            artifact = session.get(Artifact, artifact_id)
            if target is None or artifact is None or artifact.project_id != target.project_id:
                raise ValueError("target_structure_artifact_invalid")
            target.structure_artifact_id = artifact.id
            target.structure_status = "available"
            target.version += 1
        return {"target_id": target_id, "status": "available", "artifact_id": str(artifact_id)}
    pdb_id = str(payload.get("pdb_id", "")).upper()
    fmt = "cif" if payload.get("format") in {"cif", "mmcif"} else "pdb"
    response = httpx.get(
        f"https://files.rcsb.org/download/{pdb_id}.{fmt}",
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    body = response.content
    if not body or len(body) > settings.max_upload_bytes:
        raise ValueError("target_structure_size_invalid")
    checksum = hashlib.sha256(body).hexdigest()
    artifact_id = uuid.uuid4()
    key = f"projects/{project_id}/targets/{parsed}/{artifact_id}.{fmt}"
    content_type = "chemical/x-pdb" if fmt == "pdb" else "chemical/x-mmcif"
    ObjectStorage().put_bytes(key, body, content_type)
    with session_scope() as session:
        target = session.get(Target, parsed)
        if target is None:
            return {"target_id": target_id, "status": "missing"}
        artifact = Artifact(
            id=artifact_id,
            project_id=project_id,
            created_by=created_by,
            artifact_type="target_structure",
            filename=f"{pdb_id}.{fmt}",
            content_type=content_type,
            object_key=key,
            size_bytes=len(body),
            checksum_sha256=checksum,
            lineage={"source": "rcsb", "pdb_id": pdb_id, **(payload.get("metadata") or {})},
        )
        session.add(artifact)
        if payload.get("attach_to_target", True):
            target.structure_artifact_id = artifact.id
            target.structure_status = "available"
            target.version += 1
    return {
        "target_id": target_id,
        "status": "available",
        "artifact_id": str(artifact_id),
        "pdb_id": pdb_id,
        "attached": bool(payload.get("attach_to_target", True)),
    }


@celery_app.task(name="bda_v2.target_structure_prepare")
def target_structure_prepare(revision_id: str) -> dict:
    from ..targets.models import Target, TargetStructureRevision

    parsed = uuid.UUID(revision_id)
    with SessionFactory() as session:
        revision = session.get(TargetStructureRevision, parsed)
        if revision is None:
            return {"revision_id": revision_id, "status": "missing"}
        if revision.status == "available":
            return {"revision_id": revision_id, "status": "available"}
        source = session.get(Artifact, revision.source_artifact_id)
        target = session.get(Target, revision.target_id)
        if source is None or target is None:
            raise ValueError("target_structure_source_missing")
        source_key, project_id, created_by = source.object_key, source.project_id, revision.created_by
        filename, options = source.filename, revision.options
    body = ObjectStorage().read_bytes(source_key, max_bytes=settings.max_upload_bytes)
    selected = set(options.get("selected_chains") or [])
    if filename.lower().endswith(".pdb"):
        lines = []
        for raw in body.decode("utf-8", errors="strict").splitlines(keepends=True):
            record = raw[:6].strip()
            if (
                options.get("remove_waters", True)
                and record in {"ATOM", "HETATM"}
                and raw[17:20].strip() in {"HOH", "WAT"}
            ):
                continue
            if options.get("remove_heteroatoms", False) and record == "HETATM":
                continue
            if selected and record in {"ATOM", "HETATM"} and raw[21:22].strip() not in selected:
                continue
            lines.append(raw)
        prepared = "".join(lines).encode("utf-8")
    else:
        prepared = body
    checksum = hashlib.sha256(prepared).hexdigest()
    artifact_id = uuid.uuid4()
    suffix = filename.rsplit(".", 1)[-1]
    key = f"projects/{project_id}/targets/prepared/{artifact_id}.{suffix}"
    content_type = "chemical/x-pdb" if suffix == "pdb" else "chemical/x-mmcif"
    ObjectStorage().put_bytes(key, prepared, content_type)
    with session_scope() as session:
        revision = session.get(TargetStructureRevision, parsed)
        if revision is None:
            return {"revision_id": revision_id, "status": "missing"}
        artifact = Artifact(
            id=artifact_id,
            project_id=project_id,
            created_by=created_by,
            artifact_type="prepared_target_structure",
            filename=f"prepared-{filename}",
            content_type=content_type,
            object_key=key,
            size_bytes=len(prepared),
            checksum_sha256=checksum,
            lineage={"source_artifact_id": str(revision.source_artifact_id), "revision_id": revision_id},
        )
        session.add(artifact)
        revision.prepared_artifact_id = artifact.id
        revision.status = "available"
        revision.version += 1
        target = session.get(Target, revision.target_id)
        if target:
            target.structure_status = "available"
            target.version += 1
    return {"revision_id": revision_id, "status": "available", "artifact_id": str(artifact_id)}
