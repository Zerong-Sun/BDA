"""Turn paired-condition metrics into a stored comparison.

A single ipTM number cannot establish selectivity; the interpretable quantity is the
gap between a target condition and a reviewed control. Making that delta a first-class
metric keeps it queryable and traceable instead of leaving a one-off notebook result.

A delta is derived only from metric pairs recorded under the same method and model
variant. Comparing one model's self-assessed target score against another model's
control score would
attribute a modelling disagreement to a chemistry difference.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .models import CandidateMetric
from .repository import CandidateRepository

# Marks both the derived metric_key prefix ("delta_iptm") and lets a later recompute
# recognise and skip its own output rather than trying to diff a delta against itself.
DELTA_PREFIX = "delta_"


@dataclass(frozen=True)
class ConditionDelta:
    metric_key: str
    method: str
    model_variant: str
    condition_a: str
    condition_b: str
    value: float
    unit: str


def compute_condition_deltas(metrics: list[CandidateMetric]) -> list[ConditionDelta]:
    """One delta per (metric_key, method, model_variant) group with exactly two
    distinct, unambiguous conditions.

    More than two conditions, or two rows sharing one condition (e.g. two seeds filed
    under the same label), makes "which pair" a modelling choice rather than something
    to guess at silently, so those groups are skipped rather than picked arbitrarily.
    """
    groups: dict[tuple[str, str, str], dict[str, CandidateMetric]] = {}
    ambiguous: set[tuple[str, str, str]] = set()
    for metric in metrics:
        if not metric.condition or metric.metric_key.startswith(DELTA_PREFIX):
            continue
        key = (metric.metric_key, metric.method, metric.model_variant)
        by_condition = groups.setdefault(key, {})
        if metric.condition in by_condition:
            ambiguous.add(key)
        by_condition[metric.condition] = metric

    deltas: list[ConditionDelta] = []
    for key, by_condition in groups.items():
        if key in ambiguous or len(by_condition) != 2:
            continue
        metric_key, method, model_variant = key
        (condition_a, row_a), (condition_b, row_b) = sorted(by_condition.items())
        if row_a.unit != row_b.unit:
            continue
        deltas.append(
            ConditionDelta(
                metric_key=metric_key,
                method=method,
                model_variant=model_variant,
                condition_a=condition_a,
                condition_b=condition_b,
                value=row_a.value - row_b.value,
                unit=row_a.unit,
            )
        )
    return deltas


def upsert_condition_deltas(session: Session, candidate_id: uuid.UUID) -> list[CandidateMetric]:
    """Recompute and store every pairwise delta this candidate's metrics now support.

    Cheap to call after any metric write: with fewer than two conditions on a group it
    is a no-op, and with them unchanged it overwrites existing delta rows with the same
    values rather than accumulating duplicates (``_record_metrics`` matches on
    candidate/key/method/variant/condition).
    """
    # Deferred: compute/tasks.py calls this after recording a job's metrics, and
    # _record_metrics lives there, so a module-level import would cycle.
    from ..compute.parsers.base import ParsedMetric
    from ..compute.tasks import _record_metrics

    repo = CandidateRepository(session)
    deltas = compute_condition_deltas(repo.metrics_for(candidate_id))
    if not deltas:
        return []
    candidate = repo.get(candidate_id)
    if candidate is None:
        # The metrics were read a moment ago, so this only happens if the candidate was
        # deleted concurrently. Nothing to attach the derived metric to; drop it rather
        # than fail the whole collection for a candidate that no longer exists.
        return []
    parsed = [
        ParsedMetric(
            key=f"{DELTA_PREFIX}{delta.metric_key}",
            value=delta.value,
            method=delta.method,
            model_variant=delta.model_variant,
            evidence_kind="derived",
            assessor="derived",
            condition=f"{delta.condition_a} vs {delta.condition_b}",
            unit=delta.unit,
        )
        for delta in deltas
    ]
    _record_metrics(session, candidate, parsed, job_id=None)
    written_keys = {(m.key, m.method, m.model_variant, m.condition) for m in parsed}
    return [
        row
        for row in repo.metrics_for(candidate_id)
        if (row.metric_key, row.method, row.model_variant, row.condition) in written_keys
    ]
