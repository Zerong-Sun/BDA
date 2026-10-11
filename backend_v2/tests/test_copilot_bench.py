from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import tools  # noqa: F401
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.copilot.research_agent import chat_schemas
from backend_v2.app.core.problem import DomainError
from jsonschema import Draft202012Validator


def call(**overrides):
    payload = {"kind": "nucleic-a260", "material": "dsDNA", "sample_absorbance": 1,
               "blank_absorbance": 0, "absorbance_basis": "normalized-1cm", "path_length_cm": 1, "dilution_factor": 1}
    return REGISTRY.execute("calculate_bench", ToolContext(session=object()),
                            {"calculation": {**payload, **overrides}}, granted={"wetlab-read"})


def test_shared_calculator_returns_units_provenance_and_no_project_writes():
    value = call()
    assert next(row["value"] for row in value["values"] if row["key"] == "concentration_ng_uL") == 50
    assert value["formula"] and value["assumptions"] and value["references"]
    assert value["calculation_version"] == "bench-v1"
    spec = REGISTRY.get("calculate_bench")
    assert spec and spec.execution_mode == "read"
    Draft202012Validator.check_schema(spec.parameters)
    assert '"sequence"' not in json.dumps(spec.parameters)


@pytest.mark.parametrize("invalid", [{"path_length_cm": 0.1}, {"sample_absorbance": -1}, {"sample_absorbance": True}, {"sample_absorbance": float("nan")}])
def test_bad_or_double_corrected_inputs_cannot_produce_an_answer(invalid):
    with pytest.raises(DomainError):
        call(**invalid)


def test_capability_and_chat_advertisement_stay_aligned():
    with pytest.raises(DomainError) as error:
        REGISTRY.execute("calculate_bench", ToolContext(session=object()), {}, granted={"project-read"})
    assert error.value.status_code == 403
    schemas = chat_schemas(has_research=False, has_project=False, has_actions=False, has_session=True,
                           allowed_tools={"calculate_bench"})
    assert [row["function"]["name"] for row in schemas] == ["calculate_bench"]


def test_bench_only_delivery_preserves_calculator_facts_without_model_rewriting(monkeypatch):
    from backend_v2.app.copilot import research_agent

    calls = []
    def model(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            return {"content": '{"complete":true,"remaining_questions":[]}'}
        assert len(calls) == 1
        return {"content": None, "tool_calls": [{"id": "calc-1", "type": "function", "function": {
            "name": "calculate_bench", "arguments": json.dumps({"calculation": {
                "kind": "nucleic-a260", "material": "dsDNA", "sample_absorbance": 1,
                "blank_absorbance": 0, "absorbance_basis": "normalized-1cm", "path_length_cm": 1, "dilution_factor": 1,
            }})}}]}
    monkeypatch.setattr(research_agent, "completion_message", model)
    result = research_agent.complete_research_turn(
        object(), [], SimpleNamespace(session=object()), initial_citations=[], initial_tool_calls=[],
        allowed_tools={"calculate_bench"}, bench_response_language="zh",
    )
    assert "50 ng/uL" in result.content
    assert "不再按仪器实际光程重复校正" in result.content
    assert "未保存实验记录" in result.content
    assert result.tool_calls[0]["result"]["calculation_version"] == "bench-v1"
    assert result.calculator_delivery is True
    assert len(calls) == 2


def test_successive_calculations_complete_before_deterministic_delivery(monkeypatch):
    from backend_v2.app.copilot import research_agent

    replies = iter([
        {"tool_calls": [{"id": "first", "function": {"name": "calculate_bench", "arguments": json.dumps({"calculation": {
            "kind": "nucleic-a260", "material": "dsDNA", "sample_absorbance": 1, "blank_absorbance": 0,
            "absorbance_basis": "normalized-1cm", "path_length_cm": 1, "dilution_factor": 1,
        }})}}]},
        {"tool_calls": [{"id": "next", "function": {"name": "calculate_bench", "arguments": json.dumps({"calculation": {
            "kind": "nucleic-a260", "material": "dsDNA", "sample_absorbance": 2, "blank_absorbance": 0,
            "absorbance_basis": "normalized-1cm", "path_length_cm": 1, "dilution_factor": 1,
        }})}}]},
        {"content": '{"complete":true,"remaining_questions":[]}'},
    ])
    monkeypatch.setattr(research_agent, "completion_message", lambda *args, **kwargs: next(replies))
    result = research_agent.complete_research_turn(
        object(), [], SimpleNamespace(session=object()), initial_citations=[], initial_tool_calls=[],
        allowed_tools={"calculate_bench"}, bench_response_language="zh",
    )
    assert "50 ng/uL" in result.content and "100 ng/uL" in result.content
    assert len(result.tool_calls) == 2


@pytest.mark.parametrize("final", ['{"complete":false,"remaining_questions":["终体积是多少？"]}',
                                   '{"complete":true,"remaining_questions":["终体积是多少？"]}',
                                   "incorrect reinterpretation of normalized absorbance"])
def test_unresolved_or_invalid_delivery_keeps_calculation_and_marks_incomplete(final):
    from backend_v2.app.copilot.bench_tools import render_delivery

    answer = render_delivery([call()], final, language="zh")
    assert "50 ng/uL" in answer and "尚未完成全部请求" in answer
    assert "incorrect reinterpretation" not in answer
    if "终体积" in final:
        assert "终体积是多少？" in answer
