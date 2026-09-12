"""Which stages a person has to release, and why - declared per stage, not per campaign.

`autonomy` is a campaign-level dial with two positions. That granularity is the problem
the literature on this names directly: a supervised campaign either asks about everything,
in which case the reviewer starts approving without reading, or it asks about nothing.
Neither is oversight. What decides whether a step needs a person is not a dial somebody
set once; it is what the step does.

Two properties decide it, and they are the ones a human can actually answer about:

* **Is it reversible?** A draft can be deleted. An expressed construct cannot be
  un-expressed, and a submitted job has spent its slot whatever happens next.
* **Is it a value question or an empirical one?** How deep an MSA search runs is empirical
  and the agent is probably better at it. Whether to commit budget, or whether material
  goes to the bench, is neither - those belong to whoever carries the consequence.

An unrecognised stage key is held. A stage nobody has classified is a stage nobody has
thought about, and guessing "safe" on it is how a gate stops meaning anything.

**What is deliberately not held today.** `compute` is `reversible_draft`: its adapter
creates a `workflow_runs` row that stays a draft, and the platform has no path from an
Autopilot stage to a submission. Holding it now would stop a step that spends nothing and
teach people to click through the hold before it ever guards anything. The tier is
declared so that the day a stage submits, changing one word here is what gates it - rather
than someone having to notice that the question arose.
"""

from __future__ import annotations

#: A stage's risk tier. `held` is a property of the tier, not a separate switch, so a new
#: stage cannot be added at a dangerous tier and quietly left ungated.
TIERS: dict[str, bool] = {
    # Reads, plans and writes drafts. Cheap, and undone by deleting a row.
    "reversible_draft": False,
    # Commits budget or submits work to a queue. The slot is spent when it runs.
    "spends_budget": True,
    # Touches physical material or authorises someone to. Nothing undoes it.
    "irreversible": True,
}

#: stage_key -> tier. Lowercased on lookup; unknown keys fall through to `held`.
STAGE_TIERS: dict[str, str] = {
    "research": "reversible_draft",
    "plan": "reversible_draft",
    "design": "reversible_draft",
    "compute": "reversible_draft",
    "collect": "reversible_draft",
    "review": "reversible_draft",
    "report": "reversible_draft",
    # No adapter exists for these yet, and that is exactly why they are declared now: the
    # gate has to predate the capability, or the first wet stage ships ungated.
    "submit": "spends_budget",
    "wetlab": "irreversible",
    "bench": "irreversible",
    "express": "irreversible",
    "assay": "irreversible",
    "order": "irreversible",
}

#: What an unclassified stage gets. Deny-first, like the project's other fences.
UNKNOWN_TIER = "irreversible"


def tier_for(stage_key: str) -> str:
    return STAGE_TIERS.get(str(stage_key).strip().lower(), UNKNOWN_TIER)


def is_held(stage_key: str) -> bool:
    """Does a person have to release this stage before it may act?"""
    return TIERS[tier_for(stage_key)]


def explain(stage_key: str) -> str:
    """One line for the ledger and the UI, so a hold is not a mystery."""
    tier = tier_for(stage_key)
    if tier == "irreversible":
        known = str(stage_key).strip().lower() in STAGE_TIERS
        if not known:
            return (
                f"stage {stage_key!r} is not a classified stage, so it is held: an "
                "unclassified stage is one nobody has decided the risk of"
            )
        return f"stage {stage_key!r} touches physical material; nothing undoes it"
    if tier == "spends_budget":
        return f"stage {stage_key!r} commits budget or submits work; the slot is spent when it runs"
    return f"stage {stage_key!r} produces a draft and is undone by deleting it"
