from __future__ import annotations

import re

from ..core.problem import DomainError


def parse_if_match(value: str | None) -> int:
    if not value:
        raise DomainError("precondition_required", "If-Match is required", status_code=428)
    match = re.fullmatch(r'(?:W/)?"([0-9]+)"', value.strip())
    if match is None:
        raise DomainError(
            "invalid_if_match", "If-Match must contain a numeric resource version", status_code=422
        )
    try:
        return int(match[1])
    except ValueError as exc:
        raise DomainError("invalid_if_match", "Resource version is too long", status_code=422) from exc


def etag(version: int) -> str:
    return f'W/"{version}"'
