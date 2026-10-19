import json

from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.research.models import ResearchBrief
from backend_v2.tests.test_copilot_chain import _project
from backend_v2.tests.test_copilot_chain import session as session


def test_progress_correction_is_selectable_without_replacing_canonical_review(session):
    project, user = _project(session)
    other, other_user = _project(session)
    canonical = ResearchBrief(project_id=project.id, created_by=user.id,
        title="Accepted review", content="Scientific background", status="accepted")
    correction = ResearchBrief(project_id=project.id, created_by=user.id,
        title="Latest route update", content="The requested rename has completed.", status="progress_note",
        scope={"token": "must-not-leak", "record_type": "maintenance"})
    foreign = ResearchBrief(project_id=other.id, created_by=other_user.id,
        title="Private note", content="Foreign record", status="progress_note")
    session.add_all([canonical, correction, foreign])
    session.flush()
    context = ResearchContextService(session, project)
    overview = context.research_overview()
    assert overview["review_document"]["id"] == str(canonical.id)
    assert overview["recent_briefs"][0]["id"] == str(correction.id)
    result = context.build_context("go on", selected_entity_ids=[str(correction.id), str(foreign.id)])
    assert "The requested rename has completed." in result.context
    assert "Foreign record" not in result.context
    assert "must-not-leak" not in result.context
    assert json.loads(result.context)["coverage"]["unavailable_selected_ids"] == [str(foreign.id)]
    citation = next(c for c in result.citations if c["entity_id"] == str(correction.id))
    assert citation["workspace_type"] == "research_brief"
    assert citation["review_status"] == "progress_note"
    packet = json.loads(context.grounding_packet(result.citations + [{
        "source_type": "research_workspace", "workspace_type": "research_brief", "entity_id": str(foreign.id),
    }]))
    record = next(row for row in packet["project_records"] if row["entity_id"] == str(correction.id))
    assert "The requested rename has completed." in record["record"]
    assert "not independent scientific validation" in record["evidence_scope"]
    assert "must-not-leak" not in json.dumps(packet)
    assert "Foreign record" not in json.dumps(packet)
    assert packet["items"] == []
    restricted = context.build_context("go on", selected_entity_ids=[str(correction.id)], allowed_kinds={"reference"})
    assert "The requested rename has completed." not in restricted.context
    assert json.loads(restricted.context)["coverage"]["unavailable_selected_ids"] == [str(correction.id)]


def test_review_packet_prioritizes_selected_corrections_and_bounds_project_records(session):
    project, user = _project(session)
    canonical = ResearchBrief(project_id=project.id, created_by=user.id,
        title="Accepted review", content="Older scientific review. " * 1000, status="accepted")
    correction = ResearchBrief(project_id=project.id, created_by=user.id,
        title="Current correction", content="Rename completed. " * 1000, status="progress_note")
    session.add_all([canonical, correction])
    session.flush()
    context = ResearchContextService(session, project)
    result = context.build_context("go on", selected_entity_ids=[str(correction.id)])
    records = json.loads(context.grounding_packet(result.citations * 2))["project_records"]
    assert records[0]["entity_id"] == str(correction.id)
    assert "Rename completed." in records[0]["record"]
    assert records[0]["truncated"] is True
    assert all(len(record["record"]) <= 6000 for record in records)
    assert sum(len(record["record"]) for record in records) <= 12_000
    assert len({record["entity_id"] for record in records}) == len(records)
