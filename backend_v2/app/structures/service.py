"""Artifact id -> bytes -> kernel. The one impure step of structure analysis.

Same shape as `wetlab/analysis.py`, and for the same reason: the API never
receives a file body, so a structure reaches the server as an artifact id and
the analysis has to start by fetching it. The difference is that nothing is
recorded afterwards. These are reads; a stored copy of a derived residue list
would be a second source of truth for something the artifact already determines.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.problem import DomainError
from . import kernels

#: A structure is coordinates, not a trajectory. A 3000-residue complex in
#: mmCIF is a few MB; the cap is a guard against a mis-typed artifact id
#: pulling an MD trajectory or a genome into memory.
MAX_STRUCTURE_BYTES = 32 * 1024 * 1024


def _artifact(session: Session, project_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
    artifact = session.scalar(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.deleted_at.is_(None))
    )
    if artifact is None or artifact.project_id != project_id:
        # Same answer for "no such artifact" and "belongs to another project":
        # distinguishing them tells a caller which ids exist elsewhere.
        raise DomainError(
            "artifact_not_found",
            "No such artifact in this project.",
            status_code=404,
        )
    return artifact


def _text(artifact: Artifact) -> str:
    try:
        body = ObjectStorage().read_bytes(artifact.object_key, max_bytes=MAX_STRUCTURE_BYTES)
    except ValueError as error:
        raise DomainError(
            "structure_file_too_large",
            f"That artifact is larger than {MAX_STRUCTURE_BYTES // (1024 * 1024)} MB.",
            status_code=413,
        ) from error
    # Structure formats are ASCII by specification. Decoding with replacement
    # rather than failing means one stray byte in a REMARK does not make the
    # coordinates unreadable.
    return body.decode("utf-8", errors="replace")


def _run(session: Session, project_id: uuid.UUID, artifact_id: uuid.UUID, work: Any) -> dict[str, Any]:
    artifact = _artifact(session, project_id, artifact_id)
    try:
        result = work(_text(artifact))
    except kernels.StructureFormatError as error:
        raise DomainError("structure_unreadable", str(error), status_code=422) from error
    return {
        "artifact_id": str(artifact.id),
        "filename": artifact.filename,
        "checksum_sha256": artifact.checksum_sha256,
        **result,
    }


def analyse(session: Session, project_id: uuid.UUID, artifact_id: uuid.UUID) -> dict[str, Any]:
    return _run(session, project_id, artifact_id, kernels.analyse)


def contacts(
    session: Session,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    chain_a: str,
    chain_b: str,
    cutoff_angstrom: float = 4.5,
) -> dict[str, Any]:
    return _run(
        session,
        project_id,
        artifact_id,
        lambda text: kernels.contacts(
            text, chain_a=chain_a, chain_b=chain_b, cutoff_angstrom=cutoff_angstrom
        ),
    )


def site(
    session: Session,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    chain: str | None = None,
    residue_seq: int | None = None,
    ligand: str | None = None,
    radius_angstrom: float = 5.0,
) -> dict[str, Any]:
    return _run(
        session,
        project_id,
        artifact_id,
        lambda text: kernels.site(
            text,
            chain=chain,
            residue_seq=residue_seq,
            ligand=ligand,
            radius_angstrom=radius_angstrom,
        ),
    )
