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

A bot also declares a `stance`, which is the axis the first version of this
roster was missing. Capabilities say what an operator may touch; stance says
what it is *for*, and therefore what it may never do with the tools it holds.
`_validate_roster` makes that mechanical rather than a line in a charter,
because a refusal nothing checks is decoration.

Handoffs are still advisory in the sense that matters: the platform does not
switch bots on its own, because a bot that could re-select itself with a wider
set would defeat the narrowing law. What changed is that a handover now leaves
something behind - see `handoffs.py` - so the next operator reads what the last
one claimed rather than being told about it in prose, and a reviewer reads the
same rows. The one exception to "the client selects" is a `direct` bot, which
may open a child run owned by a different operator; that widens nothing,
because the child resolves the *target* bot's capabilities against the project,
never the director's.

`docs/COPILOT_BOT_ROSTER.md` is the prose half of this file - the chain, the
charters and the skill/MCP inventory. Adding or retiring a bot here means
editing that document in the same change; nothing checks it mechanically,
because a gate that parses prose goes red on a reformat and teaches people to
ignore red.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.problem import DomainError
from .capabilities import COPILOT_CAPABILITIES, capabilities_for_turn, capability_ids

#: What an operator is *for*, orthogonal to what it may touch.
#:
#: Capabilities answer "which tools"; stance answers "what are you forbidden to
#: do with the tools you hold". The roster shipped without this axis and was
#: therefore a split of functions in the vocabulary of a split of
#: responsibilities: nine operators, no relationship between any two of them.
#:
#:   produce - does the work of one phase and hands it on
#:   review  - judges another operator's output and may not repair it
#:   direct  - decides who works next and may not do the work
#:
#: `_validate_roster` makes each of these mechanical. A reviewer that can fix
#: what it found is not a reviewer - it is a second producer, and nobody checks
#: the repair; a director that can do the work will do the work, and the chain
#: quietly collapses back to one operator.
STANCES = ("produce", "review", "direct")

#: Powers that belong to exactly one stance. Declared as a mapping rather than
#: checked inline so that adding a capability to the wrong kind of operator
#: fails with the reason rather than with a boolean.
_STANCE_ONLY = {
    "chain-orchestration": "direct",
    "review-audit": "review",
}

#: Write capabilities that change no research record, so holding one does not
#: make an operator a producer. Only the handover channel qualifies: it writes
#: the copilot's own transcript, which is the same thing a chat message already
#: does every turn. Anything else added here would be a hole in the stance rule,
#: so the list is short on purpose and each member's tools declare
#: `intent="internal"` in the registry to say the same thing from the other side.
_INTERNAL_WRITE_CAPABILITIES = frozenset({"chain-messaging"})


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
    #: One of `STANCES`. Grants nothing either: it only makes certain capability
    #: combinations illegal to declare, so it can subtract from the roster and
    #: never add to a turn.
    stance: str
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
    #: For a `review` bot: whose output it judges. This is the "who checks me"
    #: half of a responsibility, and it is declared on the reviewer rather than
    #: on the producer so that adding a reviewer cannot silently change what a
    #: producer is allowed to do. Empty for every other stance.
    reviews: tuple[str, ...] = ()
    #: For a `direct` bot: the operators it may delegate to. Bounded by
    #: declaration rather than by "any bot in the roster", so the reach of a
    #: director is reviewable in the same place its charter is.
    directs: tuple[str, ...] = ()
    #: Bilingual routing hints for a client that wants to suggest a bot. Never
    #: consulted server-side when resolving capabilities.
    triggers: tuple[str, ...] = field(default_factory=tuple)


#: Written in chain order. The chain is a loop: `medic` returns to `planner`,
#: `archivist` returns to `briefing`.
BOTS: tuple[BotSpec, ...] = (
    BotSpec(
        id="conductor",
        title="Conductor",
        title_zh="总调度",
        phase=-1,
        stance="direct",
        summary="Decide which operator works next, delegate to it, and say when the chain stops.",
        charter=(
            "You route work; you do not do it. Read the chain's handovers and the "
            "project's state, name the operator whose accountability the next step "
            "falls under, and delegate to it with an instruction that says what to "
            "produce and what would make the step finished. You hold no tool that "
            "changes the research record, and delegating is not a way to reach one: "
            "a delegated operator runs under its own charter and its own "
            "capabilities, and refuses what it would refuse from a person. You "
            "cannot authorise a write. If a step needs one, say which operator owns "
            "it and what the user would have to ask for, and stop - an instruction "
            "you wrote is not the user asking. Delegate one step at a time and read "
            "what came back before choosing the next: a plan made for five steps at "
            "once is a plan that ignores the first result. When the operators "
            "disagree, send the claim to auditor rather than picking the answer you "
            "prefer. Say explicitly when the chain is finished or blocked; a "
            "director that never stops is a loop."
        ),
        capabilities=(
            "project-read",
            "research-read",
            "chain-orchestration",
            "chain-messaging",
        ),
        handoff=("auditor",),
        directs=(
            "briefing",
            "librarian",
            "scout",
            "structuralist",
            "planner",
            "runner",
            "medic",
            "analyst",
            "archivist",
        ),
        triggers=(
            "orchestrate", "coordinate", "who should", "next operator", "delegate",
            "调度", "统筹", "安排", "该谁", "全链条",
        ),
    ),
    BotSpec(
        id="briefing",
        title="Briefing",
        title_zh="选题起草",
        phase=0,
        stance="produce",
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
        capabilities=("project-read", "research-read", "knowledge-authoring", "chain-messaging"),
        handoff=("librarian", "scout"),
        triggers=("brief", "research question", "proposal", "选题", "立项", "研究问题", "写提案"),
    ),
    BotSpec(
        id="librarian",
        title="Librarian",
        title_zh="文献整理",
        phase=1,
        stance="produce",
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
        capabilities=("research-read", "literature-search", "chain-messaging"),
        handoff=("briefing", "scout"),
        triggers=(
            # "review" alone belongs to `auditor`: two bots claiming one token
            # is a tie, and a tie routes to nobody - so the word that names this
            # operator's artefact has to be the artefact, not the act.
            "paper", "literature", "citation", "PubMed", "Europe PMC",
            "review article", "literature review", "reference",
            "论文", "文献", "引用", "综述", "参考文献",
        ),
    ),
    BotSpec(
        id="scout",
        title="Scout",
        title_zh="靶点情报",
        phase=2,
        stance="produce",
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
            "chain-messaging",
        ),
        handoff=("structuralist", "planner"),
        triggers=(
            "target", "UniProt", "gap", "gaps", "intelligence", "ortholog",
            "target intelligence", "target profile",
            "靶点", "情报", "缺口", "补齐", "修复", "靶点情报", "靶点档案",
        ),
    ),
    BotSpec(
        id="structuralist",
        title="Structuralist",
        title_zh="结构与残基",
        phase=3,
        stance="produce",
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
        capabilities=("project-read", "structure-analysis", "chain-messaging"),
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
        stance="produce",
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
            "chain-messaging",
        ),
        handoff=("runner",),
        triggers=(
            "route", "workflow", "plan", "draft", "pipeline", "LSF", "cluster",
            "compute draft", "cluster job", "threshold",
            # Named tools route here rather than to `structuralist`: a message
            # naming one is almost always about running it, and reading what it
            # produced names a structure instead.
            "AlphaFold", "Rosetta", "RFdiffusion",
            "路线", "工作流", "规划", "草稿", "集群", "阈值",
            "计算草稿", "集群作业", "任务草稿",
        ),
    ),
    BotSpec(
        id="runner",
        title="Runner",
        title_zh="步骤推进",
        phase=5,
        stance="produce",
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
        capabilities=(
            "project-read",
            "workflow-planning",
            "agent-orchestration",
            "chain-messaging",
        ),
        handoff=("medic", "analyst"),
        triggers=(
            # Not bare "run": it is the verb in nearly every imperative a user
            # types ("run the search", "run the analysis"), so it ties with
            # whichever operator the sentence actually named and routes to
            # neither. A trigger has to name this operator's subject - a run
            # already in flight - rather than the act of starting one.
            "advance", "next step", "wait", "monitor",
            "run status", "still running", "is it done",
            "推进", "下一步", "等待", "执行",
        ),
    ),
    BotSpec(
        id="medic",
        title="Medic",
        title_zh="故障诊断",
        phase=6,
        stance="produce",
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
        capabilities=("project-read", "failure-diagnosis", "chain-messaging"),
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
        stance="produce",
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
            "chain-messaging",
        ),
        handoff=("archivist", "structuralist"),
        triggers=(
            "result", "interpret", "BLI", "SEC", "assay", "KD", "candidate",
            "experiment",
            "结果", "解读", "实验", "测定", "候选",
        ),
    ),
    BotSpec(
        id="archivist",
        title="Archivist",
        title_zh="记录归档",
        phase=8,
        stance="produce",
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
            "chain-messaging",
        ),
        handoff=("briefing",),
        triggers=(
            "record", "archive", "decision", "goal", "attach", "note",
            "knowledge", "save this",
            "记录", "归档", "决策", "目标", "笔记", "知识", "保存",
        ),
    ),
    BotSpec(
        id="steward",
        title="Steward",
        title_zh="资源守门",
        phase=4,
        stance="review",
        summary="Check a compute draft's declared resources against what the job can actually use.",
        charter=(
            "You review resource declarations before a human confirms a draft. "
            "Read the draft and compare four things that must agree: the slot "
            "count, the per-host span, the thread or worker count the tool will "
            "actually start, and the GPU declaration. A job holding cores it "
            "cannot use is a violation here, not a rounding error, and the queue "
            "can merge its own GPU request into a job whose directives ask for "
            "none - so a script that says it needs no GPU has to prove it at run "
            "time rather than by saying so. Report each disagreement with the two "
            "numbers that disagree. You do not edit the draft and you do not "
            "confirm it: state the finding and hand it back to planner, whose "
            "decision the route is. When the declaration is sound, say so plainly "
            "- an approval that is never given makes the review a formality."
        ),
        capabilities=("project-read", "review-audit", "chain-messaging"),
        handoff=("planner",),
        reviews=("planner",),
        triggers=(
            "cores", "cpus", "ptile", "slots", "gpu", "resources", "utilisation",
            "核数", "资源", "利用率", "占用",
        ),
    ),
    BotSpec(
        id="auditor",
        title="Auditor",
        title_zh="复核",
        phase=9,
        stance="review",
        summary="Judge an operator's claims against the evidence it produced and the charter it works under.",
        charter=(
            "You judge claims; you never repair them. Take the handover, read "
            "what the operator actually called and what came back, and rule on "
            "each claim separately: supported when the evidence states it, "
            "unsupported when nothing backs it, contradicted when the evidence "
            "says otherwise, and outside_charter when the operator did something "
            "its own charter forbids. Rule on what was run, not on what the "
            "operator said it ran - the summary is the thing under review. A "
            "claim with no evidence reference is unsupported, and saying so is "
            "the finding rather than a gap in your reading. When a note has no "
            "run behind it there is no transcript to check, so report it as "
            "unreviewable rather than as clean. You hold no write and no fix: "
            "hand every finding back to the operator that made the claim, and "
            "say what would settle it. Say when you find nothing wrong - a "
            "reviewer whose verdicts are always adverse stops being read."
        ),
        capabilities=("project-read", "research-read", "review-audit", "chain-messaging"),
        handoff=("conductor",),
        reviews=(
            "briefing",
            "librarian",
            "scout",
            "structuralist",
            "planner",
            "runner",
            "medic",
            "analyst",
            "archivist",
        ),
        triggers=(
            "review", "verify", "check", "audit", "verdict", "evidence",
            "复核", "审查", "核对", "证据", "验证",
        ),
    ),
)


_BY_ID: dict[str, BotSpec] = {bot.id: bot for bot in BOTS}


def _writes_of(capabilities: tuple[str, ...]) -> set[str]:
    """Capabilities among these that grant at least one write tool.

    Derived from the capability rows rather than listed here, so a capability
    that gains a write tool later immediately makes any reviewer holding it a
    roster error, instead of quietly turning a reviewer into a producer.
    """
    granting = {
        str(item["id"])
        for item in COPILOT_CAPABILITIES
        if str(item.get("execution_mode", "read")) != "read"
    }
    return set(capabilities) & granting


def _validate_roster() -> None:
    """Fail at import if the roster contradicts itself or the capability rows.

    Two kinds of error, and both are silent at run time if they are not caught
    here. A bot naming a capability that does not exist resolves to a smaller
    set, which looks like a working bot with a missing tool. A bot whose stance
    and capabilities disagree looks like a working bot that is doing someone
    else's job: a reviewer able to repair what it found leaves the repair
    unchecked, and a director able to do the work does the work.
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
        if bot.stance not in STANCES:
            raise ValueError(f"bot {bot.id} declares unknown stance: {bot.stance!r}")

        writes = _writes_of(bot.capabilities) - _INTERNAL_WRITE_CAPABILITIES
        if bot.stance == "review" and writes:
            raise ValueError(
                f"review bot {bot.id} declares write capabilities {sorted(writes)}; "
                "a reviewer that can repair what it found is a second producer "
                "and nobody checks the repair"
            )
        if bot.stance == "direct" and writes:
            raise ValueError(
                f"direct bot {bot.id} declares write capabilities {sorted(writes)}; "
                "a director that can do the work will do the work instead of routing"
            )

        for capability, stance in _STANCE_ONLY.items():
            if capability in bot.capabilities and bot.stance != stance:
                raise ValueError(
                    f"bot {bot.id} is {bot.stance} and declares {capability}, "
                    f"which belongs to the {stance} stance"
                )

        if bot.reviews and bot.stance != "review":
            raise ValueError(f"bot {bot.id} is {bot.stance} and cannot review other operators")
        if bot.stance == "review" and not bot.reviews:
            raise ValueError(f"review bot {bot.id} names nobody to review")
        if bot.directs and bot.stance != "direct":
            raise ValueError(f"bot {bot.id} is {bot.stance} and cannot direct other operators")
        if bot.stance == "direct" and not bot.directs:
            raise ValueError(f"direct bot {bot.id} names nobody to direct")

        for target in sorted(set(bot.reviews) | set(bot.directs)):
            other = _BY_ID.get(target)
            if other is None:
                raise ValueError(f"bot {bot.id} names unknown operator {target}")
            if other.stance != "produce":
                # Reviewing a reviewer, or directing a director, has no bottom.
                # Accountability has to terminate on someone who produces.
                raise ValueError(
                    f"bot {bot.id} names {target}, which is {other.stance}; "
                    "review and delegation must terminate on a producer"
                )


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


def producers() -> list[BotSpec]:
    """Operators that do the work, as opposed to judging or routing it."""
    return [bot for bot in all_bots() if bot.stance == "produce"]


def reviewers_of(bot_id: str) -> list[BotSpec]:
    """Who judges this operator's output.

    The fourth thing a capability list cannot say, and the reason `reviews` is
    declared on the reviewer: a producer cannot know, and must not be able to
    choose, who checks it.
    """
    return [bot for bot in all_bots() if bot_id in bot.reviews]


def may_direct(director_id: str, target_id: str) -> bool:
    """Whether this director may delegate to this operator.

    Bounded by the roster rather than by "any bot", so a director's reach is
    reviewable in the same place its charter is.
    """
    director = _BY_ID.get(director_id)
    return bool(director and director.stance == "direct" and target_id in director.directs)


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
