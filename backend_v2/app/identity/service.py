from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from datetime import UTC, datetime, timedelta

import bcrypt
import httpx
import jwt
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.problem import DomainError
from .models import OIDCLoginState, Organization, OrganizationMember, RefreshSession, User
from .repository import IdentityRepository


def hash_password(password: str) -> str:
    if (
        len(password) < 8
        or not any(char.isalpha() for char in password)
        or not any(char.isdigit() for char in password)
    ):
        raise DomainError("weak_password", "Password must contain letters and digits and be at least 8 characters")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


# A real bcrypt hash at the same cost as hash_password, compared against when no user
# matches. Skipping the comparison made a miss return in microseconds and a hit in tens of
# milliseconds, which is enough to enumerate usernames from response time alone.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"bda-v2-timing-equalizer", bcrypt.gensalt(rounds=12))


def authenticate(session: Session, username: str, password: str) -> User:
    user = IdentityRepository(session).user_by_username(username)
    stored = user.password_hash.encode() if user and user.password_hash else _DUMMY_PASSWORD_HASH
    matched = bcrypt.checkpw(password.encode(), stored)
    if user is None or not user.password_hash or not matched:
        raise DomainError("invalid_credentials", "Invalid username or password", status_code=401)
    return user


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)
    except jwt.PyJWTError as exc:
        raise DomainError("invalid_token", "Access token is invalid or expired", status_code=401) from exc


def issue_refresh_token(session: Session, user: User) -> str:
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    return raw


def rotate_refresh_token(session: Session, raw_token: str) -> tuple[User, str]:
    now = datetime.now(UTC)
    repo = IdentityRepository(session)
    stored = repo.active_refresh_session(hashlib.sha256(raw_token.encode()).hexdigest(), now)
    if stored is None:
        raise DomainError("invalid_refresh_token", "Refresh token is invalid or expired", status_code=401)
    user = repo.user_by_id(stored.user_id)
    if user is None or not user.enabled:
        raise DomainError("invalid_refresh_token", "Refresh token user is unavailable", status_code=401)
    stored.revoked_at = now
    return user, issue_refresh_token(session, user)


def bootstrap_admin(session: Session, *, username: str, password: str) -> User:
    repo = IdentityRepository(session)
    existing = repo.user_by_username_any_status(username)
    password_hash = hash_password(password)
    if existing is None:
        user = User(username=username, display_name="Administrator", role="admin", password_hash=password_hash)
        session.add(user)
        session.flush()
    else:
        user = existing
        user.password_hash = password_hash
        user.role = "admin"
        user.enabled = True
    organization = session.query(Organization).filter_by(legacy_id="bootstrap-default").one_or_none()
    if organization is None:
        organization = Organization(name="Default Organization", legacy_id="bootstrap-default")
        session.add(organization)
        session.flush()
    membership = session.get(OrganizationMember, (organization.id, user.id))
    if membership is None:
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    return user


# Asymmetric only. The list an ``id_token`` may be verified with must come from us, not
# from the provider's discovery document: taking it from the document lets whoever can
# influence that document choose the algorithm, which is the setup for algorithm
# confusion. Symmetric algorithms are excluded outright - verifying an RS256-shaped token
# under HS256 is exactly the substitution being prevented.
ALLOWED_ID_TOKEN_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"})


def _configured_redirect_uris(config: dict[str, str]) -> list[str]:
    raw = config.get("redirect_uris", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _require_allowed_redirect(config: dict[str, str], redirect_uri: str) -> str:
    """Only hand the provider a redirect this deployment declared.

    The value arrives as a query parameter. A provider is expected to enforce its own
    registered list, but accepting an arbitrary one here makes this service a party to
    sending an authorization code somewhere it does not belong.
    """
    allowed = _configured_redirect_uris(config)
    if not allowed:
        raise DomainError(
            "oidc_redirect_uri_not_configured",
            "This OIDC provider declares no permitted redirect URIs",
            status_code=500,
        )
    if redirect_uri not in allowed:
        raise DomainError("oidc_redirect_uri_rejected", "redirect_uri is not permitted", status_code=400)
    return redirect_uri


def _discover(issuer: str) -> dict:
    """Fetch a provider's discovery document over TLS.

    Plaintext discovery would let a network attacker choose the authorization, token and
    JWKS endpoints, which defeats every check performed afterwards.
    """
    if not issuer.startswith("https://"):
        raise DomainError("oidc_issuer_insecure", "OIDC issuer must be an https URL", status_code=500)
    return httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=10).raise_for_status().json()


def begin_oidc(session: Session, provider: str, redirect_uri: str) -> tuple[str, str]:
    config = get_settings().oidc_providers.get(provider)
    if not config:
        raise DomainError("oidc_provider_not_found", "OIDC provider is not configured", status_code=404)
    redirect_uri = _require_allowed_redirect(config, redirect_uri)
    issuer = config.get("issuer", "").rstrip("/")
    discovery = _discover(issuer)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    session.add(
        OIDCLoginState(
            state=state,
            provider=provider,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": config["client_id"],
            "redirect_uri": redirect_uri,
            "scope": config.get("scopes", "openid profile email"),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{discovery['authorization_endpoint']}?{query}", state


def complete_oidc(session: Session, provider: str, state: str, code: str) -> User:
    login_state = session.get(OIDCLoginState, state)
    expires_at = login_state.expires_at if login_state else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if login_state is None or login_state.provider != provider or expires_at is None or expires_at <= datetime.now(UTC):
        raise DomainError("invalid_oidc_state", "OIDC state is invalid or expired", status_code=400)
    provider_name = login_state.provider
    code_verifier = login_state.code_verifier
    redirect_uri = login_state.redirect_uri
    session.delete(login_state)
    session.commit()  # consume state and release the DB connection before provider I/O
    config = get_settings().oidc_providers.get(provider)
    if not config:
        raise DomainError("oidc_provider_not_found", "OIDC provider is not configured", status_code=404)
    issuer = config.get("issuer", "").rstrip("/")
    discovery = _discover(issuer)
    token_response = httpx.post(
        discovery["token_endpoint"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": config["client_id"],
            "client_secret": config.get("client_secret", ""),
            "code_verifier": code_verifier,
        },
        timeout=15,
    )
    token_response.raise_for_status()
    id_token = token_response.json().get("id_token")
    if not id_token:
        raise DomainError("oidc_token_missing", "OIDC provider did not return an ID token", status_code=502)
    advertised = discovery.get("id_token_signing_alg_values_supported") or ["RS256"]
    algorithms = sorted(ALLOWED_ID_TOKEN_ALGORITHMS.intersection(advertised))
    if not algorithms:
        raise DomainError(
            "oidc_no_supported_algorithm",
            "OIDC provider advertises no acceptable ID token signing algorithm",
            status_code=502,
        )
    signing_key = jwt.PyJWKClient(discovery["jwks_uri"]).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=algorithms,
        audience=config["client_id"],
        issuer=issuer,
    )
    subject = str(claims["sub"])
    repo = IdentityRepository(session)
    user = repo.user_by_oidc(issuer, subject)
    if user is None:
        base_username = str(claims.get("preferred_username") or claims.get("email") or f"oidc-{subject}")[:100]
        username = base_username
        suffix = 1
        while repo.user_by_username(username):
            suffix += 1
            username = f"{base_username[:110]}-{suffix}"
        user = User(
            username=username,
            display_name=str(claims.get("name") or username)[:160],
            role="researcher",
            oidc_issuer=issuer,
            oidc_subject=subject,
        )
        session.add(user)
        session.flush()
    if provider_name != provider:
        raise DomainError("invalid_oidc_state", "OIDC provider changed during callback", status_code=400)
    return user
