from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

from backend_v2.app.copilot import research_agent
from backend_v2.app.core.problem import DomainError


def test_research_agent_executes_model_requested_read_tool(monkeypatch) -> None:
    responses = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "search_research", "arguments": '{"query":"target","limit":5}'},
                    }
                ],
            },
            {"content": "Target evidence is available [entity-1]."},
        ]
    )
    monkeypatch.setattr(research_agent, "completion_message", lambda *args, **kwargs: next(responses))
    item = {"kind": "research_target", "id": "entity-1", "label": "Target", "data": {}}
    context = SimpleNamespace(
        search_research=lambda query, limit, allowed_kinds: [item],
        citation_for_item=lambda value: {
            "source_type": "research_workspace",
            "workspace_type": value["kind"],
            "entity_id": value["id"],
        },
    )
    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": "Find the target"}],
        cast(Any, context),
        initial_citations=[],
        initial_tool_calls=[],
    )
    assert result.content.startswith("Target evidence")
    assert result.citations[0]["entity_id"] == "entity-1"
    assert result.tool_calls[0]["name"] == "search_research"
    assert result.tool_calls[0]["status"] == "completed"


def test_research_agent_skips_tools_when_tool_budget_is_zero(monkeypatch) -> None:
    captured = {}

    def complete(*args, **kwargs):
        captured.update(kwargs)
        return {"content": "Hypothesis-only answer; project evidence is unavailable."}

    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": "Propose three concepts"}],
        cast(Any, SimpleNamespace()),
        initial_citations=[],
        initial_tool_calls=[],
        max_tool_calls=0,
    )
    assert result.content.startswith("Hypothesis-only")
    assert captured["tools"] is None


def test_research_agent_executes_permission_checked_gap_resolution(monkeypatch) -> None:
    target_id = "0964f127-9572-46d7-aa0d-21147a079803"
    operation_id = "ca9b938b-b02c-4916-96d8-23398d886a4b"
    responses = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-resolve",
                        "type": "function",
                        "function": {
                            "name": "resolve_research_gaps",
                            "arguments": (
                                f'{{"research_target_id":"{target_id}",'
                                '"resolve_references":true,"resolve_structure":true}'
                            ),
                        },
                    }
                ],
            },
            {"content": (f"Gap resolution was queued as operation {operation_id}; " "its current status is pending.")},
        ]
    )
    exposed_tools = []

    def complete(*args, **kwargs):
        exposed_tools.extend(kwargs.get("tools") or [])
        return next(responses)

    requested = {}

    def resolve(research_target_id, *, resolve_references, resolve_structure):
        requested.update(
            {
                "research_target_id": research_target_id,
                "resolve_references": resolve_references,
                "resolve_structure": resolve_structure,
            }
        )
        return {
            "operation_id": operation_id,
            "research_target_id": research_target_id,
            "status": "pending",
        }

    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": f"Fix all gaps for entity ID {target_id}."}],
        cast(Any, SimpleNamespace()),
        initial_citations=[],
        initial_tool_calls=[],
        allowed_kinds={"research_target"},
        actions=cast(Any, SimpleNamespace(resolve_research_gaps=resolve)),
    )

    assert any(item["function"]["name"] == "resolve_research_gaps" for item in exposed_tools)
    assert requested == {
        "research_target_id": target_id,
        "resolve_references": True,
        "resolve_structure": True,
    }
    assert result.tool_calls[0]["result"]["operation_id"] == operation_id
    assert result.tool_calls[0]["result"]["status"] == "pending"
    assert "pending" in result.content


def test_copilot_agent_reads_operational_project_data(monkeypatch) -> None:
    responses = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-candidates",
                        "type": "function",
                        "function": {
                            "name": "list_project_candidates",
                            "arguments": '{"status":"ranked","limit":5}',
                        },
                    }
                ],
            },
            {"content": "Candidate C1 is ranked first [candidate-1]."},
        ]
    )
    exposed = []

    def complete(*args, **kwargs):
        exposed.extend(kwargs.get("tools") or [])
        return next(responses)

    item = {
        "kind": "candidate",
        "id": "candidate-1",
        "label": "C1",
        "data": {"rank": 1},
    }
    project_context = SimpleNamespace(
        list_candidates=lambda status, limit: [item],
        citation_for_item=lambda value: {
            "source_type": "project_database",
            "workspace_type": value["kind"],
            "entity_id": value["id"],
        },
    )
    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": "List ranked candidates."}],
        cast(Any, SimpleNamespace()),
        initial_citations=[],
        initial_tool_calls=[],
        project_context=cast(Any, project_context),
        allowed_tools={"list_project_candidates"},
    )

    assert {item["function"]["name"] for item in exposed} == {"list_project_candidates"}
    assert result.citations[0]["entity_id"] == "candidate-1"
    assert result.tool_calls[0]["result_count"] == 1


def test_copilot_agent_creates_compute_draft_without_submission(monkeypatch) -> None:
    draft_id = str(uuid.uuid4())
    responses = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-draft",
                        "type": "function",
                        "function": {
                            "name": "create_compute_draft",
                            "arguments": ('{"name":"Review me","backend":"lsf",' '"specification":{"queue":"normal"}}'),
                        },
                    }
                ],
            },
            {"content": (f"Draft {draft_id} was created and still requires confirmation.")},
        ]
    )
    actions = SimpleNamespace(
        create_compute_draft=lambda name, backend, specification: {
            "compute_draft_id": draft_id,
            "status": "draft",
            "backend": backend,
            "confirmation_required": True,
        }
    )
    monkeypatch.setattr(
        research_agent,
        "completion_message",
        lambda *args, **kwargs: next(responses),
    )
    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": "Create an LSF compute draft."}],
        cast(Any, SimpleNamespace()),
        initial_citations=[],
        initial_tool_calls=[],
        actions=cast(Any, actions),
        allowed_tools={"create_compute_draft"},
    )

    assert result.tool_calls[0]["result"] == {
        "compute_draft_id": draft_id,
        "status": "draft",
        "backend": "lsf",
        "confirmation_required": True,
    }
    assert "requires confirmation" in result.content


def test_research_agent_reports_project_scope_rejection_without_failing_turn(
    monkeypatch,
) -> None:
    responses = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-intelligence",
                        "type": "function",
                        "function": {
                            "name": "start_target_intelligence",
                            "arguments": (
                                '{"target_id":"00000000-0000-0000-0000-000000000001",' '"query":"binding sites"}'
                            ),
                        },
                    }
                ],
            },
            {"content": "The target was rejected because it is not in this project."},
        ]
    )
    actions = SimpleNamespace(
        start_target_intelligence=lambda target_id, query: (_ for _ in ()).throw(
            DomainError(
                "target_not_found",
                "Target was not found in this project",
                status_code=404,
            )
        )
    )
    monkeypatch.setattr(
        research_agent,
        "completion_message",
        lambda *args, **kwargs: next(responses),
    )

    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": "Start target intelligence."}],
        cast(Any, SimpleNamespace()),
        initial_citations=[],
        initial_tool_calls=[],
        actions=cast(Any, actions),
        allowed_tools={"start_target_intelligence"},
    )

    assert result.tool_calls == [
        {
            "name": "start_target_intelligence",
            "status": "failed",
            "error": "target_not_found",
        }
    ]


def test_research_agent_reads_saved_paper_content_and_returns_traceable_citation(monkeypatch) -> None:
    responses = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-content",
                        "type": "function",
                        "function": {
                            "name": "get_reference_content",
                            "arguments": '{"reference_id":"PMCID:PMC12345","offset":0,"limit":3}',
                        },
                    }
                ],
            },
            {"content": "The saved excerpt supports only a measured binding claim."},
        ]
    )
    monkeypatch.setattr(research_agent, "completion_message", lambda *args, **kwargs: next(responses))
    excerpt = {
        "kind": "literature_excerpt",
        "id": "chunk-1",
        "label": "Measured aroma binding",
        "data": {
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "ref_id": "PMCID:PMC12345",
            "content": "Measured binding evidence.",
            "review_status": "pending_review",
            "content_provenance": {
                "content_kind": "open_full_text",
                "content_checksum_sha256": "a" * 64,
                "retrieval_trace_id": "trace-1",
            },
        },
    }
    context = SimpleNamespace(
        get_reference_content=lambda reference_id, offset, limit: [excerpt],
        citation_for_item=lambda item: {
            "source_type": "scientific_literature",
            "workspace_type": item["kind"],
            "entity_id": item["id"],
            "document_id": item["data"]["document_id"],
            "chunk_id": item["data"]["chunk_id"],
            "content_kind": item["data"]["content_provenance"]["content_kind"],
            "content_checksum_sha256": item["data"]["content_provenance"]["content_checksum_sha256"],
            "retrieval_trace_id": item["data"]["content_provenance"]["retrieval_trace_id"],
        },
    )

    result = research_agent.complete_research_turn(
        cast(Any, SimpleNamespace()),
        [{"role": "user", "content": "Read the paper before stating the binding result."}],
        cast(Any, context),
        initial_citations=[],
        initial_tool_calls=[],
        allowed_kinds={"literature_excerpt"},
    )

    assert result.tool_calls[0]["name"] == "get_reference_content"
    assert result.citations == [
        {
            "source_type": "scientific_literature",
            "workspace_type": "literature_excerpt",
            "entity_id": "chunk-1",
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "content_kind": "open_full_text",
            "content_checksum_sha256": "a" * 64,
            "retrieval_trace_id": "trace-1",
        }
    ]


def test_scientific_review_uses_no_tools_and_returns_revised_answer(monkeypatch) -> None:
    captured = {}

    def complete(*args, **kwargs):
        captured["messages"] = args[1]
        captured.update(kwargs)
        return {"content": "Revised answer with variables and unit-checked formulas."}

    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.review_scientific_answer(
        cast(Any, SimpleNamespace()),
        "Propose three cost-reducing protein concepts.",
        "Draft with unsupported prices and impossible chemistry.",
    )
    assert result.startswith("Revised answer")
    assert captured["tools"] is None
    assert "Cost-reduction logic" in captured["messages"][0]["content"]
    assert "Untrusted draft" in captured["messages"][1]["content"]


def test_grounded_scientific_review_receives_exact_evidence_packet(monkeypatch) -> None:
    captured = {}

    def complete(*args, **kwargs):
        captured["messages"] = args[1]
        captured.update(kwargs)
        return {"content": "Corrected answer with unsupported prices removed."}

    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.review_grounded_scientific_answer(
        cast(Any, SimpleNamespace()),
        "Design three flavor-protein concepts.",
        "Draft with an invented market price.",
        '{"items":[{"document_id":"doc-1","chunk_id":"chunk-1","excerpt":"Measured binding."}]}',
    )
    assert result.startswith("Corrected answer")
    assert captured["tools"] is None
    assert "Physical delivery" in captured["messages"][0]["content"]
    assert "doc-1" in captured["messages"][1]["content"]
    assert "invented market price" in captured["messages"][1]["content"]


def test_grounded_answer_quality_gate_detects_costs_and_incomplete_trace() -> None:
    issues = research_agent.grounded_answer_issues(
        "预算 10k 元/kg。Google Patents 检索结果未见。只引用 chunk `short-id`。"
    )
    assert issues == [
        "unsupported_currency_or_budget",
        "incomplete_evidence_tags",
        "unaudited_external_search_claim",
    ]

    complete = (
        "成本使用变量 C_protein（currency/kg），不填猜测值。"
        "[document_id=doc; chunk_id=chunk; content_kind=open_access_full_text; "
        "content_checksum_sha256=sha; retrieval_trace_id=trace]"
    )
    assert research_agent.grounded_answer_issues(complete) == []

    incomplete = complete + " 另见 [document_id=doc; chunk_id=short]。"
    assert research_agent.grounded_answer_issues(incomplete) == ["incomplete_evidence_tags"]

    novelty_and_delivery = "本次未见商业化先例。蛋白在胃肠酶解释放香气，再产生鼻后嗅觉。"
    assert research_agent.grounded_answer_issues(novelty_and_delivery) == [
        "incomplete_evidence_tags",
        "unsupported_absence_or_novelty_claim",
        "late_gastrointestinal_aroma_delivery",
    ]

    negated_delivery = complete + " 蛋白本身不直接激活嗅觉受体；只释放挥发性小分子。"
    assert "implausible_nonvolatile_receptor_delivery" not in research_agent.grounded_answer_issues(negated_delivery)


def test_grounded_repair_receives_automated_failures(monkeypatch) -> None:
    captured = {}

    def complete(*args, **kwargs):
        captured["messages"] = args[1]
        captured.update(kwargs)
        return {"content": "Repaired answer with full evidence tags."}

    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.repair_grounded_scientific_answer(
        cast(Any, SimpleNamespace()),
        "Design concepts.",
        "Reviewed answer with 10k budget.",
        '{"items":[]}',
        ["unsupported_currency_or_budget", "incomplete_evidence_tags"],
    )
    assert result.startswith("Repaired")
    assert captured["tools"] is None
    assert "unsupported_currency_or_budget" in captured["messages"][1]["content"]
    assert "full literal tag" in captured["messages"][0]["content"]


def test_computational_experiment_review_receives_the_run_packet(monkeypatch) -> None:
    """Run reports fail differently from literature reviews.

    They go wrong by reading a model's own score as corroboration, by dropping a negative
    result, or by asserting cause with no control arm - none of which the citation rules
    catch, so this review is separate.
    """
    captured = {}

    def complete(*args, **kwargs):
        captured["messages"] = args[1]
        captured.update(kwargs)
        return {"content": "Corrected answer separating self-assessment from cross-check."}

    monkeypatch.setattr(research_agent, "completion_message", complete)
    result = research_agent.review_computational_experiment_answer(
        cast(Any, SimpleNamespace()),
        "Summarise the binder design campaign.",
        "Draft that ranks candidates on the design model's own ipTM.",
        '{"runs":[{"id":"4083234","arm":"baseline"}],'
        '"metrics":[{"key":"iptm","value":0.94,"assessor":"design_model","condition":"ligand:TCI"}]}',
    )
    assert result.startswith("Corrected answer")
    assert captured["tools"] is None
    system = captured["messages"][0]["content"]
    # The rules this prompt exists for, each traceable to a real failure on the
    # cannabinoid project.
    assert "Self-assessment is not corroboration" in system
    assert "assessor and its condition" in system
    assert "negative results as results" in system
    assert "causal claim requires a control arm" in system
    assert "reproducible direction from reproducible magnitude" in system
    assert "pipeline failure from a scientific result" in system
    assert "4083234" in captured["messages"][1]["content"]
