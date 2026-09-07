from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs, qualification
from backend_v2.app.copilot.capabilities import normalize_capabilities
from backend_v2.app.copilot.models import CopilotConfig
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.copilot.schemas import AgentRunCreate, CopilotConfigUpdate
from backend_v2.app.copilot.service import continue_agent_run, put_config, start_agent_run
from backend_v2.app.copilot.task_contracts import build_contract, evaluate_delivery, progress
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_loop import _call, _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from sqlalchemy.orm import Session


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _turn(tool: str, result, call_id="e1"):
    return SimpleNamespace(role="tool", content=json.dumps(result), tool_calls=[{"name": tool, "tool_call_id": call_id}])


def _answer(**overrides):
    return json.dumps({"status": "completed", "summary": "Draft based on observed records.", "sections": {"objective": "Goal", "constraints": "Unknown", "success_criteria": "Needs review", "missing_inputs": "None declared"}, "evidence_call_ids": ["e1"], "missing": [], "next_action": "Review the draft.", **overrides})


def test_empty_capabilities_disable_tools_while_omitted_inherits():
    assert normalize_capabilities([]) == set()
    assert "research-read" in normalize_capabilities(None)
    assert CopilotConfigUpdate().enabled_skills == ["research"]


def test_prose_refusal_is_not_a_completed_delivery(session: Session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, task_contract=build_contract("brief", []))
    _script(monkeypatch, [{"content": "I cannot complete this goal."}])
    agent_loop.step(session, run, _provider(session))
    assert run.status == "succeeded"  # Runner completed; business delivery did not.
    session.expire(run)
    assert run.outcome["status"] == "review_required"
    assert run.outcome["missing"] == ["structured_delivery_required"]


def test_missing_steps_and_fabricated_evidence_never_complete():
    run = SimpleNamespace(task_contract=build_contract("brief", []))
    assert evaluate_delivery(run, _answer(), [])['status'] == 'review_required'
    turns = [_turn("research_overview", {"project": "existing"})]
    assert evaluate_delivery(run, _answer(), turns)['status'] == 'completed'
    assert evaluate_delivery(run, _answer(evidence_call_ids=['invented']), turns)['status'] == 'review_required'
    assert evaluate_delivery(run, _answer(missing=['need controls']), turns)['status'] == 'partial'
    assert evaluate_delivery(run, _answer(status='needs_input', missing=['target identity']), turns)['status'] == 'needs_input'


def test_search_hits_and_untraced_excerpts_do_not_satisfy_literature():
    contract = build_contract("literature", [])
    turns = [_turn("search_research", [{"title": "Found"}]), _turn("get_reference_content", [{"title": "Found"}], 'e2')]
    assert progress(contract, turns)[1]['status'] == 'pending'
    turns[1] = _turn('get_reference_content', [{'data': {'chunk_id': 'c', 'content_provenance': {'content_checksum_sha256': 'checksum', 'retrieval_trace_id': 'trace'}}}], 'e2')
    assert progress(contract, turns)[1]['status'] == 'completed'
    # Citing discovery alone is not enough to cover the excerpt step.
    run = SimpleNamespace(task_contract=contract)
    assert evaluate_delivery(run, _answer(), turns)['status'] == 'partial'


def test_failed_tools_and_queued_work_do_not_satisfy_steps():
    contract = build_contract('literature', ['start_literature_search'])
    for result in ({'error': 'denied'}, {'status': 'pending', 'id': 'queued'}, {'status': 'failed'}):
        assert progress(contract, [_turn('start_literature_search', result)])[0]['status'] == 'pending'


def test_instrument_write_is_guarded_before_handler():
    context = ToolContext(session=object(), actions=SimpleNamespace(request_allows=lambda name: False))
    with pytest.raises(DomainError, match='outside the approved task scope'):
        REGISTRY.execute('analyse_bli_run', context, {'artifact_id': 'not-even-a-uuid'})


def test_protocol_checks_gate_services_and_configuration_change_expires_them(session: Session, monkeypatch):
    project, _ = _project(session)
    provider = _provider(session)
    replies = iter([
        {'content': json.dumps({'objective': 'compare', 'success_criteria': 'cited comparison', 'missing': ['control'], 'source_id': 'bda-check-source', 'value': 7, 'route_id': 'route-ready'})},
        {'tool_calls': [_call('p', 'bda_protocol_check', {'value': 7})]},
    ])
    monkeypatch.setattr(qualification, 'completion_message', lambda *a, **k: next(replies))
    checked = qualification.assess(session, project.id)
    assert len(checked['eligible_services']) == 5
    provider.model = 'different-model'
    assert qualification.readiness(session, project.id)['eligible_services'] == []


def test_task_write_scope_is_explicit_and_cannot_escape_recipe(session: Session, monkeypatch):
    project, user = _project(session)
    monkeypatch.setattr(qualification, 'readiness', lambda *a: {'eligible_services': ['literature', 'brief']})
    read_only, _ = start_agent_run(session, project, user, AgentRunCreate(project_id=project.id, goal='Research', service_kind='literature'))
    assert 'create_knowledge_draft' not in read_only.allowed_tools
    granted, _ = start_agent_run(session, project, user, AgentRunCreate(project_id=project.id, goal='Research', service_kind='literature', authorized_writes=['create_knowledge_draft']))
    assert granted.task_contract['authorized_writes'] == ['create_knowledge_draft']
    assert 'create_compute_draft' not in granted.allowed_tools
    with pytest.raises(DomainError, match='exceed'):
        start_agent_run(session, project, user, AgentRunCreate(project_id=project.id, goal='Brief', service_kind='brief', authorized_writes=['create_compute_draft']))


def test_resume_preserves_scope_and_cannot_expand_budget(session: Session):
    project, user = _project(session)
    run = _run(session, project, user, task_contract=build_contract('literature', []), max_cost_usd_cents=10)
    agent_runs.finish(session, run, status='succeeded')
    continue_agent_run(session, run, user, 'The target is PD1.')
    assert run.status == 'running'
    assert run.task_contract['authorized_writes'] == []
    assert run.max_cost_usd_cents == 10
    agent_runs.finish(session, run, status='succeeded')
    run.cost_usd_cents = 10
    with pytest.raises(DomainError, match='budget is exhausted'):
        continue_agent_run(session, run, user, 'Keep going')


def test_config_cannot_forge_a_model_qualification(session: Session):
    project, _ = _project(session)
    row = put_config(session, None, project.id, CopilotConfigUpdate(settings={'task_qualification': {'checks': {'tools': True}}}), None)
    assert 'task_qualification' not in row.settings


def test_continuation_can_revoke_writes_but_cannot_restore_them(session: Session):
    project, user = _project(session)
    run = _run(session, project, user,
               allowed_tools=['search_research', 'create_knowledge_draft'],
               task_contract={**build_contract('literature', ['create_knowledge_draft']), 'cost_mode': 'unavailable'})
    agent_runs.finish(session, run, status='succeeded')
    continue_agent_run(session, run, user, 'Use existing evidence only.', [])
    assert run.task_contract['authorized_writes'] == []
    assert run.task_contract['cost_mode'] == 'unavailable'
    assert run.allowed_tools == ['search_research']
    assert all(step['id'] != 'note' for step in run.task_contract['steps'])
    agent_runs.finish(session, run, status='succeeded')
    with pytest.raises(DomainError, match='reduce scope'):
        continue_agent_run(session, run, user, 'Save the note.', ['create_knowledge_draft'])
    assert run.status == 'succeeded'


def test_revoked_tool_is_removed_when_run_resumes(session: Session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, allowed_tools=['list_proteins'])
    session.add(CopilotConfig(project_id=project.id, enabled_skills=[]))
    session.flush()
    _script(monkeypatch, [{'content': 'No permitted tools.'}])
    agent_loop.step(session, run, _provider(session))
    assert run.allowed_tools == []
    assert run.outcome['status'] == 'review_required'


def test_literature_steps_do_not_allow_saving_before_reading():
    from backend_v2.app.copilot.task_contracts import available_step_tools
    run = SimpleNamespace(task_contract=build_contract('literature', ['start_literature_search', 'create_knowledge_draft']),
                          allowed_tools=['start_literature_search', 'get_reference_content', 'create_knowledge_draft', 'research_overview'])
    assert available_step_tools(run, []) == {'start_literature_search', 'research_overview'}
    turns = [_turn('start_literature_search', {'status': 'succeeded'})]
    assert 'get_reference_content' in available_step_tools(run, turns)
    assert 'create_knowledge_draft' not in available_step_tools(run, turns)


def test_cost_ceiling_blocks_unpriced_calls_without_invoking_model(session: Session, monkeypatch):
    project, user = _project(session)
    run = _run(session, project, user, max_cost_usd_cents=10)
    def forbidden(*args, **kwargs):
        pytest.fail('An unpriced call must not consume a bounded budget')
    monkeypatch.setattr(agent_loop, 'completion_message', forbidden)
    with pytest.raises(DomainError, match='bda_pricing'):
        agent_loop.step(session, run, _provider(session))


def test_task_record_is_a_deduplicated_review_plan(session: Session):
    from backend_v2.app.copilot.service import save_task_record
    from backend_v2.app.timeline.models import ProjectTimelineEntry
    project, user = _project(session)
    run = _run(session, project, user)
    run.status = 'succeeded'
    run.outcome = {'status': 'partial', 'summary': 'A proposal', 'missing': ['control'], 'next_action': 'Run a control'}
    save_task_record(session, run, user)
    record_id = run.outcome['decision_record_id']
    save_task_record(session, run, user)
    assert run.outcome['decision_record_id'] == record_id
    import uuid
    record = session.get(ProjectTimelineEntry, uuid.UUID(record_id))
    assert record.entry_type == 'plan' and record.outcome == 'unspecified'
    assert record.tags == ['copilot', 'pending_review']


def test_delivery_sections_are_required_even_after_tools_succeed():
    run = SimpleNamespace(task_contract=build_contract("brief", []))
    outcome = evaluate_delivery(run, _answer(sections={}), [_turn("research_overview", {"project": "exists"})])
    assert outcome["status"] == "partial"
    assert "success_criteria" in outcome["missing"]


def test_scientific_review_covers_all_sections_and_rejects_invented_refs(session: Session, monkeypatch):
    from backend_v2.app.copilot.task_contracts import DELIVERY_SECTIONS
    project, user = _project(session)
    run = _run(session, project, user, task_contract=build_contract('literature', []))
    for name, data, call_id in [
        ('search_research', [{'id': 'reference'}], 'e1'),
        ('get_reference_content', [{'chunk_id': 'chunk', 'content_checksum_sha256': 'checksum', 'retrieval_trace_id': 'trace'}], 'e2'),
    ]:
        agent_runs.append_turn(session, run, role='assistant', tool_calls=[_call(call_id, name, {})])
        agent_runs.append_turn(session, run, role='tool', content=json.dumps(data), tool_calls=[{'name': name, 'tool_call_id': call_id}])
    delivery = _answer(sections={key: 'Source-backed draft' for key in DELIVERY_SECTIONS['literature']}, evidence_call_ids=['e1', 'e2'])
    seen = _script(monkeypatch, [{'content': delivery}, {'content': _answer(evidence_call_ids=['invented'])}])
    agent_loop.step(session, run, _provider(session))
    assert 'evidence_comparison' in seen[1][1]['content']
    assert run.outcome['status'] == 'review_required'
    assert run.outcome['scientific_review'] == 'unavailable'
