from __future__ import annotations

import base64
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CursorPage(BaseModel):
    items: list
    next_cursor: str | None = None


class CursorParams(BaseModel):
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


def encode_cursor(value: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")


def decode_cursor(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        return uuid.UUID(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError) as exc:
        from .problem import DomainError

        raise DomainError("invalid_cursor", "The pagination cursor is invalid", status_code=422) from exc


# --- time-ordered (keyset) cursors -----------------------------------------------------
#
# The uuid-only cursor above assumes rows are listed in id order. Anything read as a
# chronology - a project timeline, an event log - has to be ordered by *when it
# happened*, and id order is unrelated to that. Paging such a list on id alone silently
# skips or repeats rows.
#
# A timestamp alone is not a safe key either, because two entries can share one instant.
# These helpers therefore carry the pair (occurred_at, id): the timestamp orders the
# page, the id breaks ties so the key is total and the cursor is stable.
#
# Kept in core rather than in one domain module because it is not timeline-specific -
# any future time-ordered listing should reuse it instead of inventing a third cursor.

_CURSOR_SEPARATOR = "|"


def encode_time_cursor(moment: datetime, value: uuid.UUID) -> str:
    raw = f"{moment.isoformat()}{_CURSOR_SEPARATOR}{value}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_time_cursor(value: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not value:
        return None
    from .problem import DomainError

    try:
        padded = value + "=" * (-len(value) % 4)
        moment_text, _, id_text = base64.urlsafe_b64decode(padded).decode().partition(_CURSOR_SEPARATOR)
        return datetime.fromisoformat(moment_text), uuid.UUID(id_text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DomainError("invalid_cursor", "The pagination cursor is invalid", status_code=422) from exc
