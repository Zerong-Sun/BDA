"""Short reports must retain their evidence, identity and unresolved gaps."""
import copy
import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import agent_loop, agent_runs
from backend_v2.app.copilot.task_contracts import build_contract
from backend_v2.app.core.problem import DomainError
from backend_v2.tests.test_copilot_agent_loop import _project, _provider, _run, _script
from backend_v2.tests.test_copilot_agent_loop import session as session_fixture
from backend_v2.tests.test_copilot_agent_review import _receipt


@pytest.fixture(name="session")
def db_session():
    yield from session_fixture.__wrapped__()


def _draft(long=False):
    return {"status": "review_required", "summary": "来源abcd1234：功能读数，非直接结合结构。" + ("重复说明。" * 130 if long else ""),
            "sections": {"子任务ID": "researcher a1b2c3d4；planner b2c3d4e5；auditor c3d4e5f6",
                         "完成事项": "已核对功能读数。", "未验证结论": "映射与直接结合结构均未验证。",
                         "下一步": "①只读比对d4e5f6a7；②补充引用。", "复核限制": "成员交付仍有待审限制。"},
            "missing": ["残基映射未确认；子任务缺少两条引用。"], "next_action": "可选①只读比对，本轮结束。",
            "evidence_call_ids": ["read-1"]}


def _setup(session):
    project, user = _project(session)
    run = _run(session, project, user, bot="conductor", goal="最终报告不超过600字",
               task_contract=build_contract("custom", []))
    _receipt(session, run)
    return run


def test_empty_contract_preserves_all_sections_gaps_and_locks_identity_budget():
    draft = _draft(True)
    run = SimpleNamespace(goal="最终报告不超过600字", task_contract={})
    packet = json.loads(agent_loop._length_repair_messages(run, [], draft)[1]["content"])
    assert set(packet["target_template"]["sections"]) == set(draft["sections"])
    assert packet["target_template"]["sections"]["子任务ID"] == draft["sections"]["子任务ID"]
    assert packet["target_template"]["missing"] == draft["missing"]
    assert packet["field_budgets"]["missing_combined"] == sum(map(len, draft["missing"]))
    assert packet["field_budgets"]["sections_combined_including_titles"] >= len(draft["sections"]["子任务ID"])
    assert sum(packet["field_budgets"].values()) == 480


@pytest.mark.parametrize(("mutation", "error"), [
    (lambda d: d.update(sections={}), "shortening_sections_lost"),
    (lambda d: d.update(missing=[]), "shortening_scientific_gaps_lost"),
    (lambda d: d.update(evidence_call_ids=[]), "shortening_evidence_lost"),
    (lambda d: d["sections"].update(下一步="①只读比对；②补充引用。"), "shortening_identifiers_lost"),
    (lambda d: d["sections"].update(子任务ID="planner a1b2c3d4；researcher b2c3d4e5；auditor c3d4e5f6"), "shortening_identity_changed"),
    (lambda d: d["sections"].update(下一步="只读比对d4e5f6a7。"), "shortening_options_lost"),
])
def test_loss_or_role_swap_is_rejected(mutation, error):
    original = _draft(True)
    shortened = _draft()
    mutation(shortened)
    assert error in agent_loop._shortening_content_errors(original, shortened, list(original["sections"]))


def test_identifier_matching_excludes_plain_eight_digit_numbers():
    assert agent_loop._shortening_ids("数量12345678，PMID20302879，任务a1b2c3d4。") == {"a1b2c3d4"}
    value = "12345678-1234-1234-1234-123456789012"
    assert agent_loop._shortening_ids(value) == {value}


@pytest.mark.parametrize("role", ["文献研究员", "方案设计师", "科学审阅员", "项目负责人", "计算工程师", "数据分析师"])
def test_all_registered_chinese_role_identity_sections_are_locked(role):
    draft = _draft()
    draft["sections"]["子任务ID"] = f"{role} a1b2c3d4"
    assert agent_loop._locked_identity_sections(draft)["子任务ID"] == f"{role} a1b2c3d4"


def test_pure_shortening_cannot_drop_or_change_skill_outputs():
    original = _draft(True)
    original["skill_outputs"] = {"method": {"result": "unverified", "evidence_call_ids": ["read-1"]}}
    shortened = _draft()
    assert "shortening_skill_outputs_changed" in agent_loop._shortening_content_errors(original, shortened, list(original["sections"]))
    shortened["skill_outputs"] = copy.deepcopy(original["skill_outputs"])
    assert not agent_loop._shortening_content_errors(original, shortened, list(original["sections"]))
    shortened["skill_outputs"]["method"]["result"] = "verified"
    assert "shortening_skill_outputs_changed" in agent_loop._shortening_content_errors(original, shortened, list(original["sections"]))


@pytest.mark.parametrize("stage", ["initial", "review"])
def test_lost_content_never_completes_review_and_keeps_rejected_raw_and_original(session, monkeypatch, stage):
    run = _setup(session)
    original = _draft(True)
    bad = _draft()
    bad.update(sections={}, missing=[])
    replies = ([{"content": json.dumps(original)}, {"content": json.dumps(bad)}]
               if stage == "initial" else [{"content": json.dumps(_draft())}, {"content": json.dumps(original)}, {"content": json.dumps(bad)}])
    seen = _script(monkeypatch, replies)
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == (2 if stage == "initial" else 3)
    assert run.outcome.get("scientific_review") != "automated_review_completed"
    assert run.outcome["summary"] == original["summary"]
    assert run.outcome["sections"] == original["sections"]
    assert original["missing"][0] in run.outcome["missing"]
    key = "format_repair_rejections" if stage == "initial" else "scientific_review_rejections"
    assert "shortening_sections_lost" in run.outcome[key][-1]["validation_errors"]
    assert "shortening_scientific_gaps_lost" in run.outcome[key][-1]["validation_errors"]
    assert json.loads(agent_runs.transcript(session, run)[-1].content) == bad


@pytest.mark.parametrize("stage", ["initial", "review"])
def test_complete_shortening_can_still_finish_after_real_review(session, monkeypatch, stage):
    run = _setup(session)
    long, short = json.dumps(_draft(True)), json.dumps(_draft())
    replies = [long, short, short] if stage == "initial" else [short, long, short]
    seen = _script(monkeypatch, [{"content": value} for value in replies])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == 3
    assert run.outcome["scientific_review"] == "automated_review_completed"
    assert run.outcome["sections"] == _draft()["sections"]
    assert run.outcome["missing"] == _draft()["missing"]


def test_mandatory_scientific_gaps_do_not_receive_impossible_budget():
    draft = copy.deepcopy(_draft())
    draft["missing"] = ["不可删除的科学缺口" * 100]
    run = SimpleNamespace(goal="最终报告不超过600字", task_contract={})
    with pytest.raises(DomainError) as caught:
        agent_loop._length_repair_messages(run, [], draft)
    assert caught.value.error_code == "shortening_required_content_exceeds_limit"


@pytest.mark.parametrize("stage", ["initial", "review"])
def test_dropped_successful_call_id_cannot_pass_either_pure_shortening_path(session, monkeypatch, stage):
    run = _setup(session)
    bad = _draft()
    bad["evidence_call_ids"] = []
    values = [_draft(True), bad] if stage == "initial" else [_draft(), _draft(True), bad]
    seen = _script(monkeypatch, [{"content": json.dumps(value)} for value in values])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == len(values)
    assert run.outcome.get("scientific_review") != "automated_review_completed"
    key = "format_repair_rejections" if stage == "initial" else "scientific_review_rejections"
    assert "shortening_evidence_lost" in run.outcome[key][-1]["validation_errors"]
    assert run.outcome["evidence_call_ids"] == ["read-1"]


@pytest.mark.parametrize("stage", ["initial", "review"])
@pytest.mark.parametrize("original_status", ["blocked", "needs_input"])
@pytest.mark.parametrize("changed_status", ["partial", "completed"])
def test_shortening_cannot_promote_declared_task_state(session, monkeypatch, stage, original_status, changed_status):
    run = _setup(session)
    long = {**_draft(True), "status": original_status}
    original_short = {**_draft(), "status": original_status}
    changed = {**_draft(), "status": changed_status}
    values = [long, changed] if stage == "initial" else [original_short, long, changed]
    seen = _script(monkeypatch, [{"content": json.dumps(value)} for value in values])
    agent_loop.step(session, run, _provider(session))
    assert len(seen) == len(values)
    assert run.outcome.get("scientific_review") != "automated_review_completed"
    key = "format_repair_rejections" if stage == "initial" else "scientific_review_rejections"
    assert "shortening_status_changed" in run.outcome[key][-1]["validation_errors"]
    assert json.loads(agent_runs.transcript(session, run)[-1].content) == changed
    assert run.outcome["summary"] == long["summary"]


@pytest.mark.parametrize("stage", ["initial", "review"])
@pytest.mark.parametrize("status", ["blocked", "needs_input", "partial", "completed", "review_required"])
def test_shortening_preserves_declared_state_despite_length_validation_override(session, monkeypatch, stage, status):
    run = _setup(session)
    long, short = {**_draft(True), "status": status}, {**_draft(), "status": status}
    values = [long, short, short] if stage == "initial" else [short, long, short]
    seen = _script(monkeypatch, [{"content": json.dumps(value)} for value in values])
    agent_loop.step(session, run, _provider(session))
    assert run.outcome["scientific_review"] == "automated_review_completed"
    packet = json.loads(seen[1 if stage == "initial" else 2][1]["content"])
    assert packet["target_template"]["status"] == status
    assert packet["draft"]["status"] == status
    # The unchanged scientific gap still downgrades a declared completion.
    assert run.outcome["status"] == ("partial" if status == "completed" else status)
