from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..core.problem import DomainError
from ..registry.models import LLMProvider
from . import tools as _tools  # noqa: F401  (registers the tool catalogue)
from .actions import CopilotActionService
from .project_context import ProjectContextService
from .provider import completion_message
from .registry import REGISTRY, ToolContext
from .research_context import ResearchContextService

RESEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "research_overview",
            "description": "Return project identity, review document metadata, category counts, and available kinds.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_research",
            "description": "Search the current project's canonical Research workspace and return entity-level results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_research_items",
            "description": "Page through Research entities of one kind, optionally restricted to exact entity IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["kind"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_slice",
            "description": "Return a bounded page from a Research dataset by dataset ID or key.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["dataset_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reference",
            "description": "Expand one Research reference using its workspace document ID or ref_id.",
            "parameters": {
                "type": "object",
                "properties": {"reference_id": {"type": "string"}},
                "required": ["reference_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reference_content",
            "description": (
                "Read checksum-traced chunks extracted from a saved scientific paper full text or abstract. "
                "Use this before making factual, quantitative, or novelty claims from a reference."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_id": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["reference_id"],
                "additionalProperties": False,
            },
        },
    },
]

RESEARCH_WRITE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "resolve_research_gaps",
            "description": (
                "Queue permission-checked repairs for retrievable reference content and an AlphaFold predicted "
                "structure for one exact Research target. Call only when the user explicitly asks to fix, fill, "
                "complete, or resolve gaps. This cannot resolve wet-lab, clinical, patent-landscape, or "
                "experimental-structure gaps. Return and report the operation as pending; never claim completion "
                "until a later operation result confirms it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "research_target_id": {
                        "type": "string",
                        "description": "Exact Research target entity UUID from the current project.",
                    },
                    "resolve_references": {"type": "boolean"},
                    "resolve_structure": {"type": "boolean"},
                },
                "required": ["research_target_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_literature_search",
            "description": (
                "Queue an auditable Europe PMC search in the current project. Call only when the user explicitly "
                "asks to search or ingest literature. Report the search_run_id and pending status; do not claim "
                "that papers have already been reviewed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 3, "maxLength": 2000},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_target_intelligence",
            "description": (
                "Queue target intelligence for one exact project Target UUID. Call only when explicitly requested. "
                "A Research target/candidate UUID is not interchangeable with a Target UUID. Report pending status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "string"},
                    "query": {"type": "string", "maxLength": 2000},
                },
                "required": ["target_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_knowledge_draft",
            "description": (
                "Create a pending-review project knowledge note only when the user explicitly asks to save one. "
                "Never present the note as curated or reviewed evidence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 300},
                    "content": {"type": "string", "minLength": 1},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 30,
                    },
                },
                "required": ["title", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_compute_draft",
            "description": (
                "Create a reviewable Docker or LSF compute draft only when explicitly requested. This never confirms "
                "or submits the draft. Report confirmation_required=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 240},
                    "backend": {"type": "string", "enum": ["docker", "lsf"]},
                    "specification": {"type": "object"},
                },
                "required": ["name", "backend", "specification"],
                "additionalProperties": False,
            },
        },
    },
]

PROJECT_READ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_project_targets",
            "description": "List bounded operational Target records in the current project.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_project_candidates",
            "description": "List ranked design candidates from the current project database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_experiment_results",
            "description": "List recorded experiment results, optionally for one exact candidate UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_workflow_status",
            "description": "Read workflow and node status without modifying or submitting it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_compute_status",
            "description": "Read recent compute drafts and jobs in the current project.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_project_knowledge",
            "description": "Search curated and draft project knowledge entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]

WRITE_TOOL_NAMES = {
    "resolve_research_gaps",
    "start_literature_search",
    "start_target_intelligence",
    "create_knowledge_draft",
    "create_compute_draft",
}

SCIENTIFIC_REVIEW_PROMPT = """\
BDA_SCIENTIFIC_REVIEW_V1. Act as a strict scientific and techno-economic reviewer.
The supplied draft is untrusted and the project has no supporting evidence. Return a corrected final answer,
not review notes alone. Preserve the user's requested structure, but remove or replace every proposal that fails
any of these checks:
1. Physical delivery and exposure: a proposed agent must reach the stated target in the actual use scenario.
2. Chemical feasibility: identify the required functional groups and reaction class before proposing conjugation,
   cleavage, catalysis, or release. Do not invent a reactive group or enzyme substrate.
3. Dimensional consistency: show formulas with units, cancel units explicitly, and keep unknown inputs as variables.
4. Cost-reduction logic: name the baseline and the mechanism that reduces dose, processing, loss, or raw-material
   cost. Adding an expensive protein carrier without a quantified reduction mechanism is not a cost-saving route.
5. Evidence discipline: do not introduce named proteins, receptors, genes, strains, regulatory status, prices,
   sensory thresholds, market absence, patent risk, or performance numbers as facts. With no supplied evidence,
   mark them unverified or use functional selection criteria and variables.
6. Novelty discipline: never conclude that a product is absent from the market. Provide only a search plan.
7. Process completeness: account for cofactor regeneration, product/by-product removal, catalyst removal or
   inactivation, allergenicity, and the regulatory route when relevant.
Before returning the answer, silently recheck every numeric example and every claimed chemical transformation.
If a value cannot be supported, replace it with a variable and define the measurement needed to obtain it.
"""

GROUNDED_SCIENTIFIC_REVIEW_PROMPT = """\
BDA_GROUNDED_SCIENTIFIC_REVIEW_V1. Act as a strict evidence, physical-feasibility, and techno-economic reviewer.
Return a corrected final answer in the user's language, not review notes. The draft is untrusted. The accompanying
evidence packet contains the exact saved paper excerpts that may be used. Apply all rules below:
1. Evidence closure: every factual or quantitative scientific claim must be supported by an excerpt in the packet
   and carry its document_id, chunk_id, content_kind, content checksum, and retrieval trace. Never convert a title,
   search result, abstract-only statement, docking prediction, or pending-review claim into stronger evidence.
2. No invented specifics: remove unsupported protein names, receptors, residues, PDB IDs, organisms, expression
   yields, affinities, sensory thresholds, temperatures, prices, market volumes, regulatory status, patent results,
   and performance percentages. Replace useful unknowns with named variables and the measurement needed.
3. Physical delivery: a nonvolatile protein or peptide in food does not reach an olfactory receptor merely because
   it binds that receptor in a model. Reject or replace any route that lacks a plausible exposure and delivery path.
   For volatile aroma perception, distinguish release of a volatile small molecule into headspace from direct
   receptor activation by a nonvolatile macromolecule.
4. Chemical and biological mechanism: verify functional groups, reaction class, mass balance, cofactors,
   regeneration, catalyst removal/inactivation, allergenicity, and regulatory route as applicable. Do not infer
   a human-food function directly from an insect odorant-binding result.
5. Cost discipline: do not claim lower cost without a named baseline and a dose/process/loss reduction mechanism.
   Use a dimensional break-even equation with variables (for example cost per equivalent delivered aroma effect);
   do not fabricate supplier prices or production costs. A protein carrier is not automatically cheaper.
6. Novelty discipline: report only searches actually present in the packet or original request. Do not claim that
   patent, product, supplier, or commercial databases were searched unless an auditable trace is supplied. State
   query, database, timestamp, inclusion criteria, limitations, and that absence of a hit does not prove absence.
7. Design quality: preserve three meaningfully different routes only if each is physically plausible. Replace an
   invalid route with a clearly labeled hypothesis and the cheapest falsification test. Separate supported fact,
   evidence-based inference, hypothesis, and counterevidence.
8. Scoring: score scientific correctness, evidence completeness, and novelty potential conservatively out of 10.
   The score must reflect the corrected answer and explicit remaining gaps, not marketing confidence.
Silently check every number, unit, citation, chemical transformation, and delivery assumption before answering.
"""

COMPUTATIONAL_EXPERIMENT_PROMPT = """\
BDA_COMPUTATIONAL_EXPERIMENT_V1. Act as a strict reviewer of computational design and
prediction runs. The draft is untrusted. The other review prompts govern claims taken from
literature; this one governs claims taken from runs the platform itself executed, which
fail in different ways. Return a corrected answer, not review notes.
1. Self-assessment is not corroboration. A score produced by the model that generated the
   design is self-reported. Label it as such, and never rank, recommend, or select on it
   alone. When an independent method has scored the same objects, report both and their
   disagreement; a weak rank correlation between them is itself a finding, not noise to
   average away.
2. Every number needs its assessor and its condition. "ipTM 0.94" is not a complete
   statement; "AlphaFold3 ipTM 0.94 against the intended ligand, 0.87 against the closest
   control" is. A metric with no stated condition may not be compared with one measured
   under a different condition.
3. Report negative results as results. Zero candidates, a margin indistinguishable from
   zero, or a refuted hypothesis are conclusions, and must not be softened into "requires
   further optimisation" or omitted because they read as failure. State what was ruled out
   and what that implies for the next step.
4. A causal claim requires a control arm. Name the baseline run, the parameters that
   differed, and confirm that nothing else did. Without a control the statement is a
   hypothesis and must be written as one.
5. Separate reproducible direction from reproducible magnitude. If replicate runs agree on
   the sign of an effect but not its size, say so and do not quote the yield as a
   expectation. Report the replicate spread.
6. State sample size and variance. A conclusion from a handful of trajectories is not a
   rule. Give the number of independent runs behind every rate or median, and prefer a
   range to a point estimate when the sample is small.
7. Confidence metrics are predictions, never measurements of binding, affinity, activity,
   stability or expression. Passing a computational gate licenses the next computation, not
   an experimental claim. Do not describe a design as working, functional, or validated on
   predicted numbers alone.
8. Distinguish a pipeline failure from a scientific result. A run that produced nothing
   because a filter rejected everything is a finding about the designs; a run that produced
   nothing because it crashed is not. Check which one occurred before interpreting.
Silently recheck every number, its assessor, its condition, and its sample size before
answering.
"""

GROUNDED_REPAIR_PROMPT = """\
BDA_GROUNDED_REPAIR_V1. The previous evidence review failed automated quality checks. Return a complete corrected
answer in the user's language. Apply these fail-closed requirements:
1. Delete every supplier price, market size, production cost, budget, yield, dose, threshold, duration, percentage,
   affinity, temperature, and performance target unless that exact value appears in an evidence excerpt. Unknown
   economics must use symbols and dimensionally consistent break-even equations, not guessed ranges.
2. Every evidence-based bullet must end with the full literal tag:
   [document_id=...; chunk_id=...; content_kind=...; content_checksum_sha256=...; retrieval_trace_id=...].
   A shortened UUID or a title/PMID alone is not a valid evidence tag.
3. Report only the auditable literature database, query, and timestamp present in the evidence packet. Patent,
   product, supplier, and commercial searches are future work unless their traces are in the packet.
4. A nonvolatile protein/peptide cannot directly create retronasal aroma by activating nasal receptors. Replace
   that route with a physically deliverable route that releases, captures, converts, or separates volatile small
   molecules. Gastrointestinal or stomach release after swallowing is too late for the intended oral/retronasal
   aroma event; release must occur in food headspace or the oral cavity before/during swallowing. Clearly label
   untested routes as hypotheses.
5. Preserve three distinct routes, cost break-even variables, minimum falsification experiments, limitations, and
   conservative scores. Do not add regulatory conclusions or named examples absent from the packet.
6. The evidence packet distinguishes search hits from excerpts actually read. Preserve the recorded result_count
   and do not rewrite it as the number of papers read. Without audited patent and commercial-product searches,
   make no "no precedent", market-gap, or commercial-absence claim and cap novelty potential at 5/10.
The answer must be internally consistent: never state that unsupported numbers were removed and then include them.
"""


@dataclass(frozen=True)
class ResearchAgentResult:
    content: str
    citations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    limit_reached: bool = False


def complete_research_turn(
    provider: LLMProvider,
    messages: list[dict[str, Any]],
    context: ResearchContextService,
    *,
    initial_citations: list[dict[str, Any]],
    initial_tool_calls: list[dict[str, Any]],
    allowed_kinds: set[str] | None = None,
    actions: CopilotActionService | None = None,
    project_context: ProjectContextService | None = None,
    allowed_tools: set[str] | None = None,
    max_tool_calls: int = 12,
) -> ResearchAgentResult:
    citations = list(initial_citations)
    call_log = list(initial_tool_calls)
    conversation = list(messages)
    for _ in range(max_tool_calls + 1):
        tools: list[dict[str, Any]] = [*RESEARCH_TOOLS]
        if project_context is not None:
            tools.extend(PROJECT_READ_TOOLS)
        if actions is not None:
            tools.extend(RESEARCH_WRITE_TOOLS)
        if allowed_tools is not None:
            tools = [tool for tool in tools if tool["function"]["name"] in allowed_tools]
        message = completion_message(
            provider,
            conversation,
            tools=tools if max_tool_calls > 0 and tools else None,
        )
        requested = message.get("tool_calls")
        if not isinstance(requested, list) or not requested:
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("llm_response_empty")
            return ResearchAgentResult(content.strip(), _dedupe_citations(citations), call_log)
        if len(call_log) - len(initial_tool_calls) >= max_tool_calls:
            conversation.append(
                {
                    "role": "system",
                    "content": "The 12-call Research tool limit was reached. Answer now and state the uncovered scope.",
                }
            )
            final = completion_message(provider, conversation)
            content = final.get("content")
            if not isinstance(content, str) or not content.strip():
                content = "Research tool-call limit reached; the remaining workspace scope was not covered."
            return ResearchAgentResult(content.strip(), _dedupe_citations(citations), call_log, True)
        conversation.append(
            {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": requested,
            }
        )
        for request in requested:
            if len(call_log) - len(initial_tool_calls) >= max_tool_calls:
                break
            call_id = str(request.get("id") or "")
            function = request.get("function") or {}
            name = str(function.get("name") or "")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("tool_arguments_not_object")
                result, result_citations = _execute(
                    context,
                    name,
                    arguments,
                    allowed_kinds,
                    actions,
                    project_context,
                )
                citations.extend(result_citations)
                logged_call = {
                    "name": name,
                    "arguments": arguments,
                    "status": "completed",
                    "result_count": len(result) if isinstance(result, list) else (1 if result else 0),
                }
                if name in WRITE_TOOL_NAMES and isinstance(result, dict):
                    logged_call["result"] = result
                call_log.append(logged_call)
            except (DomainError, TypeError, ValueError, RuntimeError) as exc:
                error = exc.error_code if isinstance(exc, DomainError) else str(exc)
                result = {"error": error}
                call_log.append({"name": name, "status": "failed", "error": error[:300]})
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
    raise RuntimeError("research_tool_loop_exhausted")


def review_scientific_answer(provider: LLMProvider, request: str, draft: str) -> str:
    message = completion_message(
        provider,
        [
            {"role": "system", "content": SCIENTIFIC_REVIEW_PROMPT},
            {
                "role": "user",
                "content": (f"Original request:\n{request}\n\nUntrusted draft to correct:\n{draft}"),
            },
        ],
        tools=None,
    )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("llm_review_response_empty")
    return content.strip()


def review_computational_experiment_answer(
    provider: LLMProvider,
    request: str,
    draft: str,
    run_packet: str,
) -> str:
    """Review a draft whose claims come from runs the platform executed.

    Kept separate from the literature reviews because the failure modes differ: a run
    report goes wrong by treating a model's own score as corroboration, by dropping a
    negative result, or by asserting cause without a control arm - none of which the
    evidence-citation rules catch.
    """
    message = completion_message(
        provider,
        [
            {"role": "system", "content": COMPUTATIONAL_EXPERIMENT_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original request:\n{request}\n\n"
                    f"Run records, metrics with assessor and condition, and control arms:\n"
                    f"{run_packet}\n\n"
                    f"Untrusted draft to correct:\n{draft}"
                ),
            },
        ],
        tools=None,
    )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("llm_review_response_empty")
    return content.strip()


def review_grounded_scientific_answer(
    provider: LLMProvider,
    request: str,
    draft: str,
    evidence_packet: str,
) -> str:
    message = completion_message(
        provider,
        [
            {"role": "system", "content": GROUNDED_SCIENTIFIC_REVIEW_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original request:\n{request}\n\n"
                    f"Auditable evidence packet:\n{evidence_packet}\n\n"
                    f"Untrusted draft to correct:\n{draft}"
                ),
            },
        ],
        tools=None,
    )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("llm_grounded_review_response_empty")
    return content.strip()


def grounded_answer_issues(answer: str) -> list[str]:
    issues: list[str] = []
    if re.search(r"(?:[$¥€£]|美元|人民币|元/(?:kg|公斤)|\b\d+(?:\.\d+)?\s*[kK]\b)", answer):
        issues.append("unsupported_currency_or_budget")
    required_tags = (
        "document_id=",
        "chunk_id=",
        "content_kind=",
        "content_checksum_sha256=",
        "retrieval_trace_id=",
    )
    evidence_tags = re.findall(r"\[[^\]]*document_id=[^\]]*\]", answer)
    if not evidence_tags or any(not all(field in tag for field in required_tags) for tag in evidence_tags):
        issues.append("incomplete_evidence_tags")
    if re.search(r"(?:USPTO|Google Patents|Mintel|商业数据库).{0,80}(?:检索|搜索).{0,40}(?:结果|命中|未见)", answer):
        issues.append("unaudited_external_search_claim")
    if re.search(r"(?:未见|没有|不存在).{0,40}(?:商业化|产品|市场|先例|专利)", answer):
        issues.append("unsupported_absence_or_novelty_claim")
    if re.search(r"(?:蛋白|肽).{0,50}直接激活.{0,50}(?:嗅觉|鼻腔|受体)", answer) and not re.search(
        r"(?:不能|不可|无法|违反|不).{0,50}(?:直接激活|嗅觉|鼻腔)", answer
    ):
        issues.append("implausible_nonvolatile_receptor_delivery")
    if re.search(r"(?:消化道|胃肠|胃酸|胃环境).{0,80}(?:释放|酶解).{0,80}(?:鼻后|嗅觉|香气)", answer):
        issues.append("late_gastrointestinal_aroma_delivery")
    return issues


def repair_grounded_scientific_answer(
    provider: LLMProvider,
    request: str,
    reviewed_answer: str,
    evidence_packet: str,
    issues: list[str],
) -> str:
    message = completion_message(
        provider,
        [
            {"role": "system", "content": GROUNDED_REPAIR_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original request:\n{request}\n\n"
                    f"Automated quality failures:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
                    f"Auditable evidence packet:\n{evidence_packet}\n\n"
                    f"Reviewed answer that still failed:\n{reviewed_answer}"
                ),
            },
        ],
        tools=None,
    )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("llm_grounded_repair_response_empty")
    return content.strip()


def _cite(
    spec: Any,
    result: Any,
    context: ResearchContextService,
    project_context: ProjectContextService | None,
) -> list[dict[str, Any]]:
    """Turn a tool result into citations, following the tool's declared policy.

    The policy lives on the ToolSpec rather than in a branch here, so a new tool
    states how it is cited at the point it is declared and cannot be added
    without answering the question.
    """
    policy = getattr(spec, "citation", "none")
    if policy == "none" or result is None:
        return []
    if policy == "project_items" and project_context is not None:
        return [project_context.citation_for_item(item) for item in result]
    if policy == "project_compute" and project_context is not None:
        rows = [*result.get("drafts", []), *result.get("jobs", [])]
        return [project_context.citation_for_item(item) for item in rows]
    if policy == "research_items":
        return [context.citation_for_item(item) for item in result]
    if policy == "research_dataset":
        return [
            context.citation_for_item(
                {
                    "kind": "dataset",
                    "id": str(result.get("id")),
                    "label": str(
                        (result.get("title") or {}).get("default") or result.get("key") or "dataset"
                    ),
                    "data": result,
                }
            )
        ]
    if policy == "research_reference":
        return [
            context.citation_for_item(
                {
                    "kind": "reference",
                    "id": str(result.get("document_id")),
                    "label": str(
                        (result.get("title") or {}).get("default") or result.get("ref_id")
                    ),
                    "data": result,
                }
            )
        ]
    return []


def _execute(
    context: ResearchContextService,
    name: str,
    arguments: dict[str, Any],
    allowed_kinds: set[str] | None,
    actions: CopilotActionService | None,
    project_context: ProjectContextService | None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Run one tool.

    Dispatch, the capability check and the service check all live in the
    registry now; this only supplies the turn's services and decorates the
    result with citations. It used to be a seventeen-branch `if name == ...`
    chain in which each branch re-implemented its own guards.
    """
    spec = REGISTRY.get(name)
    if spec is None:
        raise ValueError("unknown_research_tool")
    tool_context = ToolContext(
        project_id=getattr(context, "project_id", None),
        user_id=getattr(context, "user_id", None),
        session=getattr(context, "session", None),
        research=context,
        project=project_context,
        actions=actions,
        allowed_kinds=allowed_kinds,
    )
    try:
        result = REGISTRY.execute(name, tool_context, arguments)
    except DomainError as error:
        # The agent loop reports tool failures as ValueError with a short code;
        # keeping that shape means the turn handling above is unchanged.
        raise ValueError(error.error_code) from error
    return result, _cite(spec, result, context, project_context)


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (str(citation.get("workspace_type")), str(citation.get("entity_id")))
        if key not in seen:
            result.append(citation)
            seen.add(key)
    return result
