"""Superposition, on coordinates whose answer is known before the code runs.

`binder_ca_rmsd_angstrom < 1.5` has been a gate in the route catalogue with
nothing able to compute it. These tests are about the three ways a first
implementation of that number is usually wrong:

* it reports the distance between two files instead of the distance after
  fitting them, so moving a model across the box changes the answer;
* it pairs residues by position in the list, so two files of one construct that
  differ by a missing loop get compared residue-to-wrong-residue and produce a
  small, confident, wrong number;
* it reports a TM-score that a reader will compare against a published
  TM-align value, which it is not.

Every fixture below is built from explicit coordinates, so the expected values
come from arithmetic rather than from the implementation.
"""

from __future__ import annotations

import pytest
from backend_v2.app.structures import kernels


def _chain(chain: str, coordinates: list[tuple[int, float, float, float]]) -> str:
    lines = []
    for serial, (resseq, x, y, z) in enumerate(coordinates, start=1):
        lines.append(
            f"ATOM  {serial:>5} CA   ALA {chain}{resseq:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 20.00           C"
        )
    return "\n".join(lines) + "\nEND\n"


#: A short, straight backbone. Any rigid motion of it must superpose perfectly.
STRAIGHT = [(index, float(index) * 3.8, 0.0, 0.0) for index in range(1, 11)]
REFERENCE = _chain("A", STRAIGHT)
TRANSLATED = _chain("B", [(index, x + 25.0, y + 11.0, z - 7.0) for index, x, y, z in STRAIGHT])


def test_a_model_is_fitted_before_the_distance_is_reported() -> None:
    """Moving a copy across the box must not change its RMSD."""
    result = kernels.superpose(REFERENCE, TRANSLATED, reference_chain="A", mobile_chain="B")

    assert result["rmsd_angstrom"] == pytest.approx(0.0, abs=1e-6)
    # The raw distance is reported too, so a reader can see that a fit happened.
    assert result["rmsd_before_superposition_angstrom"] > 25


def test_fitting_lowers_the_error_it_started_from() -> None:
    """One of ten residues moved 3 A.

    The *unfitted* RMSD is exactly sqrt(9/10): nine residues coincide and one
    is 3 A out. The fitted number must be strictly lower, because a
    least-squares fit buys a reduction in the large deviation by spreading a
    little error over the nine - which is the whole reason the two numbers are
    both reported. Asserting sqrt(9/10) for the fitted value would be asserting
    that no fit happened.
    """
    moved = list(STRAIGHT)
    moved[4] = (5, moved[4][1], 3.0, 0.0)
    result = kernels.superpose(REFERENCE, _chain("A", moved), reference_chain="A", mobile_chain="A")

    assert result["rmsd_before_superposition_angstrom"] == pytest.approx((9 / 10) ** 0.5, abs=1e-3)
    assert result["rmsd_angstrom"] < result["rmsd_before_superposition_angstrom"]
    assert result["largest_deviations"][0]["seq"] == 5


def test_residues_are_paired_by_number_so_a_missing_loop_does_not_shift_everything() -> None:
    """The mobile chain is missing residues 4-6; the six that remain still match."""
    gapped = [entry for entry in STRAIGHT if entry[0] not in {4, 5, 6}]
    result = kernels.superpose(REFERENCE, _chain("A", gapped), reference_chain="A", mobile_chain="A")

    assert result["paired_residue_count"] == 7
    assert result["reference_residue_count"] == 10
    assert result["mobile_residue_count"] == 7
    assert 4 not in result["paired_residue_numbers"]
    # Pairing by position would have matched residue 7 against residue 4 and
    # produced a large RMSD for two identical backbones.
    assert result["rmsd_angstrom"] == pytest.approx(0.0, abs=1e-6)


def test_numbering_that_does_not_overlap_is_refused_rather_than_guessed() -> None:
    renumbered = _chain("A", [(index + 500, x, y, z) for index, x, y, z in STRAIGHT])

    with pytest.raises(kernels.StructureFormatError) as failure:
        kernels.superpose(REFERENCE, renumbered, reference_chain="A", mobile_chain="A")

    assert "same numbering" in str(failure.value)


def test_too_few_paired_residues_is_refused() -> None:
    two = _chain("A", STRAIGHT[:2])

    with pytest.raises(kernels.StructureFormatError):
        kernels.superpose(two, two, reference_chain="A", mobile_chain="A")


def test_an_absent_chain_is_refused() -> None:
    with pytest.raises(kernels.StructureFormatError):
        kernels.superpose(REFERENCE, TRANSLATED, reference_chain="A", mobile_chain="Z")


# --- the score that needs its caveat -------------------------------------------


def test_the_tm_score_is_withheld_where_its_formula_is_undefined() -> None:
    """d0 is not defined below 15 residues; extrapolating would invent a number."""
    result = kernels.superpose(REFERENCE, REFERENCE, reference_chain="A", mobile_chain="A")

    assert result["paired_residue_count"] == 10
    assert result["tm_score_on_paired_residues"] is None


def test_identical_long_chains_score_one_and_say_what_the_score_is_not() -> None:
    long_backbone = [(index, float(index) * 3.8, 0.0, 0.0) for index in range(1, 41)]
    text = _chain("A", long_backbone)

    result = kernels.superpose(text, text, reference_chain="A", mobile_chain="A")

    assert result["tm_score_on_paired_residues"] == pytest.approx(1.0, abs=1e-6)
    assert "Not TM-align" in result["tm_score_note"]
    assert "no alignment search" in result["tm_score_note"]


def test_the_largest_deviations_are_listed_worst_first() -> None:
    moved = list(STRAIGHT)
    moved[1] = (2, moved[1][1], 1.0, 0.0)
    moved[7] = (8, moved[7][1], 4.0, 0.0)
    result = kernels.superpose(REFERENCE, _chain("A", moved), reference_chain="A", mobile_chain="A")

    deviations = [item["deviation_angstrom"] for item in result["largest_deviations"]]
    assert deviations == sorted(deviations, reverse=True)
    assert result["largest_deviations"][0]["seq"] == 8
