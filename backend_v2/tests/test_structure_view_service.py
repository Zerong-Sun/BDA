"""The one impure step of showing a structure: artifact id -> scene.

`molviewspec` is tested as a pure function and `kernels` as geometry. What is
left here is the part that can only go wrong in the joining: reading the wrong
project's artifact, guessing the format from a filename instead of the bytes,
and handing out a URL without saying that it expires.

Object storage is stubbed. The point of this test is not that MinIO signs a
URL - it is that the scene carries whatever URL storage gave, that the format
comes from the file's contents, and that a caller in the wrong project is
refused before any of that happens.
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

PDB_TEXT = """ATOM      1  N   MET A   1      11.104   6.134  -6.504  1.00 20.00           N
ATOM      2  CA  MET A   1      11.639   6.071  -5.147  1.00 20.00           C
ATOM      3  C   ARG A 164      12.000   7.000  -4.000  1.00 20.00           C
END
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


class _Storage:
    """Enough of `ObjectStorage` for a scene: the bytes and a signed URL."""

    def __init__(self, text: str = PDB_TEXT) -> None:
        self.text = text

    def read_bytes(self, object_key: str, max_bytes: int | None = None) -> bytes:  # noqa: ARG002
        return self.text.encode()

    def download_url(self, object_key: str, *, ttl_seconds: int | None = None) -> str:  # noqa: ARG002
        return f"https://storage.test/{object_key}?signature=abc"


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> _Storage:
    stub = _Storage()
    monkeypatch.setattr(structures, "ObjectStorage", lambda: stub)
    return stub


def _artifact(session: Session) -> tuple[Project, Artifact]:
    n = next(_counter)
    user = User(username=f"view-{n}", display_name="V", role="researcher", enabled=True)
    organization = Organization(name=f"View Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"view-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    artifact = Artifact(
        project_id=project.id, artifact_type="structure", filename="target.ent",
        content_type="chemical/x-pdb", object_key=f"s/{n}.bin", checksum_sha256="0" * 64,
        size_bytes=len(PDB_TEXT), status="available", created_by=user.id,
    )
    session.add(artifact)
    session.flush()
    return project, artifact


def test_a_scene_is_built_from_the_bytes_and_the_signed_url(session: Session, storage: _Storage) -> None:
    project, artifact = _artifact(session)

    result = structures.view(
        session, project.id, artifact.id, residues=[{"chain": "A", "seq": 164}], label="Hotspots"
    )

    assert result["format"] == "pdb"
    download = result["scene"]["root"]["children"][0]
    assert download["params"]["url"].startswith("https://storage.test/")
    assert result["scene_format"].startswith("molviewspec/")
    # The URL expires, and a scene pasted into a document next week should fail
    # visibly rather than render an empty viewer.
    assert result["url_ttl_seconds"] == 900


def test_the_format_comes_from_the_bytes_and_not_from_the_filename(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`target.ent` is mmCIF here. An extension is whatever somebody typed."""
    project, artifact = _artifact(session)
    monkeypatch.setattr(
        structures, "ObjectStorage", lambda: _Storage("data_TEST\n_atom_site.id\n1\n")
    )

    assert structures.view(session, project.id, artifact.id)["format"] == "mmcif"


def test_the_highlighted_residues_come_back_with_the_scene(session: Session, storage: _Storage) -> None:
    """The picker renders this list; the scene alone would make it re-parse one."""
    project, artifact = _artifact(session)

    result = structures.view(session, project.id, artifact.id, residues=[{"chain": "A", "seq": 164}])

    assert result["highlighted"] == [{"chain": "A", "seq": 164}]


def test_another_projects_artifact_is_not_rendered(session: Session, storage: _Storage) -> None:
    _project, artifact = _artifact(session)
    other, _other_artifact = _artifact(session)

    with pytest.raises(DomainError) as failure:
        structures.view(session, other.id, artifact.id)

    assert failure.value.status_code == 404


def test_an_unknown_artifact_is_a_404(session: Session, storage: _Storage) -> None:
    project, _artifact_row = _artifact(session)

    with pytest.raises(DomainError) as failure:
        structures.view(session, project.id, uuid.uuid4())

    assert failure.value.status_code == 404


def test_a_file_that_is_not_a_structure_is_refused_with_a_reason(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, artifact = _artifact(session)
    monkeypatch.setattr(structures, "ObjectStorage", lambda: _Storage("hello, world\n"))

    with pytest.raises(DomainError) as failure:
        structures.view(session, project.id, artifact.id)

    assert failure.value.status_code == 422


def test_a_selection_too_large_to_mean_anything_is_refused(session: Session, storage: _Storage) -> None:
    project, artifact = _artifact(session)
    everything = [{"chain": "A", "seq": index} for index in range(500)]

    with pytest.raises(DomainError) as failure:
        structures.view(session, project.id, artifact.id, residues=everything)

    assert failure.value.status_code == 422
