from __future__ import annotations

from ..core.problem import DomainError


def parse_if_match(value: str | None) -> int:
    if not value:
        raise DomainError("precondition_required", "If-Match is required", status_code=428)
    try:
        return int(value.strip('W/"'))
    except ValueError as exc:
        raise DomainError(
            "invalid_if_match", "If-Match must contain a numeric resource version", status_code=422
        ) from exc


def etag(version: int) -> str:
    return f'W/"{version}"'
