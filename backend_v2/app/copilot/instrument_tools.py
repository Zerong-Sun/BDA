"""Read-only instrument analysis from completed, checksummed project artifacts."""
from __future__ import annotations

from typing import Any

from ..core.problem import DomainError
from ..identity.models import User
from ..projects.service import require_project
from ..wetlab import analysis
from ..wetlab.schemas import BliAnalysisRequest
from .registry import ToolContext, ToolRegistry, ToolSpec


def preview_bli_artifact(context: ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    if context.project_id is None or context.user_id is None:
        raise DomainError("copilot_project_context_required", "Instrument analysis requires an authenticated project.", status_code=422)
    user = context.session.get(User, context.user_id)
    if user is None:
        raise DomainError("user_not_found", "User was not found.", status_code=404)
    require_project(context.session, context.project_id, user)
    request = BliAnalysisRequest.model_validate(arguments)
    artifact = analysis._load_artifact(context.session, context.project_id, request.artifact_id)
    parameters = request.model_dump(exclude={"artifact_id", "candidate_id", "supersedes_result_id"})
    measurement, summary = analysis.analyse_bli_bytes(analysis._read(artifact), **parameters)
    # A model reads the numeric evidence and QC, while the UI renders full saved
    # plot snapshots. Do not flood its context with thousands of trace points.
    summary["curves"] = [{key: value for key, value in curve.items() if not key.endswith("points")}
                         | {"displayed_measured_points": len(curve["points"])} for curve in summary["curves"]]
    return {"persisted": False, "source_artifact_id": str(artifact.id),
            "source_checksum_sha256": artifact.checksum_sha256,
            "analysis_version": measurement["analysis_version"], "value": measurement["value"],
            "unit": measurement["unit"], "summary": summary}


def register(registry: ToolRegistry) -> None:
    schema = BliAnalysisRequest.model_json_schema()
    for field in ("candidate_id", "supersedes_result_id"):
        schema["properties"].pop(field)
    schema["additionalProperties"] = False
    registry.register(ToolSpec(
        id="preview_bli_artifact",
        description=("Read a completed project BLI artifact, verify its hash and preview analysis without saving. "
                     "Detects ForteBio and Time/Data/Fit kinetic triplets. First inspect sensors, then explicitly map "
                     "sensor labels to samples. Triplet measured fitting requires an absolute dissociation switch. "
                     "Instrument-derived kinetics have no independent precision estimate. Saving uses analyse_bli_run."),
        parameters=schema, capability="wetlab-authoring", execution_mode="read", requires="session",
        handler=preview_bli_artifact,
    ))
