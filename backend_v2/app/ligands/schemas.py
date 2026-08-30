from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LigandCatalogItem(BaseModel):
    id: str
    name: str
    source: str
    metadata: dict = Field(default_factory=dict)


class LigandImportCreate(BaseModel):
    ligand_id: str = Field(min_length=1, max_length=120)
    source: str = Field(default="pubchem", pattern="^pubchem$")
    metadata: dict = Field(default_factory=dict)


class LigandImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    ligand_id: str
    source: str
    status: str
    artifact_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class LigandImportPage(BaseModel):
    items: list[LigandImportResponse]
    next_cursor: str | None = None


class LigandImportAccepted(BaseModel):
    operation_id: uuid.UUID
    ligand_import: LigandImportResponse
