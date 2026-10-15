from __future__ import annotations

import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_time_cursor, encode_time_cursor
from ..core.problem import DomainError
from ..core.rate_limit import enforce_account_quota, enforce_login_quota
from . import account_service
from .account_repository import AccountRepository
from .account_schemas import (
    AccountGrantCreate,
    AccountGrantIssued,
    AccountGrantPage,
    AccountGrantResponse,
    AccountResponse,
    AuthConfigResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    RegisterRequest,
)
from .deps import current_user, require_roles
from .models import User
from .schemas import LoginRequest, OIDCAuthorizationResponse, RefreshRequest, TokenResponse, UserResponse
from .service import (
    authenticate,
    begin_oidc,
    complete_oidc,
    create_access_token,
    issue_refresh_token,
    rotate_refresh_token,
)


def _require_auth_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return  # Non-browser clients do not ambiently attach browser cookies.
    settings = get_settings()
    current_portal = settings.public_portal_url if settings.deployment_kind == "public" else settings.private_portal_url
    own_url = urlsplit(str(request.url))
    allowed = {f"{own_url.scheme}://{own_url.netloc}", *settings.cors_origins_list}
    if current_portal:
        # A CORS allowlist may include other tools or the other deployment. It
        # must not let those origins use this portal's ambient refresh cookie.
        allowed = {current_portal.rstrip("/")}
        portal = urlsplit(current_portal)
        if not settings.is_production and portal.hostname in {"localhost", "127.0.0.1", "::1"}:
            port = f":{portal.port}" if portal.port else ""
            allowed.update(f"{portal.scheme}://{host}{port}" for host in ["localhost", "127.0.0.1", "[::1]"])
    if origin not in allowed:
        raise DomainError("auth_origin_rejected", "This origin cannot modify account sessions", status_code=403)


router = APIRouter(prefix="/auth", tags=["identity"], dependencies=[Depends(_require_auth_origin)])


def _token_response(user: User) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=settings.access_token_minutes * 60,
        user=UserResponse.model_validate(user),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/api/v2/auth",
    )


@router.post("/token", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> TokenResponse:
    enforce_login_quota(request.client.host if request.client else "unknown", payload.username)
    user = authenticate(session, payload.username, payload.password)
    _set_refresh_cookie(response, issue_refresh_token(session, user))
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> TokenResponse:
    cookie_token = request.cookies.get(get_settings().refresh_cookie_name)
    user, next_token = rotate_refresh_token(session, payload.refresh_token or cookie_token or "")
    _set_refresh_cookie(response, next_token)
    return _token_response(user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@router.get("/oidc/{provider}/authorize", response_model=OIDCAuthorizationResponse)
def oidc_authorize(
    provider: str,
    redirect_uri: str,
    session: Session = Depends(get_session),
) -> OIDCAuthorizationResponse:
    url, state = begin_oidc(session, provider, redirect_uri)
    return OIDCAuthorizationResponse(authorization_url=url, state=state)


@router.get("/oidc/{provider}/callback", response_model=TokenResponse)
def oidc_callback(
    provider: str,
    state: str,
    code: str,
    response: Response,
    session: Session = Depends(get_session),
) -> TokenResponse:
    user = complete_oidc(session, provider, state, code)
    _set_refresh_cookie(response, issue_refresh_token(session, user))
    return _token_response(user)


@router.get("/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    settings = get_settings()
    return AuthConfigResponse(
        deployment_kind=settings.deployment_kind,
        registration_mode=settings.registration_mode if settings.writes_enabled else "closed",
        realm=settings.auth_realm,
        public_portal_url=settings.public_portal_url,
        private_portal_url=settings.private_portal_url,
        public_workspace_enabled=settings.public_workspace_enabled,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: RegisterRequest, request: Request, response: Response, session: Session = Depends(get_session)
) -> TokenResponse:
    enforce_account_quota(request.client.host if request.client else "unknown")
    user = account_service.register_account(session, payload)
    _set_refresh_cookie(response, issue_refresh_token(session, user))
    response.headers["Cache-Control"] = "no-store"
    return _token_response(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> None:
    settings = get_settings()
    account_service.logout(session, request.cookies.get(settings.refresh_cookie_name, ""))
    response.delete_cookie(
        settings.refresh_cookie_name, path="/api/v2/auth", secure=settings.is_production, httponly=True, samesite="lax"
    )


@router.get("/account", response_model=AccountResponse)
def account(response: Response, user: User = Depends(current_user)) -> AccountResponse:
    response.headers["ETag"] = etag(user.version)
    response.headers["Cache-Control"] = "no-store"
    return AccountResponse(
        **UserResponse.model_validate(user).model_dump(), version=user.version, has_password=bool(user.password_hash)
    )


@router.post("/password", status_code=204, openapi_extra={"x-permission": "account.password.change"})
def password_change(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> None:
    enforce_account_quota(request.client.host if request.client else "unknown")
    account_service.change_password(
        session, user, payload.current_password, payload.new_password, parse_if_match(if_match)
    )
    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/v2/auth")


@router.post("/password/reset", status_code=204)
def password_reset(
    payload: PasswordResetRequest, request: Request, response: Response, session: Session = Depends(get_session)
) -> None:
    enforce_account_quota(request.client.host if request.client else "unknown")
    account_service.reset_password(session, payload.token, payload.new_password)
    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/v2/auth")


@router.get("/grants", response_model=AccountGrantPage)
def list_account_grants(
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles("admin")),
) -> AccountGrantPage:
    del actor
    rows = AccountRepository(session).grants(decode_time_cursor(cursor), limit + 1, get_settings().auth_realm)
    page = rows[:limit]
    return AccountGrantPage(
        items=[AccountGrantResponse.model_validate(row) for row in page],
        next_cursor=encode_time_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
    )


@router.post(
    "/grants", response_model=AccountGrantIssued, status_code=201, openapi_extra={"x-permission": "account.grant.issue"}
)
def issue_account_grant(
    payload: AccountGrantCreate,
    response: Response,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles("admin")),
) -> AccountGrantIssued:
    grant, token = account_service.issue_grant(session, payload, actor)
    response.headers["Cache-Control"] = "no-store"
    return AccountGrantIssued(grant=AccountGrantResponse.model_validate(grant), token=token)


@router.post(
    "/grants/{grant_id}/revoke",
    response_model=AccountGrantResponse,
    openapi_extra={"x-permission": "account.grant.revoke"},
)
def revoke_account_grant(
    grant_id: uuid.UUID,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles("admin")),
) -> AccountGrantResponse:
    return AccountGrantResponse.model_validate(
        account_service.revoke_grant(session, grant_id, parse_if_match(if_match), actor)
    )
