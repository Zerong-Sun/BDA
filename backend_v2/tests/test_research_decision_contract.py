"""A goal's evaluation definition is explicit, scoped, versioned human input."""
from __future__ import annotations

import uuid

import pytest
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_literature_evidence_notes import create, payload, source
from backend_v2.tests.test_room_decision_hotspot_api import client as client
from sqlalchemy import select


def contract(**changes):
    return {"hypothesis": "The effect is reproducible in our assay", "alternatives": ["Replicate", "Change assay"],
            "success_criteria": ["Three independent repeats exceed the preregistered threshold"],
            "falsification_criteria": ["Negative controls show the same effect"],
            "next_decision": "Continue only after independent replication", "evidence_note_ids": [], **changes}


def new_goal(api, ids, **body):
    result = api.post(f"/api/v2/projects/{ids['project']}/research-goals", json={"title": "Is it reproducible?", **body})
    assert result.status_code == 201, result.text
    return result.json()


def test_legacy_goals_stay_unknown_and_contract_updates_preserve_versions_and_audit(client):
    api, ids = client
    goal = new_goal(api, ids)
    assert goal["decision_contract"]["success_criteria"] == []
    path = f"/api/v2/research-goals/{goal['id']}"
    assert api.patch(path, json={"decision_contract": contract()}).status_code == 428
    result = api.patch(path, json={"decision_contract": contract()}, headers={"If-Match": 'W/"1"'})
    assert result.status_code == 200, result.text
    assert result.headers["etag"] == 'W/"2"'
    assert result.json()["decision_contract"] == contract()
    assert api.patch(path, json={"decision_contract": contract(hypothesis="Stale overwrite")}, headers={"If-Match": 'W/"1"'}).status_code == 412
    preserved = api.patch(path, json={"status": "answered"}, headers={"If-Match": 'W/"2"'})
    assert preserved.status_code == 200
    assert preserved.json()["decision_contract"] == contract()
    with ids["factory"]() as session:
        audit = session.scalar(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(goal["id"]), AuditLog.action == "research.decision_contract.updated"))
        assert audit.payload["after"] == contract()
        assert audit.payload["before"]["hypothesis"] == ""
        assert audit.actor_id == ids["user"]


def test_only_curated_project_evidence_can_be_attached_to_a_decision(client):
    api, ids = client
    document, chunk = source(ids)
    foreign_document, foreign_chunk = source(ids, other=True)
    note = create(api, document, payload(chunk)).json()
    foreign_note = create(api, foreign_document, payload(foreign_chunk)).json()
    goal = new_goal(api, ids, decision_contract=contract(evidence_note_ids=[note["id"]]))
    path = f"/api/v2/research-goals/{goal['id']}"
    for bad_id in [foreign_note["id"], str(uuid.uuid4())]:
        result = api.patch(path, headers={"If-Match": 'W/"1"'}, json={"title": "Must not persist", "decision_contract": contract(evidence_note_ids=[bad_id])})
        assert result.status_code == 422
        assert result.json()["error_code"] == "research_decision_evidence_mismatch"
    readback = api.get(f"/api/v2/projects/{ids['project']}/research-goals").json()["items"][0]
    assert readback["title"] == goal["title"] and readback["version"] == 1
    assert readback["decision_contract"]["evidence_note_ids"] == [note["id"]]


@pytest.mark.parametrize("changes", [
    {"hypothesis": "x" * 3001}, {"next_decision": "x" * 2001}, {"invented_success": True},
    {"alternatives": ["a", " a "]}, {"success_criteria": [" "]}, {"falsification_criteria": ["x" * 1001]},
    {"alternatives": [str(i) for i in range(11)]}, {"evidence_note_ids": [str(uuid.UUID(int=1))] * 2},
])
def test_invalid_decision_definitions_are_rejected(client, changes):
    api, ids = client
    result = api.post(f"/api/v2/projects/{ids['project']}/research-goals", json={"title": "Question", "decision_contract": contract(**changes)})
    assert result.status_code == 422


def test_viewers_and_foreign_organizations_cannot_write_decision_definitions(client):
    api, ids = client
    goal = new_goal(api, ids)
    path = f"/api/v2/research-goals/{goal['id']}"
    with ids["factory"]() as session:
        session.get(User, ids["user"]).role = "viewer"
        session.commit()
    assert api.patch(path, json={"decision_contract": contract()}, headers={"If-Match": 'W/"1"'}).status_code == 403
    with ids["factory"]() as session:
        session.get(User, ids["user"]).role = "researcher"
        other = Organization(name="Other institution")
        session.add(other)
        session.flush()
        session.get(Project, ids["project"]).organization_id = other.id
        session.commit()
    assert api.get(f"/api/v2/projects/{ids['project']}/research-goals").status_code == 403
    assert api.patch(path, json={"decision_contract": contract()}, headers={"If-Match": 'W/"1"'}).status_code == 403
