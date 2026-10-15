"""Versioned, deterministic protein representations; no downloaded model weights."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Protocol

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
COMPOSITION_VERSION = "aa-composition-length-v1"
SEQUENCE_VERSION = "sequence-order-v1"


class FeatureExtractor(Protocol):
    version: str
    dimensions: int

    def extract(self, sequence: str) -> list[float]: ...


class CompositionFeatures:
    version = COMPOSITION_VERSION
    dimensions = 21

    def extract(self, sequence: str) -> list[float]:
        counts = Counter(sequence)
        return [counts[aa] / len(sequence) for aa in AMINO_ACIDS] + [math.log1p(len(sequence)) / 10]


class SequenceOrderFeatures:
    version = SEQUENCE_VERSION
    dimensions = 461

    def extract(self, sequence: str) -> list[float]:
        # Ordered adjacent pairs distinguish equal-composition rearrangements.
        # Terminal windows add positional information; neither encodes structure.
        pairs = Counter(sequence[index : index + 2] for index in range(len(sequence) - 1))
        vector = CompositionFeatures().extract(sequence)
        vector.extend(pairs[a + b] / max(1, len(sequence) - 1) for a in AMINO_ACIDS for b in AMINO_ACIDS)
        width = max(1, math.ceil(len(sequence) * 0.1))
        for terminal in (sequence[:width], sequence[-width:]):
            counts = Counter(terminal)
            vector.extend(counts[aa] / width for aa in AMINO_ACIDS)
        return vector


EXTRACTORS: dict[str, FeatureExtractor] = {
    extractor.version: extractor for extractor in (CompositionFeatures(), SequenceOrderFeatures())
}


def extract(sequence: str, version: str = COMPOSITION_VERSION) -> dict:
    sequence = "".join(sequence.split()).upper()
    if not sequence or len(sequence) > 10_000 or set(sequence) - set(AMINO_ACIDS):
        raise ValueError("A canonical protein sequence of 1–10000 residues is required")
    extractor = EXTRACTORS.get(version)
    if extractor is None:
        raise ValueError("Unsupported frozen feature version")
    return {
        "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
        "feature_version": version,
        "features": extractor.extract(sequence),
    }


def validate_rows(rows: list[dict]) -> str:
    versions = {r.get("feature_version", COMPOSITION_VERSION) for r in rows}
    if len(versions) != 1 or next(iter(versions)) not in EXTRACTORS:
        raise ValueError("Training requires one supported frozen feature version")
    version = next(iter(versions))
    vectors: dict[str, list[float]] = {}
    for row in rows:
        vector = row["features"]
        if len(vector) != EXTRACTORS[version].dimensions or any(not math.isfinite(v) for v in vector):
            raise ValueError("Frozen features have invalid dimensions or non-finite values")
        if not math.isfinite(row["value"]):
            raise ValueError("Training measurements must be finite")
        key = row["sequence_sha256"]
        if key in vectors and vectors[key] != vector:
            raise ValueError("Identical sequences must have identical frozen features")
        vectors[key] = vector
    return version
