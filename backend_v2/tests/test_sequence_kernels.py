"""What a sequence scan must get right to be worth running.

A liability scan is only useful if its positions can be typed into a primer and
its misses are not silent. So the tests are about the three ways this kind of
code is usually wrong:

* off-by-one positions, which make every downstream mutagenesis wrong;
* overlapping motifs reported once, which understates a sequence;
* a sanitiser that turns a mistyped or nucleotide input into a clean report of
  nothing, which reads like a pass.

One test is about a rule rather than a number: the result must never carry the
sequence back out, because for a library construct it is the only plaintext
copy the platform holds.
"""

from __future__ import annotations

import json

import pytest
from backend_v2.app.sequences import kernels

# A designed mini-binder with liabilities planted in known places:
#   NGS at 5-7   -> glycosylation sequon and an NG deamidation site
#   DG  at 12-13 -> isomerisation
#   M   at 16, W at 20
#   two cysteines -> paired
BINDER = "GSEQANGSTKLDGAMEEKWACLLEQAKKLLEEC"


def test_positions_are_one_based_and_land_on_the_motif() -> None:
    found = {item["kind"]: item for item in kernels.motifs(BINDER)}

    sequon = found["n_glycosylation"]["sites"][0]
    assert BINDER[sequon["start"] - 1 : sequon["end"]] == sequon["match"]
    assert sequon["match"][0] == "N"


def test_overlapping_motifs_are_all_reported() -> None:
    """`NNSS` holds two sequons; a non-overlapping scan finds one."""
    found = {item["kind"]: item for item in kernels.motifs("GGGNNSSGGG")}

    assert found["n_glycosylation"]["count"] == 2


def test_a_sequon_with_proline_is_not_a_sequon() -> None:
    """N-P-S is the documented exception, and a scanner that misses it cries wolf."""
    kinds = {item["kind"] for item in kernels.motifs("GGGNPSGGGG")}

    assert "n_glycosylation" not in kinds


def test_an_odd_number_of_cysteines_is_called_unpaired(  ) -> None:
    odd = {item["kind"]: item for item in kernels.motifs("GGGCGGGCGGGCGGG")}["cysteine"]
    even = {item["kind"]: item for item in kernels.motifs("GGGCGGGCGGGG")}["cysteine"]

    assert odd["unpaired"] is True
    assert odd["severity"] == "high"
    assert even["unpaired"] is False
    assert even["severity"] == "watch"


def test_methionine_and_tryptophan_are_reported_by_position(  ) -> None:
    found = {item["kind"]: item for item in kernels.motifs(BINDER)}

    assert found["oxidation"]["count"] >= 2
    positions = {site["start"] for site in found["oxidation"]["sites"]}
    assert all(BINDER[position - 1] in {"M", "W"} for position in positions)


# --- patches -----------------------------------------------------------------


def test_a_hydrophobic_run_is_one_patch_and_not_four() -> None:
    """One feature, one entry - and the span covers the run that caused it.

    The span can start a residue or two before the run: a window mean is taken
    over the whole window, so a very hydrophobic core still clears the cutoff
    with a couple of glutamates at its edge. That is what a window mean is, and
    the alternative - trimming the span to individually hydrophobic residues -
    would report a different quantity from the one the cutoff was applied to.
    """
    found = kernels.hydrophobic_patches("EEEE" + "IIILLLVVV" + "KKKK", window=9)

    assert len(found) == 1
    assert found[0]["start"] <= 5
    assert found[0]["end"] >= 13
    assert found[0]["peak"] > kernels.PATCH_THRESHOLD


def test_a_polar_sequence_has_no_patch() -> None:
    assert kernels.hydrophobic_patches("EEEKKKEEEKKKEEEKKK") == []


def test_the_window_and_cutoff_travel_with_the_result() -> None:
    """A reader who disagrees with the cutoff needs to know what was used."""
    result = kernels.analyse(BINDER, window=7, threshold=2.0)

    assert result["patch_settings"] == {"window": 7, "threshold": 2.0}


# --- properties ---------------------------------------------------------------


def test_charge_follows_the_residues_at_both_reported_ph_values() -> None:
    basic = kernels.properties("KKKKKKKKKKGG")
    acidic = kernels.properties("EEEEEEEEEEGG")

    assert basic["isoelectric_point"] > 9
    assert acidic["isoelectric_point"] < 5
    assert basic["charge_at_ph_7_4"] > 0 > acidic["charge_at_ph_7_4"]
    # pH 6.0 is reported as well because a protein whose pI sits between the two
    # behaves differently in each buffer.
    assert acidic["charge_at_ph_6_0"] > acidic["charge_at_ph_7_4"]


def test_the_weight_agrees_with_the_protein_library() -> None:
    """One implementation: this delegates to the wetlab calculator."""
    from backend_v2.app.wetlab.kernels.calculators import calc_mw

    assert kernels.properties(BINDER)["molecular_weight_da"] == round(calc_mw(BINDER), 1)


# --- refusals ------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "1234-5678", "MK"])
def test_input_that_is_not_a_protein_is_refused_rather_than_reported_as_clean(text: str) -> None:
    with pytest.raises(kernels.SequenceError):
        kernels.analyse(text)


def test_a_nucleotide_sequence_is_refused_even_though_acgt_are_residues() -> None:
    """ACGT are all amino-acid letters, so the guard is the length of what survives."""
    with pytest.raises(kernels.SequenceError):
        kernels.analyse("ACGT")


# --- the rule that is not a number ---------------------------------------------


def test_the_result_never_carries_the_sequence_back_out() -> None:
    """For a library construct this is the only plaintext copy the platform holds."""
    result = kernels.analyse(BINDER)

    serialised = json.dumps(result)
    assert BINDER not in serialised
    assert BINDER[:12] not in serialised


def test_the_summary_counts_what_a_reader_should_look_at_first() -> None:
    result = kernels.analyse(BINDER)

    assert "n_glycosylation" in result["summary"]["high_severity_kinds"]
    assert result["summary"]["liability_sites"] == sum(
        item["count"] for item in result["liabilities"]
    )
