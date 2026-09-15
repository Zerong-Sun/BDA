"""What the public record says about whether a target can be drugged.

"成药性" is usually asked for as one number - a probability that a target, or
a molecule against it, becomes a drug. No calibrated dataset behind this
platform supports such a number, and a percentage nobody can validate is read
as certainty it does not have. So this module reports the evidence a person
would assemble by hand, each piece from a named source, and states what is
missing instead of folding it into a score:

* **Tractability** from Open Targets, per modality - small molecule (SM),
  antibody (AB), PROTAC (PR) and other clinical (OC) - with the specific
  evidence labels that were true ("Approved Drug", "Structure with Ligand"...),
  because "antibody-tractable" on the strength of an approved drug and on the
  strength of a signal-peptide prediction are different claims.
* **Drugs and clinical candidates** on the target and the furthest stage each
  has reached.
* **Safety liabilities** recorded against the target. None recorded means none
  *recorded in this source*; the report says so rather than calling it safe.
* **Clinical-trial activity** by phase from ClinicalTrials.gov, as a measure of
  how contested the space is.

Every function here is pure; retrieval and its audit trail live in the task.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

#: Open Targets modality codes, named for the reader.
MODALITIES: dict[str, str] = {
    "SM": "small molecule",
    "AB": "antibody",
    "PR": "PROTAC",
    "OC": "other clinical modality",
}

#: Furthest-first. Open Targets returns `maxClinicalStage` as free text, so a
#: value not listed here is reported as unranked rather than dropped or guessed.
STAGE_ORDER: tuple[str, ...] = (
    "APPROVAL",
    "PHASE_4",
    "PHASE_3",
    "PHASE_2_3",
    "PHASE_2",
    "PHASE_1_2",
    "PHASE_1",
    "EARLY_PHASE_1",
    "PRECLINICAL",
)

#: ClinicalTrials.gov phase values the task counts, in order.
TRIAL_PHASES: tuple[str, ...] = ("EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4")

LIMITS: tuple[str, ...] = (
    "No druggability probability is given. No calibrated dataset supports one, and a "
    "number nobody can validate would be read as certainty.",
    "Tractability describes the target, not any particular molecule designed against it.",
    "Safety liabilities list what Open Targets has recorded. An empty list means none "
    "recorded in that source, not that the target is safe.",
    "Trial counts are registrations matching a search term. They include terminated and "
    "unknown-status studies and can count one programme several times.",
    "Market size, pricing and sales are not assessed: no auditable source is connected.",
)


class DruggabilityInputError(ValueError):
    """The payload is not shaped the way the source documents it."""


def ensembl_from_uniprot(entry: Mapping[str, Any]) -> str | None:
    """The Open Targets target id UniProt itself cross-references, if any.

    Taken from UniProt's own cross-reference rather than from a name search:
    resolving an identifier by guessing from a gene name is exactly the move
    the researcher charter forbids, and a paralogue with a similar name would
    produce a confident report about the wrong protein.
    """
    for reference in entry.get("uniProtKBCrossReferences") or []:
        if not isinstance(reference, Mapping):
            continue
        if reference.get("database") == "OpenTargets" and str(reference.get("id") or "").startswith("ENSG"):
            return str(reference["id"])
    return None


def _stage_rank(stage: str | None) -> int:
    try:
        return STAGE_ORDER.index(str(stage or "").upper())
    except ValueError:
        return len(STAGE_ORDER)


def tractability(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per modality: whether any evidence bucket is true, and which ones are.

    A modality with no true bucket is still listed, as not supported: leaving
    it out would make "not assessed" and "assessed and negative" look alike.
    """
    by_modality: dict[str, list[str]] = {code: [] for code in MODALITIES}
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        code = str(row.get("modality") or "").upper()
        if not code:
            continue
        seen.add(code)
        by_modality.setdefault(code, [])
        if row.get("value") is True and row.get("label"):
            by_modality[code].append(str(row["label"]))
    return [
        {
            "modality": code,
            "name": MODALITIES.get(code, code),
            "assessed": code in seen,
            "supported": bool(labels),
            "evidence": sorted(set(labels)),
        }
        for code, labels in by_modality.items()
    ]


def clinical_candidates(payload: Mapping[str, Any] | None, *, top: int = 15) -> dict[str, Any]:
    """Drugs on the target, furthest stage first, with the stage counts."""
    block = payload or {}
    rows = [row for row in (block.get("rows") or []) if isinstance(row, Mapping)]
    candidates: list[dict[str, Any]] = []
    for row in rows:
        drug = row.get("drug") or {}
        candidates.append(
            {
                "drug_id": drug.get("id"),
                "name": drug.get("name"),
                "max_stage": row.get("maxClinicalStage"),
                "stage_ranked": _stage_rank(row.get("maxClinicalStage")) < len(STAGE_ORDER),
            }
        )
    candidates.sort(key=lambda item: (_stage_rank(item["max_stage"]), str(item["name"] or "")))
    stages = Counter(str(item["max_stage"] or "UNKNOWN") for item in candidates)
    return {
        "reported_count": block.get("count"),
        "listed": len(candidates),
        "approved": sum(1 for item in candidates if str(item["max_stage"]).upper() == "APPROVAL"),
        "by_stage": dict(sorted(stages.items(), key=lambda pair: (_stage_rank(pair[0]), pair[0]))),
        "furthest": candidates[:top],
    }


def safety_liabilities(rows: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    items = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        items.append(
            {
                "event": row.get("event"),
                "datasource": row.get("datasource"),
                "effects": [
                    effect.get("direction")
                    for effect in (row.get("effects") or [])
                    if isinstance(effect, Mapping) and effect.get("direction")
                ],
            }
        )
    return {
        "recorded": len(items),
        "items": items,
        # Stated in the payload, not left to the reader: an empty list is the
        # single easiest thing in this report to over-read.
        "interpretation": (
            "None recorded in Open Targets. This is not evidence that the target is safe."
            if not items
            else "Recorded liabilities are listed with their source; severity is not ranked here."
        ),
    }


def trial_activity(counts: Mapping[str, int | None], *, query: str) -> dict[str, Any]:
    """Registered studies by phase for a search term, with the term stated."""
    phases = {phase: counts.get(phase) for phase in TRIAL_PHASES}
    known = [value for value in phases.values() if isinstance(value, int)]
    return {
        "query": query,
        "by_phase": phases,
        "total_matching": counts.get("ALL"),
        # A phase whose count could not be retrieved is None, not zero: the two
        # mean opposite things about how crowded a space is.
        "phases_unavailable": [phase for phase, value in phases.items() if value is None],
        "late_stage": sum(value for key, value in phases.items() if key in {"PHASE3", "PHASE4"} and isinstance(value, int))
        if known
        else None,
    }


def assessment(
    *,
    target: Mapping[str, Any],
    ensembl_id: str | None,
    open_targets: Mapping[str, Any] | None,
    trials: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """The report, with every gap named where it would otherwise be a silent zero."""
    gaps: list[str] = []
    if not ensembl_id:
        gaps.append(
            "UniProt has no Open Targets cross-reference for this accession, so tractability, "
            "clinical candidates and safety liabilities were not retrieved."
        )
    ot_target = (open_targets or {}).get("target") if open_targets else None
    if ensembl_id and not ot_target:
        gaps.append("Open Targets returned no record for the mapped target id.")
    if trials is None:
        gaps.append("ClinicalTrials.gov activity was not retrieved.")
    elif trials.get("phases_unavailable"):
        gaps.append(f"Trial counts unavailable for: {', '.join(trials['phases_unavailable'])}.")

    report: dict[str, Any] = {
        "target": dict(target),
        "ensembl_id": ensembl_id,
        "tractability": tractability((ot_target or {}).get("tractability") or []) if ot_target else None,
        "clinical_candidates": (
            clinical_candidates((ot_target or {}).get("drugAndClinicalCandidates")) if ot_target else None
        ),
        "safety_liabilities": safety_liabilities((ot_target or {}).get("safetyLiabilities")) if ot_target else None,
        "trial_activity": trials,
        "gaps": gaps,
        "limits": list(LIMITS),
    }
    if not isinstance(report["target"], dict):
        raise DruggabilityInputError("target must be a mapping")
    return report
