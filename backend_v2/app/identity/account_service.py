from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.config import get_settings
from ..core.problem import DomainError
from .account_repository import AccountRepository
from .account_schemas import AccountGrantCreate, RegisterRequest, registration_username
from .models import AccountGrant, Organization, OrganizationMember, User
from .repository import IdentityRepository
from .service import authenticate, hash_password


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _active_grant(session: Session, raw: str, purpose: str) -> AccountGrant:
    grant = AccountRepository(session).grant_by_hash(_digest(raw))
    now = datetime.now(UTC)
    expires = (
        grant.expires_at.replace(tzinfo=UTC)
        if grant and grant.expires_at.tzinfo is None
        else grant.expires_at
        if grant
        else now
    )
    if (
        grant is None
        or grant.realm != get_settings().auth_realm
        or grant.purpose != purpose
        or grant.used_at
        or grant.revoked_at
        or expires <= now
    ):
        raise DomainError("invalid_account_code", "The code is invalid, expired or already used", status_code=400)
    return grant


def register_account(session: Session, payload: RegisterRequest) -> User:
    settings = get_settings()
    if settings.registration_mode == "closed":
        raise DomainError("registration_closed", "Registration is closed; contact your administrator", status_code=403)
    if settings.registration_mode == "invite" and not payload.invitation_token:
        raise DomainError("invitation_required", "An administrator invitation is required", status_code=403)
    password_hash = hash_password(payload.password)
    grant = _active_grant(session, payload.invitation_token, "invitation") if payload.invitation_token else None
    if grant and grant.username != payload.username:
        raise DomainError(
            "invitation_username_mismatch", "Use the username specified in your invitation", status_code=400
        )
    repo = AccountRepository(session)
    if repo.username_taken(payload.username):
        raise DomainError("username_unavailable", "This username is unavailable", status_code=409)
    try:
        # A savepoint makes both a duplicate username race and an invitation retry
        # atomic: no consumed code, empty organization or half-created user remains.
        with session.begin_nested():
            user = User(
                username=payload.username,
                display_name=payload.display_name,
                password_hash=password_hash,
                role=grant.member_role if grant else "researcher",
            )
            session.add(user)
            session.flush()
            if grant:
                if grant.organization_id is None or session.get(Organization, grant.organization_id) is None:
                    raise DomainError(
                        "invitation_unavailable", "The invited organization is unavailable", status_code=409
                    )
                organization_id = grant.organization_id
                membership_role = grant.member_role
                grant.used_at = datetime.now(UTC)
                grant.version += 1
            else:
                organization = Organization(name=f"Workspace · {user.id}")
                session.add(organization)
                session.flush()
                organization_id = organization.id
                membership_role = "owner"
            session.add(OrganizationMember(organization_id=organization_id, user_id=user.id, role=membership_role))
            record_audit(
                session,
                action="account.register",
                entity_type="user",
                entity_id=user.id,
                actor_id=user.id,
                organization_id=organization_id,
                payload={"mode": "invitation" if grant else "self_service"},
            )
            session.flush()
    except IntegrityError as exc:
        raise DomainError("username_unavailable", "This username is unavailable", status_code=409) from exc
    return user


def issue_grant(session: Session, payload: AccountGrantCreate, actor: User) -> tuple[AccountGrant, str]:
    if actor.role != "admin":
        raise DomainError("forbidden", "Administrator access is required", status_code=403)
    username = payload.username.strip()
    user = None
    if payload.purpose == "invitation":
        if get_settings().registration_mode == "closed":
            raise DomainError(
                "registration_closed", "Enable invitation registration before issuing invitations", status_code=409
            )
        try:
            username = registration_username(username)
        except ValueError as exc:
            raise DomainError("invalid_username", str(exc), status_code=422) from exc
        if AccountRepository(session).username_taken(username):
            raise DomainError("username_unavailable", "This username is unavailable", status_code=409)
        if payload.organization_id is None or session.get(Organization, payload.organization_id) is None:
            raise DomainError("organization_not_found", "Choose an existing organization", status_code=404)
    else:
        user = IdentityRepository(session).user_by_username(username)
        if user is None or not user.password_hash:
            raise DomainError("local_account_not_found", "An enabled password account was not found", status_code=404)
        if payload.organization_id is not None:
            raise DomainError(
                "invalid_recovery_scope", "Recovery codes cannot change organization membership", status_code=422
            )
    raw = secrets.token_urlsafe(32)
    grant = AccountGrant(
        purpose=payload.purpose,
        realm=get_settings().auth_realm,
        token_hash=_digest(raw),
        username=username,
        organization_id=payload.organization_id,
        member_role=payload.member_role,
        user_id=user.id if user else None,
        created_by=actor.id,
        credential_version=user.version if user else None,
        expires_at=datetime.now(UTC)
        + timedelta(hours=min(payload.expires_in_hours, 1) if user else payload.expires_in_hours),
    )
    session.add(grant)
    session.flush()
    record_audit(
        session,
        action="account.grant.issue",
        entity_type="account_grant",
        entity_id=grant.id,
        actor_id=actor.id,
        payload={"purpose": grant.purpose, "username": grant.username},
    )
    return grant, raw


def revoke_grant(session: Session, grant_id: uuid.UUID, version: int, actor: User) -> AccountGrant:
    if actor.role != "admin":
        raise DomainError("forbidden", "Administrator access is required", status_code=403)
    grant = AccountRepository(session).locked_grant(grant_id)
    if grant is None or grant.realm != get_settings().auth_realm:
        raise DomainError("grant_not_found", "Account code was not found", status_code=404)
    if grant.version != version:
        raise DomainError("version_conflict", "The code changed; reload before revoking", status_code=412)
    if grant.used_at or grant.revoked_at:
        raise DomainError("grant_inactive", "The code has already been used or revoked", status_code=409)
    grant.revoked_at = datetime.now(UTC)
    grant.version += 1
    record_audit(
        session, action="account.grant.revoke", entity_type="account_grant", entity_id=grant.id, actor_id=actor.id
    )
    return grant


def _replace_password(session: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    user.version += 1
    AccountRepository(session).revoke_sessions(user.id, datetime.now(UTC))


def change_password(session: Session, user: User, current: str, new: str, version: int) -> None:
    repo = AccountRepository(session)
    locked = repo.locked_user(user.id)
    if locked is None or not locked.enabled:
        raise DomainError("invalid_credentials", "Account is unavailable", status_code=401)
    if locked.version != version:
        raise DomainError("version_conflict", "Account changed; reload before changing your password", status_code=412)
    authenticate(session, locked.username, current)
    _replace_password(session, locked, hash_password(new))
    record_audit(session, action="account.password.change", entity_type="user", entity_id=locked.id, actor_id=locked.id)


def reset_password(session: Session, raw: str, password: str) -> None:
    encoded = hash_password(password)
    grant = _active_grant(session, raw, "password_reset")
    user = AccountRepository(session).locked_user(grant.user_id) if grant.user_id else None
    if user is None or not user.enabled or not user.password_hash or user.version != grant.credential_version:
        raise DomainError("invalid_account_code", "The recovery code is unavailable", status_code=400)
    _replace_password(session, user, encoded)
    grant.used_at = datetime.now(UTC)
    grant.version += 1
    record_audit(session, action="account.password.reset", entity_type="user", entity_id=user.id, actor_id=user.id)


def logout(session: Session, raw: str) -> None:
    if raw:
        stored = IdentityRepository(session).refresh_session(_digest(raw))
        if stored and stored.realm == get_settings().auth_realm:
            repo = AccountRepository(session)
            repo.locked_user(stored.user_id)
            repo.revoke_family(stored.family_id, datetime.now(UTC))
