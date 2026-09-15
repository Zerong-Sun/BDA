"""Applying a declared threshold to a recorded metric, and saying why it failed.

The route catalogue has carried acceptance thresholds since it was written -
``{"pae_interaction": "< 15", "binder_plddt": "> 70", ...}`` - as strings that
no code read. A person comparing a design against them did it by eye, which is
both the slowest part of triage and the part where a number gets misread.

The design here is one decision repeated: **a criterion has three outcomes, not
two.**

    pass    - the metric was recorded and satisfies the threshold
    fail    - the metric was recorded and does not
    missing - the metric was never recorded

Folding `missing` into `fail` is the mistake this module exists to avoid. A
design with no Rosetta score has not failed a Rosetta gate; nobody has run
Rosetta on it. A triage that reports those alike tells a person to discard
work that has not been assessed, and it does so most often exactly when a
pipeline stage was skipped - which is when someone most needs to notice.

Thresholds are passed in rather than imported. The catalogue lives in
`copilot/route_catalog.py`, and this is the candidates domain: a domain module
reaching into the copilot's tables would invert the dependency the whole module
layout exists to keep pointing one way.
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: Comparators a threshold may use, longest first so ">=" is not read as ">".
_OPERATORS: tuple[tuple[str, Callable[[float, float], bool]], ...] = (
    ("<=", operator.le),
    (">=", operator.ge),
    ("==", operator.eq),
    ("<", operator.lt),
    (">", operator.gt),
)

_THRESHOLD = re.compile(r"^\s*(?P<op><=|>=|==|<|>)\s*(?P<value>-?\d+(?:\.\d+)?)\s*$")

#: What the catalogue calls a criterion, and the stored metric key that holds
#: it. Written out rather than derived: `binder_plddt` is stored as `plddt`
#: because the platform normalises across methods, and guessing that mapping by
#: stripping a prefix would silently match nothing for anything else.
DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "pae_interaction": ("pae_interaction",),
    "binder_plddt": ("plddt",),
    "binder_ca_rmsd_angstrom": ("binder_ca_rmsd_angstrom", "rmsd", "ca_rmsd"),
    "rosetta_ddg_reu": ("rosetta_ddg_reu", "ddg", "dg"),
    "iptm": ("iptm",),
    "ptm": ("ptm",),
}


class ThresholdError(ValueError):
    """The threshold cannot be read, so nothing may be concluded from it."""


@dataclass(frozen=True)
class Criterion:
    """One declared threshold and how a candidate fared against it."""

    name: str
    threshold: str
    outcome: str
    value: float | None = None
    metric_key: str | None = None
    method: str | None = None
    #: Whether the number came from the model that produced the design. A
    #: design model's own confidence is self-assessment, and a triage that
    #: hides that is laundering it into corroboration.
    assessor: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Verdict:
    tier: str | None
    criteria: list[Criterion] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    missing: int = 0


def parse_threshold(text: str) -> tuple[Callable[[float, float], bool], float, str]:
    """`"< 15"` -> (lt, 15.0, "<"). Anything else is refused.

    Refused rather than skipped: a threshold nobody can parse is a gate nobody
    is applying, and silently dropping it would report a tier as met when one
    of its conditions was never checked.
    """
    match = _THRESHOLD.match(str(text))
    if not match:
        raise ThresholdError(
            f"{text!r} is not a threshold. Write a comparison such as '< 15' or '>= 0.8'."
        )
    symbol = match.group("op")
    compare = dict(_OPERATORS)[symbol]
    return compare, float(match.group("value")), symbol


def _best(values: list[dict[str, Any]], compare: Callable[[float, float], bool], limit: float) -> dict[str, Any] | None:
    """The recorded value most favourable to the candidate.

    A design folded with five seeds has five ipTMs. Picking the best is a
    choice, and it is the charitable one; the seed spread is preserved in the
    metric rows themselves, and `analyse` surfaces it. What this must not do is
    pick silently *and* hide which row it used - so the chosen row's method and
    assessor travel into the criterion.
    """
    passing = [item for item in values if compare(float(item["value"]), limit)]
    pool = passing or values
    if not pool:
        return None
    # Favourable means "furthest inside the threshold": smallest for a <
    # comparison, largest for a >.
    reverse = compare in (operator.gt, operator.ge)
    return sorted(pool, key=lambda item: float(item["value"]), reverse=reverse)[0]


def evaluate(
    metrics: list[dict[str, Any]],
    thresholds: dict[str, str],
    *,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> list[Criterion]:
    """Each declared threshold against the metrics actually recorded.

    `metrics` are plain dicts - `{"key", "value", "method", "assessor"}` - so
    this stays testable without a database and callable from anything that can
    produce those four fields.
    """
    lookup = aliases or DEFAULT_ALIASES
    by_key: dict[str, list[dict[str, Any]]] = {}
    for metric in metrics:
        by_key.setdefault(str(metric["key"]), []).append(metric)

    criteria: list[Criterion] = []
    for name, threshold in thresholds.items():
        compare, limit, symbol = parse_threshold(threshold)
        candidates_keys = lookup.get(name, (name,))
        recorded = [item for key in candidates_keys for item in by_key.get(key, [])]
        if not recorded:
            criteria.append(
                Criterion(
                    name=name,
                    threshold=threshold,
                    outcome="missing",
                    note=(
                        f"No {' or '.join(candidates_keys)} recorded for this candidate. "
                        "Not a failure: nothing has measured it."
                    ),
                )
            )
            continue
        chosen = _best(recorded, compare, limit)
        assert chosen is not None  # `recorded` is non-empty
        value = float(chosen["value"])
        satisfied = compare(value, limit)
        criteria.append(
            Criterion(
                name=name,
                threshold=threshold,
                outcome="pass" if satisfied else "fail",
                value=value,
                metric_key=str(chosen.get("key")),
                method=str(chosen.get("method") or "") or None,
                assessor=str(chosen.get("assessor") or "") or None,
                note="" if satisfied else f"{value:g} is not {symbol} {limit:g}",
            )
        )
    return criteria


def triage(
    metrics: list[dict[str, Any]],
    tiers: dict[str, dict[str, str]],
    *,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> Verdict:
    """The best tier whose every criterion passes, and the full detail.

    Tiers are evaluated in the order given, best first, and a tier is reached
    only when **every** criterion passes - a missing measurement blocks it, for
    the reason in the module docstring. The returned criteria are those of the
    tier that was reached, or of the last (least demanding) tier when none was,
    because that is the list a person needs in order to know what to run next.
    """
    if not tiers:
        return Verdict(tier=None)
    evaluated = {
        name: evaluate(metrics, thresholds, aliases=aliases)
        for name, thresholds in tiers.items()
    }
    for name, criteria in evaluated.items():
        if criteria and all(item.outcome == "pass" for item in criteria):
            return Verdict(
                tier=name,
                criteria=criteria,
                passed=len(criteria),
                failed=0,
                missing=0,
            )
    fallback_name = list(tiers)[-1]
    criteria = evaluated[fallback_name]
    return Verdict(
        tier=None,
        criteria=criteria,
        passed=sum(1 for item in criteria if item.outcome == "pass"),
        failed=sum(1 for item in criteria if item.outcome == "fail"),
        missing=sum(1 for item in criteria if item.outcome == "missing"),
    )
