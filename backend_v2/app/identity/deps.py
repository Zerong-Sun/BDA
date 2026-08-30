from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.database import SessionFactory, get_session
from ..core.problem import DomainError
from .models import User
from .repository import IdentityRepository
from .service import decode_access_token

bearer = HTTPBearer(auto_error=False)


def _resolve_user(
    credentials: HTTPAuthorizationCredentials | None,
    session: Session,
) -> User:
    if credentials is None:
        raise DomainError("not_authenticated", "Authentication is required", status_code=401)
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = __import__("uuid").UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise DomainError("invalid_token", "Access token subject is invalid", status_code=401) from exc
    user = IdentityRepository(session).user_by_id(user_id)
    if user is None or not user.enabled:
        raise DomainError("invalid_token", "Access token user is unavailable", status_code=401)
    return user


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    return _resolve_user(credentials, session)


def streaming_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    """Authenticate before a stream is created without retaining a request UoW.

    FastAPI keeps yield-based dependencies alive until a streaming response is
    closed.  Using ``current_user`` on SSE routes therefore pins one database
    connection per client.  This dependency owns and closes its short session
    before returning the detached, scalar-only user identity.
    """

    with SessionFactory() as session:
        user = _resolve_user(credentials, session)
        session.expunge(user)
        return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise DomainError("forbidden", "The current user cannot perform this action", status_code=403)
        return user

    return dependency


def require_command(user: User = Depends(current_user)) -> User:
    if user.role == "viewer":
        raise DomainError("forbidden", "Viewer accounts are read-only", status_code=403)
    return user
