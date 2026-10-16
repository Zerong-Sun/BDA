"""A guided task's human-review state must not bypass factual review."""
import pytest
from backend_v2.app.copilot import agent_loop
from backend_v2.app.copilot.agent_review import reviewable_delivery
from backend_v2.tests.test_copilot_agent_loop import _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from backend_v2.tests.test_copilot_agent_review import _delivery, _receipt


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _contract():
    return {"steps": [{"id": "inspect", "tools": ["list_project_candidates"]}],
            "required_sections": []}


def test_guided_human_review_delivery_gets_factual_pass(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="analyst", task_contract=_contract())
    _receipt(session, run)
    original = _delivery("review_required", missing=["independent validation"])
    reviewed = _delivery("review_required", summary="Observed only the queried subset.",
                         missing=["independent validation"])
    seen = _script(monkeypatch, [{"content": original}, {"content": reviewed}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2
    assert run.outcome["status"] == "review_required"
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["summary"] == "Observed only the queried subset."
    assert run.outcome["missing"] == ["independent validation"]
    assert run.outcome["steps"][0]["status"] == "completed"


@pytest.mark.parametrize("diagnostic", [
    "structured_delivery_required", "unverified_evidence_call_ids",
    "invalid_section_values", "delivery_length_exceeded", "invalid_skill_outputs",
    "unexpected_skill_outputs", "skill_output_invalid:method", "skill_evidence_unverified:method",
])
def test_invalid_delivery_is_not_factually_reviewable(diagnostic):
    assert not reviewable_delivery(None, {"status": "review_required", "sections": {},
                                         "missing": [diagnostic]})


def test_guided_invalid_evidence_does_not_skip_repair_into_review(session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, bot="analyst", task_contract=_contract())
    _receipt(session, run)
    bad = _delivery("review_required", evidence_call_ids=["invented"])
    seen = _script(monkeypatch, [{"content": bad}, {"content": bad}])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 2  # Actor plus one format repair, no factual review call.
    assert run.outcome["status"] == "review_required"
    assert "unverified_evidence_call_ids" in run.outcome["missing"]
    assert "scientific_review" not in run.outcome
