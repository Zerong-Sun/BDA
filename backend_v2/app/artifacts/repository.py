from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Artifact, ArtifactLineageEdge, ArtifactUpload


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upload(self, upload_id: uuid.UUID, *, for_update: bool = False) -> ArtifactUpload | None:
        query = select(ArtifactUpload).where(ArtifactUpload.id == upload_id)
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def artifact(self, artifact_id: uuid.UUID) -> Artifact | None:
        return self.session.scalar(select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None)))

    def artifact_for_upload(self, upload_id: uuid.UUID) -> Artifact | None:
        return self.session.scalar(select(Artifact).where(Artifact.upload_id == upload_id))

    def list_project(
        self,
        project_id: uuid.UUID,
        *,
        after: uuid.UUID | None,
        limit: int,
        artifact_type: str | None = None,
    ) -> list[Artifact]:
        query = select(Artifact).where(Artifact.project_id == project_id, Artifact.deleted_at.is_(None))
        if artifact_type:
            query = query.where(Artifact.artifact_type == artifact_type)
        if after:
            query = query.where(Artifact.id > after)
        return list(self.session.scalars(query.order_by(Artifact.id).limit(limit + 1)))

    def lineage(self, artifact_id: uuid.UUID) -> tuple[list[ArtifactLineageEdge], list[ArtifactLineageEdge]]:
        upstream = list(
            self.session.scalars(
                select(ArtifactLineageEdge)
                .where(ArtifactLineageEdge.child_artifact_id == artifact_id)
                .order_by(ArtifactLineageEdge.id)
            )
        )
        downstream = list(
            self.session.scalars(
                select(ArtifactLineageEdge)
                .where(ArtifactLineageEdge.parent_artifact_id == artifact_id)
                .order_by(ArtifactLineageEdge.id)
            )
        )
        return upstream, downstream
