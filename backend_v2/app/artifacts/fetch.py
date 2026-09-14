"""Artifact id -> the bytes behind it, with the project check that must not be skipped.

`structures/service.py` and `wetlab/analysis.py` each grew their own copy of
this: look the artifact up, refuse it if it belongs to another project, pull it
from object storage, refuse it if it is enormous. A third copy would be the one
that forgets the project check - the check is the only thing standing between
an artifact id and cross-project reads - so it lives here once.

The caps and the error codes stay with the caller. A structure and an
instrument trace have different notions of "too large", and a reader who sees
`alignment_file_too_large` learns more than one who sees `file_too_large`.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import Artifact
from .storage import ObjectStorage


def artifact_row(session: Session, project_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
    """The artifact, if this project owns it.

    "No such artifact" and "belongs to another project" are the same answer on
    purpose: distinguishing them tells a caller which ids exist elsewhere.
    """
    artifact = session.scalar(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None))
    )
    if artifact is None or artifact.project_id != project_id:
        raise DomainError(
            "artifact_not_found",
            "No such artifact in this project.",
            status_code=404,
        )
    return artifact


def artifact_text(
    artifact: Artifact, *, max_bytes: int, too_large_code: str, storage: Any | None = None
) -> str:
    """The artifact's bytes as text, or a 413 naming the limit it passed.

    Decoded with replacement rather than strictly: the formats this is used for
    are ASCII by specification, and one stray byte in a comment line should not
    make the whole file unreadable.

    `storage` is injectable because moving this read out of the calling domains
    moved the seam their tests already patch. A caller that passes its own
    `ObjectStorage` keeps that seam where it was; passing nothing uses the real
    one, which is what the callers who never patched it want.
    """
    try:
        body = (storage or ObjectStorage()).read_bytes(artifact.object_key, max_bytes=max_bytes)
    except ValueError as error:
        raise DomainError(
            too_large_code,
            f"That artifact is larger than {max_bytes // (1024 * 1024)} MB.",
            status_code=413,
        ) from error
    return body.decode("utf-8", errors="replace")
