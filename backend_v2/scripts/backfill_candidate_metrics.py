"""Move numbers out of ``candidates.scores`` into queryable metric rows.

Every candidate written before ``candidate_metrics`` existed carries its results in one
JSON blob: a Rosetta energy, an AlphaFold2 confidence and a ProteinMPNN likelihood all
sit side by side with nothing recording which method produced which. That cannot be
indexed, cannot be filtered on, and cannot be audited.

Which method produced a key is recoverable from the key names, so this backfill restores
method attribution. Which *run* produced it is not - the blob never stored it - so the
job reference is deliberately left empty and the metric records that it was backfilled,
rather than inventing a provenance that would later be read as first-hand.

Idempotent: re-running updates existing rows instead of duplicating them.

    python backend_v2/scripts/backfill_candidate_metrics.py --project-name SweetProtein...
    python backend_v2/scripts/backfill_candidate_metrics.py --all --dry-run
"""

from __future__ import annotations

import argparse
import uuid
from collections import Counter
from dataclasses import dataclass

from backend_v2.app.candidates.models import Candidate, CandidateMetric
from backend_v2.app.core.database import session_scope
from sqlalchemy import select

ROSETTA = "rosetta_score_jd2_beta"
ALPHAFOLD = "alphafold2_superfold"
PROTEINMPNN = "proteinmpnn"

# Rosetta Energy Units. Not a physical energy, and not comparable between score
# functions, which is why the score function is part of the method name.
REU = "REU"
ANGSTROM = "angstrom"


@dataclass(frozen=True)
class MetricSpec:
    metric_key: str
    method: str
    unit: str = ""
    evidence_kind: str = "predicted"


# Score-function terms, kept under Rosetta's own names because that is what a structural
# biologist filters on. `score` and `rosetta_score` are omitted: both restate
# `total_score` (the scorefile prints two columns that differ only by rounding), so
# emitting them would triple-count one number under three filterable names.
_ROSETTA_TERMS = (
    "total_score",
    "dslf_fa13",
    "fa_atr",
    "fa_dun_dev",
    "fa_dun_rot",
    "fa_dun_semi",
    "fa_elec",
    "fa_intra_atr_xover4",
    "fa_intra_elec",
    "fa_intra_rep_xover4",
    "fa_intra_sol_xover4",
    "fa_rep",
    "fa_sol",
    "gen_bonded",
    "hbond_bb_sc",
    "hbond_lr_bb",
    "hbond_sc",
    "hbond_sr_bb",
    "hxl_tors",
    "linear_chainbreak",
    "lk_ball",
    "lk_ball_bridge",
    "lk_ball_bridge_uncpl",
    "lk_ball_iso",
    "omega",
    "overlap_chainbreak",
    "p_aa_pp",
    "pro_close",
    "rama_prepro",
    "ref",
)

MAPPING: dict[str, MetricSpec] = {
    **{term: MetricSpec(term, ROSETTA, REU) for term in _ROSETTA_TERMS},
    # Length-normalised, so it compares designs of different sizes - which the raw total
    # does not.
    "rosetta_score_per_residue": MetricSpec("score_per_residue", ROSETTA, REU),
    "proteinmpnn_score": MetricSpec("mpnn_score", PROTEINMPNN),
    "plddt": MetricSpec("plddt", ALPHAFOLD),
    "ptm": MetricSpec("ptm", ALPHAFOLD),
    "mean_pae": MetricSpec("pae", ALPHAFOLD, ANGSTROM),
    "mean_pae_intra_chain": MetricSpec("pae_intra_chain", ALPHAFOLD, ANGSTROM),
    # Agreement between the prediction and the backbone that was designed. Derived by
    # comparing two structures rather than reported by the model, hence "derived".
    "alphafold_rmsd_to_input": MetricSpec("rmsd_to_design", ALPHAFOLD, ANGSTROM, "derived"),
    "alphafold_summary_rmsd_to_input": MetricSpec(
        "rmsd_to_design_summary", ALPHAFOLD, ANGSTROM, "derived"
    ),
    "alphafold_tmscore_to_input": MetricSpec("tmscore_to_design", ALPHAFOLD, "", "derived"),
}

# Run detail, not results. Carried as context on that method's metrics so the numbers
# stay interpretable without polluting the metric namespace.
CONTEXT_KEYS = {
    "alphafold_recycles": ("recycles", ALPHAFOLD),
    "alphafold_tol": ("tol", ALPHAFOLD),
    "alphafold_elapsed_seconds": ("elapsed_time", ALPHAFOLD),
}

# Restating total_score. See _ROSETTA_TERMS.
REDUNDANT_KEYS = {"score", "rosetta_score"}


def _numeric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if number == number and abs(number) != float("inf") else None


def plan_for(scores: dict) -> tuple[list[tuple[MetricSpec, float, dict]], list[str]]:
    """Metrics to write for one candidate, plus the keys nothing was done with."""
    context_by_method: dict[str, dict] = {}
    for raw_key, (context_name, method) in CONTEXT_KEYS.items():
        if raw_key in scores:
            context_by_method.setdefault(method, {})[context_name] = scores[raw_key]

    planned: list[tuple[MetricSpec, float, dict]] = []
    unmapped: list[str] = []
    for raw_key, raw_value in scores.items():
        if raw_key in CONTEXT_KEYS or raw_key in REDUNDANT_KEYS:
            continue
        spec = MAPPING.get(raw_key)
        if spec is None:
            unmapped.append(raw_key)
            continue
        value = _numeric(raw_value)
        if value is None:
            unmapped.append(raw_key)
            continue
        context = {"backfilled_from": "candidates.scores"}
        context.update(context_by_method.get(spec.method, {}))
        planned.append((spec, value, context))
    return planned, unmapped


def backfill(session, candidates: list[Candidate], dry_run: bool) -> Counter:
    tally: Counter = Counter()
    for candidate in candidates:
        planned, unmapped = plan_for(candidate.scores or {})
        tally["candidates_seen"] += 1
        for key in unmapped:
            tally[f"unmapped:{key}"] += 1
        if not planned:
            continue
        tally["candidates_with_metrics"] += 1
        for spec, value, context in planned:
            tally[f"metric:{spec.method}"] += 1
            if dry_run:
                continue
            existing = session.scalar(
                select(CandidateMetric).where(
                    CandidateMetric.candidate_id == candidate.id,
                    CandidateMetric.metric_key == spec.metric_key,
                    CandidateMetric.method == spec.method,
                    CandidateMetric.model_variant == "",
                )
            )
            if existing is not None:
                existing.value = value
                existing.unit = spec.unit
                existing.evidence_kind = spec.evidence_kind
                existing.context = context
                tally["updated"] += 1
                continue
            session.add(
                CandidateMetric(
                    candidate_id=candidate.id,
                    metric_key=spec.metric_key,
                    value=value,
                    method=spec.method,
                    model_variant="",
                    evidence_kind=spec.evidence_kind,
                    unit=spec.unit,
                    context=context,
                    # The blob never recorded which run produced each number, and a
                    # guess here would be indistinguishable from real provenance.
                    source_job_id=None,
                )
            )
            tally["inserted"] += 1
    return tally


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project-id", type=uuid.UUID)
    group.add_argument("--project-name")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    from backend_v2.app.projects.models import Project

    with session_scope() as session:
        query = select(Candidate)
        if args.project_id:
            query = query.where(Candidate.project_id == args.project_id)
        elif args.project_name:
            project = session.scalar(select(Project).where(Project.name == args.project_name))
            if project is None:
                raise SystemExit(f"no project named {args.project_name!r}")
            query = query.where(Candidate.project_id == project.id)
        candidates = list(session.scalars(query))
        tally = backfill(session, candidates, args.dry_run)
        if args.dry_run:
            session.rollback()

    print("dry run - nothing written" if args.dry_run else "written")
    for key in sorted(tally):
        print(f"  {key}: {tally[key]}")


if __name__ == "__main__":
    main()
