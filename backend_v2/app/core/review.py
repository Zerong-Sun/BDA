"""How much a person may be asked to approve in one act.

`research/schemas.py` discovered this rule and stated it in one place: the decision-tree
proposal caps goals, depth and branches because **a reviewer who cannot read it all stops
reviewing and starts accepting**. That is the only fuse on that path, and it works.

The problem with leaving it there is that the rule is not about decision trees. It is about
every place the platform hands a person a machine-generated batch and one button. Each such
place has to pick a number, and a number picked in isolation is picked by whoever wrote
that endpoint, on the day they wrote it, with no way to see what the others chose.

So the numbers live here, together, with the reason stated once. Adding a single-act
approval means adding a row - which is the point: it forces the question "how many of these
can someone actually read" to be answered rather than skipped.

What this is *not*: a storage limit. `Field(max_length=...)` stops a payload from being
absurd and protects the database. A review budget is smaller and has a different
justification - it is about human attention, and it binds even when the data would store
fine.

**Declared exception.** `research_generations` import (`ResearchDraftV2`: up to 2000 nodes,
5000 edges) is a single-act approval that is *not* covered by a review budget, and that is
a decision rather than an oversight. Two things make it different: the import refuses
unless `validation.valid` is true, and it refuses unless the caller echoes the checksum of
the draft they previewed - so what is approved is pinned, which the tree bootstrap has no
equivalent of. The quantity question there is real but it is attached to a released package
format, and shrinking the limit would reject packages that exist. Recorded here so the next
reader finds a reason instead of an inconsistency.
"""

from __future__ import annotations

#: name -> how many of that thing one approval may carry.
#:
#: Names are `<surface>.<thing>`. Keep them boring; this table is read by people asking
#: "what did we decide a human can review", and a clever name answers a different question.
REVIEW_BUDGETS: dict[str, int] = {
    # A bootstrapped goal tree. 12/12/3 are the numbers `research/schemas.py` chose and
    # they are kept exactly, so moving the rule here changes no behaviour.
    "decision_tree.goals": 12,
    "decision_tree.branches": 12,
    "decision_tree.depth": 3,
    # Autopilot stages. Confirming a campaign is one act that accepts every stage in the
    # frozen spec, and the spec is normalised from a prompt - so nothing but this stops a
    # model proposing forty stages and a person clicking through them. 12 matches the
    # decision tree deliberately: both are "a list a person reads before committing".
    "autopilot.stages": 12,
}


def budget(name: str) -> int:
    """The declared limit, or a loud failure.

    A missing name is a programming error rather than bad input: it means a call site is
    enforcing a budget that was never agreed on.
    """
    try:
        return REVIEW_BUDGETS[name]
    except KeyError:  # pragma: no cover - guards a typo at import time
        raise RuntimeError(f"no review budget declared for {name!r}") from None


def check_review_budget(name: str, count: int, *, unit: str) -> None:
    """Refuse a batch nobody can review. Raises ValueError.

    ValueError rather than DomainError so a Pydantic validator can raise it and get a 422
    with the other field errors; service-layer callers translate it themselves. The message
    says why, because "at most 12" on its own reads as an arbitrary limit and the next
    person to hit it will simply raise it.
    """
    limit = budget(name)
    if count > limit:
        raise ValueError(
            f"at most {limit} {unit} may be approved at once; got {count}. "
            "A reviewer who cannot read the whole list stops reviewing and starts accepting, "
            "so the limit is on what one approval may carry, not on what will fit."
        )
