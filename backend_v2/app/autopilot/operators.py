"""Which operator is accountable for each stage of a campaign.

`gates.py` answers *may this stage act without a person*. This answers *whose job
is it when it does*. The two are deliberately separate and both are per stage
rather than per campaign, for the same reason: a campaign-level dial is a thing
somebody set once, and what decides who should carry a step is what the step is.

Until now an Autopilot stage had a tier and a resource and no operator. The
roster in `copilot/bots.py` exists to say who is accountable for a phase and
what that operator must refuse, and a campaign is the platform's own name for
running those phases in order - so a stage with no operator was the one place
the chain ran with nobody's charter applying to it.

Mapping a stage to an operator grants nothing. The run a stage opens resolves
`bot.capabilities ∩ project.enabled_skills` like every other run, and it is held
or released by `gates.py` exactly as before. What the mapping adds is a charter,
a set of refusals, and a name in the ledger.

Two stage keys are deliberately absent:

* `submit` and every wet key - those are `spends_budget` or `irreversible`, so a
  person releases them, and the operator that would carry them afterwards is a
  decision for whoever releases, not a default declared here.
* `collect` - collection is the platform moving artifacts, not an operator
  reasoning about them; `analyst` picks up at the next stage.
"""

from __future__ import annotations

from ..copilot import bots

#: stage_key -> roster bot id. Lowercased on lookup. An absent key means the
#: stage has no accountable operator, which is a real state and not a gap: a
#: `review` stage is a person's judgement, and naming a bot for it would be the
#: platform quietly answering a question it was asked to hold open.
STAGE_OPERATORS: dict[str, str] = {
    "research": "librarian",
    "plan": "planner",
    "design": "planner",
    # `planner`, not `runner`, and the difference is the whole reason `gates.py`
    # calls this stage `reversible_draft`: its adapter creates a workflow run
    # that *stays a draft*. Drafting is `planner`'s accountability. `runner`
    # becomes accountable when a person confirms the draft, which is a step
    # outside the campaign's automatic path - naming it here would put an
    # operator's name on work the campaign does not do.
    "compute": "planner",
    "report": "archivist",
}

#: Stage keys that exist and deliberately have no operator, each with why. Kept
#: as data so "unmapped" can be told apart from "nobody has looked at it yet" -
#: the same distinction `gates.UNKNOWN_TIER` draws for risk.
UNSTAFFED: dict[str, str] = {
    "collect": (
        "collection moves artifacts; no operator reasons about them until the "
        "next stage"
    ),
    "review": (
        "a review stage is a person's judgement, and naming an operator for it "
        "would answer a question the campaign was asked to hold open"
    ),
    "submit": (
        "spends budget, so a person releases it; who carries it afterwards is "
        "that person's decision rather than a default"
    ),
    "wetlab": "touches physical material; nothing here is automatic",
    "bench": "touches physical material; nothing here is automatic",
    "express": "touches physical material; nothing here is automatic",
    "assay": "touches physical material; nothing here is automatic",
    "order": "touches physical material; nothing here is automatic",
}


def _validate() -> None:
    """Fail at import if a stage names an operator the roster does not have.

    The roster is code and this is code, so they can be checked against each
    other rather than kept in step by hand. A stage naming a retired bot would
    otherwise produce a campaign that runs with no charter and looks fine.
    """
    known = bots.bot_ids()
    for stage_key, bot_id in STAGE_OPERATORS.items():
        if bot_id not in known:
            raise ValueError(f"stage {stage_key!r} names unknown operator {bot_id!r}")
        spec = bots.require(bot_id)
        if spec.stance != "produce":
            # A reviewer or a director carrying a stage would be doing the work
            # its own stance forbids - the rule `bots._validate_roster` enforces,
            # restated where a second mapping could break it.
            raise ValueError(
                f"stage {stage_key!r} names {bot_id!r}, which is {spec.stance}; "
                "a stage is carried by a producer"
            )
    overlap = set(STAGE_OPERATORS) & set(UNSTAFFED)
    if overlap:
        raise ValueError(f"stage keys both staffed and unstaffed: {sorted(overlap)}")


_validate()


def operator_for(stage_key: str) -> str | None:
    """The operator accountable for this stage, or None."""
    return STAGE_OPERATORS.get(str(stage_key).strip().lower())


def explain(stage_key: str) -> str:
    """One line for the ledger and the UI, so an unstaffed stage is not a mystery."""
    key = str(stage_key).strip().lower()
    bot_id = STAGE_OPERATORS.get(key)
    if bot_id:
        spec = bots.require(bot_id)
        return f"stage {stage_key!r} is carried by {spec.id} ({spec.title_zh}): {spec.summary}"
    reason = UNSTAFFED.get(key)
    if reason:
        return f"stage {stage_key!r} has no operator: {reason}"
    return (
        f"stage {stage_key!r} is not a classified stage, so it has no operator: "
        "an unclassified stage is one nobody has decided the shape of"
    )
