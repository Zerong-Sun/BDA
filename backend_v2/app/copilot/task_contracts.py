"""Task recipes, evidence-backed progress and explicit delivery outcomes.

The runner may stop successfully without delivering its goal. Only this bounded
contract can mark delivery complete; scientific claims still require human review.
"""
from __future__ import annotations

import json
from typing import Any

from .models import CopilotAgentRun, CopilotAgentTurn


def _step(key: str, en: str, zh: str, tools: list[str]) -> dict:
    return {"id": key, "title": en, "title_zh": zh, "tools": tools}


SERVICES: dict[str, dict] = {
    "brief": {
        "title": "Define the research goal", "title_zh": "明确研究目标",
        "deliverable": "An editable brief, success criteria and missing inputs",
        "deliverable_zh": "可编辑任务书、成功标准和待补充信息",
        "capabilities": ["project-read", "research-read"], "write_tools": [],
        "steps": [_step("context", "Read project context", "读取项目目标与已有资料", ["research_overview", "list_project_targets"])],
    },
    "literature": {
        "title": "Research the evidence", "title_zh": "调研与比较证据",
        "deliverable": "Search scope, traced excerpts, disagreements and evidence gaps",
        "deliverable_zh": "检索范围、来源片段、证据分歧与缺口；可选保存待审核笔记",
        "capabilities": ["project-read", "research-read", "knowledge-authoring", "literature-search"],
        "write_tools": ["start_literature_search", "create_knowledge_draft"],
        "steps": [
            _step("discovery", "Find evidence", "发现相关文献", ["search_research"]),
            _step("excerpts", "Read traced excerpts", "读取可追溯正文或摘要", ["get_reference_content"]),
        ],
    },
    "planning": {
        "title": "Prepare an experimental plan", "title_zh": "制定实验方案",
        "deliverable": "Available routes, tradeoffs, missing inputs and a plan for review",
        "deliverable_zh": "适用路线、比较依据、输入缺口和待审核方案",
        "capabilities": ["project-read", "research-read", "workflow-planning"], "write_tools": [],
        "steps": [
            _step("context", "Inspect inputs", "检查目标与输入", ["list_project_targets", "research_overview"]),
            _step("routes", "Compare registered routes", "比较已注册路线", ["plan_workflow_route"]),
        ],
    },
    "execution": {
        "title": "Track execution and diagnose problems", "title_zh": "跟进执行与处理异常",
        "deliverable": "Current state, blockers and a recovery proposal; submission stays with the user",
        "deliverable_zh": "运行状态、阻碍和恢复建议；提交仍由用户确认",
        "capabilities": ["project-read"], "write_tools": [],
        "steps": [
            _step("workflow", "Inspect the workflow", "检查工作流", ["get_workflow_status"]),
            _step("jobs", "Inspect execution", "检查作业与异常", ["get_compute_status"]),
        ],
    },
    "interpretation": {
        "title": "Interpret results and plan the next round", "title_zh": "解读结果与设计下一轮",
        "deliverable": "Observed results, limitations, supported/refuted hypotheses and next actions",
        "deliverable_zh": "结果比较、限制、支持或否定的假设和下一轮建议",
        "capabilities": ["project-read", "research-read", "result-interpretation"], "write_tools": [],
        "steps": [_step("results", "Read recorded results", "读取实际结果", ["list_experiment_results", "list_project_candidates"])],
    },
}

DELIVERY_SECTIONS = {
    "brief": ["objective", "constraints", "success_criteria", "missing_inputs"],
    "literature": ["search_scope", "evidence_comparison", "disagreements", "limitations"],
    "planning": ["route_comparison", "inputs", "risks", "next_step"],
    "execution": ["current_state", "blockers", "recovery"],
    "interpretation": ["observations", "limitations", "hypotheses", "next_round"],
}

FINAL_INSTRUCTION = """
Return your final delivery as JSON (no markdown fence):
{"status":"completed|partial|blocked|needs_input", "summary":"the deliverable, with source IDs and limitations",
 "sections":{"each required_sections key":"nonempty content, with sources or an explicit unknown"},
 "evidence_call_ids":["successful tool_call_id used"], "missing":["remaining item"], "next_action":"specific next action"}.
A completed delivery must satisfy every contract step and cite the successful tool calls
that support it. This confirms delivery of a draft/diagnosis, never scientific validity.
If you cannot proceed, report blocked or needs_input with an actionable reason. Do not
invent artifact links or evidence IDs. A brief must include objectives, constraints,
success criteria and missing inputs. For literature distinguish excerpts from search hits.
Keep the summary to one or two sentences. Make each section concise and focused on
its own purpose, preserving the source IDs, units, analysis versions and limitations
needed to review its claims. Do not repeat complete tool payloads or the same content
across the summary and sections. State a shared limitation once unless its effect
differs for a particular result.
"""


def build_contract(kind: str, writes: list[str]) -> dict:
    service = SERVICES.get(kind)
    steps = [dict(step) for step in service["steps"]] if service else []
    if kind == "literature":
        if "start_literature_search" in writes:
            steps[0] = _step("discovery", "Search external literature", "执行外部文献检索", ["start_literature_search"])
        if "create_knowledge_draft" in writes:
            steps.append(_step("note", "Save a review draft", "保存待审核笔记", ["create_knowledge_draft"]))
    return {"version": 1, "required_sections": DELIVERY_SECTIONS.get(kind, []), "service_kind": kind, "authorized_writes": sorted(writes), "steps": steps,
            "deliverable": service["deliverable"] if service else "Reviewable answer to the stated goal",
            "deliverable_zh": service["deliverable_zh"] if service else "针对目标的可审核答复",
            "submission_policy": "human_confirmation"}


def tool_records(turns: list[CopilotAgentTurn]) -> list[dict]:
    records = []
    for turn in turns:
        if turn.role != "tool":
            continue
        try:
            result = json.loads(turn.content)
        except (ValueError, TypeError):
            continue
        meta = (turn.tool_calls or [{}])[0]
        # A settled compute wait reports the job's failure, not a failed read.
        # Keep failed actions/delegations and unresolved waits unsuccessful.
        observed_job = (meta.get("name") == "await_compute_job" and isinstance(result, dict)
                        and ((result.get("kind") == "gpu_job" and result.get("resource_id")
                              and result.get("job_status") in {"succeeded", "failed", "cancelled"})
                             or (result.get("job_id") and result.get("waiting") is False
                                 and result.get("status") in {"succeeded", "failed", "cancelled"})))
        observed_run = (meta.get("name") == "read_operator_work" and isinstance(result, dict)
                        and result.get("run_id") and isinstance(result.get("tool_results"), list)
                        and not result.get("error"))
        bad = not (observed_job or observed_run) and isinstance(result, dict) and (result.get("error") or result.get("status") in {"failed", "cancelled", "pending", "running"})
        records.append({"call_id": meta.get("tool_call_id", ""), "tool": meta.get("name", ""),
                        # An empty list is a successful query with no matches.
                        # Steps that require actual rows enforce that below.
                        "successful": result is not None and not bool(bad), "result": result})
    return records


def _has_excerpt(value: Any) -> bool:
    if isinstance(value, list):
        return any(_has_excerpt(item) for item in value)
    if not isinstance(value, dict):
        return False
    provenance = value.get("content_provenance") or value
    content = value.get("content")
    if (isinstance(content, str) and content.strip() and isinstance(provenance, dict)
            and value.get("chunk_id") and provenance.get("content_checksum_sha256")
            and provenance.get("retrieval_trace_id")):
        return True
    return any(_has_excerpt(item) for item in value.values() if isinstance(item, (list, dict)))


def progress(contract: dict, turns: list[CopilotAgentTurn]) -> list[dict]:
    records = tool_records(turns)
    rows = []
    for step in contract.get("steps", []):
        matches = [r for r in records if r["tool"] in step["tools"] and r["successful"]]
        if step["id"] == "excerpts":
            matches = [r for r in matches if _has_excerpt(r["result"])]
        if step["id"] == "results":
            matches = [r for r in matches if isinstance(r["result"], list) and r["result"] or isinstance(r["result"], dict) and r["result"].get("items")]
        rows.append({**step, "status": "completed" if matches else "pending", "evidence_call_ids": [r["call_id"] for r in matches]})
    return rows


def _delivery_json(answer: str) -> Any:
    """Read JSON or one terminal JSON fence, optionally introduced by prose.

    Real providers sometimes add a sentence before the otherwise valid final
    object. Accept that presentation variation without guessing among multiple
    blocks or stripping trailing text that might qualify the delivery.
    """
    text = answer.strip()
    try:
        return json.loads(text)
    except ValueError:
        if text.count("```") != 2:
            raise
        _, block, suffix = text.split("```")
        language, separator, payload = block.partition("\n")
        if suffix.strip() or not separator or language.strip().lower() not in {"", "json"}:
            raise ValueError("ambiguous delivery fence") from None
        return json.loads(payload)


def evaluate_delivery(run: CopilotAgentRun, answer: str, turns: list[CopilotAgentTurn]) -> dict:
    steps = progress(run.task_contract or {}, turns)
    try:
        data = _delivery_json(answer)
        if not isinstance(data, dict) or data.get("status") not in {"completed", "partial", "blocked", "needs_input"}:
            raise ValueError("invalid delivery status")
        if not isinstance(data.get("summary"), str) or not data["summary"].strip():
            raise ValueError("missing summary")
        refs = data.get("evidence_call_ids")
        missing = data.get("missing")
        if not isinstance(refs, list) or not all(isinstance(v, str) for v in refs):
            raise ValueError("invalid evidence list")
        if not isinstance(missing, list) or not all(isinstance(v, str) for v in missing):
            raise ValueError("invalid missing list")
        if not isinstance(data.get("next_action"), str):
            raise ValueError("missing next action")
    except (ValueError, TypeError):
        return {"status": "review_required", "summary": answer, "missing": ["structured_delivery_required"],
                "next_action": "Review the answer or continue with a specific request.", "steps": steps, "evidence_call_ids": []}
    successful = {r["call_id"] for r in tool_records(turns) if r["successful"]}
    invalid = set(refs) - successful
    gaps = [s["id"] for s in steps if s["status"] != "completed"]
    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        sections = {}
    invalid_sections = any(not isinstance(v, str) or not v.strip() for v in sections.values())
    sections = {k: v for k, v in sections.items() if isinstance(v, str) and v.strip()}
    gaps += [key for key in (run.task_contract or {}).get("required_sections", []) if key not in sections]
    status = data["status"]
    checks = []
    if invalid_sections:
        checks.append("invalid_section_values")
    if invalid:
        checks.append("unverified_evidence_call_ids")
    if status == "completed" and (gaps or missing or not refs or any(not set(s["evidence_call_ids"]) & set(refs) for s in steps)):
        status = "partial"
    if status == "completed" and not steps:
        status = "review_required"  # Open-ended goals have no machine-verifiable delivery contract.
    if invalid or invalid_sections:
        status = "review_required"
    return {"status": status, "summary": data["summary"], "sections": sections, "missing": list(dict.fromkeys(missing + gaps + checks)),
            "next_action": data["next_action"], "evidence_call_ids": [ref for ref in refs if ref in successful], "steps": steps}


def task_view(run: CopilotAgentRun, turns: list[CopilotAgentTurn]) -> dict:
    result = dict(run.outcome or {})
    result["steps"] = progress(run.task_contract or {}, turns)
    records = tool_records(turns)
    result["evidence"] = [{"call_id": r["call_id"], "tool": r["tool"], "successful": r["successful"]} for r in records]
    result["deliverables"] = [
        {"kind": kind, "id": str(r["result"][field])}
        for r in records if r["successful"] and isinstance(r["result"], dict)
        for field, kind in (("knowledge_entry_id", "knowledge"), ("search_run_id", "literature"))
        if r["result"].get(field)
    ]
    if not result.get("status"):
        result["status"] = {"running": "running", "awaiting_tasks": "waiting", "failed": "blocked", "cancelled": "cancelled"}.get(run.status, "review_required")
    return result


def available_step_tools(run: CopilotAgentRun, turns: list[CopilotAgentTurn]) -> set[str]:
    allowed = set(run.allowed_tools or [])
    steps = progress(run.task_contract or {}, turns)
    if not steps:
        return allowed
    pending = next((step for step in steps if step['status'] != 'completed'), None)
    from .registry import REGISTRY
    reads = allowed - REGISTRY.user_intent_write_ids()
    bookkeeping = allowed & (REGISTRY.write_ids() - REGISTRY.user_intent_write_ids())
    if pending is None:
        return reads
    # Evidence reads must not disappear behind a recipe step. A user may name
    # a known source directly, and diagnosis may need several kinds of reads.
    # Only user-intent writes are gated by the current step; delivery still
    # requires every declared step and its verified evidence.
    return reads | bookkeeping | (allowed & set(pending['tools']))
