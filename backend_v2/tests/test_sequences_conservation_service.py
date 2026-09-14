"""Alignment artifact -> conservation, and the refusals on the way.

The arithmetic is covered in test_sequences_conservation.py. What matters here
is the boundary the kernel knows nothing about: whose project the file is in,
how big it may be, and what happens when the bytes are not an alignment.

Storage is patched on `artifacts.fetch` rather than on the sequences module,
because that is where this domain reads from - the structure domain injects its
own `ObjectStorage` so its long-standing seam keeps working, and this one does
not need to.
"""

from __future__ import annotations

import hashlib
import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts import fetch as artifacts_fetch
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.sequences import service as sequences
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ALIGNMENT = """\
>query
MKVLAA
>homolog1
MKVLAA
>homolog2
MKILAA
>homolog3
MRVLGA
"""


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch):
    contents: dict[str, bytes] = {}

    class FakeStorage:
        def read_bytes(self, object_key: str, *, max_bytes: int | None = None) -> bytes:
            body = contents[object_key]
            if max_bytes is not None and len(body) > max_bytes:
                raise ValueError("object_too_large")
            return body

    monkeypatch.setattr(artifacts_fetch, "ObjectStorage", FakeStorage)
    return contents


_counter = itertools.count()


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    n = next(_counter)
    user = User(username=f"cons-{n}", display_name="Cons", role="editor", enabled=True)
    organization = Organization(name=f"Cons Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"cons-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _stored_alignment(session: Session, stored, *, text: str = ALIGNMENT) -> tuple[uuid.UUID, Artifact]:
    project_id, user_id = _project(session)
    body = text.encode()
    artifact = Artifact(
        project_id=project_id,
        created_by=user_id,
        artifact_type="msa",
        filename="homologues.a3m",
        content_type="text/plain",
        object_key=f"projects/{project_id}/{uuid.uuid4()}/homologues.a3m",
        size_bytes=len(body),
        checksum_sha256=hashlib.sha256(body).hexdigest(),
    )
    session.add(artifact)
    session.flush()
    stored[artifact.object_key] = body
    return project_id, artifact


def test_the_result_says_which_file_it_was_derived_from(session: Session, stored) -> None:
    """Nothing is recorded, so a number that cannot name its file cannot be re-derived."""
    project_id, artifact = _stored_alignment(session, stored)

    result = sequences.conservation_from_artifact(session, project_id, artifact_id=artifact.id)

    assert result["artifact_id"] == str(artifact.id)
    assert result["filename"] == "homologues.a3m"
    assert result["checksum_sha256"] == artifact.checksum_sha256
    assert result["alignment"]["sequences"] == 4
    assert result["most_conserved"]


def test_another_projects_alignment_is_a_404(session: Session, stored) -> None:
    project_id, _ = _stored_alignment(session, stored)
    _, elsewhere = _stored_alignment(session, stored)

    with pytest.raises(DomainError) as error:
        sequences.conservation_from_artifact(session, project_id, artifact_id=elsewhere.id)

    assert error.value.status_code == 404
    assert error.value.error_code == "artifact_not_found"


def test_a_file_that_is_not_an_alignment_is_refused_with_a_reason(session: Session, stored) -> None:
    project_id, artifact = _stored_alignment(session, stored, text=">only\nMKVLAA\n")

    with pytest.raises(DomainError) as error:
        sequences.conservation_from_artifact(session, project_id, artifact_id=artifact.id)

    assert error.value.status_code == 422
    assert error.value.error_code == "alignment_unreadable"


def test_a_file_too_large_to_read_is_a_413(
    session: Session, stored, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sequences, "MAX_ALIGNMENT_BYTES", 10)
    project_id, artifact = _stored_alignment(session, stored)

    with pytest.raises(DomainError) as error:
        sequences.conservation_from_artifact(session, project_id, artifact_id=artifact.id)

    assert error.value.status_code == 413
    assert error.value.error_code == "alignment_file_too_large"


def test_the_weighting_asked_for_is_the_one_used(session: Session, stored) -> None:
    project_id, artifact = _stored_alignment(session, stored)

    result = sequences.conservation_from_artifact(
        session, project_id, artifact_id=artifact.id, weighting="none"
    )

    assert result["alignment"]["weighting"] == "none"


def test_an_unknown_weighting_is_a_422_not_a_crash(session: Session, stored) -> None:
    project_id, artifact = _stored_alignment(session, stored)

    with pytest.raises(DomainError) as error:
        sequences.conservation_from_artifact(
            session, project_id, artifact_id=artifact.id, weighting="blosum"
        )

    assert error.value.status_code == 422
