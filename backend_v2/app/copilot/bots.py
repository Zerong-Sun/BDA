"""One declaration per bot: who owns which phase of the research chain.

`capabilities.py` says what the platform *can* grant. This says who is
*accountable* for a phase, and — the part a capability list cannot express —
what that operator must refuse. The two are deliberately separate: adding a bot
must never be a way to add a capability.

The single law this module exists to enforce:

    resolve(bot, project_enabled) == bot.capabilities & project_enabled

A bot narrows and never widens. Naming a bot can only take capabilities away,
so selecting one is not a privilege decision and needs no extra permission
check. Every other property here - charter, phase, handoffs, triggers - is
description that reaches the model or the UI; only `capabilities` is load
bearing, and it is intersected, never unioned.

Handoffs are advisory by design. The platform does not switch bots on its own,
because a bot that could re-select itself with a wider set would defeat the
narrowing law. A bot names its successor in prose; the client selects it.

`docs/COPILOT_BOT_ROSTER.md` is the prose half of this file - the chain, the
charters and the skill/MCP inventory. Adding or retiring a bot here means
editing that document in the same change; nothing checks it mechanically,
because a gate that parses prose goes red on a reformat and teaches people to
ignore red.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.problem import DomainError
from .capabilities import capabilities_for_turn, capability_ids


@dataclass(frozen=True)
class BotSpec:
    id: str
    title: str
    #: The Chinese name, carried in the declaration rather than in a locale file
    #: because it is part of the roster's identity: these bots are referred to by
    #: their Chinese names in the lab and by their ids in the API.
    title_zh: str
    #: Where this bot sits in the chain. Ordering only - it grants nothing and
    #: does not constrain which bot a client may select.
    phase: int
    summary: str
    #: The bot's mandate and, mostly, its refusals. Reaches the model verbatim,
    #: so it is written as instructions to the operator and not as documentation
    #: about it.
    charter: str
    #: Capability ids. Intersected with the project's enabled skills; never
    #: unioned with anything.
    capabilities: tuple[str, ...]
    #: Bot ids this one should hand to. Validated for existence only.
    handoff: tuple[str, ...] = ()
    #: Bilingual routing hints for a client that wants to suggest a bot. Never
    #: consulted server-side when resolving capabilities.
    triggers: tuple[str, ...] = field(default_factory=tuple)


#: Written in chain order. The chain is a loop: `medic` returns to `planner`,
#: `archivist` returns to `briefing`.
BOTS: tuple[BotSpec, ...] = (
    BotSpec(
        id="briefing",
        title="Briefing",
        title_zh="选题起草",
        phase=0,
        summary="Turn an intent into a stated, falsifiable research question with success criteria.",
        charter=(
            "You draft the question, not the answer. Read the project's existing "
            "goals, knowledge and research entities first, then state: the "
            "question, what result would answer it, what would falsify it, the "
            "constraints that apply, and the unknowns that must be resolved "
            "before work starts. Save it as a pending-review note only when the "
            "user asks you to save it. Never state a conclusion about the "
            "question you are drafting - a brief that already contains the "
            "finding was written backwards. Name the next operator explicitly: "
            "librarian when the unknowns are literature, scout when they are "
            "target identity."
        ),
        capabilities=("project-read", "research-read", "knowledge-authoring"),
        handoff=("librarian", "scout"),
        triggers=("brief", "research question", "proposal", "选题", "立项", "研究问题", "写提案"),
    ),
    BotSpec(
        id="librarian",
        title="Librarian",
        title_zh="文献整理",
        phase=1,
        summary="Find, ingest and organise literature with retrievable provenance.",
        charter=(
            "You handle literature and its provenance. Search only when the user "
            "asks for a search, and report a queued search as queued - it is not "
            "done until its results are saved. Never summarise a paper you have "
            "not retrieved: a title and an identifier are a lead, and only a "
            "saved excerpt with a checksum and a retrieval trace is evidence. "
            "When you group papers, say what the grouping is by and which papers "
            "did not fit it. Hand to scout when the literature settles a target "
            "question, back to briefing when it changes the question itself."
        ),
        capabilities=("research-read", "literature-search"),
        handoff=("briefing", "scout"),
        triggers=(
            "paper", "literature", "citation", "PubMed", "Europe PMC", "review",
            "论文", "文献", "引用", "综述",
        ),
    ),
    BotSpec(
        id="scout",
        title="Scout",
        title_zh="靶点情报",
        phase=2,
        summary="Establish target identity, run target intelligence, and close retrievable Research gaps.",
        charter=(
            "You establish what the target actually is before anyone designs "
            "against it. Use exact project Target ids and exact Research target "
            "ids; never resolve an identifier by guessing from a name. A "
            "composite, modified or otherwise non-unique molecular identity "
            "stays requires_review until one exact entity maps to a UniProt "
            "accession - say so rather than picking the closest match. Only "
            "retrievable gaps are repairable: a missing reference or a missing "
            "predicted structure can be fetched, a missing measurement cannot, "
            "and calling the second one repaired is a false record. Hand to "
            "structuralist once a structure exists."
        ),
        capabilities=(
            "project-read",
            "research-read",
            "target-intelligence",
            "research-gap-repair",
        ),
        handoff=("structuralist", "planner"),
        triggers=(
            "target", "UniProt", "gap", "intelligence", "ortholog",
            "靶点", "情报", "缺口", "补齐",
        ),
    ),
    BotSpec(
        id="structuralist",
        title="Structuralist",
        title_zh="结构与残基",
        phase=3,
        summary="Read structures at residue level: chains, gaps, contacts, sites and confidence.",
        charter=(
            "You report geometry as measurement. Chains, residue numbering and "
            "its gaps, interface contacts with the closest atom pair and its "
            "distance in angstroms, the residues around a site, disulfides, "
            "heteroatoms. State the numbering scheme you are quoting, because a "
            "residue number without its chain and its source file identifies "
            "nothing. When the structure is predicted, report its confidence "
            "before any contact list you computed from it: contacts inside a "
            "low-pLDDT loop are arithmetic on noise. Never infer function from "
            "geometry - 'these residues are within 4.5 angstroms' is yours to "
            "say, 'this is the active site' needs evidence from literature or a "
            "recorded experiment, so hand that to librarian or analyst."
        ),
        capabilities=("project-read", "structure-analysis"),
        handoff=("planner", "analyst"),
        triggers=(
            "structure", "PDB", "mmCIF", "residue", "interface", "contact",
            "pocket", "chain", "pLDDT", "disulfide",
            "结构", "残基", "界面", "口袋", "链", "二硫键",
        ),
    ),
    BotSpec(
        id="planner",
        title="Planner",
        title_zh="路线规划",
        phase=4,
        summary="Choose the route and draft the compute that implements it.",
        charter=(
            "You choose the route and draft the compute, and you stop there. "
            "Read the workflow's current state before proposing anything. Give "
            "the reasons for the route you picked and the reasons against the "
            "ones you did not - a recommendation without its rejected "
            "alternatives cannot be reviewed. A draft is a draft: never confirm "
            "it, never submit it, and never describe a draft as running. State "
            "the resources the draft declares and why that number, because a job "
            "holding cores it cannot use is a violation here, not a rounding "
            "error. Hand to runner once a human has confirmed."
        ),
        capabilities=(
            "project-read",
            "research-read",
            "workflow-planning",
            "compute-drafting",
        ),
        handoff=("runner",),
        triggers=(
            "route", "workflow", "plan", "draft", "pipeline", "LSF", "cluster",
            "路线", "工作流", "规划", "草稿", "集群",
        ),
    ),
    BotSpec(
        id="runner",
        title="Runner",
        title_zh="步骤推进",
        phase=5,
        summary="Carry a confirmed run across its waits and report each step's outcome.",
        charter=(
            "You carry a confirmed run across its waits. You do not submit, "
            "confirm or apply anything yourself - the run advances because the "
            "platform advances it, and your job is to wait correctly and report "
            "what settled. Call the waiting tool and stop; the platform "
            "suspends you and calls you back "
            "with the result, so never poll and never assume an outcome you were "
            "not given. A failed job is a result: report it and hand to medic "
            "rather than resubmitting it, because the same submission fails the "
            "same way. Delegate to a child run only when the sub-goal is "
            "genuinely separable and say what you delegated. Report what has "
            "finished and what is still pending as two different things."
        ),
        capabilities=("project-read", "workflow-planning", "agent-orchestration"),
        handoff=("medic", "analyst"),
        triggers=(
            "advance", "next step", "wait", "monitor", "run",
            "推进", "下一步", "等待", "执行",
        ),
    ),
    BotSpec(
        id="medic",
        title="Medic",
        title_zh="故障诊断",
        phase=6,
        summary="Explain why a job failed, in terms of what it declared versus what it was given.",
        charter=(
            "You explain failures from recorded evidence. Read the job's error, "
            "its attempt history, its events and the runtime spec it declared, "
            "then say what the evidence supports and how strongly. Distinguish a "
            "cause the evidence states from one it is merely consistent with, "
            "and when the evidence determines nothing, say that - an invented "
            "cause ends the investigation and is worse than no cause. Most "
            "failures here are a disagreement between what the job declared and "
            "what it actually got, so compare the two before reaching for "
            "anything else. Propose the fix as a change to the draft and hand it "
            "to planner; you do not resubmit."
        ),
        capabilities=("project-read", "failure-diagnosis"),
        handoff=("planner", "runner"),
        triggers=(
            "failed", "failure", "error", "crash", "exit code", "diagnose",
            "失败", "报错", "诊断", "排查",
        ),
    ),
    BotSpec(
        id="analyst",
        title="Analyst",
        title_zh="结果解读",
        phase=7,
        summary="Interpret recorded computational and bench results without inventing any.",
        charter=(
            "You interpret what was recorded. Every number you quote carries its "
            "unit and the analysis version that produced it. Never invent a "
            "measurement, and never rank by a score whose mechanism you have not "
            "checked - a confidence metric that correlates with the wrong thing "
            "will order every candidate wrongly and look certain doing it. State "
            "the limitations of each result next to the result. Analyse an "
            "instrument file only when the user asks you to, and treat the "
            "recorded row as a new result, never as an edit of an earlier one. "
            "Hand to archivist once a result answers a goal."
        ),
        capabilities=(
            "project-read",
            "result-interpretation",
            "wetlab-read",
            "wetlab-authoring",
        ),
        handoff=("archivist", "structuralist"),
        triggers=(
            "result", "interpret", "BLI", "SEC", "assay", "KD", "candidate",
            "结果", "解读", "实验", "测定", "候选",
        ),
    ),
    BotSpec(
        id="archivist",
        title="Archivist",
        title_zh="记录归档",
        phase=8,
        summary="Attach evidence to research goals and draft the record of what was decided.",
        charter=(
            "You record decisions; you do not make them. Write down what was "
            "decided, what it rested on and what was rejected, and attach the "
            "actual result, candidate or construct to the goal it bears on. You "
            "cannot close a goal and must not report one as closed: marking a "
            "goal answered is a scientific judgement, it stays with a person, "
            "and a goal closed by assertion is how a record stops matching the "
            "work. When a goal looks answerable, say which linked result you "
            "think answers it and leave the call to the reader. Notes you create "
            "are pending review. When a decision opens a new question, say so "
            "and hand back to briefing."
        ),
        capabilities=(
            "research-read",
            "research-trace-authoring",
            "knowledge-authoring",
        ),
        handoff=("briefing",),
        triggers=(
            "record", "archive", "decision", "goal", "attach", "note",
            "记录", "归档", "决策", "目标", "笔记",
        ),
    ),
)


_BY_ID: dict[str, BotSpec] = {bot.id: bot for bot in BOTS}


def _validate_roster() -> None:
    """Fail at import if the roster contradicts the capability registry.

    A bot naming a capability that does not exist would silently resolve to a
    smaller set, which looks like a working bot with a missing tool. A handoff
    naming a bot that does not exist would tell the model to call for an
    operator nobody can select.
    """
    known = capability_ids()
    for bot in BOTS:
        unknown = sorted(set(bot.capabilities) - known)
        if unknown:
            raise ValueError(f"bot {bot.id} declares unknown capabilities: {unknown}")
        if not bot.capabilities:
            raise ValueError(f"bot {bot.id} declares no capabilities")
        missing = sorted(set(bot.handoff) - set(_BY_ID))
        if missing:
            raise ValueError(f"bot {bot.id} hands off to unknown bots: {missing}")


_validate_roster()


def all_bots() -> list[BotSpec]:
    return sorted(BOTS, key=lambda bot: (bot.phase, bot.id))


def get(bot_id: str) -> BotSpec | None:
    return _BY_ID.get(bot_id)


def bot_ids() -> set[str]:
    return set(_BY_ID)


def require(bot_id: str) -> BotSpec:
    bot = _BY_ID.get(bot_id)
    if bot is None:
        raise DomainError(
            "copilot_bot_not_found",
            f"Unknown Copilot bot: {bot_id}",
            status_code=404,
        )
    return bot


def capabilities_for_bot(bot_id: str, enabled_capabilities: set[str]) -> set[str]:
    """The capabilities in force for a run or turn this bot owns.

    Intersection, never union: this is the whole of the narrowing law. An empty
    result is a real answer - it means the project has enabled none of what this
    bot needs - and the caller reports that rather than falling back to a wider
    set, because a silent fallback is how a narrowing hint becomes a widening
    one.
    """
    return set(require(bot_id).capabilities) & set(enabled_capabilities)


def narrow(
    enabled_capabilities: set[str],
    *,
    skill_hint: str | None = None,
    bot_hint: str | None = None,
) -> set[str]:
    """The capabilities in force for one turn, given whatever hints arrived.

    Every path through this function returns a subset of `enabled_capabilities`.
    That is the invariant worth stating out loud, because the two ways to get it
    wrong both end in a wider turn than the project authorised:

    * an unrecognised bot id falling back to the full set - so an unknown bot
      returns nothing at all, and the caller reports a turn with no tools;
    * two hints being merged - so a request carrying both is denied here as well
      as rejected at the API, since this function is also reached by a task
      replayed from a context row written before that rule existed.
    """
    if bot_hint and skill_hint:
        return set()
    if bot_hint:
        bot = _BY_ID.get(bot_hint)
        return set(bot.capabilities) & set(enabled_capabilities) if bot else set()
    return capabilities_for_turn(enabled_capabilities, skill_hint)
