"""The impure half of the interface measurement: artifact id in, metrics out.

The geometry is tested against hand-built coordinates in
`test_structure_interface.py`. What only shows up here is the part the kernel
cannot know: that the artifact belongs to this project, that an unreadable file
is a 422 rather than a stack trace, and that a chain the caller invented is
refused rather than measured as an empty interface.
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

# Chain A aspartate facing chain B lysine, 3 A apart - the same arrangement the
# kernel tests reason about, written out so this file stands on its own.
COMPLEX_PDB = """ATOM      1 N    ASP A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2 CA   ASP A   1       1.458   0.000   0.000  1.00 20.00           C
ATOM      3 C    ASP A   1       2.009   1.420   0.000  1.00 20.00           C
ATOM      4 O    ASP A   1       1.251   2.390   0.000  1.00 20.00           O
ATOM      5 CB   ASP A   1       1.988  -0.773   1.200  1.00 20.00           C
ATOM      6 OD1  ASP A   1       3.200  -0.500   1.500  1.00 20.00           O
ATOM      7 N    LYS B   1       6.200  -0.500   1.500  1.00 20.00           N
ATOM      8 CA   LYS B   1       7.658  -0.500   1.500  1.00 20.00           C
ATOM      9 C    LYS B   1       8.209   0.920   1.500  1.00 20.00           C
ATOM     10 O    LYS B   1       7.451   1.890   1.500  1.00 20.00           O
ATOM     11 CB   LYS B   1       8.188  -1.273   2.700  1.00 20.00           C
ATOM     12 NZ   LYS B   1       6.500  -0.500   1.500  1.00 20.00           N
END
"""


class _Storage:
    def __init__(self, text: str = COMPLEX_PDB) -> None:
        self.text = text

    def read_bytes(self, object_key: str, max_bytes: int | None = None) -> bytes:  # noqa: ARG002
        return self.text.encode()

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


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> _Storage:
    stub = _Storage()
    monkeypatch.setattr(structures, "ObjectStorage", lambda: stub)
    return stub


def _artifact(session: Session) -> tuple[Project, Artifact]:
    n = next(_counter)
    user = User(username=f"iface-{n}", display_name="I", role="researcher", enabled=True)
    organization = Organization(name=f"Iface Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"iface-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    artifact = Artifact(
        project_id=project.id, artifact_type="structure", filename="complex.pdb",
        content_type="chemical/x-pdb", object_key=f"c/{n}.pdb", checksum_sha256="0" * 64,
        size_bytes=len(COMPLEX_PDB), status="available", created_by=user.id,
    )
    session.add(artifact)
    session.flush()
    return project, artifact


def test_the_metrics_come_back_with_the_artifact_they_describe(
    session: Session, storage: _Storage
) -> None:
    project, artifact = _artifact(session)

    result = structures.interface(session, project.id, artifact.id, chain_a="A", chain_b="B")

    assert result["artifact_id"] == str(artifact.id)
    assert result["checksum_sha256"] == "0" * 64
    assert result["salt_bridge_count"] >= 1
    assert result["interface_area_a2"] > 0


def test_another_projects_complex_is_not_measured(session: Session, storage: _Storage) -> None:
    _project, artifact = _artifact(session)
    other, _other_artifact = _artifact(session)

    with pytest.raises(DomainError) as failure:
        structures.interface(session, other.id, artifact.id, chain_a="A", chain_b="B")

    assert failure.value.status_code == 404


def test_an_unknown_artifact_is_a_404(session: Session, storage: _Storage) -> None:
    project, _artifact_row = _artifact(session)

    with pytest.raises(DomainError) as failure:
        structures.interface(session, project.id, uuid.uuid4(), chain_a="A", chain_b="B")

    assert failure.value.status_code == 404


def test_a_chain_that_is_not_in_the_file_is_refused(session: Session, storage: _Storage) -> None:
    project, artifact = _artifact(session)

    with pytest.raises(DomainError) as failure:
        structures.interface(session, project.id, artifact.id, chain_a="A", chain_b="Q")

    assert failure.value.status_code == 422


def test_a_file_that_is_not_a_structure_is_refused_with_a_reason(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, artifact = _artifact(session)
    monkeypatch.setattr(structures, "ObjectStorage", lambda: _Storage("not a structure at all\n"))

    with pytest.raises(DomainError) as failure:
        structures.interface(session, project.id, artifact.id, chain_a="A", chain_b="B")

    assert failure.value.status_code == 422
