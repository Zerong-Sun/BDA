"""Versioned data-transfer policy; shared by graph editing, preview and dispatch."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Predicate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str = Field(min_length=1, max_length=160)
    op: Literal["gt", "gte", "lt", "lte", "eq", "ne"] = "gte"
    value: float = Field(allow_inf_nan=False)


class Rules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator: Literal["and", "or"] = "and"
    conditions: list[Predicate] = Field(default_factory=list, max_length=100)
    sort_metric: str | None = None
    descending: bool = True
    top_n: int | None = Field(default=None, ge=1, le=1000000)


class StructurePolicy(BaseModel):
    preset: Literal["multi_helix", "structured", "beta_sheet"] = "multi_helix"
    min_strands: int = Field(default=2, ge=1)
    model_config = ConfigDict(extra="forbid")
    chains: list[str] = Field(min_length=1, max_length=100)
    start: int | None = None
    end: int | None = None
    min_helix_length: int = Field(default=4, ge=1)
    min_helices: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def region(self):
        if any(not chain.strip() for chain in self.chains) or len(set(self.chains)) != len(self.chains):
            raise ValueError("Design chains must be nonempty and unique")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("structure region start must be <= end")
        return self


class GatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["automatic", "manual", "review", "integrity", "dependency"] = "automatic"
    configured: bool = False
    rules: Rules = Field(default_factory=Rules)
    structure: StructurePolicy | None = None
    script_preview_id: uuid.UUID | None = None
    script: str | None = Field(default=None, max_length=100000)


class ConnectionUpdate(BaseModel):
    edges: list[dict] = Field(max_length=500)


class GateRelease(BaseModel):
    version: int
    selected_ids: list[str] = Field(max_length=100000)


class ScriptImport(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=100000)
    language: Literal["python", "shell"]


class GatePreview(BaseModel):
    source_job_id: uuid.UUID | None = None
    policy: GatePolicy
