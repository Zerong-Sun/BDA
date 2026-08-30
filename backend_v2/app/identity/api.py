from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_session
from .deps import current_user
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

router = APIRouter(prefix="/auth", tags=["identity"])


def _token_response(user: User) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=settings.access_token_minutes * 60,
        user=UserResponse.model_validate(user),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "bda_v2_refresh",
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/api/v2/auth",
    )


@router.post("/token", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_session)) -> TokenResponse:
    user = authenticate(session, payload.username, payload.password)
    _set_refresh_cookie(response, issue_refresh_token(session, user))
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    response: Response,
    cookie_token: str | None = Cookie(default=None, alias="bda_v2_refresh"),
    session: Session = Depends(get_session),
) -> TokenResponse:
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
