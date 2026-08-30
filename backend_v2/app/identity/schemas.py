from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class OIDCAuthorizationResponse(BaseModel):
    authorization_url: str
    state: str


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class OrganizationMemberCreate(BaseModel):
    user_id: uuid.UUID
    role: str = Field(pattern="^(owner|admin|researcher|viewer)$")


class OrganizationMemberResponse(BaseModel):
    """A membership, joined with the identity it grants the role to.

    The username and display name travel with it because a membership keyed only by
    user UUID cannot be reviewed: "who is in this organization" is the question the
    screen exists to answer, and a list of UUIDs does not answer it.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    display_name: str
    role: str


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legacy_id: str | None
    name: str
    version: int
    created_at: datetime
