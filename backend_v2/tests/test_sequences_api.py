"""The codon routes over HTTP.

The kernels have their own tests. What only an HTTP test reaches is what the
route decides: that a construct is returned to the person who asked, that the
protein it was built from is *not*, that another project's protein is not
reachable through this door, and that a bad request is a 422 rather than a
stack trace.

Same fixture shape as `test_room_decision_hotspot_api.py`, deliberately: a
second harness for the same app drifts from the first.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.main import app
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.sequences import codon
from backend_v2.app.wetlab.models import Protein
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

#: A construct with a His tag, a Met run and a couple of awkward neighbours -
#: enough for the optimiser to have had to make choices.
PROTEIN = "MGSSHHHHHHSSGLVPRGSHMASMTGGQQMGRGSEFEARWQKLDSAINQCVE"


def _digest(sequence: str) -> str:
    return hashlib.sha256(sequence.encode()).hexdigest()


@pytest.fixture
def client() -> Generator[tuple[TestClient, dict]]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        user = User(username="codon-api", display_name="Codon API", role="admin", enabled=True)
        organization = Organization(name="Codon API Org")
        session.add_all([user, organization])
        session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
        project = Project(
            organization_id=organization.id, owner_id=user.id, name="Codon project",
            project_type="protein_design",
        )
        other = Project(
            organization_id=organization.id, owner_id=user.id, name="Another project",
            project_type="protein_design",
        )
        session.add_all([project, other])
        session.flush()
        session.add_all([
            ProjectMember(project_id=project.id, user_id=user.id, role="owner"),
            ProjectMember(project_id=other.id, user_id=user.id, role="owner"),
        ])
        protein = Protein(
            project_id=project.id, name="Binder v1", sequence=PROTEIN,
            sequence_sha256=_digest(PROTEIN), length=len(PROTEIN), created_by=user.id,
        )
        elsewhere = Protein(
            project_id=other.id, name="Someone else's", sequence=PROTEIN,
            sequence_sha256=_digest(PROTEIN), length=len(PROTEIN), created_by=user.id,
        )
        session.add_all([protein, elsewhere])
        session.flush()
        ids = {
            "user": user.id, "project": project.id, "other_project": other.id,
            "protein": protein.id, "foreign_protein": elsewhere.id,
        }
        session.commit()

    def session_override() -> Generator[Session]:
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def user_override() -> User:
        with factory() as session:
            return session.get(User, ids["user"])  # type: ignore[return-value]

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[current_user] = user_override
    try:
        yield TestClient(app, raise_server_exceptions=True), ids
    finally:
        app.dependency_overrides.clear()
        drop_all(engine, Base.metadata)


def _optimise(client: TestClient, project_id: uuid.UUID, **body: object):
    return client.post(
        f"/api/v2/projects/{project_id}/codon-optimisations",
        json={"host": "ecoli_k12", **body},
    )


def test_hosts_are_listed_with_the_evidence_behind_them(client) -> None:
    api, _ = client

    response = api.get("/api/v2/codon-hosts")

    assert response.status_code == 200
    hosts = {host["key"]: host for host in response.json()}
    assert "ecoli_k12" in hosts
    # The point of counting them ourselves: a table worth optimising against.
    assert hosts["ecoli_k12"]["cds_counted"] > 1000
    assert hosts["ecoli_k12"]["accessions"] == ["U00096"]


def test_a_construct_comes_back_and_codes_for_the_protein(client) -> None:
    api, ids = client

    response = _optimise(api, ids["project"], protein_id=str(ids["protein"]))

    assert response.status_code == 200
    body = response.json()
    assert codon.translate(body["dna"], translation_table=11) == PROTEIN
    assert body["protein_length"] == len(PROTEIN)
    assert body["assessment"]["forbidden_sites"] == []
    assert body["host"]["key"] == "ecoli_k12"


def test_the_response_identifies_the_source_without_carrying_it(client) -> None:
    """The DNA is returned; the protein it came from stays in the library."""
    api, ids = client

    body = _optimise(api, ids["project"], protein_id=str(ids["protein"])).json()

    assert body["source"]["sequence_sha256"] == _digest(PROTEIN)
    assert body["source"]["name"] == "Binder v1"
    assert PROTEIN not in response_text(body)


def response_text(body: object) -> str:
    """The whole response as text, for asserting something is absent from it."""
    import json

    return json.dumps(body)


def test_another_projects_protein_is_not_reachable_through_this_door(client) -> None:
    api, ids = client

    response = _optimise(api, ids["project"], protein_id=str(ids["foreign_protein"]))

    assert response.status_code == 404
    assert response.json()["error_code"] == "protein_not_found"


def test_an_unknown_host_is_a_422_naming_the_ones_that_exist(client) -> None:
    api, ids = client

    response = api.post(
        f"/api/v2/projects/{ids['project']}/codon-optimisations",
        json={"host": "no_such_host", "protein_id": str(ids["protein"])},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "codon_request_invalid"
    assert "ecoli_k12" in response.json()["detail"]


def test_naming_two_sources_is_refused(client) -> None:
    api, ids = client

    response = _optimise(
        api,
        ids["project"],
        protein_id=str(ids["protein"]),
        candidate_id=str(uuid.uuid4()),
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "sequence_source_ambiguous"


def test_a_flank_that_is_not_dna_is_rejected_by_the_contract(client) -> None:
    api, ids = client

    response = _optimise(api, ids["project"], protein_id=str(ids["protein"]), prefix="ATGZZZ")

    assert response.status_code == 422


def test_flanks_are_returned_as_part_of_the_construct(client) -> None:
    api, ids = client

    body = _optimise(
        api, ids["project"], protein_id=str(ids["protein"]), prefix="AATTC", suffix="GGATC"
    ).json()

    assert body["dna"].startswith("AATTC")
    assert body["dna"].endswith("GGATC")
    assert body["flanks"] == {"prefix": "AATTC", "suffix": "GGATC", "stop_added": True}
