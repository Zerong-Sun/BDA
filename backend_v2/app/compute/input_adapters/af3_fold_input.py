"""Build AlphaFold 3's ``fold_input.json`` from bound sequence inputs.

AF3 does not read a FASTA. It reads a JSON job specification with the sequences inside,
which meant an AF3 node could only ever take a hand-authored file and could not sit
downstream of a sequence-producing node such as ProteinMPNN.

This adapter closes that gap: bind sequences to AF3's ``sequences`` port and the JSON is
generated at dispatch.

The emitted shape follows AF3's documented input format::

    {
      "name": "...",
      "modelSeeds": [1],
      "sequences": [{"protein": {"id": "A", "sequence": "MKT..."}}],
      "dialect": "alphafold3",
      "version": 1
    }

Verify it against the AF3 build actually installed before relying on it for science; the
format has changed across AF3 releases and this has not been run against a real AF3.
"""

from __future__ import annotations

import json
import re

from .base import AdapterContext, AdapterResult, GeneratedInput, register_input_adapter

FOLD_INPUT_PORT = "json_path"
SEQUENCE_PORT = "sequences"
FASTA_SUFFIXES = (".fa", ".fasta", ".fas", ".faa", ".seq")

# AF3 chain ids: A..Z then AA, AB, ... Long jobs exceed the alphabet.
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Anything that is not a standard residue letter; keeps 'X' since it is a valid unknown.
_NON_RESIDUE = re.compile(r"[^ACDEFGHIKLMNPQRSTVWYX]", re.I)

# Chosen to keep a run reproducible. Override with the `model_seeds` parameter.
DEFAULT_SEEDS = [1]


def chain_id(index: int) -> str:
    label = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = _ALPHABET[remainder] + label
    return label


def parse_fasta(text: str) -> list[tuple[str, str]]:
    """Return (header, sequence) pairs. Tolerates blank lines and CRLF."""
    records: list[tuple[str, str]] = []
    header: str | None = None
    chunks: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(chunks)))
            header, chunks = line[1:].strip(), []
        elif line and header is not None:
            chunks.append(line)
    if header is not None:
        records.append((header, "".join(chunks)))
    return [(name, seq.upper()) for name, seq in records if seq]


def build_fold_input(
    records: list[tuple[str, str]],
    *,
    name: str,
    model_seeds: list[int] | None = None,
) -> dict:
    """Assemble the AF3 job specification.

    Every record becomes its own chain, so a multi-record FASTA is folded as a complex —
    which is what a designed binder plus its target looks like coming out of an upstream
    design node.
    """
    sequences = [
        {"protein": {"id": chain_id(index), "sequence": sequence}}
        for index, (_header, sequence) in enumerate(records)
    ]
    return {
        "name": name,
        "modelSeeds": list(model_seeds or DEFAULT_SEEDS),
        "sequences": sequences,
        "dialect": "alphafold3",
        "version": 1,
    }


@register_input_adapter("af3_fold_input")
def adapt(ctx: AdapterContext) -> AdapterResult:
    warnings: list[str] = []

    # An explicitly bound fold_input.json always wins; the adapter is a convenience, not
    # a mandate, and a hand-tuned specification must not be silently overwritten.
    if any(item.get("port") == FOLD_INPUT_PORT for item in ctx.inputs):
        return AdapterResult(warnings=["fold_input.json was bound explicitly; not generated"])

    sources = [
        item
        for item in ctx.inputs
        if item.get("port") == SEQUENCE_PORT
        or str(item.get("filename", "")).lower().endswith(FASTA_SUFFIXES)
    ]
    if not sources:
        return AdapterResult(warnings=["no sequence input bound; AlphaFold 3 needs one"])

    records: list[tuple[str, str]] = []
    for item in sources:
        try:
            text = ctx.read_bytes(str(item["object_key"])).decode("utf-8", errors="strict")
        except (UnicodeDecodeError, KeyError, OSError) as exc:
            warnings.append(f"{item.get('filename')}: unreadable ({type(exc).__name__})")
            continue
        parsed = parse_fasta(text)
        if not parsed:
            warnings.append(f"{item.get('filename')}: no FASTA records found")
        records.extend(parsed)

    if not records:
        return AdapterResult(warnings=[*warnings, "no sequences could be read from the bound inputs"])

    invalid = [name for name, sequence in records if _NON_RESIDUE.search(sequence)]
    if invalid:
        # Non-protein polymers need a different AF3 entity type, which this adapter does
        # not emit. Failing loudly beats folding a silently mangled sequence.
        raise ValueError(
            "af3_fold_input_non_protein_residues:" + ",".join(invalid[:5])
        )

    seeds = ctx.parameters.get("model_seeds")
    if not isinstance(seeds, list) or not all(isinstance(item, int) for item in seeds):
        seeds = None

    payload = build_fold_input(
        records,
        name=ctx.job_name or f"bda-{ctx.job_id.hex[:12]}",
        model_seeds=seeds,
    )
    return AdapterResult(
        generated=[
            GeneratedInput(
                port=FOLD_INPUT_PORT,
                filename="fold_input.json",
                content=json.dumps(payload, indent=2).encode("utf-8"),
            )
        ],
        warnings=warnings,
    )
