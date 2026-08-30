"""Reference parser: ProteinMPNN FASTA output.

Shows what a real parser looks like — the platform reads the model's native output
instead of requiring the container to emit BDA-shaped JSON.

ProteinMPNN writes FASTA whose headers carry comma-separated key=value scores, e.g.::

    >3HTN, score=1.1387, global_score=1.2686, seq_recovery=0.3448
    >T=0.1, sample=1, score=0.9126, global_score=1.1197, seq_recovery=0.4310

The first record is the input backbone's native sequence; subsequent records are the
designs. Lower ``score`` is better, so rank ascends with score.
"""

from __future__ import annotations

from .base import ParseContext, ParsedCandidate, ParsedOutputs, register_parser

FASTA_SUFFIXES = (".fa", ".fasta", ".fas")


@register_parser("proteinmpnn_fasta")
def parse(ctx: ParseContext) -> ParsedOutputs:
    candidates: list[ParsedCandidate] = []
    warnings: list[str] = []

    for output in ctx.outputs:
        if not output["filename"].lower().endswith(FASTA_SUFFIXES):
            continue
        try:
            text = ctx.read_bytes(output["object_key"]).decode("utf-8", errors="strict")
        except (UnicodeDecodeError, KeyError, OSError) as exc:
            warnings.append(f"{output['filename']}: unreadable ({type(exc).__name__})")
            continue

        stem = output["filename"].rsplit(".", 1)[0]
        for sample, (header, sequence) in enumerate(_records(text)):
            scores = _header_scores(header)
            if sample == 0 and "sample" not in scores:
                # The native input sequence, not a design.
                continue
            score = scores.get("score")
            candidates.append(
                ParsedCandidate(
                    candidate_key=f"{stem}_sample{int(scores.get('sample', sample))}",
                    name=f"{stem} sample {int(scores.get('sample', sample))}",
                    status="generated",
                    score=score,
                    scores={key: value for key, value in scores.items() if key != "sample"},
                    properties={"sequence": sequence, "length": len(sequence)},
                    structure_output_index=None,
                )
            )

    ranked = sorted(
        range(len(candidates)), key=lambda i: (candidates[i].score is None, candidates[i].score or 0.0)
    )
    candidates = [
        ParsedCandidate(**{**candidates[position].__dict__, "rank": rank + 1})
        for rank, position in enumerate(ranked)
    ]
    if not candidates:
        warnings.append("no ProteinMPNN FASTA designs found in job outputs")
    return ParsedOutputs(candidates=candidates, warnings=warnings)


def _records(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(chunks)))
            header, chunks = line[1:].strip(), []
        elif header is not None and line.strip():
            chunks.append(line.strip())
    if header is not None:
        records.append((header, "".join(chunks)))
    return records


def _header_scores(header: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for token in header.split(","):
        key, separator, raw = token.partition("=")
        if not separator:
            continue
        try:
            scores[key.strip()] = float(raw.strip())
        except ValueError:
            continue
    return scores
