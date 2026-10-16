import uuid

import pytest
from backend_v2.app.copilot import bots
from backend_v2.app.copilot.api import download_bot_records, get_bot_records
from backend_v2.app.copilot.capabilities import tools_for_capabilities
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotAgentTurn
from backend_v2.app.copilot.records import KIND, read_record, refresh_project_records
from backend_v2.app.core.problem import DomainError
from backend_v2.app.knowledge.models import KnowledgeEntry
from backend_v2.tests.test_copilot_room import _conversation, _message, _project
from backend_v2.tests.test_copilot_room import session as session  # noqa: F401
from sqlalchemy import func, select


def count(session):
    return session.scalar(select(func.count()).select_from(KnowledgeEntry).where(KnowledgeEntry.entry_type == KIND))


def test_hook_is_durable_idempotent_and_records_failures_without_reasoning(session):
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    message = _message(session, conversation, bot="researcher", content="Evidence reviewed")
    message.reasoning_content = "PRIVATE REASONING"
    message.status = "failed"
    message.error = "Provider disconnected"
    message.citations = [{"document_id": str(uuid.uuid4()), "token": "PRIVATE CREDENTIAL"}]
    session.commit()
    latest = read_record(session, project.id, "researcher")
    assert latest["items"][0]["status"] == "failed"
    assert "Provider disconnected" in latest["markdown"]
    assert "PRIVATE" not in latest["markdown"]
    before = count(session)
    session.flush()
    session.commit()
    assert count(session) == before
    assert latest["items"][0]["id"] == str(message.id)


def test_exact_bot_and_project_isolation_and_authorized_download(session):
    project, user = _project(session)
    other, outsider = _project(session)
    _message(session, _conversation(session, project, user), bot="runner", content="Runner work")
    _message(session, _conversation(session, other, outsider), bot="runner", content="OTHER PROJECT SECRET")
    session.commit()
    assert read_record(session, project.id, "analyst")["total"] == 0
    assert "OTHER PROJECT SECRET" not in read_record(session, project.id, "runner")["markdown"]
    with pytest.raises(DomainError):
        get_bot_records(project.id, "runner", "", 100, 0, session, outsider)
    with pytest.raises(DomainError):
        download_bot_records(project.id, "runner", session, outsider)
    response = download_bot_records(project.id, "runner", session, user)
    assert b"Runner work" in response.body
    assert "attachment" in response.headers["content-disposition"]


def test_run_status_turn_and_explicit_workflow_refs_are_sources(session):
    project, user = _project(session)
    workflow = str(uuid.uuid4())
    run = CopilotAgentRun(
        project_id=project.id, created_by=user.id, bot="runner", goal="Observe workflow", status="running"
    )
    session.add(run)
    session.flush()
    turn = CopilotAgentTurn(
        run_id=run.id,
        sequence=1,
        role="assistant",
        content="internal transcript",
        tool_calls=[{"name": "get_workflow_status", "arguments": {"workflow_id": workflow}}],
    )
    session.add(turn)
    session.flush()
    run.status = "failed"
    run.error = "Scheduler failure"
    session.commit()
    record = read_record(session, project.id, "runner", workflow)
    assert record["matched"] == 1
    item = record["items"][0]
    assert item["id"] == str(run.id)
    assert item["status"] == "failed"
    assert item["turn_ids"] == [str(turn.id)]
    assert ["workflow_id", workflow] in item["references"]
    assert read_record(session, project.id, "planner", workflow)["matched"] == 0


def test_refresh_is_idempotent_search_paginates_and_all_bots_can_read(session):
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    for i in range(3):
        _message(session, conversation, bot="analyst", content=f"workflow review {i}")
    session.commit()
    refresh_project_records(session, project.id, user.id)
    session.commit()
    before = count(session)
    refresh_project_records(session, project.id, user.id)
    session.commit()
    assert count(session) == before
    first = read_record(session, project.id, "analyst", "WORKFLOW", 2)
    second = read_record(session, project.id, "analyst", "WORKFLOW", 2, 2)
    assert first["matched"] == 3 and len(first["items"]) == 2 and len(second["items"]) == 1
    assert {x["id"] for x in first["items"]}.isdisjoint({x["id"] for x in second["items"]})
    for bot in bots.all_bots():
        assert "search_bot_records" in tools_for_capabilities(set(bot.capabilities))


def test_system_records_cannot_be_forged_changed_or_deleted_through_knowledge_service(session):
    from backend_v2.app.knowledge import service
    from backend_v2.app.knowledge.schemas import KnowledgeCreate, KnowledgeUpdate

    project, user = _project(session)
    with pytest.raises(DomainError, match="generated from source"):
        service.create_entry(session, project, KnowledgeCreate(title="fake", content="fake", entry_type=KIND), user)
    refresh_project_records(session, project.id, user.id)
    session.commit()
    record_id = read_record(session, project.id, "runner")["record_id"]
    record = session.get(KnowledgeEntry, uuid.UUID(record_id))
    with pytest.raises(DomainError):
        service.update_entry(record, KnowledgeUpdate(content="forged"), record.version)
    with pytest.raises(DomainError):
        service.delete_entry(session, record, record.version)
    note = KnowledgeEntry(
        project_id=project.id, created_by=user.id, title="note", content="note", entry_type="note", version=1
    )
    with pytest.raises(DomainError):
        service.update_entry(note, KnowledgeUpdate(entry_type=KIND), 1)


def test_records_do_not_enter_scientific_methods_or_datasets(session):
    from backend_v2.app.research.workspace import _knowledge

    project, user = _project(session)
    refresh_project_records(session, project.id, user.id)
    session.commit()
    rows = list(session.scalars(select(KnowledgeEntry).where(KnowledgeEntry.project_id == project.id)))
    assert _knowledge(rows) == ([], [])


def test_generic_knowledge_search_keeps_science_and_legacy_notes(session):
    from backend_v2.app.knowledge.repository import KnowledgeRepository

    project, user = _project(session)
    refresh_project_records(session, project.id, user.id)
    legacy = KnowledgeEntry(
        project_id=project.id,
        created_by=user.id,
        title="Legacy bot record",
        content="Scientific evidence",
        entry_type="note",
        source={"entry_key": KIND},
    )
    session.add(legacy)
    session.commit()
    repo = KnowledgeRepository(session)
    assert [row.id for row in repo.search(project.id, "")] == [legacy.id]
    assert [row.id for row in repo.list_project(project.id, None, 100)] == [legacy.id]
    assert len(repo.list_project(project.id, None, 100, entry_type=KIND)) == 6
