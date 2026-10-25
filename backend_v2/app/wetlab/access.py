"""Anonymous access is limited to pure calculators in the Public deployment."""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_session
from ..core.rate_limit import enforce_public_calculator_quota
from ..identity.deps import _resolve_user, bearer
from ..identity.models import User


def calculator_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User | None:
    if get_settings().deployment_kind == "public":
        enforce_public_calculator_quota(request.client.host if request.client else "unknown")
        return None
    return _resolve_user(credentials, session)
