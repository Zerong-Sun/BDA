from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import UserResponse


def registration_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9._-]{2,63}", value):
        raise ValueError("Use 3–64 characters: start with a letter, then letters, digits, dots, underscores or hyphens")
    return value


class AuthConfigResponse(BaseModel):
    deployment_kind: str
    registration_mode: str
    realm: str
    public_portal_url: str
    private_portal_url: str
    public_workspace_enabled: bool = False


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=8, max_length=256)
    invitation_token: str | None = Field(default=None, min_length=20, max_length=256)

    _username = field_validator("username")(registration_username)

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Display name is required")
        return value.strip()


class AccountResponse(UserResponse):
    version: int
    has_password: bool


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class AccountGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Literal["invitation", "password_reset"]
    username: str = Field(min_length=1, max_length=120)
    organization_id: uuid.UUID | None = None
    member_role: Literal["viewer", "researcher"] = "viewer"
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class AccountGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    purpose: str
    username: str
    organization_id: uuid.UUID | None
    member_role: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None


class AccountGrantIssued(BaseModel):
    grant: AccountGrantResponse
    token: str


class AccountGrantPage(BaseModel):
    items: list[AccountGrantResponse]
    next_cursor: str | None = None
