"""Output parser contract."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedMetric:
    """One number a method produced about a candidate.

    Reported separately from ``scores`` so it lands in a queryable row carrying its own
    provenance, rather than being flattened into an opaque blob.
    """

    key: str
    value: float
    method: str
    model_variant: str = ""
    # "predicted" for anything a model inferred, "measured" only for real observation.
    evidence_kind: str = "predicted"
    # Who produced it: "design_model" when the model is scoring its own output,
    # "independent_model" for a separate cross-check, "experiment" for a measurement.
    # A design model's own score is self-assessment, not corroboration.
    assessor: str = "unknown"
    # What the value is about beyond the candidate - the ligand it was scored against,
    # the binding partner. Part of the metric's identity, so a panel accumulates.
    condition: str = ""
    unit: str = ""
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedCandidate:
    """A design the job produced. ``candidate_key`` is unique within a project."""

    candidate_key: str
    name: str | None = None
    status: str = "generated"
    rank: int | None = None
    score: float | None = None
    scores: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)
    # Index into the job's collected outputs that holds this candidate's structure.
    structure_output_index: int | None = None
    complex_output_index: int | None = None
    # Attached even when the candidate already exists, so a second method scoring an
    # earlier design records its numbers instead of dropping them.
    metrics: list[ParsedMetric] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedExperimentResult:
    experiment_type: str
    candidate_ref: str | None = None
    pass_status: str = "unknown"
    value: float | None = None
    unit: str | None = None
    conclusion: str | None = None
    failure_reason: str | None = None
    batch_key: str | None = None
    metadata: dict = field(default_factory=dict)
    source_output_index: int | None = None


@dataclass(frozen=True)
class ParsedOutputs:
    candidates: list[ParsedCandidate] = field(default_factory=list)
    results: list[ParsedExperimentResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParseContext:
    """Everything a parser may look at.

    ``read_bytes`` is injected rather than imported so parsers stay unit-testable
    without object storage.
    """

    job_id: uuid.UUID
    project_id: uuid.UUID
    attempt_number: int
    outputs: list[dict]
    parameters: dict
    read_bytes: Callable[[str], bytes]


Parser = Callable[[ParseContext], ParsedOutputs]

_REGISTRY: dict[str, Parser] = {}

DEFAULT_PARSER = "manifest_metadata"


def register_parser(name: str) -> Callable[[Parser], Parser]:
    def decorator(func: Parser) -> Parser:
        _REGISTRY[name] = func
        return func

    return decorator


def get_parser(name: str | None) -> Parser:
    """Resolve a parser, falling back to the manifest-metadata behaviour."""
    return _REGISTRY.get(name or DEFAULT_PARSER, _REGISTRY[DEFAULT_PARSER])


def available_parsers() -> list[str]:
    return sorted(_REGISTRY)
