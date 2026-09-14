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


class HotspotResidue(BaseModel):
    """One residue in the author numbering a person reads off the viewer."""

    chain: str = Field(min_length=1, max_length=4)
    seq: int
    #: The residue name when the caller knows it. "A164" and "A164 ARG" read
    #: differently to somebody checking the set against a structure.
    name: str | None = Field(default=None, max_length=8)


class HotspotSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    target_id: uuid.UUID
    structure_artifact_id: uuid.UUID | None
    label: str
    residues: list[HotspotResidue] = Field(default_factory=list)
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    #: "agent" (proposed), "human" (chosen), or "agent_proposed_human_confirmed".
    #: The same vocabulary as a timeline entry's `decided_by`.
    origin: str
    status: str
    created_by: uuid.UUID
    confirmed_by: uuid.UUID | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class HotspotSetPage(BaseModel):
    items: list[HotspotSetResponse]


class HotspotSetCreate(BaseModel):
    """A set a person chose. An operator's proposal comes through its tool."""

    label: str = Field(min_length=1, max_length=200)
    residues: list[HotspotResidue] = Field(min_length=1, max_length=40)
    structure_artifact_id: uuid.UUID | None = None
    rationale: str = Field(default="", max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class HotspotSetRejection(BaseModel):
    reason: str = Field(default="", max_length=2000)
