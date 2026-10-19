"""Room previews retain the real page boundary through repeated prompt packing."""
import pytest
from backend_v2.app.copilot.delivery_context import room_preview
from backend_v2.app.copilot.registry import ToolContext
from backend_v2.app.copilot.tools import _read_team_progress
from backend_v2.tests.test_copilot_room import _conversation, _message, _project, _run
from backend_v2.tests.test_copilot_room import session as session_fixture


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def test_repeated_room_preview_keeps_list_truncation_and_source_unchanged():
    source = {"active_tasks": [{"run_id": str(i)} for i in range(31)],
              "recent_activity": [{"id": str(i)} for i in range(31)]}
    preview = room_preview(source)
    assert preview["active_tasks_truncated"] is True
    assert preview["recent_activity_truncated"] is True
    assert room_preview(preview) == preview
    assert len(source["active_tasks"]) == len(source["recent_activity"]) == 31


@pytest.mark.parametrize("count, truncated", [(0, False), (30, False), (31, True)])
def test_progress_tool_uses_real_active_task_boundary(session, count, truncated):
    project, user = _project(session)
    for _ in range(count):
        _run(session, project, user, status="running")
    result = _read_team_progress(ToolContext(project_id=project.id, session=session), {})
    assert len(result["active_tasks"]) == min(count, 30)
    assert result["active_tasks_truncated"] is truncated
    assert result["recent_activity_truncated"] is truncated
    assert room_preview(result) == result


@pytest.mark.parametrize("count, truncated", [(30, False), (31, True)])
def test_progress_tool_uses_room_cursor_without_guessing_from_page_size(session, count, truncated):
    project, user = _project(session)
    conversation = _conversation(session, project, user)
    for _ in range(count):
        _message(session, conversation)
    result = _read_team_progress(ToolContext(project_id=project.id, session=session), {})
    assert len(result["recent_activity"]) == 30
    assert result["recent_activity_truncated"] is truncated
    assert result["active_tasks_truncated"] is False
    assert room_preview(result) == result
