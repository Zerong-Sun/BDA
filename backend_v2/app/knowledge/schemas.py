from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    entry_type: str = "note"
    source: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class KnowledgeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1)
    entry_type: str | None = None
    source: dict | None = None
    tags: list[str] | None = None


class KnowledgeDeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool = True


class KnowledgeResponse(KnowledgeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class KnowledgePage(BaseModel):
    items: list[KnowledgeResponse]
    next_cursor: str | None = None
