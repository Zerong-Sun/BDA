from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TargetKind = Literal["protein", "small_molecule"]


class TargetUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sequence: str | None = Field(default=None, max_length=100000)
    uniprot_accession: str | None = Field(default=None, max_length=32)
    organism: str | None = Field(default=None, max_length=200)
    target_kind: TargetKind = "protein"
    # {"ccd": "TCI", "inchikey": ..., "smiles": ...} - any one identifies the molecule.
    chemical_identity: dict = Field(default_factory=dict)


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sequence: str | None = Field(default=None, max_length=100000)
    uniprot_accession: str | None = Field(default=None, max_length=32)
    organism: str | None = Field(default=None, max_length=200)
    target_kind: TargetKind | None = None
    chemical_identity: dict | None = None


class TargetStructureAttach(BaseModel):
    artifact_id: uuid.UUID


class TargetStructureImport(BaseModel):
    source: str = Field(pattern="^(pdb|artifact)$")
    pdb_id: str | None = Field(default=None, min_length=4, max_length=16)
    artifact_id: uuid.UUID | None = None
    format: str = Field(default="pdb", pattern="^(pdb|cif|mmcif)$")
    attach_to_target: bool = True
    metadata: dict = Field(default_factory=dict)


class TargetStructurePrepare(BaseModel):
    source_artifact_id: uuid.UUID
    selected_chains: list[str] = Field(default_factory=list, max_length=100)
    remove_waters: bool = True
    remove_heteroatoms: bool = False


class TargetStructureReview(BaseModel):
    approve: bool


class PrimaryTargetUpdate(BaseModel):
    target_id: uuid.UUID


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    sequence: str | None
    uniprot_accession: str | None
    organism: str | None
    identity_status: str
    structure_artifact_id: uuid.UUID | None
    structure_status: str
    target_kind: TargetKind = "protein"
    chemical_identity: dict = Field(default_factory=dict)
    version: int
    created_at: datetime
    updated_at: datetime


class TargetPage(BaseModel):
    items: list[TargetResponse]
    next_cursor: str | None = None


class TargetStructureRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_id: uuid.UUID
    source_artifact_id: uuid.UUID
    prepared_artifact_id: uuid.UUID | None
    options: dict
    status: str
    approved: bool
    version: int
    created_at: datetime
    updated_at: datetime


class TargetStructureRevisionPage(BaseModel):
    items: list[TargetStructureRevisionResponse]
    next_cursor: str | None = None


class TargetStructureView(BaseModel):
    target_id: uuid.UUID
    structure_status: str
    current_artifact_id: uuid.UUID | None
    approved_revision_id: uuid.UUID | None
    latest_revision: TargetStructureRevisionResponse | None


class TargetStructureImportAccepted(BaseModel):
    operation_id: uuid.UUID
    target_id: uuid.UUID
    status: str = "pending"
