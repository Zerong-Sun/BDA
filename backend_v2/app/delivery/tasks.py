"""Assemble verified research data, source files and RO-Crate metadata."""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select

from ..artifacts.models import Artifact, ArtifactLineageEdge
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.database import SessionFactory, session_scope  # noqa: F401 - shared task fixture compatibility
from ..core.problem import DomainError
from .bundle import assemble_bundle, snapshot_selection
from .models import DeliveryPackage


@celery_app.task(name="bda_v2.delivery_build")
def build_delivery_package(package_id: str) -> dict:
    parsed = uuid.UUID(package_id)
    try:
        with session_scope() as session:
            # Duplicate workers serialize before reading/building the frozen package.
            package = session.scalar(select(DeliveryPackage).where(DeliveryPackage.id == parsed).with_for_update())
            if package is None or package.status == "available":
                return {"status": "ignored"}
            selection = dict(package.selection)
            snapshot = selection.get("_snapshot")
            if snapshot is None:
                # Legacy queued packages had only a selection, with no frozen data.
                # Only the package row has been locked; project data is untouched.
                # The independent read view deliberately includes committed rows only.
                snapshot = snapshot_selection(session, package.project_id, selection, allow_locked_transaction=True)
                selection.update({"_snapshot": snapshot, "format": "ro-crate-1.1", "frozen_at": snapshot["frozen_at"],
                                  "consistency": snapshot.get("consistency", "caller-transaction")})
            storage = ObjectStorage()
            data, counts = assemble_bundle(session, storage, package.id, package.name, snapshot, selection)
            checksum = hashlib.sha256(data).hexdigest()
            key = f"projects/{package.project_id}/delivery/{parsed}/{checksum}.zip"
            storage.put_bytes(key, data, "application/zip")
            artifact = Artifact(project_id=package.project_id, created_by=package.created_by,
                                artifact_type="delivery_package", filename=f"{package.name}.zip",
                                content_type="application/zip", object_key=key, size_bytes=len(data),
                                checksum_sha256=checksum,
                                lineage={"delivery_package_id": package_id, "format": "ro-crate-1.1", "record_counts": counts})
            session.add(artifact)
            session.flush()
            for source in snapshot["artifacts"]:
                session.add(ArtifactLineageEdge(project_id=package.project_id,
                                               parent_artifact_id=uuid.UUID(source["id"]), child_artifact_id=artifact.id,
                                               relation="delivery_includes", details={"checksum_sha256": source["checksum_sha256"]}))
            package.selection = {**selection, "record_counts": counts}
            package.artifact_id = artifact.id
            package.status = "available"
            package.error = None
            package.version += 1
        return {"status": "available", "package_id": package_id}
    except Exception as exc:
        with session_scope() as session:
            package = session.scalar(select(DeliveryPackage).where(DeliveryPackage.id == parsed).with_for_update())
            if package is not None and package.status != "available":
                package.status = "failed"
                package.error = exc.detail if isinstance(exc, DomainError) else "Delivery files could not be verified or assembled."
                package.version += 1
        raise
