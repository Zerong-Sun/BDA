"""PD-L1 team coordination from a real chat row through durable waits and review.

The model is scripted; database writes, routing, outbox, waits and room are real.
"""
import json
import uuid

import pytest
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.copilot import agent_loop, agent_runs, decisions, room, service
from backend_v2.app.copilot.actions import CopilotActionService
from backend_v2.app.copilot.models import CopilotAgentRun, CopilotDecisionRequest
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from backend_v2.tests.test_copilot_agent_loop import _call, _provider, _script
from backend_v2.tests.test_copilot_chain import _project
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session():
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://", poolclass=StaticPool))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as opened:
        yield opened
    drop_all(engine, Base.metadata)


def _delivery(summary):
    return {"content": json.dumps({"status": "partial", "summary": summary,
        "sections": {}, "missing": ["实验测量"], "next_action": "检查证据",
        "evidence_call_ids": []}, ensure_ascii=False)}


def _chat(session, text="请安排团队研究 PD-L1 项目，分工分析现有证据并完成复核"):
    project, user = _project(session)
    conversation, source, _ = service.submit_chat(session, project, None, text, user,
        context={"bot_hint": "conductor"})
    ctx = ToolContext(project_id=project.id, user_id=user.id, session=session, bot="conductor",
        actions=CopilotActionService(session, project, user,
            request_text=source.content, source_message_id=source.id))
    return project, user, conversation, source, ctx


def test_pd_l1_chat_delegates_reviews_waits_for_choice_and_reports(session, monkeypatch):
    project, user, conversation, source, ctx = _chat(session)
    started = REGISTRY.execute("start_team_task", ctx, {})
    assert started["continuation"] == "background_worker"
    assert REGISTRY.execute("start_team_task", ctx, {})["run_id"] == started["run_id"]
    audits = list(session.scalars(select(AuditLog).where(AuditLog.action == "copilot.team.start")))
    assert len(audits) == 1
    assert audits[0].payload["source_message_id"] == str(source.id)
    lead = session.get(CopilotAgentRun, uuid.UUID(started["run_id"]))
    assert lead.goal == source.content
    assert lead.conversation_id == conversation.id
    provider = _provider(session)
    seen = _script(monkeypatch, [
        {"content": "文献研究员先检查 PD-L1 的现有证据。", "tool_calls": [
            _call("delegate", "delegate_to_operator", {"bot": "researcher", "instruction": "检查 PD-L1 证据缺口"})]},
        _delivery("PD-L1 证据检查完成；缺少测量，不能宣称有效。"),
        {"content": "请科学审阅员独立复核。", "tool_calls": [
            _call("review", "delegate_to_operator", {"bot": "auditor", "instruction": "复核研究员的证据缺口报告"})]},
        _delivery("复核完成，缺少实验测量的限制必须保留。"),
        {"content": "需要选择下一步目标。", "tool_calls": [_call("decision", "request_decision", {
            "question": "接下来优先哪一项？", "options": [
                {"key": "evidence", "label": "补齐证据", "rationale": "先确定依据"},
                {"key": "design", "label": "比较方案", "rationale": "先整理路线"}], "recommended": "evidence"})]},
        _delivery("已收到补齐证据的选择。本轮证据检查与复核完成，后续工作按该方向推进。"),
        _delivery("本轮检查完成；缺少实验测量。"),
    ])
    assert agent_loop.step(session, lead, provider) == "awaiting_tasks"
    child = session.scalar(select(CopilotAgentRun).where(CopilotAgentRun.parent_run_id == lead.id))
    assert child.bot == "researcher"
    assert agent_loop.step(session, child, provider) == "succeeded"
    assert agent_runs.resume(session, lead)
    assert agent_loop.step(session, lead, provider) == "awaiting_tasks"
    review = session.scalar(select(CopilotAgentRun).where(
        CopilotAgentRun.parent_run_id == lead.id, CopilotAgentRun.bot == "auditor"))
    assert not (set(review.allowed_tools) & REGISTRY.user_intent_write_ids())
    assert agent_loop.step(session, review, provider) == "succeeded"
    assert agent_runs.resume(session, lead)
    assert agent_loop.step(session, lead, provider) == "awaiting_tasks"
    choice = session.scalar(select(CopilotDecisionRequest).where(CopilotDecisionRequest.run_id == lead.id))
    grants = list(lead.allowed_tools)
    session.commit()
    session.expire_all()  # Resumption must depend on records, not an in-memory continuation.
    decisions.answer(session, choice, project=project, user=user, choice="evidence")
    assert lead.status == "running"
    assert lead.allowed_tools == grants
    assert agent_loop.step(session, lead, provider) == "succeeded"
    assert any('"answer": "evidence"' in msg.get("content", "") for msg in seen[-2])
    entries, _ = room.events(session, project_id=project.id)
    speeches = [entry for entry in entries if entry["kind"] == "discussion"]
    assert {entry["bot"] for entry in speeches} == {"conductor", "researcher", "auditor"}
    assert len(speeches) == 7
    assert any(entry["kind"] == "decision" and entry["decision"]["status"] == "answered" for entry in entries)


@pytest.mark.parametrize("text", ["Who should work on the project next?", "Do not start the project task", "只建议研究项目下一步，不要执行任务"])
def test_advice_does_not_start_a_team_run(session, text):
    *_, ctx = _chat(session, text)
    with pytest.raises(DomainError, match="approved task scope"):
        REGISTRY.execute("start_team_task", ctx, {})
    assert session.scalar(select(CopilotAgentRun)) is None


def test_room_discussion_is_scoped_paged_and_excludes_private_reasoning(session):
    project, user, _, _, ctx = _chat(session)
    started = REGISTRY.execute("start_team_task", ctx, {})
    run = session.get(CopilotAgentRun, uuid.UUID(started["run_id"]))
    agent_runs.append_turn(session, run, role="assistant", content="Public update", reasoning_content="Private reasoning")
    agent_runs.append_turn(session, run, role="tool", content="Raw tool internals")
    agent_runs.append_turn(session, run, role="system", content="System instructions")
    agent_runs.append_turn(session, run, role="assistant", content="", reasoning_content="Private only")
    entries, _ = room.events(session, project_id=project.id)
    discussions = [entry for entry in entries if entry["kind"] == "discussion"]
    assert [entry["discussion"]["content"] for entry in discussions] == ["Public update"]
    other, _ = _project(session)
    assert room.events(session, project_id=other.id)[0] == []
    cursor = None
    collected = []
    while True:
        page, cursor = room.events(session, project_id=project.id, limit=1, cursor=cursor)
        collected.extend(entry["id"] for entry in page)
        if cursor is None:
            break
    assert collected == [entry["id"] for entry in entries]


def test_withdrawn_choice_resumes_without_restarting_cancelled_work(session):
    project, user, _, _, ctx = _chat(session)
    started = REGISTRY.execute("start_team_task", ctx, {})
    run = session.get(CopilotAgentRun, uuid.UUID(started["run_id"]))
    decision = decisions.record(session, project_id=project.id, user_id=user.id, asked_by="conductor",
        run_id=run.id, question="Which next?", options=[{"label": "A"}, {"label": "B"}])
    agent_runs.suspend(session, run, [("decision", decision.id, "choose")])
    decisions.withdraw(session, decision)
    assert run.status == "running"
    second = decisions.record(session, project_id=project.id, user_id=user.id, asked_by="conductor",
        run_id=run.id, question="Which now?", options=[{"label": "A"}, {"label": "B"}])
    agent_runs.suspend(session, run, [("decision", second.id, "choose-again")])
    agent_runs.cancel(session, run)
    decisions.withdraw(session, second)
    assert run.status == "cancelled"


def test_specialists_can_read_shared_discussion_without_delegation_rights(session):
    from dataclasses import replace

    from backend_v2.app.copilot import bots
    from backend_v2.app.copilot.capabilities import normalize_capabilities

    project, user, _, _, ctx = _chat(session)
    started = REGISTRY.execute("start_team_task", ctx, {})
    run = session.get(CopilotAgentRun, uuid.UUID(started["run_id"]))
    agent_runs.append_turn(session, run, role="assistant", content="Please inspect the PD-L1 source.")
    enabled = normalize_capabilities(None)
    specialist = replace(ctx, bot="researcher")
    result = REGISTRY.execute("read_team_progress", specialist, {},
        granted=bots.capabilities_for_bot("researcher", enabled))
    assert any(item.get("discussion", {}).get("content") == "Please inspect the PD-L1 source."
               for item in result["recent_activity"] if item.get("discussion"))
    assert not bots.may_direct("researcher", "planner")


def test_chat_task_rejects_a_rewritten_authorizing_request(session):
    _, _, _, _, ctx = _chat(session, "Who should work on the project next?")
    ctx.actions.request_text = "Please start the project task"
    with pytest.raises(ValueError, match="team_request_required"):
        REGISTRY.execute("start_team_task", ctx, {})


def test_chat_task_cannot_reuse_another_projects_run_marker(session):
    _, _, _, source, ctx = _chat(session)
    *_, other_ctx = _chat(session)
    other = REGISTRY.execute("start_team_task", other_ctx, {})
    source.context = {**source.context, "team_run_id": other["run_id"]}
    with pytest.raises(ValueError, match="team_request_required"):
        REGISTRY.execute("start_team_task", ctx, {})


def test_start_team_task_is_an_explicit_write_not_a_read_only_tool():
    assert "start_team_task" in REGISTRY.user_intent_write_ids()
    assert REGISTRY.get("start_team_task").audit


@pytest.mark.parametrize("marker", [17, "not-a-uuid", {"unexpected": "value"}])
def test_malformed_task_marker_is_rejected_without_starting_work(session, marker):
    *_, source, ctx = _chat(session)
    source.context = {**source.context, "team_run_id": marker}
    with pytest.raises(ValueError, match="team_request_required"):
        REGISTRY.execute("start_team_task", ctx, {})
    assert session.scalar(select(CopilotAgentRun)) is None


@pytest.mark.parametrize("large", [False, True])
def test_review_receives_bounded_final_claims_separate_from_evidence(session, large):
    from dataclasses import replace

    _, _, _, _, ctx = _chat(session)
    started = REGISTRY.execute("start_team_task", ctx, {})
    run = session.get(CopilotAgentRun, uuid.UUID(started["run_id"]))
    run.outcome = {"status": "partial", "summary": "A claim requiring review" * (2000 if large else 1)}
    session.flush()
    result = REGISTRY.execute("read_operator_work", replace(ctx, bot="auditor"), {"run_id": str(run.id)})
    assert result["tool_results"] == []  # A final claim never becomes evidence.
    assert result["outcome_truncated"] is large
    if large:
        assert result["outcome"] is None
        assert len(result["outcome_preview"]) == 32000
    else:
        assert result["outcome"] == run.outcome
        assert result["outcome_preview"] is None
