"""Abbreviated run references resolve only when unique inside the caller's project."""
import uuid

import pytest
from backend_v2.app.copilot import agent_runs
from backend_v2.app.copilot.models import CopilotAgentRun
from backend_v2.app.copilot.registry import ToolContext
from backend_v2.app.copilot.tools import _read_operator_work
from backend_v2.tests.test_copilot_room import _project
from backend_v2.tests.test_copilot_room import session as session_fixture
from sqlalchemy.dialects import postgresql


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _run(session, project, user, run_id):
    run = CopilotAgentRun(id=uuid.UUID(run_id), project_id=project.id, created_by=user.id,
                          goal="Inspect recorded evidence", bot="researcher", status="succeeded",
                          allowed_tools=[], outcome={})
    session.add(run)
    session.flush()
    agent_runs.append_turn(session, run, role="tool", content='{"count": 2}',
                           tool_calls=[{"tool_call_id": "read-1", "name": "list_project_candidates"}])
    return run


@pytest.mark.parametrize("requested", ["e3ddab87", "E3DDAB87", "e3ddab8700000000000000000000000"])
def test_unique_prefix_returns_exact_receipts_and_explicit_canonical_identity(session, requested):
    project, user = _project(session)
    run = _run(session, project, user, "e3ddab87-0000-0000-0000-000000000001")
    context = ToolContext(project_id=project.id, session=session)
    expected = _read_operator_work(context, {"run_id": str(run.id)})
    result = _read_operator_work(context, {"run_id": requested})
    assert result.pop("requested_run_id") == requested
    assert result.pop("run_id_resolution") == "unique_project_prefix"
    assert result == expected
    assert result["run_id"] == str(run.id)


def test_prefix_ambiguity_is_refused_with_query_limited_to_two_project_matches(session, monkeypatch):
    project, user = _project(session)
    for suffix in ("0", "1", "f"):
        _run(session, project, user, "e3ddab87" + suffix * 24)
    statements = []
    original = session.scalars

    def capture(statement, *args, **kwargs):
        statements.append(statement)
        return original(statement, *args, **kwargs)

    monkeypatch.setattr(session, "scalars", capture)
    with pytest.raises(ValueError, match="copilot_agent_run_prefix_ambiguous_use_full_uuid"):
        _read_operator_work(ToolContext(project_id=project.id, session=session), {"run_id": "e3ddab87"})
    # Native UUID range bindings also compile for PostgreSQL; no cast/function
    # on the indexed ID column or unscoped global prefix search is required.
    query = statements[0].compile(dialect=postgresql.dialect())
    assert query.params["param_1"] == 2
    assert query.params["project_id_1"] == project.id
    assert query.params["id_1"] == uuid.UUID("e3ddab87" + "0" * 24)
    assert query.params["id_2"] == uuid.UUID("e3ddab87" + "f" * 24)
    assert "CAST(" not in str(query)


def test_other_project_matches_neither_resolve_nor_make_local_match_ambiguous(session):
    project, user = _project(session)
    other, other_user = _project(session)
    foreign = _run(session, other, other_user, "e3ddab87-ffff-ffff-ffff-ffffffffffff")
    context = ToolContext(project_id=project.id, session=session)
    for requested in ("e3ddab87", "aaaaaaaa", str(foreign.id)):
        with pytest.raises(ValueError, match="^copilot_agent_run_not_found$"):
            _read_operator_work(context, {"run_id": requested})
    local = _run(session, project, user, "e3ddab87-0000-0000-0000-000000000000")
    assert _read_operator_work(context, {"run_id": "e3ddab87"})["run_id"] == str(local.id)


@pytest.mark.parametrize("requested", ["", "e3ddab8", "e3ddab8g", "e3ddab87%", " e3ddab87", "e3ddab87-0", "e" * 33])
def test_invalid_prefixes_are_rejected_without_a_database_query(session, monkeypatch, requested):
    project, _ = _project(session)

    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid prefix must not query runs")

    monkeypatch.setattr(session, "scalars", unexpected)
    with pytest.raises(ValueError, match="^copilot_agent_run_id_invalid_use_full_uuid_or_at_least_8_hex_prefix$"):
        _read_operator_work(ToolContext(project_id=project.id, session=session), {"run_id": requested})


@pytest.mark.parametrize("run_id", ["ffffffff-ffff-ffff-ffff-ffffffffffff", "00000000-0000-0000-0000-000000000000"])
def test_prefix_range_includes_uuid_boundaries_and_full_hex_keeps_exact_behavior(session, run_id):
    project, user = _project(session)
    run = _run(session, project, user, run_id)
    context = ToolContext(project_id=project.id, session=session)
    assert _read_operator_work(context, {"run_id": run.id.hex[:8]})["run_id"] == str(run.id)
    exact = _read_operator_work(context, {"run_id": run.id.hex})
    assert exact["run_id"] == str(run.id)
    assert "run_id_resolution" not in exact
