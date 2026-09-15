"""Pure functions over an amino-acid sequence.

The platform could already compute a construct's molecular weight and
extinction coefficient, because those are what a concentration measurement
needs. What it could not say was anything about whether the construct is a
sensible thing to make: a binder with an unpaired cysteine, an N-glycosylation
sequon across its interface, or a nine-residue hydrophobic patch is a design
that will cost a month at the bench, and nothing in this repository looked for
one.

Two rules run through the module, both inherited from `structures/kernels.py`
for the same reasons.

**Measurements, not verdicts.** Every function reports what is in the sequence -
which motif, at which position, how many - and none of them says a design is
"developable" or "risky". That word would be a claim about an experiment nobody
has run; the numbers here are inputs to a judgement a person makes.

**One implementation.** Molecular weight, extinction coefficient and the
sanitiser already exist in `wetlab/kernels/calculators.py`, and Biopython's
`ProteinAnalysis` already computes pI, charge, GRAVY, aromaticity and the
instability index. Both are imported rather than rewritten: a second molecular
weight that disagrees with the one on the protein library page would be worse
than no second number at all.

Positions are **1-based and inclusive**, because that is how a sequence is
numbered in every paper, ordering form and mutagenesis primer a person will
write from this output.
"""

from __future__ import annotations

import re
from typing import Any

from Bio.SeqUtils.ProtParam import ProteinAnalysis

from ..wetlab.kernels.calculators import calc_ext_coeff, sanitize_seq

#: Kyte-Doolittle hydropathy. Used for GRAVY (via Biopython) and, here, for the
#: sliding window that finds a patch - the quantity a formulation scientist
#: actually asks about, which a whole-sequence average hides by construction.
KYTE_DOOLITTLE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

#: Window and cutoff for a hydrophobic patch. Nine residues is roughly one face
#: of a helix plus its neighbours, and 1.5 is high enough that ordinary cores do
#: not trip it. Both are reported with the result so a reader can disagree with
#: them rather than having to guess what was used.
PATCH_WINDOW = 9
PATCH_THRESHOLD = 1.5

#: The sequence motifs worth flagging, each with why it matters. `severity` is
#: about how well established the liability is, never about this molecule:
#:   "high"  - a documented degradation or modification route
#:   "watch" - context-dependent; unremarkable in a loop, awkward in an interface
_MOTIFS: tuple[tuple[str, str, str, str], ...] = (
    (
        "n_glycosylation",
        r"N[^P][ST]",
        "high",
        "N-X-S/T sequon: glycosylated in eukaryotic expression, which changes mass and can block an interface.",
    ),
    (
        "deamidation",
        r"N[GS]",
        "high",
        "NG/NS deamidates fastest; introduces a negative charge and a mass shift of +1 Da.",
    ),
    (
        "deamidation_slow",
        r"N[THND]",
        "watch",
        "Slower deamidation context. Usually tolerable unless it sits in the binding site.",
    ),
    (
        "isomerisation",
        r"D[GST]",
        "high",
        "Aspartate isomerisation: converts to iso-aspartate, which is a different backbone.",
    ),
    (
        "fragmentation",
        r"DP",
        "watch",
        "Acid-labile Asp-Pro bond; fragments at low pH, which includes some purification steps.",
    ),
    (
        "integrin_motif",
        r"RGD",
        "watch",
        "RGD binds integrins; an unintended cell-adhesion motif in a therapeutic candidate.",
    ),
    (
        "polyq_run",
        r"[QN]{5,}",
        "watch",
        "Low-complexity Q/N run: aggregation-prone and hard to synthesise as DNA.",
    ),
)

#: Residues reported by count and position rather than as a regex hit, because
#: what matters is how many there are and where, not that they exist. Keyed by
#: *kind*, not by residue: methionine and tryptophan are one liability with two
#: letters, and two entries sharing a kind collapse wherever a caller indexes
#: by it.
_RESIDUE_NOTES: tuple[tuple[str, str, str, str], ...] = (
    (
        "oxidation",
        "MW",
        "watch",
        "Methionine and tryptophan oxidise under light and peroxide stress; "
        "tryptophan is the usual cause of a new late-eluting peak.",
    ),
    (
        "cysteine",
        "C",
        "watch",
        "Cysteines: an odd number means at least one is unpaired.",
    ),
)


class SequenceError(ValueError):
    """The text is not a sequence this module can analyse."""


def sanitise(sequence: str) -> str:
    """The 20 canonical residues, upper case, nothing else.

    Delegates to the wetlab sanitiser so a sequence means the same thing here as
    it does on the protein library page. Raises rather than returning an empty
    string: an empty analysis of a mistyped sequence reads like a clean bill of
    health.
    """
    cleaned = sanitize_seq(sequence or "")
    if not cleaned:
        raise SequenceError(
            "No amino-acid residues were found. A nucleotide sequence or an "
            "accession is not analysed here."
        )
    if len(cleaned) < 5:
        raise SequenceError("A sequence of fewer than five residues has nothing to report.")
    return cleaned


def motifs(sequence: str) -> list[dict[str, Any]]:
    """Every liability motif, with 1-based inclusive positions.

    Overlapping matches are found: `NNGS` contains two deamidation sites and
    reporting one of them would understate the sequence. The regex is applied
    with a lookahead for that reason.
    """
    seq = sanitise(sequence)
    found: list[dict[str, Any]] = []
    for kind, pattern, severity, note in _MOTIFS:
        hits = [
            {"start": match.start() + 1, "end": match.start() + len(match.group(1)), "match": match.group(1)}
            for match in re.finditer(f"(?=({pattern}))", seq)
        ]
        if hits:
            found.append(
                {"kind": kind, "pattern": pattern, "severity": severity, "note": note, "count": len(hits), "sites": hits}
            )
    for kind, residues, severity, note in _RESIDUE_NOTES:
        sites = [
            {"start": index + 1, "end": index + 1, "match": letter}
            for index, letter in enumerate(seq)
            if letter in residues
        ]
        if not sites:
            continue
        entry = {
            "kind": kind,
            "residues": residues,
            "severity": severity,
            "note": note,
            "count": len(sites),
            "sites": sites,
        }
        if kind == "cysteine":
            # An odd count cannot pair internally. This is the one place the
            # module states a consequence, because it is arithmetic rather than
            # a prediction: some cysteine is free.
            entry["unpaired"] = len(sites) % 2 == 1
            entry["severity"] = "high" if entry["unpaired"] else "watch"
        found.append(entry)
    return found


def hydrophobic_patches(
    sequence: str, *, window: int = PATCH_WINDOW, threshold: float = PATCH_THRESHOLD
) -> list[dict[str, Any]]:
    """Windows whose mean hydropathy exceeds the cutoff, merged when they overlap.

    Merged because a twelve-residue patch is one patch: reporting it as four
    overlapping windows would make a single feature look like four.
    """
    seq = sanitise(sequence)
    if window < 3:
        raise SequenceError("A hydrophobic patch window shorter than three residues is noise.")
    if len(seq) < window:
        return []
    spans: list[dict[str, Any]] = []
    for start in range(len(seq) - window + 1):
        chunk = seq[start : start + window]
        mean = sum(KYTE_DOOLITTLE[letter] for letter in chunk) / window
        if mean < threshold:
            continue
        if spans and start + 1 <= spans[-1]["end"]:
            spans[-1]["end"] = start + window
            spans[-1]["peak"] = max(spans[-1]["peak"], round(mean, 2))
        else:
            spans.append({"start": start + 1, "end": start + window, "peak": round(mean, 2)})
    for span in spans:
        span["length"] = span["end"] - span["start"] + 1
    return spans


def properties(sequence: str) -> dict[str, Any]:
    """The numbers an ordering form and a buffer choice need.

    `charge_at_ph_7_4` and `charge_at_ph_6_0` are both reported because the
    question "will this stick to the column / to itself" is asked at the pH of
    the buffer, not at pH 7: a protein whose pI sits between the two behaves
    differently in each.
    """
    seq = sanitise(sequence)
    analysis = ProteinAnalysis(seq)
    extinction = calc_ext_coeff(seq)
    return {
        "length": len(seq),
        "molecular_weight_da": round(analysis.molecular_weight(), 1),
        "extinction_coefficient_reduced": extinction["ext_red"],
        "extinction_coefficient_oxidised": extinction["ext_ox"],
        "a280_0_1_percent": extinction["abs_0_1pct"],
        "isoelectric_point": round(analysis.isoelectric_point(), 2),
        "charge_at_ph_7_4": round(analysis.charge_at_pH(7.4), 2),
        "charge_at_ph_6_0": round(analysis.charge_at_pH(6.0), 2),
        "gravy": round(analysis.gravy(), 3),
        "aromaticity": round(analysis.aromaticity(), 3),
        # Guruprasad's index. Over 40 is conventionally called unstable *in
        # vitro*; the number is reported and the convention is not applied,
        # because "unstable" is a claim about an experiment nobody ran here.
        "instability_index": round(analysis.instability_index(), 2),
        "composition_fraction": {
            "charged": round(sum(seq.count(letter) for letter in "DEKR") / len(seq), 3),
            "hydrophobic": round(sum(seq.count(letter) for letter in "AILMFVWY") / len(seq), 3),
            "aromatic": round(sum(seq.count(letter) for letter in "FWY") / len(seq), 3),
            "cysteine": round(seq.count("C") / len(seq), 3),
        },
    }


def analyse(sequence: str, *, window: int = PATCH_WINDOW, threshold: float = PATCH_THRESHOLD) -> dict[str, Any]:
    """Everything above in one call, plus a count of what a reader should look at.

    The result deliberately does **not** contain the sequence. Some sequences
    this runs on are the only plaintext copy the platform holds (see
    `wetlab.models.Protein`), and a result that echoed them would hand that
    copy to whatever called the tool.
    """
    seq = sanitise(sequence)
    liabilities = motifs(seq)
    patches = hydrophobic_patches(seq, window=window, threshold=threshold)
    return {
        "properties": properties(seq),
        "liabilities": liabilities,
        "hydrophobic_patches": patches,
        "patch_settings": {"window": window, "threshold": threshold},
        "summary": {
            "high_severity_kinds": sorted(
                {item["kind"] for item in liabilities if item["severity"] == "high"}
            ),
            "liability_sites": sum(item["count"] for item in liabilities),
            "patch_count": len(patches),
        },
    }
