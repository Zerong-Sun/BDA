"""Turning a protein into DNA somebody can order, and saying what the DNA is.

Codon optimisation is usually sold as one number to maximise. It is not: a
construct that scores a perfect CAI and carries a BsaI site in the middle is
unusable, and so is one whose GC content swings from 30% to 75% across a
window. This module treats it as what it is - a constrained choice per residue,
with the constraints stated - and reports every quantity it used so the result
can be argued with.

**Deterministic.** No random tie-breaks. The same protein, host and constraints
produce the same DNA on every machine, because an ordering form that changes
between runs cannot be reviewed or reproduced.

**Measurements, not a verdict.** As in `kernels.py`: CAI, GC, GC3, the sites
found and the rare codons kept are reported. Nothing here calls a construct
"good" - whether 0.78 CAI is enough is a decision about an experiment.

**The weights are counted, not invented.** `codon_usage.py` is generated from
annotated genomes by `scripts/build_codon_usage.py`, and carries how many
coding sequences each host's numbers rest on.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import exp, log
from typing import Any

from Bio.Data import CodonTable

from ..wetlab.kernels.calculators import sanitize_seq
from .codon_usage import CODON_USAGE
from .kernels import SequenceError

#: Recognition sequences of the enzymes a cloning strategy usually forbids in
#: an insert. Type IIS enzymes (BsaI, BsmBI, SapI) matter most: Golden Gate
#: assembly cuts outside its recognition site, so one internal occurrence
#: silently removes a fragment. Palindromic sites need only be searched on one
#: strand; the others are searched on both.
DEFAULT_AVOID_SITES: dict[str, str] = {
    "EcoRI": "GAATTC",
    "BamHI": "GGATCC",
    "HindIII": "AAGCTT",
    "XhoI": "CTCGAG",
    "NdeI": "CATATG",
    "NcoI": "CCATGG",
    "NotI": "GCGGCCGC",
    "BsaI": "GGTCTC",
    "BsmBI": "CGTCTC",
    "SapI": "GCTCTTC",
}

#: Windowed GC bounds. Synthesis vendors reject or surcharge long stretches
#: outside roughly this band, and the window matters more than the average: a
#: construct at 52% overall can still carry a 75% GC window that will not
#: assemble.
GC_WINDOW = 30
GC_MIN = 0.30
GC_MAX = 0.70

#: A run this long of one base is the other common synthesis failure.
MAX_HOMOPOLYMER = 6

#: A synonymous codon used less than this often within its family is "rare".
#: Reported, not banned: for some hosts the rarest codon of a two-codon family
#: is still 20% of its family, and refusing it would say more about the
#: threshold than about the construct.
RARE_CODON_FRACTION = 0.10

_BASES = frozenset("ACGT")
_COMPLEMENT = str.maketrans("ACGT", "TGCA")


class CodonError(ValueError):
    """The request cannot be turned into a construct."""


def _residues(protein: str) -> str:
    """The protein, sanitised, with no minimum length.

    `kernels.sanitise` refuses anything under five residues, which is right for
    the analysis it guards - a four-residue "clean bill of health" would be
    meaningless. Back-translation has no such problem: a linker or a tag of two
    residues is a real thing to order, and refusing to spell it would be this
    module inheriting a threshold that was never about it.
    """
    cleaned = sanitize_seq(protein or "")
    if not cleaned:
        raise CodonError(
            "No amino-acid residues were found. A nucleotide sequence is not back-translated."
        )
    return cleaned


def hosts() -> list[dict[str, Any]]:
    """Every host a table was counted for, with the evidence behind it."""
    return [
        {
            "key": key,
            "label": table["label"],
            "organism": table["organism"],
            "taxon_id": table["taxon_id"],
            "translation_table": table["translation_table"],
            "accessions": list(table["accessions"]),
            "cds_counted": table["cds_counted"],
            "codons_counted": table["codons_counted"],
            "note": table["note"],
        }
        for key, table in sorted(CODON_USAGE.items())
    ]


def _table(host: str) -> dict[str, Any]:
    table = CODON_USAGE.get(host)
    if table is None:
        known = ", ".join(sorted(CODON_USAGE)) or "none"
        raise CodonError(f"No codon usage table for host {host!r}. Counted hosts: {known}.")
    return table


def synonymous_codons(translation_table: int) -> dict[str, list[str]]:
    """Residue -> its codons, stops excluded, in a fixed order."""
    forward = CodonTable.unambiguous_dna_by_id[translation_table].forward_table
    families: dict[str, list[str]] = {}
    for codon, residue in sorted(forward.items()):
        families.setdefault(residue, []).append(codon)
    return families


def relative_adaptiveness(host: str) -> dict[str, float]:
    """Each codon's frequency within its family, divided by the family's best.

    This is Sharp and Li's *w*. A codon the host never used would give a weight
    of zero and take a whole construct's geometric mean to zero with it, so an
    unseen codon is floored at half the smallest observed weight - the
    conventional treatment, and recorded here rather than hidden in a constant.
    """
    table = _table(host)
    counts: Mapping[str, int] = table["counts"]
    weights: dict[str, float] = {}
    for _residue, codons in synonymous_codons(table["translation_table"]).items():
        best = max((counts.get(codon, 0) for codon in codons), default=0)
        if best <= 0:
            # A family the host never used at all: every member equally unknown.
            for codon in codons:
                weights[codon] = 1.0
            continue
        for codon in codons:
            weights[codon] = counts.get(codon, 0) / best
    observed = [weight for weight in weights.values() if weight > 0]
    floor = min(observed) / 2 if observed else 1.0
    return {codon: (weight if weight > 0 else floor) for codon, weight in weights.items()}


def cai(dna: str, host: str) -> float:
    """Codon adaptation index: the geometric mean of the codons' weights.

    Single-codon families (Met, Trp) are excluded, as in the original
    definition: a codon with no alternative says nothing about adaptation, and
    including its weight of 1 inflates every short construct.
    """
    table = _table(host)
    weights = relative_adaptiveness(host)
    families = synonymous_codons(table["translation_table"])
    single = {codons[0] for codons in families.values() if len(codons) == 1}
    scored = [
        weights[codon]
        for codon in codons_of(dna)
        if codon in weights and codon not in single
    ]
    if not scored:
        return 0.0
    return exp(sum(log(weight) for weight in scored) / len(scored))


def codons_of(dna: str) -> list[str]:
    """The reading frame as triplets. A trailing partial codon is dropped."""
    text = dna.upper()
    return [text[index : index + 3] for index in range(0, len(text) - len(text) % 3, 3)]


def gc_fraction(dna: str) -> float:
    text = dna.upper()
    return (text.count("G") + text.count("C")) / len(text) if text else 0.0


def gc3(dna: str) -> float:
    """GC at third positions - where synonymous choice actually shows."""
    thirds = [codon[2] for codon in codons_of(dna)]
    return sum(base in "GC" for base in thirds) / len(thirds) if thirds else 0.0


def gc_windows(dna: str, *, window: int = GC_WINDOW) -> list[dict[str, Any]]:
    """Windows outside the GC band, 1-based and inclusive."""
    text = dna.upper()
    if len(text) < window:
        return []
    out: list[dict[str, Any]] = []
    for start in range(len(text) - window + 1):
        fraction = gc_fraction(text[start : start + window])
        if GC_MIN <= fraction <= GC_MAX:
            continue
        direction = "low" if fraction < GC_MIN else "high"
        # Overlapping windows merge only when they fail the same way. A GC-poor
        # stretch running into a GC-rich one overlaps at the transition, and
        # merging those would report one span labelled with whichever came
        # first - a region described as the opposite of half of itself.
        if out and start + 1 <= out[-1]["end"] and out[-1]["direction"] == direction:
            out[-1]["end"] = start + window
            out[-1]["extreme"] = (
                min(out[-1]["extreme"], round(fraction, 3))
                if direction == "low"
                else max(out[-1]["extreme"], round(fraction, 3))
            )
        else:
            out.append(
                {
                    "start": start + 1,
                    "end": start + window,
                    "extreme": round(fraction, 3),
                    "direction": direction,
                }
            )
    return out


def reverse_complement(dna: str) -> str:
    return dna.upper().translate(_COMPLEMENT)[::-1]


def site_hits(dna: str, sites: Mapping[str, str]) -> list[dict[str, Any]]:
    """Every occurrence of a forbidden site, on either strand, 1-based."""
    text = dna.upper()
    found: list[dict[str, Any]] = []
    for name, site in sorted(sites.items()):
        pattern = site.upper()
        for strand, needle in (("+", pattern), ("-", reverse_complement(pattern))):
            if strand == "-" and needle == pattern:
                continue  # palindromic: the same hits, counted twice
            start = text.find(needle)
            while start != -1:
                found.append(
                    {
                        "enzyme": name,
                        "site": pattern,
                        "strand": strand,
                        "start": start + 1,
                        "end": start + len(needle),
                    }
                )
                start = text.find(needle, start + 1)
    return sorted(found, key=lambda hit: (hit["start"], hit["enzyme"]))


def homopolymer_runs(dna: str, *, limit: int = MAX_HOMOPOLYMER) -> list[dict[str, Any]]:
    """Runs of one base longer than the limit, 1-based and inclusive."""
    text = dna.upper()
    runs: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(text) + 1):
        if index < len(text) and text[index] == text[start]:
            continue
        length = index - start
        if length > limit:
            runs.append({"base": text[start], "start": start + 1, "end": index, "length": length})
        start = index
    return runs


def _violates(candidate: str, tail: str, sites: Mapping[str, str], limit: int) -> bool:
    """Would appending this codon create a forbidden site or a long run?

    Only the join is re-examined: everything before `tail` was already checked
    when it was written, so this stays linear in the length of the construct
    rather than quadratic.
    """
    combined = tail + candidate
    for site in sites.values():
        pattern = site.upper()
        for needle in {pattern, reverse_complement(pattern)}:
            # A site can only be new if it overlaps the codon just added.
            if needle in combined and combined.rfind(needle) + len(needle) > len(tail):
                return True
    run = 1
    for index in range(len(combined) - 1, 0, -1):
        if combined[index] != combined[index - 1]:
            break
        run += 1
    return run > limit


def back_translate(
    protein: str,
    *,
    host: str,
    avoid_sites: Mapping[str, str] | None = None,
    max_homopolymer: int = MAX_HOMOPOLYMER,
    add_stop: bool = True,
) -> dict[str, Any]:
    """DNA for this protein, choosing the host's preferred codon where it can.

    Greedy with one step of backtracking, and deterministic. At each residue
    the highest-weighted synonymous codon that creates no forbidden site and no
    long homopolymer run is taken.

    The backtracking is not an optimisation, it is the difference between
    working and not: a site is usually formed *across* a codon boundary, and
    the residue that could avoid it is often the one already written. His-Met
    spells CAT ATG, which is NdeI - and methionine has no second codon, so the
    only repair is to re-spell the histidine as CAC. Without a lookback every
    His-Met in a construct would be an unavoidable site, which is wrong.

    When even that fails, the highest-weighted codon is used and the position
    is reported in `compromises`: a construct with a stated problem is more
    useful than a silent change to the protein, which is not ours to make.
    """
    residues = _residues(protein)
    table = _table(host)
    weights = relative_adaptiveness(host)
    families = synonymous_codons(table["translation_table"])
    sites = dict(DEFAULT_AVOID_SITES if avoid_sites is None else avoid_sites)
    longest_site = max((len(site) for site in sites.values()), default=0)
    keep = max(longest_site, max_homopolymer) + 3

    def ranked_for(residue: str, position: int) -> list[str]:
        codons = families.get(residue)
        if not codons:
            raise CodonError(
                f"Residue {residue!r} at position {position} has no codon in translation table "
                f"{table['translation_table']}."
            )
        return sorted(codons, key=lambda codon: (-weights.get(codon, 0.0), codon))

    pieces: list[str] = []
    compromises: list[dict[str, Any]] = []
    respelled: list[dict[str, Any]] = []
    for index, residue in enumerate(residues, start=1):
        ranked = ranked_for(residue, index)
        tail = "".join(pieces)[-keep:] if pieces else ""
        chosen = next(
            (codon for codon in ranked if not _violates(codon, tail, sites, max_homopolymer)),
            None,
        )

        if chosen is None and pieces:
            # Re-spell the previous residue, best alternative first, and keep
            # the first pairing that clears the constraint.
            previous_ranked = ranked_for(residues[index - 2], index - 1)
            before = "".join(pieces[:-1])[-keep:]
            for alternative in previous_ranked:
                if alternative == pieces[-1]:
                    continue
                if _violates(alternative, before, sites, max_homopolymer):
                    continue
                retry_tail = (before + alternative)[-keep:]
                candidate = next(
                    (
                        codon
                        for codon in ranked
                        if not _violates(codon, retry_tail, sites, max_homopolymer)
                    ),
                    None,
                )
                if candidate is None:
                    continue
                respelled.append(
                    {
                        "position": index - 1,
                        "residue": residues[index - 2],
                        "from_codon": pieces[-1],
                        "to_codon": alternative,
                        "reason": f"the preferred codon would have formed a site with position {index}",
                    }
                )
                pieces[-1] = alternative
                chosen = candidate
                break

        if chosen is None:
            chosen = ranked[0]
            compromises.append(
                {
                    "position": index,
                    "residue": residue,
                    "codon": chosen,
                    "reason": "every synonymous codon would create a forbidden site or a long run",
                }
            )
        pieces.append(chosen)

    if add_stop:
        # TAA is the most used stop in both counted hosts and is the least
        # likely to be read through; the choice is stated rather than derived,
        # because a stop codon has no synonymous family to weigh.
        pieces.append("TAA")

    return {"dna": "".join(pieces), "compromises": compromises, "respelled": respelled}


def assess(dna: str, *, host: str, avoid_sites: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Everything measurable about a coding sequence, for any DNA."""
    text = dna.upper()
    if not text or not set(text) <= _BASES:
        raise CodonError("A coding sequence must be A, C, G and T only.")
    sites = dict(DEFAULT_AVOID_SITES if avoid_sites is None else avoid_sites)
    weights = relative_adaptiveness(host)
    table = _table(host)
    families = synonymous_codons(table["translation_table"])
    rare = {
        codon
        for codons in families.values()
        for codon in codons
        if len(codons) > 1 and weights.get(codon, 1.0) < RARE_CODON_FRACTION
    }
    used_rare = [
        {"position": index + 1, "codon": codon, "weight": round(weights.get(codon, 0.0), 3)}
        for index, codon in enumerate(codons_of(text))
        if codon in rare
    ]
    return {
        "length_nt": len(text),
        "cai": round(cai(text, host), 4),
        "gc": round(gc_fraction(text), 4),
        "gc3": round(gc3(text), 4),
        "gc_windows_outside_band": gc_windows(text),
        "gc_band": {"window": GC_WINDOW, "min": GC_MIN, "max": GC_MAX},
        "forbidden_sites": site_hits(text, sites),
        "homopolymer_runs": homopolymer_runs(text),
        "rare_codons": used_rare,
        "rare_codon_threshold": RARE_CODON_FRACTION,
    }


def optimise(
    protein: str,
    *,
    host: str,
    avoid_sites: Mapping[str, str] | None = None,
    max_homopolymer: int = MAX_HOMOPOLYMER,
    add_stop: bool = True,
    prefix: str = "",
    suffix: str = "",
) -> dict[str, Any]:
    """A construct for this protein, with what it is made of stated.

    `prefix` and `suffix` are added verbatim - a start codon, a tag, an
    overhang for the assembly method - and are measured along with the rest,
    because a site that spans the junction is still a site.
    """
    for label, flank in (("prefix", prefix), ("suffix", suffix)):
        if flank and not set(flank.upper()) <= _BASES:
            raise CodonError(f"The {label} must be A, C, G and T only.")

    built = back_translate(
        protein,
        host=host,
        avoid_sites=avoid_sites,
        max_homopolymer=max_homopolymer,
        add_stop=add_stop,
    )
    table = _table(host)
    # Proved here rather than left to the caller: every path that produces a
    # construct goes through this function, and a frame error would otherwise
    # leave a plausible ordering form for a different molecule. Checked on the
    # insert, before the flanks - those are verbatim and may be out of frame by
    # design (an overhang, a partial codon of a vector).
    ensure_round_trip(protein, built["dna"], translation_table=table["translation_table"])
    dna = f"{prefix.upper()}{built['dna']}{suffix.upper()}"
    return {
        "dna": dna,
        "host": {
            "key": host,
            "label": table["label"],
            "organism": table["organism"],
            "taxon_id": table["taxon_id"],
            "translation_table": table["translation_table"],
            "cds_counted": table["cds_counted"],
            "codons_counted": table["codons_counted"],
        },
        "protein_length": len(_residues(protein)),
        "flanks": {"prefix": prefix.upper(), "suffix": suffix.upper(), "stop_added": add_stop},
        "compromises": built["compromises"],
        "respelled": built["respelled"],
        "assessment": assess(dna, host=host, avoid_sites=avoid_sites),
    }


def translate(dna: str, *, translation_table: int = 11) -> str:
    """What the DNA codes for, so a caller can check the round trip."""
    forward = CodonTable.unambiguous_dna_by_id[translation_table].forward_table
    stops = set(CodonTable.unambiguous_dna_by_id[translation_table].stop_codons)
    residues: list[str] = []
    for codon in codons_of(dna):
        if codon in stops:
            break
        residue = forward.get(codon)
        if residue is None:
            raise CodonError(f"Codon {codon!r} is not in translation table {translation_table}.")
        residues.append(residue)
    return "".join(residues)


def ensure_round_trip(protein: str, dna: str, *, translation_table: int) -> None:
    """Fail loudly if the DNA does not code for the protein it was built from.

    Called on every optimisation. The whole value of this module is that the
    construct is the protein; a silent frame error would produce a plausible
    ordering form for the wrong molecule.
    """
    expected = _residues(protein)
    actual = translate(dna, translation_table=translation_table)
    if actual != expected:
        raise SequenceError(
            "The optimised DNA does not translate back to the protein it was built from."
        )


def available_sites() -> dict[str, str]:
    """The forbidden-site set a caller gets when it does not name one."""
    return dict(DEFAULT_AVOID_SITES)


def known_hosts() -> Sequence[str]:
    return sorted(CODON_USAGE)
