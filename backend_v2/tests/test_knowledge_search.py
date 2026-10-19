"""Literal project search is applied before paging, including decoded Unicode tags."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from backend_v2.app.copilot.project_context import ProjectContextService
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.knowledge.models import KnowledgeEntry
from backend_v2.app.projects.models import Project
from backend_v2.tests.test_room_decision_hotspot_api import client as client


def seed(ids, title, *, content="A recorded observation", tags=None, kind="note", other=False, identifier=None, timestamp=None):
    with ids["factory"]() as session:
        values = {"id": identifier} if identifier else {}
        if timestamp:
            values.update({"created_at": timestamp, "updated_at": timestamp})
        row = KnowledgeEntry(project_id=ids["other_project" if other else "project"], created_by=ids["user"], title=title,
                             content=content, tags=tags or [], entry_type=kind,
                             source={"citation": "https://example.org/paper", "review_status": "pending_review", "source_message_id": "original-message"}, **values)
        session.add(row)
        session.commit()
        return str(row.id)


def test_literal_wildcards_case_chinese_tags_and_type_filters(client):
    api, ids = client
    literal = seed(ids, "Reported 100% identity", content="Lower_Confidence on A/B", tags=["抗体结合", "MixedCASE"], kind="copilot_draft")
    seed(ids, "Reported 1000 identity", content="LowerZConfidence on AC B", tags=["different"])
    seed(ids, "Reported 100% identity", other=True)
    path = f"/api/v2/projects/{ids['project']}/knowledge"
    for query in ["100%", "lower_", "A/B", "抗体", "mixedcase"]:
        response = api.get(path, params={"q": query})
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["items"]] == [literal]
    assert api.get(path, params={"q": "抗体", "entry_type": "note"}).json()["items"] == []
    result = api.get(path, params={"q": "抗体", "entry_type": "copilot_draft"}).json()["items"][0]
    assert result["source"]["source_message_id"] == "original-message"
    assert result["source"]["review_status"] == "pending_review"
    assert api.get(path, params={"q": "x" * 501}).status_code == 422
    assert api.get(path, params={"entry_type": "x" * 81}).status_code == 422


def test_filters_run_before_cursor_limits_and_browse_all_is_supported(client):
    api, ids = client
    first = seed(ids, "Needle one", identifier=uuid.UUID(int=10))
    seed(ids, "Unrelated entry", identifier=uuid.UUID(int=11))
    second = seed(ids, "Needle two", identifier=uuid.UUID(int=12))
    seed(ids, "Needle foreign", other=True, identifier=uuid.UUID(int=13))
    path = f"/api/v2/projects/{ids['project']}/knowledge"
    page = api.get(path, params={"q": "needle", "limit": 1}).json()
    assert [item["id"] for item in page["items"]] == [first]
    next_page = api.get(path, params={"q": "needle", "limit": 1, "cursor": page["next_cursor"]}).json()
    assert [item["id"] for item in next_page["items"]] == [second]
    assert next_page["next_cursor"] is None
    assert len(api.get(path, params={"q": ""}).json()["items"]) == 3


def test_bot_search_finds_an_older_matching_entry_beyond_500_newer_rows(client):
    api, ids = client
    moment = datetime(2025, 1, 1, tzinfo=UTC)
    old_id = seed(ids, "Old assay controls", tags=["旧记录"], timestamp=moment)
    with ids["factory"]() as session:
        session.add_all([KnowledgeEntry(project_id=ids["project"], created_by=ids["user"], title=f"Unrelated filler {index}", content="Routine observation",
                                       entry_type="note", tags=[], source={}, created_at=moment + timedelta(days=1), updated_at=moment + timedelta(days=1)) for index in range(520)])
        session.commit()
        context = ProjectContextService(session, session.get(Project, ids["project"]))
        rows = context.search_knowledge("旧记录", limit=5)
        assert [item["id"] for item in rows] == [old_id]
        assert rows[0]["data"]["source"]["citation"] == "https://example.org/paper"
    result = api.get(f"/api/v2/projects/{ids['project']}/knowledge", params={"q": "old assay", "limit": 1}).json()
    assert result["items"][0]["id"] == old_id


def test_search_preserves_project_authorization(client):
    api, ids = client
    seed(ids, "Secret target", other=True)
    with ids["factory"]() as session:
        org = Organization(name="Foreign organization")
        session.add(org)
        session.flush()
        session.get(Project, ids["other_project"]).organization_id = org.id
        session.get(User, ids["user"]).role = "researcher"
        session.commit()
    response = api.get(f"/api/v2/projects/{ids['other_project']}/knowledge", params={"q": "Secret"})
    assert response.status_code == 403
    assert api.get(f"/api/v2/projects/{ids['project']}/knowledge", params={"q": "Secret"}).json()["items"] == []
