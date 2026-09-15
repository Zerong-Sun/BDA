"""Codon optimisation: the construct must be the protein, and say what it is.

Most of these run against a **synthetic** usage table rather than the counted
one. A test that asserts "CGT is preferred" against real genome counts is
really asserting a fact about *E. coli*, and it would start failing the day the
table is regenerated from a newer assembly - which is exactly when the suite
should stay quiet. The synthetic table makes the preference an input, so what
is tested is the rule that applies it.

Two tests do use the counted tables, because two properties belong to the data
itself: every codon of the standard genetic code must have a weight, and a real
construct must translate back to the protein it was built from.
"""

from __future__ import annotations

import copy

import pytest
from backend_v2.app.sequences import codon
from backend_v2.app.sequences.kernels import SequenceError

# A four-residue language is enough to test preference, avoidance and rarity.
# Values are chosen so that the preferred codon of each family is unambiguous.
SYNTHETIC = {
    "label": "Synthetic host",
    "organism": "Synthetic organism",
    "taxon_id": 0,
    "translation_table": 11,
    "accessions": ["SYNTHETIC"],
    "note": "Fixture.",
    "cds_counted": 1,
    "codons_counted": 1000,
    "counts": {
        # Glu: GAA strongly preferred over GAG.
        "GAA": 900, "GAG": 100,
        # Phe: TTC preferred; TTT rare enough to be reported as such.
        "TTC": 980, "TTT": 20,
        # Ala: GCT preferred, then GCA, GCC, GCG.
        "GCT": 500, "GCA": 300, "GCC": 150, "GCG": 50,
        # Arg: CGT preferred; the rest are present so the family is not degenerate.
        "CGT": 600, "CGC": 200, "CGA": 100, "CGG": 60, "AGA": 30, "AGG": 10,
        # Met and Trp have no alternative.
        "ATG": 400, "TGG": 200,
    },
}


@pytest.fixture
def synthetic_host():
    # A deep copy, because a test that adds a codon family to the table must
    # not leave it there for the next one.
    codon.CODON_USAGE["synthetic"] = copy.deepcopy(SYNTHETIC)
    try:
        yield "synthetic"
    finally:
        codon.CODON_USAGE.pop("synthetic", None)


# --- The weighting ------------------------------------------------------------


def test_relative_adaptiveness_is_the_family_fraction(synthetic_host: str) -> None:
    weights = codon.relative_adaptiveness(synthetic_host)

    assert weights["GAA"] == pytest.approx(1.0)
    assert weights["GAG"] == pytest.approx(100 / 900)
    assert weights["GCT"] == pytest.approx(1.0)
    assert weights["GCA"] == pytest.approx(300 / 500)


def test_an_unused_codon_is_floored_rather_than_zero(synthetic_host: str) -> None:
    """A zero weight would take any construct containing it to CAI 0."""
    weights = codon.relative_adaptiveness(synthetic_host)

    # No count was given for CTG (Leu family is entirely absent from the
    # fixture), so every member of that family is treated as unknown.
    assert weights["CTG"] > 0
    assert all(weight > 0 for weight in weights.values())


def test_cai_ignores_codons_with_no_alternative(synthetic_host: str) -> None:
    """Met and Trp cannot be adapted, so they cannot raise the score."""
    preferred = codon.cai("GAAGCTCGT", synthetic_host)
    with_met = codon.cai("GAAGCTCGTATG", synthetic_host)

    assert preferred == pytest.approx(1.0)
    assert with_met == pytest.approx(preferred)


def test_cai_falls_when_dispreferred_codons_are_used(synthetic_host: str) -> None:
    assert codon.cai("GAGGCGAGG", synthetic_host) < codon.cai("GAAGCTCGT", synthetic_host)


# --- Measuring a sequence -----------------------------------------------------


def test_finds_a_forbidden_site_on_either_strand() -> None:
    forward = codon.site_hits("AAAGAATTCAAA", {"EcoRI": "GAATTC"})
    # NdeI's site CATATG is palindromic; NotI's GCGGCCGC too. XhoI CTCGAG is as
    # well, so use a non-palindromic one to exercise the reverse strand.
    reverse = codon.site_hits("AAA" + codon.reverse_complement("GGTCTC") + "AAA", {"BsaI": "GGTCTC"})

    assert [hit["start"] for hit in forward] == [4]
    assert [(hit["strand"], hit["start"]) for hit in reverse] == [("-", 4)]


def test_a_palindromic_site_is_reported_once() -> None:
    hits = codon.site_hits("AAAGAATTCAAA", {"EcoRI": "GAATTC"})

    assert len(hits) == 1


def test_homopolymer_runs_are_reported_beyond_the_limit() -> None:
    runs = codon.homopolymer_runs("ACGAAAAAAAGT", limit=6)

    assert runs == [{"base": "A", "start": 4, "end": 10, "length": 7}]


def test_gc_windows_do_not_merge_a_low_span_into_a_high_one() -> None:
    """A GC-poor stretch running into a GC-rich one is two findings, not one."""
    dna = "AT" * 30 + "GC" * 30

    windows = codon.gc_windows(dna, window=30)

    directions = [window["direction"] for window in windows]
    assert "low" in directions and "high" in directions
    for window in windows:
        assert window["direction"] in {"low", "high"}


def test_assess_rejects_anything_that_is_not_dna(synthetic_host: str) -> None:
    with pytest.raises(codon.CodonError):
        codon.assess("GAANNNGCT", host=synthetic_host)


# --- Building a construct -----------------------------------------------------


def test_back_translation_takes_the_preferred_codon(synthetic_host: str) -> None:
    built = codon.back_translate("EAREAR", host=synthetic_host, add_stop=False)

    assert built["dna"] == "GAAGCTCGT" * 2
    assert built["compromises"] == []


def test_back_translation_avoids_a_site_the_preferred_codons_would_create(
    synthetic_host: str,
) -> None:
    """The preferred codons for E-F spell GAA TTC - an EcoRI site across the join."""
    preferred = codon.back_translate("EF", host=synthetic_host, avoid_sites={}, add_stop=False)
    avoided = codon.back_translate(
        "EF", host=synthetic_host, avoid_sites={"EcoRI": "GAATTC"}, add_stop=False
    )

    assert preferred["dna"] == "GAATTC"
    assert "GAATTC" not in avoided["dna"]
    assert avoided["compromises"] == []
    assert codon.translate(avoided["dna"], translation_table=11) == "EF"


def test_an_unavoidable_site_is_reported_rather_than_hidden(synthetic_host: str) -> None:
    """Met has one codon, so ATG ATG cannot be spelled any other way."""
    built = codon.back_translate(
        "MM", host=synthetic_host, avoid_sites={"Fake": "ATGATG"}, add_stop=False
    )

    assert built["dna"] == "ATGATG"
    assert [entry["position"] for entry in built["compromises"]] == [2]


def test_a_site_formed_with_the_previous_codon_is_repaired_by_respelling_it(
    synthetic_host: str,
) -> None:
    """His-Met spells CAT ATG - NdeI - and only the histidine can move."""
    codon.CODON_USAGE[synthetic_host]["counts"].update({"CAT": 900, "CAC": 100})

    built = codon.back_translate(
        "HM", host=synthetic_host, avoid_sites={"NdeI": "CATATG"}, add_stop=False
    )

    assert built["dna"] == "CACATG"
    assert built["compromises"] == []
    assert [entry["position"] for entry in built["respelled"]] == [1]
    assert codon.translate(built["dna"], translation_table=11) == "HM"


def test_optimisation_reports_the_host_evidence_and_the_measurements(
    synthetic_host: str,
) -> None:
    result = codon.optimise("EARM", host=synthetic_host)

    assert result["host"]["cds_counted"] == 1
    assert result["protein_length"] == 4
    assert result["dna"].endswith("TAA")
    assert result["assessment"]["length_nt"] == len(result["dna"])
    assert result["assessment"]["cai"] > 0


def test_flanks_are_measured_with_the_insert(synthetic_host: str) -> None:
    """A site spanning the junction is still a site.

    The insert avoids the site - the flank is verbatim, so the junction it
    forms with the first codon cannot be designed away, only reported.
    """
    result = codon.optimise(
        "EARM",
        host=synthetic_host,
        avoid_sites={"Fake": "TTTGAA"},
        prefix="TTT",
        add_stop=False,
    )

    assert result["dna"] == "TTT" + "GAAGCTCGTATG"
    assert [hit["enzyme"] for hit in result["assessment"]["forbidden_sites"]] == ["Fake"]
    assert [hit["start"] for hit in result["assessment"]["forbidden_sites"]] == [1]


def test_a_flank_that_is_not_dna_is_refused(synthetic_host: str) -> None:
    with pytest.raises(codon.CodonError):
        codon.optimise("EAR", host=synthetic_host, prefix="ATGX")


def test_an_unknown_host_names_the_ones_that_exist() -> None:
    with pytest.raises(codon.CodonError) as error:
        codon.relative_adaptiveness("nothing_counted_this")

    assert "nothing_counted_this" in str(error.value)


def test_round_trip_check_catches_a_construct_that_is_not_the_protein() -> None:
    with pytest.raises(SequenceError):
        codon.ensure_round_trip("EARM", "GAAGCTCGTATG"[:-3], translation_table=11)


# --- The counted tables themselves --------------------------------------------


@pytest.mark.parametrize("host", codon.known_hosts())
def test_every_counted_host_weights_the_whole_genetic_code(host: str) -> None:
    """A missing weight would silently drop a residue's family from the CAI."""
    table = codon.CODON_USAGE[host]
    weights = codon.relative_adaptiveness(host)
    families = codon.synonymous_codons(table["translation_table"])

    for codons in families.values():
        for triplet in codons:
            assert weights.get(triplet, 0) > 0, f"{host} has no weight for {triplet}"


@pytest.mark.parametrize("host", codon.known_hosts())
def test_a_real_construct_translates_back_to_its_protein(host: str) -> None:
    protein = "MGSSHHHHHHSSGLVPRGSHMASMTGGQQMGRGSEFEARWQKLDSAINQCVE"

    result = codon.optimise(protein, host=host)

    codon.ensure_round_trip(
        protein,
        result["dna"],
        translation_table=result["host"]["translation_table"],
    )
    assert result["assessment"]["forbidden_sites"] == []
    assert result["assessment"]["cai"] > 0.5
