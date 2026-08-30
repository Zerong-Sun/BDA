"""Delivery package assembly.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.database import SessionFactory, session_scope


@celery_app.task(name="bda_v2.delivery_build")
def build_delivery_package(package_id: str) -> dict:
    from ..delivery.models import DeliveryPackage

    parsed = uuid.UUID(package_id)
    with SessionFactory() as session:
        package = session.get(DeliveryPackage, parsed)
        if package is None or package.status == "available":
            return {"status": "ignored"}
        selection, project_id, created_by, name = (
            package.selection,
            package.project_id,
            package.created_by,
            package.name,
        )
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"schema_version": "1", "project_id": str(project_id), "selection": selection}, indent=2),
        )
    data = body.getvalue()
    checksum = hashlib.sha256(data).hexdigest()
    key = f"projects/{project_id}/delivery/{parsed}.zip"
    ObjectStorage().put_bytes(key, data, "application/zip")
    with session_scope() as session:
        package = session.get(DeliveryPackage, parsed)
        if package and package.status != "available":
            artifact = Artifact(
                project_id=project_id,
                created_by=created_by,
                artifact_type="delivery_package",
                filename=f"{name}.zip",
                content_type="application/zip",
                object_key=key,
                size_bytes=len(data),
                checksum_sha256=checksum,
                lineage={"delivery_package_id": package_id},
            )
            session.add(artifact)
            session.flush()
            package.artifact_id = artifact.id
            package.status = "available"
            package.version += 1
    return {"status": "available", "package_id": package_id}
