from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot import tools  # noqa: F401
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.copilot.research_agent import chat_schemas
from backend_v2.app.core.problem import DomainError
from jsonschema import Draft202012Validator


@pytest.mark.parametrize("missing", ["blank_absorbance", "absorbance_basis", "path_length_cm", "dilution_factor"])
def test_chat_calculator_requires_explicit_absorbance_conditions(missing):
    payload = {"kind": "nucleic-a260", "material": "dsDNA", "sample_absorbance": 1,
               "blank_absorbance": 0, "absorbance_basis": "normalized-1cm", "path_length_cm": 1, "dilution_factor": 1}
    payload.pop(missing)
    with pytest.raises(DomainError):
        REGISTRY.execute("calculate_bench", ToolContext(session=object()), {"calculation": payload}, granted={"wetlab-read"})


@pytest.mark.parametrize(("stock_unit", "stock", "target_unit", "target", "expected"), [
    ("uM", 1, "nM", 10, 10), ("nM", 1000, "uM", .01, 10), ("mg/mL", 1, "ug/mL", 10, 10),
])
def test_dilution_converts_stock_and_target_units_before_feasibility(stock_unit, stock, target_unit, target, expected):
    result = REGISTRY.execute("calculate_bench", ToolContext(session=object()), {"calculation": {
        "kind": "dilution", "stock_concentration": stock, "target_concentration": target,
        "concentration_unit": stock_unit, "target_concentration_unit": target_unit, "final_volume_uL": 1000,
    }}, granted={"wetlab-read"})
    assert next(row["value"] for row in result["values"] if row["key"] == "stock_volume_uL") == pytest.approx(expected)
    assert "换算" in result["assumptions_zh"][-1]


def test_dilution_still_rejects_infeasible_target_after_unit_conversion():
    with pytest.raises(DomainError):
        REGISTRY.execute("calculate_bench", ToolContext(session=object()), {"calculation": {
            "kind": "dilution", "stock_concentration": 1, "target_concentration": 10000,
            "concentration_unit": "uM", "target_concentration_unit": "nM", "final_volume_uL": 1000,
        }}, granted={"wetlab-read"})


def _calculation_request(call_id="calc"):
    return {"id": call_id, "type": "function", "function": {"name": "calculate_bench", "arguments": json.dumps({"calculation": {
        "kind": "nucleic-a260", "material": "dsDNA", "sample_absorbance": 1,
        "blank_absorbance": 0, "absorbance_basis": "normalized-1cm", "path_length_cm": 1, "dilution_factor": 1,
    }})}}


def _turn(monkeypatch, replies, **kwargs):
    from backend_v2.app.copilot import research_agent
    responses = iter(replies)
    def model(*args, **kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(research_agent, "completion_message", model)
    return research_agent.complete_research_turn(
        object(), [], SimpleNamespace(session=object()), initial_citations=[], initial_tool_calls=[],
        allowed_tools={"calculate_bench", "list_proteins", "compute_concentration", "plan_dilution_series"},
        bench_response_language="zh", **kwargs,
    )


def test_skipped_batch_cannot_be_reported_as_fully_completed(monkeypatch):
    result = _turn(monkeypatch, [
        {"tool_calls": [_calculation_request("first"), _calculation_request("skipped")]},
        {"content": '{"complete":true,"remaining_questions":[]}'},
    ], max_tool_calls=1)
    assert result.limit_reached
    assert "尚未完成全部请求" in result.content
    assert any(row.get("status") == "skipped" for row in result.tool_calls)


@pytest.mark.parametrize("failure", [DomainError("llm_output_truncated", "Output limit", status_code=502), ValueError("llm_response_empty")])
def test_final_model_failure_preserves_completed_calculations(monkeypatch, failure):
    result = _turn(monkeypatch, [{"tool_calls": [_calculation_request()]}, failure])
    assert result.calculator_delivery
    assert result.delivery_incomplete
    assert "50 ng/uL" in result.content and "尚未完成全部请求" in result.content


def test_library_results_are_not_lost_when_mixed_with_calculations(monkeypatch):
    from backend_v2.app.copilot import research_agent
    execute = research_agent._execute
    def mixed(context, name, *args, **kwargs):
        if name == "list_proteins":
            return [{"id": "synthetic-protein", "name": "Library control", "length": 100, "molecular_weight": 12000}], []
        return execute(context, name, *args, **kwargs)
    monkeypatch.setattr(research_agent, "_execute", mixed)
    result = _turn(monkeypatch, [
        {"tool_calls": [{"id": "library", "function": {"name": "list_proteins", "arguments": "{}"}}, _calculation_request()]},
        {"content": '{"complete":true,"remaining_questions":[]}'},
    ])
    assert "Library control" in result.content and "50 ng/uL" in result.content


def test_failed_tool_is_not_hidden_by_a_later_completion_claim(monkeypatch):
    invalid = _calculation_request("invalid")
    invalid["function"]["arguments"] = '{"calculation":{"kind":"nucleic-a260","material":"dsDNA","sample_absorbance":1}}'
    result = _turn(monkeypatch, [{"tool_calls": [invalid, _calculation_request("good")]},
                                 {"content": '{"complete":true,"remaining_questions":[]}'}])
    assert "50 ng/uL" in result.content and "尚未完成全部请求" in result.content
    assert result.delivery_incomplete


def test_dedicated_mode_advertises_one_calculator_contract(monkeypatch):
    from backend_v2.app.copilot import research_agent
    seen = []
    def model(*args, **kwargs):
        seen.extend(tool['function']['name'] for tool in kwargs['tools'])
        return {"content": "请补充样本类型。"}
    monkeypatch.setattr(research_agent, "completion_message", model)
    research_agent.complete_research_turn(object(), [], SimpleNamespace(session=object()), initial_citations=[], initial_tool_calls=[],
                                         allowed_tools={"calculate_bench", "list_proteins", "compute_concentration", "plan_dilution_series"},
                                         bench_response_language="zh")
    assert set(seen) == {"calculate_bench", "list_proteins"}


def test_empty_final_content_does_not_lose_calculations(monkeypatch):
    result = _turn(monkeypatch, [{"tool_calls": [_calculation_request()]}, {"content": None}])
    assert result.delivery_incomplete and "50 ng/uL" in result.content


def test_single_fenced_json_envelope_is_accepted_but_mixed_prose_is_not():
    from backend_v2.app.copilot.bench_tools import completion_status
    envelope = '```json\n{"complete":true,"remaining_questions":[]}\n```'
    assert completion_status(envelope) == (True, [])
    assert completion_status('Unverified explanation\n' + envelope) == (False, [])


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
