"""Final length limits include visible diagnostics derived by the server."""
import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot.agent_review import reviewable_delivery
from backend_v2.app.copilot.delivery_context import visible_characters
from backend_v2.app.copilot.task_contracts import evaluate_delivery


@pytest.mark.parametrize("gap_kind", ["contract", "skill"])
def test_server_gap_cannot_bypass_final_character_limit(monkeypatch, gap_kind):
    gap = "source_provenance"
    contract = {"steps": [], "required_sections": [gap] if gap_kind == "contract" else []}
    if gap_kind == "skill":
        monkeypatch.setattr(
            "backend_v2.app.copilot.procedural_skills.evaluate_outputs",
            lambda *args: ({}, [gap]),
        )
    run = SimpleNamespace(goal="最终报告不超过20字", task_contract=contract)
    draft = {"status": "partial", "summary": "字" * 20, "sections": {},
             "missing": [], "next_action": "", "evidence_call_ids": []}
    outcome = evaluate_delivery(run, json.dumps(draft), [])
    assert visible_characters(outcome) > 20
    assert outcome["missing"] == [gap, "delivery_length_exceeded"]
    assert outcome["status"] == "review_required"
    assert not reviewable_delivery(run, outcome)


def test_shortened_delivery_recomputes_limit_with_deduplicated_server_gaps():
    gap = "source_provenance"
    run = SimpleNamespace(goal="最终报告不超过20字",
                          task_contract={"steps": [], "required_sections": [gap]})
    draft = {"status": "partial", "summary": "字" * 3, "sections": {},
             "missing": [gap, "delivery_length_exceeded"], "next_action": "", "evidence_call_ids": []}
    outcome = evaluate_delivery(run, json.dumps(draft), [])
    assert visible_characters(outcome) == 20
    assert outcome["missing"] == [gap]
    assert outcome["status"] == "partial"
    assert reviewable_delivery(run, outcome)
