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
from . import kernels, molviewspec

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


def superpose(
    session: Session,
    project_id: uuid.UUID,
    reference_artifact_id: uuid.UUID,
    mobile_artifact_id: uuid.UUID,
    *,
    reference_chain: str,
    mobile_chain: str,
) -> dict[str, Any]:
    """Fit one structure onto another and report how far off it lands.

    The only call here that reads two artifacts, so it cannot use `_run`: both
    have to be resolved and checked against the same project before either is
    fetched. A comparison that silently crossed projects would be the one place
    this domain leaked, and it would look like a number rather than an error.
    """
    reference = _artifact(session, project_id, reference_artifact_id)
    mobile = _artifact(session, project_id, mobile_artifact_id)
    try:
        result = kernels.superpose(
            _text(reference),
            _text(mobile),
            reference_chain=reference_chain,
            mobile_chain=mobile_chain,
        )
    except kernels.StructureFormatError as error:
        raise DomainError("structure_unreadable", str(error), status_code=422) from error
    return {
        "reference": {
            "artifact_id": str(reference.id),
            "filename": reference.filename,
            "checksum_sha256": reference.checksum_sha256,
        },
        "mobile": {
            "artifact_id": str(mobile.id),
            "filename": mobile.filename,
            "checksum_sha256": mobile.checksum_sha256,
        },
        **result,
    }


def interface(
    session: Session,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    chain_a: str,
    chain_b: str,
    cutoff_angstrom: float = 4.5,
) -> dict[str, Any]:
    """How much surface two chains bury, and what the contact is made of.

    `contacts` says which residues touch; this says what that costs. Kept
    beside it rather than folded into it because the two have different
    expense: a contact list is a neighbour search, and this parses the model
    three times to compute solvent accessibility with and without each partner.
    """
    return _run(
        session,
        project_id,
        artifact_id,
        lambda text: kernels.interface(
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


def view(
    session: Session,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    residues: list[dict[str, Any]] | None = None,
    title: str = "",
    label: str = "",
) -> dict[str, Any]:
    """A MolViewSpec scene of this artifact, with the given residues picked out.

    The one place a structure becomes something a person can be shown rather
    than told about. It stays a read: the scene is derived from the artifact
    every time, so there is no stored copy to go stale against the coordinates.

    The URL inside the scene is a presigned GET with the storage layer's default
    lifetime, which is why the result says how long it lasts. A scene pasted
    into a document a week later should fail visibly rather than render an
    empty viewer.
    """
    artifact = _artifact(session, project_id, artifact_id)
    text = _text(artifact)
    try:
        fmt = kernels.detect_format(text)
    except kernels.StructureFormatError as error:
        raise DomainError("structure_unreadable", str(error), status_code=422) from error
    try:
        built = molviewspec.scene(
            url=ObjectStorage().download_url(artifact.object_key),
            fmt=fmt,
            highlights=residues or [],
            title=title or artifact.filename,
            label=label,
        )
    except molviewspec.SceneError as error:
        raise DomainError("structure_scene_invalid", str(error), status_code=422) from error
    return {
        "artifact_id": str(artifact.id),
        "filename": artifact.filename,
        "checksum_sha256": artifact.checksum_sha256,
        "format": fmt,
        "highlighted": list(residues or []),
        "scene_format": f"molviewspec/{molviewspec.MVS_VERSION}",
        "scene": built,
        "url_ttl_seconds": 900,
    }
