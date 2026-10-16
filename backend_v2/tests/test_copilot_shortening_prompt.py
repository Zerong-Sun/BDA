"""Pure shortening gets an explicit target layout and actual size feedback."""
import json
from types import SimpleNamespace

from backend_v2.app.copilot.agent_loop import _length_repair_messages


def test_740_character_draft_gets_480_target_without_replaying_task_or_diagnostics():
    run = SimpleNamespace(goal="最终报告不超过600字；ORIGINAL_TASK_SENTINEL", task_contract={})
    turns = [SimpleNamespace(role="user", content="FOLLOWUP_TASK_SENTINEL")]
    draft = {"status": "review_required", "summary": "甲" * 131,
             "sections": {"乙": "丙" * 472}, "missing": ["丁" * 66, "delivery_length_exceeded"],
             "next_action": "戊" * 70, "evidence_call_ids": []}
    messages = _length_repair_messages(run, turns, draft)
    packet = json.loads(messages[1]["content"])
    assert packet["target_template"] == {
        "status": "review_required", "summary": "", "sections": {},
        "evidence_call_ids": [], "missing": [], "next_action": "",
    }
    assert packet["length_feedback"] == {
        "current_visible_characters": 740, "target_max_visible_characters": 480,
        "minimum_characters_to_remove": 260,
        "current_field_characters": {"summary": 131, "sections_combined_including_titles": 473,
                                     "missing_combined": 66, "next_action": 70},
    }
    assert packet["contract"] == {"required_sections": []}
    assert packet["delivery_constraints"]["max_visible_characters"] == 600
    assert "goal" not in packet and "user_followups" not in packet
    assert "ORIGINAL_TASK_SENTINEL" not in json.dumps(messages)
    assert "FOLLOWUP_TASK_SENTINEL" not in json.dumps(messages)
    assert packet["draft"]["missing"] == ["丁" * 66]
    assert draft["missing"] == ["丁" * 66, "delivery_length_exceeded"]
    assert "BDA_DELIVERY_SHORTENING_V1" in messages[0]["content"]


def test_required_section_template_and_supporting_ids_are_preserved():
    run = SimpleNamespace(goal="最终报告不超过600字", task_contract={
        "required_sections": ["observations", "limitations"], "cost_mode": "unavailable"})
    turns = [SimpleNamespace(role="tool", content='{"items":[1]}',
                             tool_calls=[{"tool_call_id": "read-1", "name": "inspect"}])]
    draft = {"status": "partial", "summary": "Observed data with unresolved limitations.",
             "sections": {"observations": "Observed only this subset.", "limitations": "Not independently validated.",
                          "surplus": "Repeated explanation."},
             "missing": ["independent validation"], "next_action": "Human review.",
             "evidence_call_ids": ["read-1"], "skill_outputs": {"method": {"evidence_call_ids": ["read-1"]}}}
    packet = json.loads(_length_repair_messages(run, turns, draft)[1]["content"])
    assert packet["target_template"]["sections"] == {"observations": "", "limitations": ""}
    assert packet["target_template"]["evidence_call_ids"] == ["read-1"]
    assert packet["target_template"]["skill_outputs"] == draft["skill_outputs"]
    assert packet["field_budgets"]["sections_combined_including_titles"] == 300
    assert packet["length_feedback"]["target_max_visible_characters"] == 480
    assert packet["valid_evidence_calls"] == [{"call_id": "read-1", "tool": "inspect"}]
