"""The three new route groups, exercised over HTTP.

The services behind these routes have their own tests. What only an HTTP test
reaches is the part that lives in the route: the version precondition, the
project scope, the status codes a client branches on, and - the one that
matters most here - that the operator-facing and person-facing halves of the
same object really are different doors.

Written against `TestClient` with the same overrides `test_v2_domains.py` uses,
because a second fixture shape for the same app would drift from it.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.copilot import decisions
from backend_v2.app.copilot.models import CopilotConversation, CopilotMessage
from backend_v2.app.core.database import get_session
from backend_v2.app.core.models import Base
from backend_v2.app.identity.deps import current_user
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.main import app
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.targets import hotspots
from backend_v2.app.targets.models import Target
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

RESIDUES = [{"chain": "A", "seq": 164}, {"chain": "A", "seq": 168}]


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
        user = User(username="room-api", display_name="Room API", role="admin", enabled=True)
        organization = Organization(name="Room API Org")
        session.add_all([user, organization])
        session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
        project = Project(
            organization_id=organization.id, owner_id=user.id, name="Room API project",
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
        target = Target(project_id=project.id, name="PD-1")
        session.add(target)
        session.flush()
        ids = {
            "user": user.id, "project": project.id, "other_project": other.id,
            "target": target.id, "factory": factory,
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


def _ask(ids: dict, *, project_key: str = "project") -> uuid.UUID:
    with ids["factory"]() as session:
        row = decisions.record(
            session,
            project_id=ids[project_key],
            user_id=ids["user"],
            asked_by="planner",
            question="Which hotspot set should the binder target?",
            options=[{"key": "loop", "label": "CC' loop"}, {"key": "hot3", "label": "I126/L128/A132"}],
        )
        session.commit()
        return row.id


def _propose(ids: dict) -> uuid.UUID:
    with ids["factory"]() as session:
        row = hotspots.record(
            session,
            project_id=ids["project"],
            target_id=ids["target"],
            user_id=ids["user"],
            label="CC' loop face",
            residues=RESIDUES,
            origin="agent",
        )
        session.commit()
        return row.id


# --- the room ----------------------------------------------------------------


def test_the_room_returns_the_three_records_in_one_order(client) -> None:
    api, ids = client
    with ids["factory"]() as session:
        conversation = CopilotConversation(project_id=ids["project"], created_by=ids["user"], title="c")
        session.add(conversation)
        session.flush()
        session.add(CopilotMessage(conversation_id=conversation.id, role="user", content="which route?"))
        session.commit()
    _ask(ids)

    body = api.get(f"/api/v2/copilot/projects/{ids['project']}/room").json()

    assert {entry["kind"] for entry in body["items"]} == {"message", "decision"}
    assert body["next_cursor"] is None


def test_the_room_is_scoped_to_its_project(client) -> None:
    api, ids = client
    _ask(ids, project_key="other_project")

    body = api.get(f"/api/v2/copilot/projects/{ids['project']}/room").json()

    assert body["items"] == []


def test_an_unreadable_room_cursor_is_a_422_rather_than_a_silent_first_page(client) -> None:
    api, ids = client

    response = api.get(f"/api/v2/copilot/projects/{ids['project']}/room", params={"cursor": "nope"})

    assert response.status_code == 422


# --- decision requests ---------------------------------------------------------


def test_a_question_is_listed_and_answered_by_a_person(client) -> None:
    api, ids = client
    request_id = _ask(ids)

    listed = api.get(f"/api/v2/copilot/projects/{ids['project']}/decision-requests").json()
    assert [item["id"] for item in listed["items"]] == [str(request_id)]
    assert listed["items"][0]["status"] == "open"

    answered = api.post(
        f"/api/v2/copilot/decision-requests/{request_id}/answers",
        json={"choice": "hot3", "note": "designability"},
        headers={"If-Match": 'W/"1"'},
    )

    assert answered.status_code == 200
    body = answered.json()
    assert body["status"] == "answered"
    assert body["answer"] == "hot3"
    # The decision record the answer produced, addressable from the question.
    assert body["decision_entry_id"]


def test_answering_without_the_version_is_refused(client) -> None:
    api, ids = client
    request_id = _ask(ids)

    assert api.post(
        f"/api/v2/copilot/decision-requests/{request_id}/answers", json={"choice": "loop"}
    ).status_code == 428


def test_answering_a_question_that_moved_is_a_412(client) -> None:
    api, ids = client
    request_id = _ask(ids)

    stale = api.post(
        f"/api/v2/copilot/decision-requests/{request_id}/answers",
        json={"choice": "loop"},
        headers={"If-Match": 'W/"7"'},
    )

    assert stale.status_code == 412


def test_an_option_nobody_offered_is_refused(client) -> None:
    api, ids = client
    request_id = _ask(ids)

    response = api.post(
        f"/api/v2/copilot/decision-requests/{request_id}/answers",
        json={"choice": "whatever"},
        headers={"If-Match": 'W/"1"'},
    )

    assert response.status_code == 422


def test_a_question_can_be_withdrawn_and_then_not_answered(client) -> None:
    api, ids = client
    request_id = _ask(ids)

    withdrawn = api.post(
        f"/api/v2/copilot/decision-requests/{request_id}/withdrawals", headers={"If-Match": 'W/"1"'}
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"

    assert api.post(
        f"/api/v2/copilot/decision-requests/{request_id}/answers",
        json={"choice": "loop"},
        headers={"If-Match": 'W/"2"'},
    ).status_code == 409


def test_a_question_in_another_project_is_a_404_not_a_403(client) -> None:
    """Same answer for absent and out of scope: the difference leaks ids."""
    api, _ids = client

    assert api.post(
        f"/api/v2/copilot/decision-requests/{uuid.uuid4()}/answers",
        json={"choice": "loop"},
        headers={"If-Match": 'W/"1"'},
    ).status_code == 404


# --- hotspot sets --------------------------------------------------------------


def test_a_proposal_is_listed_as_pending_and_confirmed_by_a_person(client) -> None:
    api, ids = client
    set_id = _propose(ids)

    listed = api.get(f"/api/v2/projects/{ids['project']}/hotspot-sets").json()
    assert [item["origin"] for item in listed["items"]] == ["agent"]
    assert listed["items"][0]["status"] == "proposed"

    confirmed = api.post(
        f"/api/v2/hotspot-sets/{set_id}/confirmations", headers={"If-Match": 'W/"1"'}
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["origin"] == "agent_proposed_human_confirmed"
    assert confirmed.json()["confirmed_by"] == str(ids["user"])


def test_a_person_records_their_own_set_as_confirmed(client) -> None:
    api, ids = client

    created = api.post(
        f"/api/v2/targets/{ids['target']}/hotspot-sets",
        json={"label": "My face", "residues": RESIDUES},
    )

    assert created.status_code == 201
    assert created.json()["origin"] == "human"
    assert created.json()["status"] == "confirmed"


def test_a_client_cannot_declare_who_chose_a_set(client) -> None:
    """There is no `origin` on the payload; sending one changes nothing."""
    api, ids = client

    created = api.post(
        f"/api/v2/targets/{ids['target']}/hotspot-sets",
        json={"label": "Minted", "residues": RESIDUES, "origin": "agent_proposed_human_confirmed"},
    )

    assert created.status_code == 201
    assert created.json()["origin"] == "human"


def test_confirming_a_set_that_moved_is_a_412(client) -> None:
    api, ids = client
    set_id = _propose(ids)

    assert api.post(
        f"/api/v2/hotspot-sets/{set_id}/confirmations", headers={"If-Match": 'W/"9"'}
    ).status_code == 412


def test_rejecting_keeps_the_set_and_its_reason(client) -> None:
    api, ids = client
    set_id = _propose(ids)

    rejected = api.post(
        f"/api/v2/hotspot-sets/{set_id}/rejections",
        json={"reason": "The loop is disordered in this model"},
        headers={"If-Match": 'W/"1"'},
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert "disordered" in rejected.json()["rationale"]


def test_the_list_can_be_narrowed_to_what_a_job_may_use(client) -> None:
    api, ids = client
    set_id = _propose(ids)
    api.post(f"/api/v2/hotspot-sets/{set_id}/confirmations", headers={"If-Match": 'W/"1"'})
    _propose(ids)

    confirmed = api.get(
        f"/api/v2/projects/{ids['project']}/hotspot-sets", params={"status": "confirmed"}
    ).json()

    assert [item["id"] for item in confirmed["items"]] == [str(set_id)]


def test_a_set_on_an_unknown_target_is_a_404(client) -> None:
    api, _ids = client

    assert api.post(
        f"/api/v2/targets/{uuid.uuid4()}/hotspot-sets",
        json={"label": "Nowhere", "residues": RESIDUES},
    ).status_code == 404
