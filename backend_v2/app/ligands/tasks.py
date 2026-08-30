"""Ligand import.

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

settings = get_settings()


@celery_app.task(name="bda_v2.ligand_import")


def ligand_import(import_id: str) -> dict:
    import httpx

    from ..ligands.catalog import pubchem_sdf_url
    from ..ligands.models import LigandImport

    parsed = uuid.UUID(import_id)
    with SessionFactory() as session:
        row = session.get(LigandImport, parsed)
        if row is None or row.status == "available":
            return {"status": "ignored"}
        source, project_id, created_by, ligand_id = row.source, row.project_id, row.created_by, row.ligand_id
    if source != "pubchem":
        raise ValueError("ligand_source_unsupported")
    source_url = pubchem_sdf_url(ligand_id)
    response = httpx.get(source_url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    data = response.content
    if len(data) > settings.max_upload_bytes:
        raise ValueError("ligand_file_too_large")
    checksum = hashlib.sha256(data).hexdigest()
    key = f"projects/{project_id}/ligands/{checksum}"
    ObjectStorage().put_bytes(key, data, response.headers.get("content-type", "chemical/x-mdl-sdfile"))
    with session_scope() as session:
        row = session.get(LigandImport, parsed)
        if row and row.status != "available":
            artifact = Artifact(
                project_id=project_id,
                created_by=created_by,
                artifact_type="ligand",
                filename=f"{ligand_id}.sdf",
                content_type=response.headers.get("content-type", "chemical/x-mdl-sdfile"),
                object_key=key,
                size_bytes=len(data),
                checksum_sha256=checksum,
                lineage={"source": source, "source_url": source_url, "ligand_import_id": import_id},
            )
            session.add(artifact)
            session.flush()
            row.artifact_id = artifact.id
            row.status = "available"
            row.version += 1
    return {"import_id": import_id, "status": "available"}
