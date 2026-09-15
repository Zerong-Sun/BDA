"""Conservation from an alignment: the ways this could quietly mislead.

Each test here is a failure mode that would still produce a plausible-looking
table: insert columns shifting every position, a redundant alignment reading as
universally conserved, gaps counted as agreement, a ragged file treated as an
alignment, and the query's own sequence leaking back out through the result.
"""

from __future__ import annotations

import pytest
from backend_v2.app.sequences import conservation

FASTA = """\
>query
MKVLAA
>homolog1
MKVLAA
>homolog2
MKILAA
>homolog3
MRVLGA
"""

# The same four sequences, written as a3m: lower case and dots are insertions
# relative to the query and must not become columns.
A3M = """\
>query
MKVLAA
>homolog1
MKvlVLAA
>homolog2
MKILAA
>homolog3
MRVLGA
"""

STOCKHOLM = """\
# STOCKHOLM 1.0
#=GF ID test
query     MKVLAA
homolog1  MKVLAA
homolog2  MKILAA
homolog3  MRVLGA
#=GC RF   xxxxxx
//
"""


def test_reads_fasta_stockholm_and_a3m_to_the_same_width() -> None:
    assert len(conservation.parse_alignment(FASTA)[0]) == 6
    assert len(conservation.parse_alignment(STOCKHOLM)[0]) == 6
    # The a3m row carries two inserted residues; stripping them restores the
    # query's numbering rather than shifting everything after position 2.
    rows = conservation.parse_alignment(A3M)
    assert {len(row) for row in rows} == {6}


def test_stockholm_blocks_are_joined_per_sequence() -> None:
    wrapped = """\
# STOCKHOLM 1.0
query     MKV
homolog   MKI

query     LAA
homolog   LGA
//
"""

    rows = conservation.parse_alignment(wrapped)

    assert rows == ["MKVLAA", "MKILGA"]


def test_a_single_sequence_is_not_an_alignment() -> None:
    with pytest.raises(conservation.AlignmentError):
        conservation.parse_alignment(">only\nMKVLAA\n")


def test_a_ragged_file_is_refused_rather_than_scored() -> None:
    with pytest.raises(conservation.AlignmentError) as error:
        conservation.parse_alignment(">a\nMKVLAA\n>b\nMKV\n")

    assert "not an aligned file" in str(error.value)


def test_an_invariant_column_is_fully_conserved_and_a_varied_one_is_not() -> None:
    table = conservation.columns(FASTA, weighting="none")
    by_position = {row["position"]: row for row in table["positions"]}

    # Position 1 is M in every sequence; position 2 is K,K,K,R.
    assert by_position[1]["conservation"] == pytest.approx(1.0)
    assert by_position[2]["conservation"] < 1.0
    assert by_position[1]["consensus"] == "M"


def test_gaps_are_reported_separately_not_counted_as_agreement() -> None:
    gapped = ">query\nMKV\n>a\nM-V\n>b\nM-V\n>c\nM-V\n"

    by_position = {row["position"]: row for row in conservation.columns(gapped)["positions"]}

    # Column 2 holds one K and three gaps. The residue distribution is a single
    # K, so entropy is zero - but the column is three-quarters gap and says so.
    assert by_position[2]["gap_fraction"] == pytest.approx(0.75, abs=0.05)
    assert by_position[2]["shallow"] is True


def test_query_gap_columns_do_not_consume_a_position() -> None:
    """An insertion in the homologues must not shift the query's numbering."""
    with_insert = ">query\nMK-VL\n>a\nMKWVL\n>b\nMKWVL\n"

    positions = [row["position"] for row in conservation.columns(with_insert)["positions"]]

    assert positions == [1, 2, 3, 4]


def test_henikoff_weighting_discounts_a_crowd_of_near_identical_sequences() -> None:
    """Twenty copies of one homologue are not twenty pieces of evidence."""
    crowd = ">query\nMKVLAA\n" + "".join(f">copy{i}\nMKVLAA\n" for i in range(20)) + ">far\nMRVLGA\n"

    weighted = conservation.columns(crowd, weighting="henikoff")
    unweighted = conservation.columns(crowd, weighting="none")

    position_2_weighted = weighted["positions"][1]["conservation"]
    position_2_unweighted = unweighted["positions"][1]["conservation"]
    # Unweighted, 21 of 22 rows say K and the column looks nearly invariant.
    assert position_2_unweighted > 0.8
    assert position_2_weighted < position_2_unweighted


def test_the_summary_names_both_ends_and_returns_no_sequence() -> None:
    summary = conservation.summarise(FASTA, limit=3)

    assert summary["alignment"]["sequences"] == 4
    assert summary["alignment"]["query_length"] == 6
    assert len(summary["most_conserved"]) == 3
    assert len(summary["most_variable"]) == 3
    # The query's residues must not be reconstructable from the result: no row
    # carries the query letter, and the consensus appears only for the capped
    # lists, not for every position.
    assert "positions" not in summary
    assert all("residue" not in row for row in summary["most_conserved"])


def test_the_weighting_used_travels_with_the_numbers() -> None:
    assert conservation.summarise(FASTA)["alignment"]["weighting"] == "henikoff"
    assert conservation.summarise(FASTA, weighting="none")["alignment"]["weighting"] == "none"


def test_an_unknown_weighting_is_refused() -> None:
    with pytest.raises(conservation.AlignmentError):
        conservation.columns(FASTA, weighting="blosum")


def test_a_limit_outside_the_band_is_refused() -> None:
    with pytest.raises(conservation.AlignmentError):
        conservation.summarise(FASTA, limit=0)
