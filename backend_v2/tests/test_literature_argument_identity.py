"""Identity, citation coordinates, and source freshness are separate contracts."""
from __future__ import annotations

import uuid

import pytest
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.literature.models import LiteratureClaim, LiteratureDocument
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_literature_evidence_notes import create, payload, source
from backend_v2.tests.test_room_decision_hotspot_api import client as client


def test_arguments_share_stable_project_identity_and_explicit_links(client):
    api, ids = client
    document, chunk = source(ids)
    second_document, second_chunk = source(ids)
    note = create(api, document, payload(chunk)).json()
    second = create(api, second_document, payload(second_chunk, argument_id=note["argument_id"], relation="contradicts"))
    assert second.status_code == 201, second.text
    assert second.json()["argument_id"] == note["argument_id"]
    updated = api.put(f"/api/v2/literature/evidence-notes/{note['id']}", headers={"If-Match": 'W/"1"'},
                      json=payload(chunk, interpretation="A revised inference with the same assertion", argument_id=note["argument_id"]))
    assert updated.status_code == 200
    assert updated.json()["argument_id"] == note["argument_id"]
    # A wording edit is a new assertion, not a silent global rename of other sources.
    detached = api.put(f"/api/v2/literature/evidence-notes/{note['id']}", headers={"If-Match": 'W/"2"'},
                       json=payload(chunk, argument="A new experimentally distinct assertion"))
    assert detached.status_code == 200
    assert detached.json()["argument_id"] != note["argument_id"]
    assert second.json()["argument"] == note["argument"]


def test_foreign_or_mismatched_argument_identity_is_rejected_without_mutation(client):
    api, ids = client
    document, chunk = source(ids)
    foreign_document, foreign_chunk = source(ids, other=True)
    own = create(api, document, payload(chunk)).json()
    foreign = create(api, foreign_document, payload(foreign_chunk)).json()
    assert own["argument_id"] != foreign["argument_id"]
    for identity, argument in [(foreign["argument_id"], own["argument"]), (own["argument_id"], "Different assertion"), (str(uuid.uuid4()), own["argument"])]:
        result = api.put(f"/api/v2/literature/evidence-notes/{own['id']}", headers={"If-Match": 'W/"1"'},
                         json=payload(chunk, argument_id=identity, argument=argument))
        assert result.status_code == 409, result.text
        assert result.json()["error_code"] == "evidence_argument_conflict"
    rows = api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").json()["items"]
    assert len(rows) == 1 and rows[0]["version"] == 1 and rows[0]["argument"] == own["argument"]


def test_legacy_argument_identity_is_stable_without_writing_on_read(client):
    api, ids = client
    document, chunk = source(ids)
    note = create(api, document, payload(chunk)).json()
    with ids["factory"]() as session:
        claim = session.get(LiteratureClaim, uuid.UUID(note["id"]))
        claim.attributes = {key: value for key, value in claim.attributes.items() if key != "argument_id"}
        session.commit()
    path = f"/api/v2/projects/{ids['project']}/literature/evidence-notes"
    assert api.get(path).json()["items"][0]["argument_id"] == note["argument_id"]
    assert api.get(path).json()["items"][0]["argument_id"] == note["argument_id"]
    with ids["factory"]() as session:
        claim = session.get(LiteratureClaim, uuid.UUID(note["id"]))
        assert "argument_id" not in claim.attributes
        assert claim.version == 1


def test_unreadable_project_cannot_expose_or_modify_argument_metadata(client):
    api, ids = client
    foreign_document, foreign_chunk = source(ids, other=True)
    note = create(api, foreign_document, payload(foreign_chunk)).json()
    with ids["factory"]() as session:
        foreign_org = Organization(name="Unrelated organization")
        session.add(foreign_org)
        session.flush()
        session.get(Project, ids["other_project"]).organization_id = foreign_org.id
        session.get(User, ids["user"]).role = "researcher"
        session.commit()
    assert api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").status_code == 200
    assert api.get(f"/api/v2/projects/{ids['other_project']}/literature/evidence-notes").status_code == 403
    assert create(api, foreign_document, payload(foreign_chunk, argument_id=note["argument_id"])).status_code == 403
    assert api.put(f"/api/v2/literature/evidence-notes/{note['id']}", json=payload(foreign_chunk), headers={"If-Match": 'W/"1"'}).status_code == 403


@pytest.mark.parametrize("locator", [{"page": 0}, {"page": -1}, {"page": True}, {"page": 2.5},
                                     {"page": 100001}, {"section": "x" * 501}, {"pdf_verified": True}])
def test_invalid_structured_coordinates_are_rejected(client, locator):
    api, ids = client
    document, chunk = source(ids)
    assert create(api, document, payload(chunk, structured_locator=locator)).status_code == 422


def test_human_coordinates_and_fingerprint_freshness_have_independent_status(client):
    api, ids = client
    document, chunk = source(ids)
    with ids["factory"]() as session:
        row = session.get(LiteratureDocument, uuid.UUID(document))
        row.metadata_json = {"content_provenance": {"content_kind": "open_access_full_text", "content_checksum_sha256": "a" * 64}}
        session.commit()
    coordinates = {"page": 5, "section": " Results ", "figure": " Fig. 2 "}
    created = create(api, document, payload(chunk, structured_locator=coordinates))
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["structured_locator"] == {"page": 5, "section": "Results", "figure": "Fig. 2"}
    assert note["source_ref"]["location_verification"] == "user_supplied"
    assert note["anchor_status"] == "matched"
    with ids["factory"]() as session:
        row = session.get(LiteratureDocument, uuid.UUID(document))
        row.metadata_json = {"content_provenance": {"content_checksum_sha256": "b" * 64}}
        session.commit()
    result = api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").json()["items"][0]
    assert result["anchor_status"] == "changed"
    assert result["structured_locator"]["page"] == 5
    assert result["source_ref"]["content_checksum_sha256"] == "a" * 64
    for path in [f"/api/v2/literature/evidence-notes/{note['id']}/review", f"/api/v2/literature/claims/{note['id']}"]:
        assert api.patch(path, headers={"If-Match": 'W/"1"'}, json={"review_status": "accepted"}).status_code == 409
