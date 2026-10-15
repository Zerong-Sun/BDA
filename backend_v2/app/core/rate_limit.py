from __future__ import annotations

import hashlib
import uuid
from typing import cast

from redis import Redis
from redis.exceptions import RedisError

from .config import get_settings
from .problem import DomainError

_FIXED_WINDOW = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


def _consume(key: str, limit: int) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    try:
        redis = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            decode_responses=True,
        )
        result = cast(
            list[int],
            redis.eval(_FIXED_WINDOW, 1, key, str(settings.rate_limit_window_seconds)),
        )
        count, ttl = result
    except RedisError as exc:
        if settings.rate_limit_fail_closed:
            raise DomainError(
                "rate_limit_unavailable",
                "Rate-limit service is unavailable",
                status_code=503,
            ) from exc
        return
    if int(count) > limit:
        retry_after = max(1, int(ttl))
        raise DomainError(
            "rate_limit_exceeded",
            "Request quota exceeded",
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )


def enforce_login_quota(client_ip: str, username: str) -> None:
    digest = hashlib.sha256(username.strip().lower().encode()).hexdigest()[:24]
    _consume(f"bda:rate:login:{client_ip}:{digest}", get_settings().rate_limit_login)


def enforce_account_quota(client_ip: str) -> None:
    """Bound credential hashing and signup attempts even when usernames vary."""
    _consume(f"bda:rate:account:{get_settings().auth_realm}:{client_ip}", get_settings().rate_limit_login)


def enforce_public_calculator_quota(client_ip: str) -> None:
    settings = get_settings()
    _consume(f"bda:rate:public-calculator:{settings.auth_realm}:{client_ip}", settings.rate_limit_expensive)


def enforce_public_workspace_quota(client_ip: str) -> None:
    settings = get_settings()
    _consume(f"bda:rate:public-workspace:{settings.auth_realm}:{client_ip}", settings.public_workspace_read_limit)


def enforce_project_quota(user_id: uuid.UUID, organization_id: uuid.UUID, action: str) -> None:
    expensive = action in {"compute", "research_import", "autopilot"}
    category = "expensive" if expensive else "write"
    limit = get_settings().rate_limit_expensive if expensive else get_settings().rate_limit_write
    _consume(f"bda:rate:{category}:user:{user_id}", limit)
    _consume(f"bda:rate:{category}:organization:{organization_id}", limit)
