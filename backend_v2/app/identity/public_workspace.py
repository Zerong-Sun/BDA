"""Resolve anonymous readers to an explicitly provisioned, passwordless viewer.

No session or credential is issued. The ordinary organization authorization and
PostgreSQL RLS apply to all reads. A dedicated publishing organization is required.
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import set_request_rls_context
from ..core.problem import DomainError
from ..core.rate_limit import enforce_public_workspace_quota
from .models import OrganizationMember, User


def public_workspace_user(request: Request, session: Session) -> User:
    settings = get_settings()
    if not settings.public_workspace_enabled:
        raise DomainError("not_authenticated", "Authentication is required", status_code=401)
    if request.method not in {"GET", "HEAD"}:
        raise DomainError(
            "public_workspace_read_only", "Sign in to Private to create or change research", status_code=403
        )
    enforce_public_workspace_quota(request.client.host if request.client else "unknown")
    user = session.get(User, settings.public_workspace_user_id)
    if (
        user is None
        or not user.enabled
        or user.role != "viewer"
        or user.password_hash
        or user.oidc_subject
        or user.oidc_issuer
    ):
        raise DomainError(
            "public_workspace_unavailable", "Public workspace viewer is not configured safely", status_code=503
        )
    set_request_rls_context(session, user_id=user.id, is_global_admin=False)
    memberships = list(session.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)))
    if (
        len(memberships) != 1
        or memberships[0].organization_id != settings.public_workspace_organization_id
        or memberships[0].role != "viewer"
    ):
        raise DomainError(
            "public_workspace_unavailable",
            "Public workspace requires one dedicated publishing organization",
            status_code=503,
        )
    return user
