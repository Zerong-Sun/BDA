"""Source-backed scientific gate approvals, bound to immutable execution settings.

Candidate and review events are append-only audit records. Graph JSON is never an
approval authority. No literature request or model computation runs in dispatch.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from ..artifacts.models import Artifact
from ..audit.models import AuditLog
from ..audit.service import record_audit
from ..core.problem import DomainError
from ..core.trace import current_trace_id
from ..literature.models import LiteratureChunk, LiteratureDocument
from ..projects.service import require_project_permission
from ..registry.models import ModelPlugin
from .gate_schemas import GatePolicy
from .gate_service import _workflow
from .repository import WorkflowRepository

CANDIDATE = "workflow.scientific_gate.candidate"
REVIEW = "workflow.scientific_gate.review"
SCHEMA_VERSION = "1"


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    quote: str = Field(min_length=12, max_length=2000)
    locator: str = Field(min_length=3, max_length=500)
    supported_methods: list[str] = Field(min_length=1, max_length=20)


class ParameterBasis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    path: str = Field(min_length=1, max_length=300)
    value: Any
    unit: str = Field(min_length=1, max_length=100)
    meaning: str = Field(min_length=12, max_length=2000)
    method_key: str = Field(min_length=1, max_length=160)
    method_version: str = Field(min_length=1, max_length=300)
    source_indexes: list[int] = Field(min_length=1, max_length=30)

    @field_validator("value")
    @classmethod
    def finite_json_value(cls, value):
        try:
            encoded = json.dumps(value, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValueError("Parameter value must be finite JSON") from exc
        if len(encoded) > 100000:
            raise ValueError("Parameter value is too large")
        return value


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, serialize_by_alias=True, validate_by_name=True)
    artifact_id: uuid.UUID
    summary: str = Field(min_length=20, max_length=4000)
    raw_data_artifact_ids: list[uuid.UUID] = Field(min_length=1, max_length=30)
    positive_controls: list[str] = Field(min_length=1, max_length=50)
    negative_controls: list[str] = Field(min_length=1, max_length=50)
    construct_description: str = Field(alias="construct", min_length=5, max_length=2000)
    protocol: str = Field(min_length=20, max_length=4000)
    acceptance_criteria: str = Field(min_length=20, max_length=4000)


class ScientificEvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    workflow_version: int = Field(ge=1)
    sources: list[EvidenceSource] = Field(min_length=1, max_length=30)
    parameters: list[ParameterBasis] = Field(min_length=1, max_length=200)
    calibration: Calibration | None = None
    applicability: str = Field(min_length=20, max_length=8000)


class ScientificEvidenceReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    workflow_version: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    rationale: str = Field(min_length=20, max_length=4000)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _policy(value):
    result = GatePolicy.model_validate(value or {}).model_dump(mode="json")
    result.pop("script_preview_id", None)
    return result


# These are the immutable declaration fields copied into each compute job. Site
# resolution adds backend-specific settings separately and must not alter this
# identity. A registry edit under the same nominal version invalidates authoring
# approval; already submitted jobs retain their original frozen declaration.
PLUGIN_DECLARATION_FIELDS = (
    "image",
    "command",
    "parameter_schema",
    "output_schema",
    "input_ports",
    "output_ports",
    "resources",
    "runtime_mode",
    "output_parser",
    "input_adapter",
    "runtime_setup",
)


def _plugin_declaration(plugin=None, snapshot=None):
    if snapshot is not None:
        return {key: snapshot.get(key) for key in PLUGIN_DECLARATION_FIELDS}
    if plugin is None:
        return {key: None for key in PLUGIN_DECLARATION_FIELDS}
    return {key: getattr(plugin, "container_image" if key == "image" else key) for key in PLUGIN_DECLARATION_FIELDS}


def _initial_parameters(spec):
    """Bind the authored values and expressions, not a selected-count result.

    The scheduler deterministically resolves parameter_links before dispatch.
    Those expressions are part of the configuration hash and require their own
    source basis. Only declared linked names may differ from the frozen template;
    changing an unrelated scalar remains a fail-closed execution error.
    """
    current = spec.get("parameters", {})
    links = (spec.get("configuration") or {}).get("parameter_links", {})
    template = (spec.get("input_manifest_template") or {}).get("parameters")
    if not isinstance(template, dict):
        if links:
            raise ValueError("scientific_initial_parameters_missing")
        return current
    expected_static = {key: value for key, value in template.items() if key not in links}
    actual_static = {key: value for key, value in current.items() if key not in links}
    if digest(actual_static) != digest(expected_static):
        raise ValueError("scientific_static_parameters_changed")
    return template


def binding(session, workflow, edge, *, workflow_version=None, source_job=None, target_job=None):
    """The same parameters are checked at authoring, preflight, and gate execution."""
    nodes = {n.node_key: n for n in WorkflowRepository(session).nodes(workflow.id)}
    execution = {}
    for side, job in (("source", source_job), ("target", target_job)):
        node = nodes.get(edge.get(side))
        if job is not None:
            spec = job.runtime_spec
            execution[side] = {
                "parameters": _initial_parameters(spec),
                "configuration": spec.get("configuration", {}),
                "plugin_id": (spec.get("plugin_snapshot") or {}).get("id"),
                "method_key": (spec.get("plugin_snapshot") or {}).get("key"),
                "method_version": (spec.get("plugin_snapshot") or {}).get("version"),
                "plugin_declaration_sha256": digest(_plugin_declaration(snapshot=spec.get("plugin_snapshot") or {})),
            }
        else:
            plugin = session.get(ModelPlugin, node.model_plugin_id) if node and node.model_plugin_id else None
            execution[side] = {
                "parameters": (node.parameters or {}) if node else {},
                "configuration": (node.configuration or {}) if node else {},
                "plugin_id": str(node.model_plugin_id) if node and node.model_plugin_id else None,
                "method_key": plugin.plugin_key if plugin else None,
                "method_version": plugin.plugin_version if plugin else None,
                "plugin_declaration_sha256": digest(_plugin_declaration(plugin=plugin)),
            }
    policy = _policy(edge.get("gate"))
    output = execution["source"]["configuration"].get("output_policy")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "project_id": str(workflow.project_id),
        "workflow_id": str(workflow.id),
        "workflow_version": workflow.version if workflow_version is None else workflow_version,
        "edge": {k: edge.get(k) for k in ("id", "source", "target", "source_port", "target_port")},
        "policy": policy,
        "execution": execution,
    }
    required = {}
    for prefix, p in (("gate", policy), ("output_policy", _policy(output) if output else None)):
        if not p:
            continue
        if p["rules"]["conditions"] or p["rules"]["top_n"] is not None:
            required[f"{prefix}.rules"] = p["rules"]
        if p["structure"]:
            required[f"{prefix}.structure"] = p["structure"]
        if p["script"]:
            required[f"{prefix}.script_sha256"] = hashlib.sha256(p["script"].encode()).hexdigest()
    for side in ("source", "target"):
        for name, value in execution[side]["parameters"].items():
            required[f"{side}.parameters.{name}"] = value
        for name, expression in execution[side]["configuration"].get("parameter_links", {}).items():
            required[f"{side}.parameter_links.{name}"] = expression
    methods = {
        path: {
            k: execution["target" if path.startswith("target.") else "source"][k]
            for k in ("method_key", "method_version")
        }
        for path in required
    }
    return {**payload, "parameter_hash": digest(payload), "required_parameters": required, "required_methods": methods}


def _events(session, workflow):
    return list(
        session.scalars(
            select(AuditLog)
            .where(
                AuditLog.project_id == workflow.project_id,
                AuditLog.entity_id == workflow.id,
                AuditLog.action.in_([CANDIDATE, REVIEW]),
                AuditLog.result == "success",
            )
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    )


def _source_snapshots(session, project_id, sources):
    items = []
    for source in sources:
        document = session.get(LiteratureDocument, source.document_id)
        chunk = session.get(LiteratureChunk, source.chunk_id)
        if document is None or document.project_id != project_id or chunk is None or chunk.document_id != document.id:
            raise DomainError(
                "scientific_source_not_found",
                "Evidence must reference a document and chunk in this project",
                status_code=422,
            )
        if source.quote not in chunk.content:
            raise DomainError(
                "scientific_quote_not_anchored",
                "Quote must occur verbatim in the selected literature chunk",
                status_code=422,
            )
        items.append(
            {
                **source.model_dump(mode="json"),
                "title": document.title,
                "external_id": document.external_id,
                "source": document.source,
                "chunk_sha256": hashlib.sha256(chunk.content.encode()).hexdigest(),
            }
        )
    return items


def _calibration_snapshot(session, project_id, calibration):
    if calibration is None:
        return None
    artifact = session.get(Artifact, calibration.artifact_id)
    if (
        artifact is None
        or artifact.project_id != project_id
        or artifact.status != "available"
        or artifact.deleted_at is not None
        or not artifact.checksum_sha256
    ):
        raise DomainError(
            "scientific_calibration_unavailable",
            "Calibration must be an available, checksum-addressed artifact in this project",
            status_code=422,
        )
    raw_data = []
    if any(not x.strip() for x in calibration.positive_controls + calibration.negative_controls):
        raise DomainError("scientific_controls_invalid", "Control identifiers cannot be blank", status_code=422)
    if set(calibration.positive_controls) & set(calibration.negative_controls):
        raise DomainError(
            "scientific_controls_invalid", "Positive and negative controls must be distinct", status_code=422
        )
    for artifact_id in calibration.raw_data_artifact_ids:
        raw = session.get(Artifact, artifact_id)
        if (
            raw is None
            or raw.project_id != project_id
            or raw.status != "available"
            or raw.deleted_at is not None
            or not raw.checksum_sha256
        ):
            raise DomainError(
                "scientific_calibration_unavailable",
                "Raw calibration data must be available in this project",
                status_code=422,
            )
        if raw.id == artifact.id or raw.artifact_type == "analysis_report":
            raise DomainError(
                "scientific_calibration_raw_required",
                "A calibration report is not its independent raw data",
                status_code=422,
            )
        raw_data.append({"artifact_id": str(raw.id), "sha256": raw.checksum_sha256, "filename": raw.filename})
    return {
        **calibration.model_dump(mode="json"),
        "sha256": artifact.checksum_sha256,
        "filename": artifact.filename,
        "raw_data": raw_data,
    }


def _candidate_issues(session, workflow, candidate, current):
    issues = []
    if candidate["binding"] != current:
        issues.append("scientific_evidence_stale")
    evidence = candidate["evidence"]
    parameters = {p["path"]: p for p in evidence["parameters"]}
    if set(parameters) != set(current["required_parameters"]):
        issues.append("scientific_parameters_incomplete")
    for path, value in current["required_parameters"].items():
        if path in parameters and digest(parameters[path]["value"]) != digest(value):
            issues.append("scientific_parameter_value_mismatch")
        if path in parameters:
            parameter = parameters[path]
            expected = current["required_methods"][path]
            if (
                not expected["method_key"]
                or not expected["method_version"]
                or any(str(parameter[k]) != str(expected[k]) for k in expected)
            ):
                issues.append("scientific_method_scope_mismatch")
            if any(
                parameter["method_key"] not in evidence["sources"][i]["supported_methods"]
                for i in parameter["source_indexes"]
            ):
                issues.append("scientific_source_method_mismatch")
    try:
        sources = _source_snapshots(
            session, workflow.project_id, [EvidenceSource.model_validate(s) for s in evidence["sources"]]
        )
        if sources != candidate["sources"]:
            issues.append("scientific_source_changed")
        calibration = _calibration_snapshot(
            session,
            workflow.project_id,
            Calibration.model_validate(evidence["calibration"]) if evidence["calibration"] else None,
        )
        if calibration is None:
            issues.append("scientific_calibration_required")
        elif calibration != candidate["calibration"]:
            issues.append("scientific_calibration_changed")
    except DomainError as exc:
        issues.append(exc.error_code)
    return sorted(set(issues))


def approval_status(session, workflow, edge, *, current=None, events=None):
    current = current or binding(session, workflow, edge)
    required = current["policy"]["mode"] == "automatic"
    candidates = {}
    reviews = {}
    for event in _events(session, workflow) if events is None else events:
        data = event.payload
        if event.action == CANDIDATE and data.get("binding", {}).get("edge", {}).get("id") == edge.get("id"):
            candidates[str(event.id)] = (event, data)
        elif event.action == REVIEW:
            reviews[data.get("evidence_id")] = event
    items = []
    approved = None
    for evidence_id, (event, data) in reversed(list(candidates.items())):
        issues = _candidate_issues(session, workflow, data, current)
        review = reviews.get(evidence_id)
        trusted = (
            review is not None
            and review.actor_id is not None
            and review.payload.get("binding_hash") == current["parameter_hash"]
        )
        accepted = trusted and review.payload.get("decision") == "approve" and not issues
        if accepted and approved is None:
            approved = evidence_id
        items.append(
            {
                "id": evidence_id,
                "created_by": str(event.actor_id),
                "created_at": event.created_at.isoformat(),
                **data,
                "issues": issues,
                "review": (
                    {**review.payload, "actor_id": str(review.actor_id), "created_at": review.created_at.isoformat()}
                    if review
                    else None
                ),
                "approved": bool(accepted),
            }
        )
    blockers = [] if not required or approved else ["scientific_evidence_approval_required"]
    return {
        "edge_id": edge.get("id"),
        "mode": current["policy"]["mode"],
        "required": required,
        "binding": current,
        "approved_evidence_id": approved,
        "allowed": not blockers,
        "blockers": blockers,
        "items": items,
    }


def list_scientific_gates(workflow_id, session, user):
    workflow = _workflow(session, workflow_id, user)
    events = _events(session, workflow)
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_id": str(workflow.id),
        "workflow_version": workflow.version,
        "items": [approval_status(session, workflow, edge, events=events) for edge in workflow.graph.get("edges", [])],
    }


def _locked_workflow(session, workflow_id, user, permission, version):
    workflow = _workflow(session, workflow_id, user)
    project = require_project_permission(session, workflow.project_id, user, permission)
    session.refresh(workflow, with_for_update=True)
    if workflow.version != version:
        raise DomainError(
            "version_conflict", "Workflow changed; reload the gate and its parameter binding", status_code=412
        )
    if workflow.status != "draft":
        raise DomainError(
            "workflow_not_editable", "Scientific evidence is authored and reviewed on a draft workflow", status_code=409
        )
    return workflow, project


def save_evidence(workflow_id, edge_id, payload, session, user):
    workflow, project = _locked_workflow(session, workflow_id, user, "write", payload.workflow_version)
    edge = next((e for e in workflow.graph.get("edges", []) if e.get("id") == edge_id), None)
    if edge is None:
        raise DomainError("connection_not_found", "Connection not found", status_code=404)
    paths = [p.path for p in payload.parameters]
    if len(set(paths)) != len(paths) or any(
        i < 0 or i >= len(payload.sources) for p in payload.parameters for i in p.source_indexes
    ):
        raise DomainError(
            "scientific_parameter_invalid",
            "Parameter paths must be unique and source indexes must resolve",
            status_code=422,
        )
    current = binding(session, workflow, edge)
    data = {
        "schema_version": SCHEMA_VERSION,
        "binding": current,
        "evidence": payload.model_dump(mode="json"),
        "sources": _source_snapshots(session, workflow.project_id, payload.sources),
        "calibration": _calibration_snapshot(session, workflow.project_id, payload.calibration),
    }
    # The public API cannot choose the audit identity, actor, review status or binding hash.
    event = AuditLog(
        id=uuid.uuid4(),
        actor_id=user.id,
        project_id=project.id,
        organization_id=project.organization_id,
        action=CANDIDATE,
        entity_type="workflow_scientific_evidence",
        entity_id=workflow.id,
        trace_id=current_trace_id(),
        result="success",
        payload=data,
    )
    session.add(event)
    session.flush()
    return {"id": str(event.id), **data, "issues": _candidate_issues(session, workflow, data, current)}


def review_evidence(workflow_id, edge_id, evidence_id, payload, session, user):
    workflow, project = _locked_workflow(session, workflow_id, user, "manage", payload.workflow_version)
    edge = next((e for e in workflow.graph.get("edges", []) if e.get("id") == edge_id), None)
    event = session.get(AuditLog, evidence_id)
    if (
        edge is None
        or event is None
        or event.action != CANDIDATE
        or event.entity_id != workflow.id
        or event.project_id != project.id
        or event.payload.get("binding", {}).get("edge", {}).get("id") != edge_id
    ):
        raise DomainError(
            "scientific_evidence_not_found", "Scientific evidence not found on this connection", status_code=404
        )
    current = binding(session, workflow, edge)
    issues = _candidate_issues(session, workflow, event.payload, current)
    if payload.decision == "approve" and issues:
        raise DomainError(
            "scientific_evidence_not_ready",
            "Evidence cannot authorize this gate",
            status_code=409,
            errors=[{"code": c} for c in issues],
        )
    record_audit(
        session,
        action=REVIEW,
        entity_type="workflow_scientific_evidence",
        entity_id=workflow.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
        payload={
            "evidence_id": str(evidence_id),
            "binding_hash": current["parameter_hash"],
            "decision": payload.decision,
            "rationale": payload.rationale,
            "reviewed_at": datetime.now(UTC).isoformat(),
        },
    )
    session.flush()
    return approval_status(session, workflow, edge, current=current)


def assert_runtime_approval(session, gate):
    edge = gate.snapshot["edge"]
    if GatePolicy.model_validate(edge.get("gate") or {}).mode != "automatic":
        return
    from ..compute.models import Job
    from .models import WorkflowRun

    workflow = session.get(WorkflowRun, gate.workflow_run_id)
    source = session.get(Job, uuid.UUID(gate.snapshot["source_job_id"]))
    target = session.get(Job, gate.target_job_id) if gate.target_job_id else None
    # Previews can evaluate tentative policies but never authorize a real transfer.
    if gate.preview:
        return
    if (
        workflow is None
        or source is None
        or target is None
        or not isinstance(target.runtime_spec.get("workflow_version"), int)
        or any(j.project_id != gate.project_id or j.workflow_run_id != workflow.id for j in (source, target))
    ):
        raise ValueError("scientific_gate_execution_context_invalid")
    current = binding(
        session,
        workflow,
        edge,
        workflow_version=target.runtime_spec.get("workflow_version"),
        source_job=source,
        target_job=target,
    )
    status = approval_status(session, workflow, edge, current=current)
    if not status["allowed"]:
        raise ValueError("scientific_evidence_approval_required")
    gate.snapshot = {
        **gate.snapshot,
        "scientific_approval": {
            "evidence_id": status["approved_evidence_id"],
            "parameter_hash": current["parameter_hash"],
            "checked_at": datetime.now(UTC).isoformat(),
        },
    }


def search_sources(workflow_id, edge_id, q, session, user):
    """Search already-imported source text. Network retrieval is an explicit research job."""
    workflow = _workflow(session, workflow_id, user)
    if not any(e.get("id") == edge_id for e in workflow.graph.get("edges", [])):
        raise DomainError("connection_not_found", "Connection not found", status_code=404)
    query = (
        select(LiteratureDocument, LiteratureChunk)
        .join(LiteratureChunk, LiteratureChunk.document_id == LiteratureDocument.id)
        .where(LiteratureDocument.project_id == workflow.project_id)
    )
    if q.strip():
        # Bound each term, escape SQL wildcards, AND across up to eight words.
        for term in q.split()[:8]:
            term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where(
                (LiteratureDocument.title.ilike(f"%{term}%", escape="\\"))
                | (LiteratureChunk.content.ilike(f"%{term}%", escape="\\"))
            )
    rows = session.execute(query.order_by(LiteratureDocument.created_at.desc(), LiteratureChunk.position).limit(40))
    items = []
    for document, chunk in rows:
        metadata = document.metadata_json or {}
        items.append(
            {
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "title": document.title,
                "quote": chunk.content[:2000],
                "locator": f"chunk {chunk.position}",
                "url": metadata.get("url") or metadata.get("source_url"),
                "external_id": document.external_id,
                "source": document.source,
                "chunk_sha256": hashlib.sha256(chunk.content.encode()).hexdigest(),
            }
        )
    return {"items": items, "limit": 40, "query": q, "scope": "project_imported_literature"}
