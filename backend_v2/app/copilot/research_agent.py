from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..core.problem import DomainError
from ..registry.models import LLMProvider
from . import tools as _tools  # noqa: F401  (registers the tool catalogue)
from .actions import CopilotActionService
from .citations import citations_for
from .citations import dedupe as dedupe_citations
from .project_context import ProjectContextService
from .provider import completion_message
from .registry import REGISTRY, ToolContext
from .research_context import ResearchContextService

#: The tools a chat turn may advertise, derived from the registry.
#:
#: These used to be three hand-written schema lists, and they had drifted: they
#: covered the tools that need the research context, the project context or the
#: action service, and nothing was ever added for the ones that need only a
#: session. Thirteen registry tools - every bench tool, the research-goal tools
#: and the whole structure and diagnosis surface - were therefore declared in
#: `capabilities.py` as chat tools, returned by `tools_for_capabilities`, and
#: then silently dropped here because no schema existed to advertise. Dispatch
#: had already moved to `REGISTRY.execute`; only the advertisement had not, so a
#: tool could be callable and unofferable at the same time.
#:
#: `agent_loop._schemas` and `mcp.available_tools` both derive from the registry.
#: This is the third surface doing the same thing, which is what makes "adding a
#: capability is adding a row" true for chat as well.
#:
#: Availability is decided by the same rule `REGISTRY.execute` enforces - the
#: `ToolContext` attribute a spec names in `requires` must be present - so what
#: is offered and what will run can no longer disagree.
CHAT_UNSUPPORTED_REQUIRES = frozenset({"agent_run"})


def chat_schemas(
    *,
    has_research: bool,
    has_project: bool,
    has_actions: bool,
    has_session: bool,
    allowed_tools: set[str] | None,
    has_operator: bool = True,
) -> list[dict[str, Any]]:
    """Schemas for the tools this turn can both offer and run.

    `has_operator` is the same kind of condition as the four above it: a turn
    that named no bot cannot hand over, because a handover whose sender is "the
    assistant" names nobody accountable. Offering the tool anyway would put a
    guaranteed failure in front of the model - the state this function was
    rewritten to end, one axis over.
    """
    present = {
        "research": has_research,
        "project": has_project,
        "actions": has_actions,
        "session": has_session,
    }
    return [
        spec.schema()
        for spec in REGISTRY.all()
        if spec.requires not in CHAT_UNSUPPORTED_REQUIRES
        and present.get(spec.requires, False)
        and (has_operator or not spec.needs_operator)
        and (allowed_tools is None or spec.id in allowed_tools)
    ]


#: Write tools, derived rather than listed. The hand-written version of this set
#: named five of the registry's ten writes, which was harmless only for as long
#: as the other five were unreachable anyway. `tasks.py` filters exactly this set
#: through the user's own words, so a write missing from it is a write the model
#: could call on a turn nobody asked for one.
#: The writes `tasks.py` filters through the user's own words. Narrower than
#: `REGISTRY.write_ids()` by the copilot's own bookkeeping - a handover note
#: changes no research record, and gating it on the user saying "handoff" would
#: stop operators handing over rather than stop a write nobody asked for.
WRITE_TOOL_NAMES = REGISTRY.user_intent_write_ids()

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
    bot: str | None = None,
    enabled_capabilities: set[str] | None = None,
) -> ResearchAgentResult:
    citations = list(initial_citations)
    call_log = list(initial_tool_calls)
    conversation = list(messages)
    for _ in range(max_tool_calls + 1):
        tools = chat_schemas(
            has_research=context is not None,
            has_project=project_context is not None,
            has_actions=actions is not None,
            has_session=getattr(context, "session", None) is not None,
            allowed_tools=allowed_tools,
            has_operator=bot is not None,
        )
        offered = {tool["function"]["name"] for tool in tools}
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
            return ResearchAgentResult(content.strip(), dedupe_citations(citations), call_log)
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
            return ResearchAgentResult(content.strip(), dedupe_citations(citations), call_log, True)
        assistant_turn: dict[str, Any] = {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": requested,
        }
        # Thinking-mode models return their reasoning alongside the tool calls
        # and require it back on the next round: DeepSeek refuses the follow-up
        # with "The `reasoning_content` in the thinking mode must be passed back
        # to the API", which made every tool-using turn on such a model fail at
        # the second round. Copied through only when the provider sent it, so
        # providers that do not use the field see no change.
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            assistant_turn["reasoning_content"] = reasoning
        conversation.append(assistant_turn)
        answered: set[str] = set()
        for request in requested:
            if len(call_log) - len(initial_tool_calls) >= max_tool_calls:
                break
            call_id = str(request.get("id") or "")
            function = request.get("function") or {}
            name = str(function.get("name") or "")
            try:
                if name not in offered:
                    raise ValueError("tool_not_allowed_for_this_turn")
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
                    bot=bot,
                    enabled_capabilities=enabled_capabilities,
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
            answered.add(call_id)
        # Every tool call gets a reply, including the ones the budget cut off.
        # The loop above breaks mid-batch when the limit lands inside a batch,
        # which used to leave an assistant message carrying N tool calls followed
        # by fewer than N tool messages - a conversation the API rejects outright
        # ("insufficient tool messages following tool_calls message"), losing the
        # whole turn rather than the one call that did not run.
        for request in requested:
            call_id = str(request.get("id") or "")
            if not call_id or call_id in answered:
                continue
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": str((request.get("function") or {}).get("name") or ""),
                    "content": json.dumps({"error": "tool_call_budget_exhausted"}, ensure_ascii=False),
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


def _execute(
    context: ResearchContextService,
    name: str,
    arguments: dict[str, Any],
    allowed_kinds: set[str] | None,
    actions: CopilotActionService | None,
    project_context: ProjectContextService | None,
    *,
    bot: str | None = None,
    enabled_capabilities: set[str] | None = None,
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
        user_id=getattr(getattr(actions, "user", None), "id", None) or getattr(context, "user_id", None),
        session=getattr(context, "session", None),
        research=context,
        project=project_context,
        actions=actions,
        allowed_kinds=allowed_kinds,
        # A chat turn carries its operator here; a run carries it on the row.
        # Both reach `tools._bot_of`, which refuses when neither is set - an
        # unowned turn has no accountable sender to put on a handover.
        bot=bot,
        allowed_capabilities=frozenset(enabled_capabilities) if enabled_capabilities else None,
    )
    try:
        result = REGISTRY.execute(name, tool_context, arguments)
    except DomainError as error:
        # The agent loop reports tool failures as ValueError with a short code;
        # keeping that shape means the turn handling above is unchanged.
        raise ValueError(error.error_code) from error
    return result, citations_for(spec, result, context, project_context)
