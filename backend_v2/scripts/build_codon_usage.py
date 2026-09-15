#!/usr/bin/env python3
"""Compute a host's codon usage from its annotated genome, and write it down.

Codon optimisation needs a table of how often each synonymous codon is actually
used by the expression host. The obvious source is a published table, and the
obvious published tables are unusable here: Kazusa's *E. coli* K-12 page is
built from 14 coding sequences, its *Pichia pastoris* page from 137. A table
that thin makes "the preferred codon" a coin toss, and nothing downstream would
show that.

So the tables are computed from the annotated genome instead, and the numbers
carry where they came from: accession, sequence version, how many coding
sequences were counted, how many were rejected and why. A reviewer who doubts a
weight can re-run this script and diff the output.

    PYTHONPATH=. backend_v2/.venv/bin/python backend_v2/scripts/build_codon_usage.py

This is an offline generator, not part of the service: it reaches the network,
CI never runs it, and its output - `backend_v2/app/sequences/codon_usage.py` -
is committed. Re-run it only to add a host or to move to a newer assembly, and
commit the regenerated module with the reason.

What is counted, and what is not:

* only CDS features whose location is exact - a partial gene (`<1..500`) has no
  reading frame this can trust;
* only lengths that are a multiple of three, and only codons of A/C/G/T - an
  ambiguity code is not a codon;
* pseudogenes are skipped: their codon choices are not under translational
  selection, which is the whole basis of the weights;
* the terminal stop codon is dropped, and internal stops reject the CDS
  outright as a frame or annotation error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature

#: EMBL flat files with features, from EBI's dbfetch. ENA is used rather than
#: NCBI because this host cannot reach NCBI's E-utilities.
_DBFETCH = "https://www.ebi.ac.uk/Tools/dbfetch/dbfetch?db=ena_sequence&id={accession}&format=embl&style=raw"

_BASES = frozenset("ACGT")


@dataclass(frozen=True)
class Host:
    """An expression host, and the records its coding sequences live in."""

    key: str
    label: str
    organism: str
    taxon_id: int
    #: NCBI genetic code id, as Biopython numbers translation tables.
    translation_table: int
    accessions: tuple[str, ...]
    note: str


HOSTS: tuple[Host, ...] = (
    Host(
        key="ecoli_k12",
        label="Escherichia coli K-12 MG1655",
        organism="Escherichia coli str. K-12 substr. MG1655",
        taxon_id=511145,
        translation_table=11,
        accessions=("U00096",),
        note="The standard laboratory K-12 genome; one circular record carrying every CDS.",
    ),
    Host(
        key="scerevisiae_s288c",
        label="Saccharomyces cerevisiae S288C",
        organism="Saccharomyces cerevisiae S288C",
        taxon_id=559292,
        translation_table=1,
        # Sixteen nuclear chromosomes, one record each. The mitochondrial
        # genome is deliberately absent: it uses a different genetic code, and
        # mixing it into a nuclear table would corrupt the weights.
        accessions=(
            "BK006935", "BK006936", "BK006937", "BK006938", "BK006939", "BK006940",
            "BK006941", "BK006942", "BK006943", "BK006944", "BK006945", "BK006946",
            "BK006947", "BK006948", "BK006949", "BK006934",
        ),
        note="Sixteen nuclear chromosomes. Mitochondrial DNA excluded: different genetic code.",
    ),
)


def fetch(accession: str, cache: Path) -> str:
    """The EMBL record, from the cache if it is already there.

    Cached because a genome is several megabytes and adding a host should not
    re-download the ones that already worked.
    """
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{accession}.embl"
    if path.exists() and path.stat().st_size > 0:
        return path.read_text()
    url = _DBFETCH.format(accession=accession)
    try:
        with urllib.request.urlopen(url, timeout=300) as response:  # noqa: S310 - fixed https host
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:  # pragma: no cover - network failure path
        raise SystemExit(f"{accession}: could not be fetched from ENA ({error})") from error
    if not text.startswith("ID   "):
        raise SystemExit(f"{accession}: ENA returned something that is not an EMBL record")
    path.write_text(text)
    return text


def _coding_sequence(feature: SeqFeature, record_sequence: Seq) -> Seq | None:
    """The CDS, or None when it is not one this can count."""
    if feature.location is None:
        return None
    # `str(location)` carries `<`/`>` for a partial end; Biopython models them
    # as fuzzy positions, and either way the reading frame is a guess.
    if "<" in str(feature.location) or ">" in str(feature.location):
        return None
    if "pseudo" in feature.qualifiers or "pseudogene" in feature.qualifiers:
        return None
    try:
        return feature.extract(record_sequence)
    except Exception:  # pragma: no cover - malformed location
        return None


def count_record(text: str, *, translation_table: int) -> tuple[Counter[str], dict[str, int]]:
    """Codon counts for one EMBL record, and why anything was rejected."""
    from io import StringIO

    counts: Counter[str] = Counter()
    rejected = Counter({"partial_or_pseudo": 0, "not_a_triplet": 0, "internal_stop": 0, "ambiguous": 0})
    accepted = 0

    stops = {
        codon
        for codon, residue in _forward_and_stops(translation_table).items()
        if residue == "*"
    }

    for record in SeqIO.parse(StringIO(text), "embl"):
        for feature in record.features:
            if feature.type != "CDS":
                continue
            coding = _coding_sequence(feature, record.seq)
            if coding is None:
                rejected["partial_or_pseudo"] += 1
                continue
            sequence = str(coding).upper()
            if len(sequence) < 6 or len(sequence) % 3:
                rejected["not_a_triplet"] += 1
                continue
            codons = [sequence[index : index + 3] for index in range(0, len(sequence), 3)]
            if codons[-1] in stops:
                codons = codons[:-1]
            if any(codon in stops for codon in codons):
                rejected["internal_stop"] += 1
                continue
            if any(not set(codon) <= _BASES for codon in codons):
                rejected["ambiguous"] += 1
                continue
            counts.update(codons)
            accepted += 1

    summary = dict(rejected)
    summary["accepted_cds"] = accepted
    return counts, summary


def _forward_and_stops(translation_table: int) -> dict[str, str]:
    """Every codon mapped to its residue, with stops as `*`."""
    from Bio.Data import CodonTable

    table = CodonTable.unambiguous_dna_by_id[translation_table]
    mapping = dict(table.forward_table)
    for codon in table.stop_codons:
        mapping[codon] = "*"
    return mapping


def build(host: Host, cache: Path) -> dict[str, Any]:
    """One host's table, with the provenance a reader needs to check it."""
    counts: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    for accession in host.accessions:
        record_counts, summary = count_record(
            fetch(accession, cache), translation_table=host.translation_table
        )
        counts.update(record_counts)
        rejected.update(summary)
        print(f"  {accession}: {summary['accepted_cds']} CDS, {sum(record_counts.values())} codons", file=sys.stderr)
    if not counts:
        raise SystemExit(f"{host.key}: no coding sequences were counted")
    return {
        "key": host.key,
        "label": host.label,
        "organism": host.organism,
        "taxon_id": host.taxon_id,
        "translation_table": host.translation_table,
        "accessions": list(host.accessions),
        "note": host.note,
        "cds_counted": int(rejected.get("accepted_cds", 0)),
        "cds_rejected": {
            key: int(value) for key, value in sorted(rejected.items()) if key != "accepted_cds"
        },
        "codons_counted": int(sum(counts.values())),
        "counts": {codon: int(counts[codon]) for codon in sorted(counts)},
    }


_HEADER = '''"""Codon usage per expression host, counted from annotated genomes.

Generated by `backend_v2/scripts/build_codon_usage.py` - do not edit by hand.
Re-run that script to add a host or move to a newer assembly.

Each entry carries the accessions it was counted from and how many coding
sequences survived the filters, because a codon weight is only as good as the
number of genes behind it. Counts are raw occurrences; the relative
adaptiveness a CAI needs is derived in `app/sequences/codon.py`, so the data
here stays the measurement and the weighting stays a decision.

Retrieved from EBI/ENA on {date}.
"""

from __future__ import annotations

from typing import Any

#: Keyed by host id. Counts exclude the terminal stop codon; see the generator.
CODON_USAGE: dict[str, dict[str, Any]] = {{
'''


def render(tables: list[dict[str, Any]], date: str) -> str:
    lines = [_HEADER.format(date=date)]
    for table in tables:
        lines.append(f"    {table['key']!r}: {{\n")
        for field in ("label", "organism", "taxon_id", "translation_table", "note"):
            lines.append(f"        {field!r}: {table[field]!r},\n")
        lines.append(f"        'accessions': {table['accessions']!r},\n")
        lines.append(f"        'cds_counted': {table['cds_counted']!r},\n")
        lines.append(f"        'cds_rejected': {table['cds_rejected']!r},\n")
        lines.append(f"        'codons_counted': {table['codons_counted']!r},\n")
        lines.append("        'counts': {\n")
        codons = sorted(table["counts"])
        for index in range(0, len(codons), 4):
            row = "".join(f"{codon!r}: {table['counts'][codon]}, " for codon in codons[index : index + 4])
            lines.append(f"            {row.rstrip()}\n")
        lines.append("        },\n")
        lines.append("    },\n")
    lines.append("}\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append", choices=[host.key for host in HOSTS], default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "app" / "sequences" / "codon_usage.py",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(os.environ.get("BDA_ENA_CACHE") or Path(tempfile.gettempdir()) / "bda-ena-cache"),
        help=(
            "Where downloaded EMBL records are kept between runs. Outside the repository "
            "by default: these are tens of megabytes of public genome records, and this "
            "repository holds software only."
        ),
    )
    args = parser.parse_args()

    wanted = [host for host in HOSTS if args.host is None or host.key in args.host]
    tables = []
    for host in wanted:
        print(f"{host.key}: {host.label}", file=sys.stderr)
        tables.append(build(host, args.cache))

    text = render(tables, dt.date.today().isoformat())
    args.out.write_text(text)
    for table in tables:
        print(
            f"{table['key']}: {table['cds_counted']} CDS, {table['codons_counted']} codons"
            f" -> {args.out}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
