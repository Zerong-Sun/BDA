"""A citation must preserve the quote, its scope, and the human's separate inference."""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager

import pytest
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.identity.models import User
from backend_v2.app.intelligence import tasks as intelligence_tasks
from backend_v2.app.intelligence.models import IntelligenceEvidence, IntelligenceRun
from backend_v2.app.literature.models import LiteratureChunk, LiteratureClaim, LiteratureDocument
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_room_decision_hotspot_api import client as client
from sqlalchemy import select


def source(ids, *, other=False, content="Before. 😀 Binding increased in mice. Human effects remain unknown."):
    with ids["factory"]() as session:
        document = LiteratureDocument(project_id=ids["other_project" if other else "project"], title="Source paper",
                                      source="fixture", metadata_json={"content_provenance": {"content_kind": "database_abstract"}})
        session.add(document)
        session.flush()
        chunk = LiteratureChunk(document_id=document.id, position=0, content=content)
        session.add(chunk)
        session.commit()
        return str(document.id), str(chunk.id)


def payload(chunk_id=None, **changes):
    return {
        "argument": "Binding might increase in our assay", "paper_claim": "The authors report increased binding in mice",
        "interpretation": "Motivates a controlled replication, not a claim about human efficacy",
        "limitations": "Mouse experiment; unknown transfer to our assay", "relation": "supports",
        "quote": "Binding increased in mice.", "source_url": "https://example.org/paper", "locator": "Abstract",
        "chunk_id": chunk_id, **changes,
    }


def create(api, document_id, body):
    return api.post(f"/api/v2/literature/documents/{document_id}/evidence-notes", json=body)


def test_original_quote_has_unicode_offsets_context_and_a_separate_argument(client):
    api, ids = client
    document, chunk = source(ids)
    result = create(api, document, payload(chunk))
    assert result.status_code == 201, result.text
    note = result.json()
    assert note["anchor_status"] == "matched"
    assert note["review_status"] == "pending"
    assert note["argument"] != note["quote"]
    quote, position = note["source_ref"]["selector"]
    assert quote["prefix"] == "Before. 😀 "
    assert quote["suffix"] == " Human effects remain unknown."
    assert position == {"type": "TextPositionSelector", "start": 10, "end": 36}
    assert len(note["source_ref"]["excerpt_checksum_sha256"]) == 64
    page = api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").json()
    assert page["items"][0]["id"] == note["id"]
    with ids["factory"]() as session:
        audit = session.scalar(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(note["id"])))
        assert audit.payload["after"]["quote"] == note["quote"]


@pytest.mark.parametrize("changes", [
    {"quote": "Binding decreased in mice."}, {"quote_start": 0},
    {"source_url": "javascript:alert(1)"}, {"source_url": "https://user:secret@example.org"},
    {"argument": "   "}, {"quote": "   "}, {"relation": "proven"},
])
def test_invalid_or_rewritten_quotes_do_not_become_evidence(client, changes):
    api, ids = client
    document, chunk = source(ids)
    assert create(api, document, payload(chunk, **changes)).status_code == 422
    assert api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").json()["items"] == []


def test_repeated_quote_requires_exact_occurrence_and_preserves_whitespace(client):
    api, ids = client
    document, chunk = source(ids, content=" Yes. Yes. ")
    assert create(api, document, payload(chunk, quote="Yes.")).status_code == 422
    result = create(api, document, payload(chunk, quote="Yes.", quote_start=6))
    assert result.status_code == 201
    assert result.json()["source_ref"]["selector"][1]["start"] == 6
    result = create(api, document, payload(chunk, quote=" Yes. Yes. "))
    assert result.status_code == 201
    assert result.json()["quote"] == " Yes. Yes. "


def test_a_manual_quote_does_not_inherit_verification_and_foreign_chunks_are_rejected(client):
    api, ids = client
    document, _ = source(ids)
    _, foreign_chunk = source(ids, other=True)
    assert create(api, document, payload(foreign_chunk)).status_code == 422
    note = create(api, document, payload()).json()
    assert note["anchor_status"] == "unverified"
    assert note["source_ref"]["content_kind"] == "user_supplied_excerpt"
    assert note["source_ref"]["retrieval_trace_id"] is None
    assert "chunk_id" not in note["source_ref"]
    assert create(api, document, payload(quote_start=0)).status_code == 422


def test_intelligence_preserves_a_curated_notes_assertion_boundary(client, monkeypatch):
    api, ids = client
    document, chunk = source(ids)
    note = create(api, document, payload(chunk, relation="contradicts")).json()
    with ids["factory"]() as session:
        run = IntelligenceRun(project_id=ids["project"], target_id=ids["target"], created_by=ids["user"], query={})
        session.add(run)
        session.commit()
        run_id = run.id

    @contextmanager
    def task_session():
        with ids["factory"]() as session:
            yield session
            session.commit()

    monkeypatch.setattr(intelligence_tasks, "session_scope", task_session)
    assert intelligence_tasks.intelligence_run.run(str(run_id))["status"] == "succeeded"
    with ids["factory"]() as session:
        evidence = session.scalar(select(IntelligenceEvidence).where(IntelligenceEvidence.run_id == run_id))
        assert evidence.evidence_type == "literature_evidence_note"
        content = json.loads(evidence.content)
        assert content["claim"] == note["paper_claim"] != note["argument"]
        assert content["project_argument"] == note["argument"]
        assert content["evidence_relation"] == "contradicts"
        assert content["limitations"] == note["limitations"]
        assert content["excerpt"] == note["quote"]
        assert content["review_status"] == "pending"
        assert content["anchor_status"] == "matched"
        assert evidence.citation["url"] == note["source_url"]


def test_edit_and_review_enforce_versions_preserve_audit_and_reset_review(client):
    api, ids = client
    document, chunk = source(ids)
    body = payload(chunk)
    note = create(api, document, body).json()
    path = f"/api/v2/literature/evidence-notes/{note['id']}"
    assert api.put(path, json=body).status_code == 428
    reviewed = api.patch(path + "/review", json={"review_status": "accepted"}, headers={"If-Match": 'W/"1"'})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewed_by"] == str(ids["user"])
    assert api.put(path, json=body, headers={"If-Match": 'W/"1"'}).status_code == 412
    updated = api.put(path, json={**body, "relation": "context"}, headers={"If-Match": 'W/"2"'})
    assert updated.status_code == 200, updated.text
    assert updated.json()["review_status"] == "pending"
    assert updated.json()["reviewed_at"] is None
    assert updated.headers["etag"] == 'W/"3"'
    with ids["factory"]() as session:
        audits = session.scalars(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(note["id"]))).all()
        assert len(audits) == 3
        edited = next(row for row in audits if row.action.endswith("updated"))
        assert edited.payload["before"]["review_status"] == "accepted"
        assert edited.payload["after"]["relation"] == "context"


def test_source_drift_remains_visible_and_cannot_be_accepted_through_either_api(client):
    api, ids = client
    document, chunk_id = source(ids)
    note = create(api, document, payload(chunk_id)).json()
    with ids["factory"]() as session:
        chunk = session.get(LiteratureChunk, uuid.UUID(chunk_id))
        chunk.content = "Changed source without the earlier result."
        session.commit()
    page = api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").json()
    assert page["items"][0]["anchor_status"] == "changed"
    assert page["items"][0]["quote"] == note["quote"]
    for path in [f"/api/v2/literature/evidence-notes/{note['id']}/review", f"/api/v2/literature/claims/{note['id']}"]:
        assert api.patch(path, json={"review_status": "accepted"}, headers={"If-Match": 'W/"1"'}).status_code == 409


def test_project_pagination_excludes_automatic_sentences_and_other_projects(client):
    api, ids = client
    document, chunk = source(ids)
    other_document, other_chunk = source(ids, other=True)
    for _ in range(3):
        create(api, document, payload(chunk))
    create(api, other_document, payload(other_chunk))
    with ids["factory"]() as session:
        session.add(LiteratureClaim(document_id=uuid.UUID(document), claim="An automatically extracted sentence"))
        session.commit()
    path = f"/api/v2/projects/{ids['project']}/literature/evidence-notes?limit=2"
    first = api.get(path).json()
    second = api.get(path + "&cursor=" + first["next_cursor"]).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert second["next_cursor"] is None
    assert all(row["document_id"] == document for row in first["items"] + second["items"])


def test_viewer_can_read_but_cannot_create_edit_or_review(client):
    api, ids = client
    document, chunk = source(ids)
    body = payload(chunk)
    note = create(api, document, body).json()
    with ids["factory"]() as session:
        session.get(User, ids["user"]).role = "viewer"
        session.commit()
    assert api.get(f"/api/v2/projects/{ids['project']}/literature/evidence-notes").status_code == 200
    assert create(api, document, body).status_code == 403
    path = f"/api/v2/literature/evidence-notes/{note['id']}"
    assert api.put(path, json=body, headers={"If-Match": 'W/"1"'}).status_code == 403
    assert api.patch(path + "/review", json={"review_status": "accepted"}, headers={"If-Match": 'W/"1"'}).status_code == 403


def test_copilot_keeps_paper_claim_and_project_inference_separate(client):
    api, ids = client
    document, chunk = source(ids)
    create(api, document, payload(chunk, relation="contradicts"))
    assert api.get(f"/api/v2/projects/{ids['project']}/literature/claims").json()["items"] == []
    with ids["factory"]() as session:
        context = ResearchContextService(session, session.get(Project, ids["project"]))
        item, = context._literature_evidence_items()
        assert item["data"]["claim"] == payload()["paper_claim"]
        assert item["data"]["project_argument"] == payload()["argument"]
        assert item["data"]["evidence_relation"] == "contradicts"
        citation = context.citation_for_item(item)
        assert citation["excerpt"] == payload()["quote"]
        assert citation["limitations"] == payload()["limitations"]
        assert citation["paper_claim"] != citation["project_argument"]
