"""A re-collected candidate must end up pointing at its structure.

ProteinHunter reports a *complex* (binder + ligand), never a bare monomer, so it sets
`complex_output_index` and leaves `structure_output_index` empty. The collection path
used to backfill only `structure_artifact_id` on an already-existing candidate, which
meant every re-collected ProteinHunter candidate kept a null complex and the UI reported
"no structure file for this candidate yet" for a design whose PDB had in fact been
collected and stored.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.compute.parsers.base import ParsedCandidate, ParsedOutputs
from backend_v2.app.compute.tasks import backfill_candidate_structures
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def env() -> Generator[dict]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="cs", display_name="CS", role="admin", enabled=True)
        org = Organization(name="CS Org")
        session.add_all([user, org])
        session.flush()
        project = Project(organization_id=org.id, owner_id=user.id, name="CS", project_type="design")
        session.add(project)
        session.flush()
        yield {"session": session, "project": project, "user": user}
    engine.dispose()


def _artifact(session: Session, project: Project, user: User, filename: str) -> Artifact:
    artifact = Artifact(
        project_id=project.id,
        created_by=user.id,
        artifact_type="candidate_complex",
        filename=filename,
        content_type="chemical/x-pdb",
        object_key=f"k/{filename}",
        size_bytes=10,
        checksum_sha256="a" * 64,
    )
    session.add(artifact)
    session.flush()
    return artifact


def _backfill(existing: Candidate, item: ParsedCandidate, artifacts: list[Artifact]) -> None:
    """Calls the real production function, not a copy of it.

    An earlier version of this test re-implemented the backfill branch locally, which
    would have kept passing if the real code regressed - the exact failure mode the test
    exists to catch.
    """

    def artifact_at(index):
        return artifacts[index] if index is not None and 0 <= index < len(artifacts) else None

    backfill_candidate_structures(existing, item, artifact_at)


def test_recollection_backfills_the_complex_structure(env) -> None:
    """The regression: ProteinHunter candidates only ever have a complex."""
    session, project, user = env["session"], env["project"], env["user"]
    candidate = Candidate(project_id=project.id, candidate_key="ph-run4-cycle3", name="run4")
    session.add(candidate)
    session.flush()
    assert candidate.complex_artifact_id is None

    artifacts = [_artifact(session, project, user, "run4.pdb")]
    parsed = ParsedCandidate(candidate_key="ph-run4-cycle3", complex_output_index=0)
    _backfill(candidate, parsed, artifacts)
    session.flush()

    assert candidate.complex_artifact_id == artifacts[0].id, (
        "a re-collected ProteinHunter candidate still has no structure"
    )


def test_backfill_does_not_repoint_an_existing_structure(env) -> None:
    """Whoever produced the coordinates first keeps them."""
    session, project, user = env["session"], env["project"], env["user"]
    original = _artifact(session, project, user, "first.pdb")
    later = _artifact(session, project, user, "second.pdb")
    candidate = Candidate(
        project_id=project.id,
        candidate_key="c1",
        name="c1",
        complex_artifact_id=original.id,
    )
    session.add(candidate)
    session.flush()

    _backfill(candidate, ParsedCandidate(candidate_key="c1", complex_output_index=1), [original, later])
    session.flush()
    assert candidate.complex_artifact_id == original.id


def test_monomer_backfill_still_works(env) -> None:
    session, project, user = env["session"], env["project"], env["user"]
    candidate = Candidate(project_id=project.id, candidate_key="c2", name="c2")
    session.add(candidate)
    session.flush()
    artifacts = [_artifact(session, project, user, "mono.pdb")]
    _backfill(candidate, ParsedCandidate(candidate_key="c2", structure_output_index=0), artifacts)
    session.flush()
    assert candidate.structure_artifact_id == artifacts[0].id


def test_out_of_range_index_is_ignored_rather_than_raising(env) -> None:
    """A parser that reports an index the collector did not produce must not kill the job."""
    session, project = env["session"], env["project"]
    candidate = Candidate(project_id=project.id, candidate_key="c3", name="c3")
    session.add(candidate)
    session.flush()
    _backfill(candidate, ParsedCandidate(candidate_key="c3", complex_output_index=7), [])
    assert candidate.complex_artifact_id is None


def test_parsed_outputs_shape_is_what_the_collector_expects() -> None:
    """Guards the assumption the backfill relies on: both slots exist and default None."""
    item = ParsedCandidate(candidate_key="x")
    assert item.structure_output_index is None
    assert item.complex_output_index is None
    assert ParsedOutputs().candidates == []
