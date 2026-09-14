"""Reading AF3's confidences, on the output shape this repository already validates.

`scripts/validate_qm_acceptance_outputs.py` describes what a real run writes:
one summary at the job root and one per ``seed-N_sample-M`` directory, beside
the model and a fuller confidences file. These tests encode the three ways a
parser for that shape goes wrong quietly:

* averaging the seeds, which destroys the only evidence that a prediction is
  unstable - the spread between seeds is the informative part;
* counting the root summary as well as the per-seed ones, so one prediction is
  recorded twice and every downstream average is biased;
* recording a model's opinion of somebody else's design as if it were the
  design model's own confidence.
"""

from __future__ import annotations

import json
import math
import uuid

from backend_v2.app.compute.parsers import get_parser
from backend_v2.app.compute.parsers.base import ParseContext

METHOD = "alphafold3"


def _summary(iptm: float, ptm: float, **extra: object) -> bytes:
    payload = {"iptm": iptm, "ptm": ptm, "ranking_score": round(iptm * 0.9, 3), **extra}
    return json.dumps(payload).encode()


def _context(files: dict[str, bytes]) -> ParseContext:
    outputs = [{"filename": name, "object_key": f"k/{name}"} for name in files]
    keyed = {f"k/{name}": data for name, data in files.items()}
    return ParseContext(
        job_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        attempt_number=1,
        outputs=outputs,
        parameters={},
        read_bytes=lambda key: keyed[key],
    )


def _parse(files: dict[str, bytes]):
    return get_parser(METHOD)(_context(files))


SEEDED = {
    "pd1_binder/seed-1_sample-0/pd1_binder_summary_confidences.json": _summary(0.82, 0.77),
    "pd1_binder/seed-2_sample-0/pd1_binder_summary_confidences.json": _summary(0.41, 0.70),
    "pd1_binder/pd1_binder_summary_confidences.json": _summary(0.82, 0.77),
    "pd1_binder/seed-1_sample-0/pd1_binder_model.cif": b"data_x\n_atom_site.id\n1\n",
}


def test_the_parser_is_reachable_by_name() -> None:
    """An unregistered module leaves the plugin silently on the default parser."""
    from backend_v2.app.compute.parsers import available_parsers

    assert METHOD in available_parsers()


def test_every_seed_is_its_own_metric_row() -> None:
    """The spread between seeds is the finding; an average would erase it."""
    parsed = _parse(SEEDED)

    iptm = sorted(
        metric.value for metric in parsed.candidates[0].metrics if metric.key == "iptm"
    )
    assert iptm == [0.41, 0.82]
    variants = {metric.model_variant for metric in parsed.candidates[0].metrics}
    assert variants == {"seed-1_sample-0", "seed-2_sample-0"}


def test_the_root_summary_is_not_counted_beside_its_own_seeds() -> None:
    """AF3 copies the best sample to the job root; counting both doubles it."""
    parsed = _parse(SEEDED)

    assert len([m for m in parsed.candidates[0].metrics if m.key == "iptm"]) == 2


def test_a_run_without_seed_directories_still_scores() -> None:
    parsed = _parse({"lone/lone_summary_confidences.json": _summary(0.66, 0.60)})

    assert [m.value for m in parsed.candidates[0].metrics if m.key == "iptm"] == [0.66]
    assert parsed.candidates[0].candidate_key == "lone"


def test_the_candidate_is_ranked_on_its_worst_seed() -> None:
    """A complex only one seed likes is not a complex worth carrying forward."""
    parsed = _parse(SEEDED)

    assert parsed.candidates[0].score == 0.41
    assert parsed.candidates[0].scores["iptm"] == 0.82
    assert parsed.candidates[0].scores["iptm_min"] == 0.41


def test_the_prediction_is_recorded_as_another_models_opinion() -> None:
    """AF3 scoring somebody else's design is not that design model's own confidence."""
    parsed = _parse(SEEDED)

    assert {metric.assessor for metric in parsed.candidates[0].metrics} == {"independent_model"}
    assert {metric.evidence_kind for metric in parsed.candidates[0].metrics} == {"predicted"}


def test_a_clash_travels_with_the_numbers_it_changes_the_meaning_of() -> None:
    parsed = _parse(
        {"x/seed-1_sample-0/x_summary_confidences.json": _summary(0.9, 0.8, has_clash=True)}
    )

    assert parsed.candidates[0].metrics[0].context["has_clash"] is True
    assert parsed.candidates[0].metrics[0].context["seed"] == 1


def test_the_predicted_complex_is_linked_to_the_candidate() -> None:
    parsed = _parse(SEEDED)

    assert parsed.candidates[0].complex_output_index is not None
    assert parsed.candidates[0].properties["seed_count"] == 2


def test_values_that_are_not_numbers_are_skipped_rather_than_stored() -> None:
    parsed = _parse(
        {
            "x/x_summary_confidences.json": json.dumps(
                {"iptm": None, "ptm": "high", "ranking_score": float("nan"), "fraction_disordered": 0.1}
            ).encode()
        }
    )

    keys = {metric.key for metric in parsed.candidates[0].metrics}
    assert keys == {"fraction_disordered"}
    assert all(math.isfinite(metric.value) for metric in parsed.candidates[0].metrics)


def test_an_unreadable_summary_warns_instead_of_failing_the_collection() -> None:
    parsed = _parse({"x/x_summary_confidences.json": b"{not json"})

    assert parsed.candidates == []
    assert any("unreadable" in warning for warning in parsed.warnings)


def test_outputs_with_no_summary_say_so() -> None:
    parsed = _parse({"x/x_model.cif": b"data_x\n"})

    assert parsed.candidates == []
    assert any("nothing scored" in warning for warning in parsed.warnings)
