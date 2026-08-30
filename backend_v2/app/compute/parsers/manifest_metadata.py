"""Default parser: trust what the runner declared in the output manifest.

This is a faithful extraction of the logic that used to live inline in ``collect_job``,
kept so plugins written before the parser interface behave identically.
"""

from __future__ import annotations

from .base import ParseContext, ParsedCandidate, ParsedExperimentResult, ParsedOutputs, register_parser

STRUCTURE_TYPES = frozenset({"structure", "candidate_structure"})


@register_parser("manifest_metadata")
def parse(ctx: ParseContext) -> ParsedOutputs:
    candidates: list[ParsedCandidate] = []
    results: list[ParsedExperimentResult] = []

    for index, output in enumerate(ctx.outputs):
        raw_metadata = output.get("metadata")
        metadata: dict = raw_metadata if isinstance(raw_metadata, dict) else {}

        payload = metadata.get("candidate")
        candidate_key = None
        if isinstance(payload, dict):
            candidate_key = str(payload.get("candidate_key") or output["filename"])
            candidates.append(
                ParsedCandidate(
                    candidate_key=candidate_key,
                    name=str(payload.get("name") or candidate_key),
                    status=str(payload.get("status") or "generated"),
                    rank=payload.get("rank"),
                    score=payload.get("score"),
                    scores=payload.get("scores") or {},
                    properties=payload.get("properties") or {},
                    structure_output_index=index if output["artifact_type"] in STRUCTURE_TYPES else None,
                    complex_output_index=index if output["artifact_type"] == "candidate_complex" else None,
                )
            )

        result_payload = metadata.get("experiment_result")
        if isinstance(result_payload, dict) and result_payload.get("experiment_type"):
            results.append(
                ParsedExperimentResult(
                    experiment_type=str(result_payload["experiment_type"]),
                    candidate_ref=result_payload.get("candidate_ref") or candidate_key,
                    pass_status=str(result_payload.get("pass_status") or "unknown"),
                    value=result_payload.get("value"),
                    unit=result_payload.get("unit"),
                    conclusion=result_payload.get("conclusion"),
                    failure_reason=result_payload.get("failure_reason"),
                    batch_key=result_payload.get("batch_key"),
                    metadata=result_payload.get("metadata") or {},
                    source_output_index=index,
                )
            )

    return ParsedOutputs(candidates=candidates, results=results)
