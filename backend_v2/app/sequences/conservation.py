"""Which positions a design must not touch, read off an alignment.

A binder designer changes residues. The question that decides which ones are
cheap to change is "how conserved is this position across homologues", and
until now nothing here could answer it - the platform could align nothing and
read no alignment, so conservation was a thing people worked out elsewhere and
pasted back as a comment.

Three decisions worth stating, because each is a place this could quietly
mislead:

**Redundancy is corrected for, by default.** An alignment of 500 sequences of
which 480 are near-identical proteobacterial orthologues is not 500 pieces of
evidence. Unweighted entropy reads that as near-perfect conservation
everywhere. Henikoff position-based weights are applied instead, and the
weighting used is named in the result, so a number can be recomputed the other
way and compared.

**Gaps are not a twenty-first residue.** They are excluded from the residue
distribution and reported separately as `gap_fraction`: a column that is 90%
gap and 10% tryptophan is not a conserved tryptophan, and the two numbers say
that plainly where one merged number would hide it.

**No sequence is returned.** The alignment's first row is the query, and
echoing its residues position by position would hand back the sequence the
protein library keeps exactly one plaintext copy of. Positions carry numbers;
the consensus letter appears only for the handful of columns a caller asks to
see, which is what makes the answer usable without reconstructing the input.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

#: The 20 canonical residues. Anything else in a column (B, Z, X, U, O, and
#: whatever a generator invented) is counted as unknown rather than as its own
#: residue: an alignment column is not the place to decide what a 'B' meant.
RESIDUES = "ACDEFGHIKLMNPQRSTVWY"
_RESIDUE_SET = frozenset(RESIDUES)
_GAPS = frozenset("-.")

#: Entropy is normalised by this, so conservation is 0..1 regardless of how
#: many residue types a column happens to use.
_MAX_ENTROPY = math.log2(len(RESIDUES))

#: Below this many effective sequences a column's conservation is arithmetic
#: rather than evidence, and it is flagged instead of quietly reported.
MIN_DEPTH = 3

#: Guards. An a3m from a deep metagenomic search is routinely hundreds of
#: thousands of rows; nothing here needs more than a slice of that to be
#: stable, and the number used is reported so a reader knows it was truncated.
MAX_SEQUENCES = 20_000
MAX_COLUMNS = 10_000


class AlignmentError(ValueError):
    """The text is not an alignment this module can read."""


def _rows_from_fasta(text: str) -> list[str]:
    """Rows of a FASTA or a3m alignment, headers dropped.

    a3m marks insertions relative to the query with lower-case letters and
    dots. Those columns do not exist in the query's numbering, so they are
    removed - keeping them would shift every position after the first
    insertion, which is the classic way a conservation table ends up describing
    the wrong residues.
    """
    rows: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if current:
                rows.append("".join(current))
                current = []
            continue
        if line.startswith("#") or not line.strip():
            continue
        current.append(line.strip())
    if current:
        rows.append("".join(current))
    # Drop insert columns: lower case and '.' in a3m. Upper case and '-' are
    # the match columns, which are the ones the query is numbered by.
    return [re.sub(r"[a-z.]", "", row) for row in rows]


def _rows_from_stockholm(text: str) -> list[str]:
    """Rows of a Stockholm alignment, in first-appearance order.

    Stockholm wraps long alignments into blocks, so a sequence's row is the
    concatenation of every line carrying its name. `#=GC` annotation lines and
    the `//` terminator are not sequences.
    """
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "//":
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        name, chunk = parts[0], parts[-1]
        if name not in blocks:
            blocks[name] = []
            order.append(name)
        blocks[name].append(chunk)
    return ["".join(blocks[name]) for name in order]


def parse_alignment(text: str) -> list[str]:
    """The aligned rows, first row first. Never returned to a caller.

    Raises rather than guessing: a file that is not an alignment produces a
    clear error here instead of a conservation table computed over one row.
    """
    if not text or not text.strip():
        raise AlignmentError("The file is empty.")
    stockholm = text.lstrip().startswith("# STOCKHOLM")
    rows = _rows_from_stockholm(text) if stockholm else _rows_from_fasta(text)
    rows = [row.upper() for row in rows if row]
    if len(rows) < 2:
        raise AlignmentError(
            "An alignment needs at least two sequences; this file has "
            f"{len(rows)}. A single sequence has nothing to be conserved against."
        )
    if len(rows) > MAX_SEQUENCES:
        rows = rows[:MAX_SEQUENCES]
    width = len(rows[0])
    if width == 0:
        raise AlignmentError("The first sequence is empty.")
    if width > MAX_COLUMNS:
        raise AlignmentError(f"An alignment wider than {MAX_COLUMNS} columns is not read here.")
    ragged = [index for index, row in enumerate(rows) if len(row) != width]
    if ragged:
        raise AlignmentError(
            f"Rows {ragged[:3]} are not the same length as the first sequence "
            f"({width}). This is not an aligned file."
        )
    return rows


def henikoff_weights(rows: list[str]) -> list[float]:
    """Position-based sequence weights (Henikoff & Henikoff, 1994).

    Each column contributes 1/(r * n) to a sequence, where r is how many
    distinct residues the column holds and n how many sequences share that
    sequence's residue there. A sequence in a crowd of near-identical relatives
    therefore contributes little, and a lone divergent homologue contributes a
    lot - which is the correction that stops a redundant alignment reading as
    universally conserved. Normalised to sum to the number of sequences, so
    "effective depth" stays comparable to a count.
    """
    width = len(rows[0])
    weights = [0.0] * len(rows)
    for column in range(width):
        letters = [row[column] for row in rows]
        counts = Counter(letter for letter in letters if letter in _RESIDUE_SET)
        distinct = len(counts)
        if distinct < 2:
            # A column with one residue type (or none) separates nothing, and
            # including it would add the same constant to every sequence.
            continue
        for index, letter in enumerate(letters):
            if letter in counts:
                weights[index] += 1.0 / (distinct * counts[letter])
    total = sum(weights)
    if total <= 0:
        # Every column was invariant or empty: nothing distinguishes the rows.
        return [1.0] * len(rows)
    scale = len(rows) / total
    return [weight * scale for weight in weights]


def columns(text: str, *, weighting: str = "henikoff") -> dict[str, Any]:
    """Per-column conservation, numbered by the query (the first sequence).

    Columns where the query has a gap carry no query position - they are
    insertions in the homologues - and are left out, so every position returned
    is a residue somebody could choose to mutate.
    """
    if weighting not in {"henikoff", "none"}:
        raise AlignmentError("weighting must be 'henikoff' or 'none'.")
    rows = parse_alignment(text)
    weights = henikoff_weights(rows) if weighting == "henikoff" else [1.0] * len(rows)
    query = rows[0]

    positions: list[dict[str, Any]] = []
    query_position = 0
    for column in range(len(query)):
        query_letter = query[column]
        if query_letter in _GAPS:
            continue
        query_position += 1
        observed: Counter[str] = Counter()
        gap_weight = 0.0
        unknown_weight = 0.0
        for row, weight in zip(rows, weights, strict=True):
            letter = row[column]
            if letter in _GAPS:
                gap_weight += weight
            elif letter in _RESIDUE_SET:
                observed[letter] += weight  # type: ignore[assignment]
            else:
                unknown_weight += weight
        depth = sum(observed.values())
        total = depth + gap_weight + unknown_weight
        if depth <= 0:
            positions.append(
                {
                    "position": query_position,
                    "conservation": None,
                    "entropy_bits": None,
                    "gap_fraction": round(gap_weight / total, 3) if total else 1.0,
                    "effective_depth": 0.0,
                    "shallow": True,
                }
            )
            continue
        entropy = -sum(
            (weight / depth) * math.log2(weight / depth) for weight in observed.values() if weight > 0
        )
        top_letter, top_weight = observed.most_common(1)[0]
        positions.append(
            {
                "position": query_position,
                "conservation": round(1 - entropy / _MAX_ENTROPY, 4),
                "entropy_bits": round(entropy, 4),
                "gap_fraction": round(gap_weight / total, 3) if total else 0.0,
                "effective_depth": round(depth, 2),
                "consensus": top_letter,
                "consensus_fraction": round(top_weight / depth, 3),
                # Below MIN_DEPTH the number is arithmetic over two or three
                # sequences. Reported, but never silently.
                "shallow": depth < MIN_DEPTH,
            }
        )
    return {
        "alignment": {
            "sequences": len(rows),
            "columns": len(query),
            "query_length": len(positions),
            "weighting": weighting,
            "truncated": len(rows) >= MAX_SEQUENCES,
        },
        "positions": positions,
    }


def summarise(text: str, *, weighting: str = "henikoff", limit: int = 25) -> dict[str, Any]:
    """The whole table, plus the two ends of it a person actually reads.

    `most_conserved` is where a substitution is most likely to cost function;
    `most_variable` is where the homologues already disagree, which is where a
    design has room. Both are capped, because this result is written into a
    conversation transcript and a 400-row table there helps nobody.
    """
    if limit < 1 or limit > 200:
        raise AlignmentError("limit must be between 1 and 200.")
    table = columns(text, weighting=weighting)
    scored = [row for row in table["positions"] if row["conservation"] is not None]
    ranked = sorted(scored, key=lambda row: (-row["conservation"], row["position"]))
    variable = sorted(scored, key=lambda row: (row["conservation"], row["position"]))
    covered = [row for row in scored if not row["shallow"]]
    return {
        "alignment": table["alignment"],
        "scored_positions": len(scored),
        "shallow_positions": sum(1 for row in scored if row["shallow"]),
        "mean_conservation": (
            round(sum(row["conservation"] for row in covered) / len(covered), 4) if covered else None
        ),
        "most_conserved": ranked[:limit],
        "most_variable": variable[:limit],
        "notes": [
            "Conservation is 1 - normalised Shannon entropy over the 20 canonical residues; "
            "gaps are excluded from the distribution and reported as gap_fraction.",
            "Positions are numbered by the first sequence in the alignment, which is taken "
            "to be the query; columns where it has a gap are not numbered.",
            f"Columns backed by fewer than {MIN_DEPTH} effective sequences are marked shallow.",
        ],
    }
