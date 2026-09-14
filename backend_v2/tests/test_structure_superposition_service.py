"""Comparing two artifacts: the half the kernel cannot check.

The geometry is covered against hand-built coordinates. This is about the two
artifacts: both must belong to the caller's project, an unreadable one must be
a 422 rather than a traceback, and the answer must name the two files it
compared - a bare RMSD with no filenames is a number nobody can reproduce.

It is the only call in this domain that reads two artifacts, which is exactly
why the project check is worth a test: a comparison that silently crossed
projects would surface as a plausible number rather than as an error.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.structures import service as structures
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_counter = itertools.count()


def _chain_text(offset: float = 0.0) -> str:
    lines = []
    for index in range(1, 11):
        lines.append(
            f"ATOM  {index:>5} CA   ALA A{index:>4}    "
            f"{index * 3.8 + offset:>8.3f}{0.0:>8.3f}{0.0:>8.3f}  1.00 20.00           C"
        )
    return "\n".join(lines) + "\nEND\n"


class _Storage:
    """Per-key text, so the reference and the mobile file can differ."""

    def __init__(self, texts: dict[str, str]) -> None:
        self.texts = texts

    def read_bytes(self, object_key: str, max_bytes: int | None = None) -> bytes:  # noqa: ARG002
        return self.texts[object_key].encode()

    def download_url(self, object_key: str, *, ttl_seconds: int | None = None) -> str:  # noqa: ARG002
        return f"https://storage.test/{object_key}"


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


def _project(session: Session) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"sup-{n}", display_name="S", role="researcher", enabled=True)
    organization = Organization(name=f"Sup Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"sup-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project, user


def _artifact(session: Session, project: Project, user: User, name: str) -> Artifact:
    artifact = Artifact(
        project_id=project.id, artifact_type="structure", filename=f"{name}.pdb",
        content_type="chemical/x-pdb", object_key=f"{name}-{next(_counter)}.pdb",
        checksum_sha256=f"{abs(hash(name)) % 10:x}" * 64, size_bytes=512,
        status="available", created_by=user.id,
    )
    session.add(artifact)
    session.flush()
    return artifact


def test_the_comparison_names_both_files_it_compared(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    reference = _artifact(session, project, user, "design")
    mobile = _artifact(session, project, user, "prediction")
    monkeypatch.setattr(
        structures, "ObjectStorage",
        lambda: _Storage({reference.object_key: _chain_text(), mobile.object_key: _chain_text(18.0)}),
    )

    result = structures.superpose(
        session, project.id, reference.id, mobile.id, reference_chain="A", mobile_chain="A"
    )

    assert result["reference"]["filename"] == "design.pdb"
    assert result["mobile"]["filename"] == "prediction.pdb"
    # A rigid translation: the fit removes it entirely.
    assert result["rmsd_angstrom"] == pytest.approx(0.0, abs=1e-6)
    assert result["rmsd_before_superposition_angstrom"] > 17


def test_a_reference_from_another_project_is_refused(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    other, other_user = _project(session)
    mine = _artifact(session, project, user, "mine")
    theirs = _artifact(session, other, other_user, "theirs")
    monkeypatch.setattr(
        structures, "ObjectStorage",
        lambda: _Storage({mine.object_key: _chain_text(), theirs.object_key: _chain_text()}),
    )

    with pytest.raises(DomainError) as failure:
        structures.superpose(
            session, project.id, theirs.id, mine.id, reference_chain="A", mobile_chain="A"
        )

    assert failure.value.status_code == 404


def test_a_mobile_file_from_another_project_is_refused_too(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both sides are checked; checking only the first is the easy half-fix."""
    project, user = _project(session)
    other, other_user = _project(session)
    mine = _artifact(session, project, user, "mine")
    theirs = _artifact(session, other, other_user, "theirs")
    monkeypatch.setattr(
        structures, "ObjectStorage",
        lambda: _Storage({mine.object_key: _chain_text(), theirs.object_key: _chain_text()}),
    )

    with pytest.raises(DomainError) as failure:
        structures.superpose(
            session, project.id, mine.id, theirs.id, reference_chain="A", mobile_chain="A"
        )

    assert failure.value.status_code == 404


def test_an_unknown_artifact_is_a_404(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    project, user = _project(session)
    reference = _artifact(session, project, user, "design")
    monkeypatch.setattr(
        structures, "ObjectStorage", lambda: _Storage({reference.object_key: _chain_text()})
    )

    with pytest.raises(DomainError) as failure:
        structures.superpose(
            session, project.id, reference.id, uuid.uuid4(), reference_chain="A", mobile_chain="A"
        )

    assert failure.value.status_code == 404


def test_numbering_that_does_not_overlap_surfaces_as_a_422(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, user = _project(session)
    reference = _artifact(session, project, user, "design")
    mobile = _artifact(session, project, user, "renumbered")
    renumbered = "\n".join(
        f"ATOM  {index:>5} CA   ALA A{index + 500:>4}    "
        f"{index * 3.8:>8.3f}{0.0:>8.3f}{0.0:>8.3f}  1.00 20.00           C"
        for index in range(1, 11)
    ) + "\nEND\n"
    monkeypatch.setattr(
        structures, "ObjectStorage",
        lambda: _Storage({reference.object_key: _chain_text(), mobile.object_key: renumbered}),
    )

    with pytest.raises(DomainError) as failure:
        structures.superpose(
            session, project.id, reference.id, mobile.id, reference_chain="A", mobile_chain="A"
        )

    assert failure.value.status_code == 422
