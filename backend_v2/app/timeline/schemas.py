from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ENTRY_TYPES, OUTCOMES

# Keys allowed inside `provenance`. Restricted so a caller cannot invent a fifth spelling
# of "job_ids" that no reader will ever look for; unknown keys are rejected loudly rather
# than stored and forgotten.
PROVENANCE_KEYS = frozenset(
    {"job_ids", "candidate_ids", "artifact_ids", "workflow_run_ids", "finding_ids", "external_refs"}
)


def _check_entry_type(value: str) -> str:
    if value not in ENTRY_TYPES:
        raise ValueError(f"entry_type must be one of {sorted(ENTRY_TYPES)}")
    return value


def _check_outcome(value: str) -> str:
    if value not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
    return value


def _check_provenance(value: dict) -> dict:
    unknown = set(value) - PROVENANCE_KEYS
    if unknown:
        raise ValueError(f"unknown provenance key(s) {sorted(unknown)}; allowed: {sorted(PROVENANCE_KEYS)}")
    for key, items in value.items():
        if not isinstance(items, list):
            raise ValueError(f"provenance['{key}'] must be a list")
    return value


class CodeRef(BaseModel):
    """A script or module a step actually used."""

    path: str = Field(min_length=1, max_length=400)
    role: str = Field(default="", max_length=200)


class TimelineEntryCreate(BaseModel):
    occurred_at: datetime
    #: Stable per-project identifier for entries generated from a source file, so a
    #: seeder can be re-run without duplicating history. Left unset for hand-written
    #: entries, which have no natural key.
    entry_key: str | None = Field(default=None, max_length=160)
    entry_type: str = "decision"
    phase: str = Field(default="", max_length=80)
    title: str = Field(min_length=1, max_length=300)
    summary: str = ""
    body: str = ""
    outcome: str = "unspecified"
    provenance: dict = Field(default_factory=dict)
    code_refs: list[CodeRef] = Field(default_factory=list)
    supersedes_id: uuid.UUID | None = None
    caused_by_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("entry_type")
    @classmethod
    def _known_entry_type(cls, value: str) -> str:
        return _check_entry_type(value)

    @field_validator("outcome")
    @classmethod
    def _known_outcome(cls, value: str) -> str:
        return _check_outcome(value)

    @field_validator("provenance")
    @classmethod
    def _known_provenance_keys(cls, value: dict) -> dict:
        return _check_provenance(value)


class TimelineEntryUpdate(BaseModel):
    occurred_at: datetime | None = None
    entry_type: str | None = None
    phase: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    summary: str | None = None
    body: str | None = None
    outcome: str | None = None
    provenance: dict | None = None
    code_refs: list[CodeRef] | None = None
    supersedes_id: uuid.UUID | None = None
    caused_by_id: uuid.UUID | None = None
    tags: list[str] | None = None

    # Same rules as on create, reusing the same functions rather than a second copy -
    # a validator that drifts between create and update is how an invalid row gets in
    # through the side door. None means "field not being changed", so it is left alone.
    @field_validator("entry_type")
    @classmethod
    def _known_entry_type(cls, value: str | None) -> str | None:
        return None if value is None else _check_entry_type(value)

    @field_validator("outcome")
    @classmethod
    def _known_outcome(cls, value: str | None) -> str | None:
        return None if value is None else _check_outcome(value)

    @field_validator("provenance")
    @classmethod
    def _known_provenance_keys(cls, value: dict | None) -> dict | None:
        return None if value is None else _check_provenance(value)


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    occurred_at: datetime
    entry_key: str | None
    entry_type: str
    phase: str
    title: str
    summary: str
    body: str
    outcome: str
    provenance: dict
    code_refs: list
    supersedes_id: uuid.UUID | None
    caused_by_id: uuid.UUID | None
    tags: list
    created_by: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class TimelineEntryPage(BaseModel):
    items: list[TimelineEntryResponse]
    next_cursor: str | None = None


class TimelineEntryDeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool = True
