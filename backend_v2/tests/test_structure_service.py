"""Artifact id -> bytes -> kernel, and the refusals on the way.

The geometry is covered in test_structure_kernels.py. What matters here is the
boundary the kernels deliberately know nothing about: whose project the file is
in, how big it may be, and what happens when the bytes are not a structure.
"""

from __future__ import annotations

import hashlib
import itertools
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.copilot import tools as _copilot_tools  # noqa: F401  (registers the catalogue)
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.structures import service as structures
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from backend_v2.tests.test_structure_kernels import PDB_TEXT
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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

    monkeypatch.setattr(structures, "ObjectStorage", FakeStorage)
    return contents


_counter = itertools.count()


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    n = next(_counter)
    user = User(username=f"struct-{n}", display_name="Struct", role="editor", enabled=True)
    organization = Organization(name=f"Struct Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        name=f"struct-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _artifact(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID, filename: str, body: bytes
) -> Artifact:
    artifact = Artifact(
        project_id=project_id,
        created_by=user_id,
        artifact_type="structure",
        filename=filename,
        content_type="chemical/x-pdb",
        object_key=f"projects/{project_id}/{uuid.uuid4()}/{filename}",
        size_bytes=len(body),
        checksum_sha256=hashlib.sha256(body).hexdigest(),
    )
    session.add(artifact)
    session.flush()
    return artifact


def _stored_structure(session: Session, stored, *, text: str = PDB_TEXT) -> tuple[uuid.UUID, Artifact]:
    project_id, user_id = _project(session)
    body = text.encode()
    artifact = _artifact(session, project_id, user_id, "model.pdb", body)
    stored[artifact.object_key] = body
    return project_id, artifact


def test_analysis_carries_the_artifact_identity_it_was_derived_from(session: Session, stored) -> None:
    """Nothing is recorded, so the result must say what it came from.

    A residue list with no artifact id and no checksum cannot be re-derived, and
    cannot be told apart from one computed against a different upload.
    """
    project_id, artifact = _stored_structure(session, stored)

    result = structures.analyse(session, project_id, artifact.id)

    assert result["artifact_id"] == str(artifact.id)
    assert result["checksum_sha256"] == artifact.checksum_sha256
    assert result["filename"] == "model.pdb"
    assert result["chain_ids"] == ["A", "B"]


def test_contacts_and_sites_reach_the_kernels_with_their_arguments(session: Session, stored) -> None:
    project_id, artifact = _stored_structure(session, stored)

    interface = structures.contacts(
        session, project_id, artifact.id, chain_a="A", chain_b="B", cutoff_angstrom=4.5
    )
    pocket = structures.site(session, project_id, artifact.id, ligand="LIG", radius_angstrom=5.0)

    assert interface["cutoff_angstrom"] == 4.5
    assert interface["pair_count"] >= 1
    assert pocket["centre"]["name"] == "LIG"


def test_an_artifact_from_another_project_is_not_found(session: Session, stored) -> None:
    """Same answer as a missing id, on purpose: the alternative leaks which ids exist."""
    project_id, artifact = _stored_structure(session, stored)
    other_project_id, _ = _project(session)

    with pytest.raises(DomainError) as raised:
        structures.analyse(session, other_project_id, artifact.id)

    assert raised.value.status_code == 404
    with pytest.raises(DomainError) as missing:
        structures.analyse(session, project_id, uuid.uuid4())
    assert missing.value.status_code == 404


def test_a_deleted_artifact_is_not_analysable(session: Session, stored) -> None:
    project_id, artifact = _stored_structure(session, stored)
    artifact.deleted_at = datetime.now(UTC)
    session.flush()

    with pytest.raises(DomainError) as raised:
        structures.analyse(session, project_id, artifact.id)

    assert raised.value.status_code == 404


def test_an_oversized_file_is_refused_rather_than_read_into_memory(
    session: Session, stored, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, artifact = _stored_structure(session, stored)
    monkeypatch.setattr(structures, "MAX_STRUCTURE_BYTES", 10)

    with pytest.raises(DomainError) as raised:
        structures.analyse(session, project_id, artifact.id)

    assert raised.value.error_code == "structure_file_too_large"
    assert raised.value.status_code == 413


def test_a_file_that_is_not_a_structure_is_a_422_not_a_500(session: Session, stored) -> None:
    """The caller passed a real artifact id; the file is simply the wrong kind.

    Letting the kernel's ValueError escape would surface as an internal error
    and read as a platform fault rather than a mis-chosen file.
    """
    project_id, artifact = _stored_structure(session, stored, text="not a structure at all")

    with pytest.raises(DomainError) as raised:
        structures.analyse(session, project_id, artifact.id)

    assert raised.value.status_code == 422
    assert raised.value.error_code == "structure_unreadable"


def test_a_bad_argument_is_a_422_carrying_what_was_wrong(session: Session, stored) -> None:
    project_id, artifact = _stored_structure(session, stored)

    with pytest.raises(DomainError) as raised:
        structures.contacts(session, project_id, artifact.id, chain_a="A", chain_b="Z")

    assert raised.value.status_code == 422
    assert "Z" in str(raised.value.detail)


def test_a_file_with_undecodable_bytes_still_parses_its_coordinates(session: Session, stored) -> None:
    """One stray byte in a REMARK must not make the coordinates unreadable."""
    project_id, user_id = _project(session)
    body = PDB_TEXT.encode().replace(b"TEST STRUCTURE", b"TEST \xff\xfe STRUCT")
    artifact = _artifact(session, project_id, user_id, "model.pdb", body)
    stored[artifact.object_key] = body

    assert structures.analyse(session, project_id, artifact.id)["residue_total"] == 7


# --- Through the tool registry ----------------------------------------------
# The handlers are thin, and thin is where argument coercion hides. An LLM
# writes these arguments, so the cases below are the ones it will actually
# produce: a malformed id, a missing chain, a number sent as a string.


def _context(session: Session, project_id: uuid.UUID) -> ToolContext:
    return ToolContext(project_id=project_id, session=session)


def test_the_three_structure_tools_run_through_the_registry(session: Session, stored) -> None:
    project_id, artifact = _stored_structure(session, stored)
    ctx = _context(session, project_id)
    granted = {"structure-analysis"}

    summary = REGISTRY.execute("analyse_structure", ctx, {"artifact_id": str(artifact.id)}, granted=granted)
    interface = REGISTRY.execute(
        "list_structure_contacts",
        ctx,
        {"artifact_id": str(artifact.id), "chain_a": "A", "chain_b": "B"},
        granted=granted,
    )
    pocket = REGISTRY.execute(
        "describe_structure_site",
        ctx,
        {"artifact_id": str(artifact.id), "ligand": "LIG"},
        granted=granted,
    )

    assert summary["chain_ids"] == ["A", "B"]
    assert interface["cutoff_angstrom"] == 4.5  # the declared default, not None
    assert pocket["radius_angstrom"] == 5.0


def test_numeric_arguments_sent_as_strings_are_coerced(session: Session, stored) -> None:
    """Models emit `"4.0"` for a number field often enough to matter."""
    project_id, artifact = _stored_structure(session, stored)

    result = REGISTRY.execute(
        "list_structure_contacts",
        _context(session, project_id),
        {"artifact_id": str(artifact.id), "chain_a": "A", "chain_b": "B", "cutoff_angstrom": "3.0"},
        granted={"structure-analysis"},
    )

    assert result["cutoff_angstrom"] == 3.0


def test_a_malformed_argument_raises_rather_than_reaching_storage(session: Session, stored) -> None:
    """The agent loop turns these into a tool error the model can read.

    What matters is that they raise before any artifact is fetched, so a
    mistyped id cannot become a lookup in another project.
    """
    project_id, _ = _stored_structure(session, stored)
    ctx = _context(session, project_id)

    with pytest.raises(ValueError):
        REGISTRY.execute("analyse_structure", ctx, {"artifact_id": "not-a-uuid"}, granted={"structure-analysis"})
    with pytest.raises(DomainError, match="declared schema"):
        REGISTRY.execute(
            "list_structure_contacts",
            ctx,
            {"artifact_id": str(uuid.uuid4()), "chain_a": "A", "chain_b": "B", "cutoff_angstrom": "wide"},
            granted={"structure-analysis"},
        )


def test_the_structure_tools_are_refused_without_their_capability(session: Session, stored) -> None:
    project_id, artifact = _stored_structure(session, stored)

    with pytest.raises(DomainError) as raised:
        REGISTRY.execute(
            "analyse_structure",
            _context(session, project_id),
            {"artifact_id": str(artifact.id)},
            granted={"project-read"},
        )

    assert raised.value.status_code == 403


def test_a_turn_with_no_project_cannot_reach_a_structure(session: Session, stored) -> None:
    """Without this the repository query would run unscoped across every project."""
    _stored_structure(session, stored)

    with pytest.raises(ValueError, match="project_context_required"):
        REGISTRY.execute(
            "analyse_structure",
            ToolContext(session=session),
            {"artifact_id": str(uuid.uuid4())},
            granted={"structure-analysis"},
        )
