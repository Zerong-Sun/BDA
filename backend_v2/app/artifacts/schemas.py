from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadCreate(BaseModel):
    project_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")
    artifact_type: str = Field(min_length=1, max_length=80)
    content_type: str = Field(min_length=1, max_length=160)


class UploadResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]


class UploadComplete(BaseModel):
    checksum_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    lineage: dict = Field(default_factory=dict)
    lineage_edges: list[ArtifactLineageEdgeCreate] = Field(default_factory=list, max_length=500)


class ArtifactLineageEdgeCreate(BaseModel):
    parent_artifact_id: uuid.UUID
    relation: str = Field(default="derived_from", min_length=1, max_length=80)
    details: dict = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    artifact_type: str
    filename: str
    content_type: str
    status: str
    size_bytes: int
    checksum_sha256: str
    lineage: dict
    version: int
    created_at: datetime
    updated_at: datetime
    download_url: str | None = None


class ArtifactPage(BaseModel):
    items: list[ArtifactResponse]
    next_cursor: str | None = None


class ArtifactLineageEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_artifact_id: uuid.UUID
    child_artifact_id: uuid.UUID
    relation: str
    details: dict
    version: int
    created_at: datetime
    updated_at: datetime


class ArtifactLineageResponse(BaseModel):
    artifact: ArtifactResponse
    upstream: list[ArtifactLineageEdgeResponse]
    downstream: list[ArtifactLineageEdgeResponse]
