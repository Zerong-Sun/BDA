"""Operator-approved egress boundary for requests carrying research and API keys."""
from __future__ import annotations

from urllib.parse import urlsplit

from ..core.config import get_settings
from ..core.problem import DomainError


def _origin(endpoint: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(character.isspace() or ord(character) < 32 for character in endpoint)
            or "\\" in endpoint
        ):
            raise ValueError
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        if port <= 0:
            raise ValueError
        return parsed.scheme, parsed.hostname.lower(), port
    except ValueError as exc:
        raise DomainError("llm_endpoint_invalid", "Model endpoint must be an HTTP(S) URL without credentials, query or fragment", status_code=422) from exc


def validate_llm_endpoint(endpoint: str, *, require_approval: bool = True) -> None:
    origin = _origin(endpoint)
    settings = get_settings()
    if settings.is_production and origin[0] != "https":
        raise DomainError("llm_endpoint_tls_required", "Production model endpoints require HTTPS", status_code=422)
    if not require_approval:
        return
    approved = []
    for value in settings.llm_allowed_endpoint_origins.split(","):
        value = value.strip()
        if not value:
            continue
        # Accept exact origins only. A path must not silently widen an operator's
        # intended policy; wildcards are deliberately unsupported.
        if urlsplit(value).path not in {"", "/"} or "*" in value:
            raise DomainError("llm_egress_policy_invalid", "Approved model endpoints must be exact origins", status_code=503)
        approved.append(_origin(value))
    if origin not in approved:
        raise DomainError(
            "llm_endpoint_not_approved",
            "The model endpoint origin must be approved by the deployment administrator before research or credentials can be sent",
            status_code=422,
        )
