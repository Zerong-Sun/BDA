"""Durable gates between collection and dispatch. No downstream task sees rejected bytes."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from ..artifacts.models import Artifact, ArtifactLineageEdge
from ..artifacts.storage import ObjectStorage
from ..compute.binding import _manifest_entry
from ..compute.models import Job, JobSubmission
from ..compute.repository import ComputeRepository
from .gate_engine import evaluate, records_in_file, subset_file
from .gate_schemas import GatePolicy
from .models import GateEvaluation, WorkflowResult, WorkflowRun

MAX_FILE = 64 * 1024 * 1024


def json_safe(value):
    """Missing/nonfinite measurements remain missing, including on PostgreSQL JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def capture_results(session, job, artifacts, parsed, storage=None):
    """Persist per-attempt metrics, rather than reading mutable Candidate scores later."""
    storage = storage or ObjectStorage()
    existing = set(session.scalars(select(WorkflowResult.result_key).where(WorkflowResult.job_id == job.id)))
    candidates = {c.candidate_key: c for c in parsed.candidates}
    groups: dict[str, dict[str, Any]] = {}
    port_counts: dict[str, int] = {}
    for output_index, artifact in enumerate(artifacts):
        lineage = artifact.lineage or {}
        port = lineage.get("output_port")
        if not port:
            continue
        metadata = lineage.get("metadata") or {}
        try:
            selectors = records_in_file(artifact.filename, storage.read_bytes(artifact.object_key, max_bytes=MAX_FILE))
        except Exception as exc:
            selectors = [{"key": artifact.filename, "format": "unsupported", "error": str(exc)[:500]}]
        port_counts.setdefault(port, 0)
        for selector in selectors:
            if (
                selector.get("native")
                and (job.runtime_spec.get("plugin_snapshot") or {}).get("output_parser") == "proteinmpnn_fasta"
            ):
                continue
            port_counts[port] += 1
            candidate_meta = metadata.get("candidate") or {}
            associated = [
                c for c in parsed.candidates if output_index in (c.structure_output_index, c.complex_output_index)
            ]
            associated_key = (
                associated[0].candidate_key if len(associated) == 1 and selector["format"] == "whole" else None
            )
            # File-level metadata cannot identify individual members of a bundle.
            key = str(
                (metadata.get("candidate_key") or candidate_meta.get("candidate_key") or associated_key)
                if selector["format"] == "whole"
                and (metadata.get("candidate_key") or candidate_meta.get("candidate_key") or associated_key)
                else selector["key"]
            )
            if len(key) > 490:
                key = hashlib.sha256(key.encode()).hexdigest()
            row = groups.setdefault(
                key,
                {
                    "key": key,
                    "files": [],
                    "metrics": {},
                    "parent_ids": metadata.get(
                        "parent_result_ids",
                        job.runtime_spec.get("selected_result_ids", [])
                        if len(job.runtime_spec.get("selected_result_ids", [])) == 1
                        else [],
                    ),
                    "input_result_ids": job.runtime_spec.get("selected_result_ids", []),
                    "attempt": job.attempt_number,
                    "node_key": job.runtime_spec.get("node_key"),
                    "plugin": {
                        k: v
                        for k, v in (job.runtime_spec.get("plugin_snapshot") or {}).items()
                        if k in {"id", "key", "version", "checksum_sha256"}
                    },
                    "sequence": selector.get("sequence"),
                },
            )
            if any(f["port"] == port for f in row["files"]):
                selector = {**selector, "error": "ambiguous_result_identity_across_files"}
            row["files"].append({"artifact_id": str(artifact.id), "port": port, "selector": selector})
            if selector.get("sequence"):
                row["sequence"] = selector["sequence"]
            row["metrics"].update(selector.get("metrics", {}))
            row["metrics"].update({k: v for k, v in metadata.get("metrics", {}).items() if isinstance(v, (int, float))})
            candidate = candidates.get(key)
            if candidate:
                row["metrics"].update(candidate.scores)
                if candidate.score is not None:
                    row["metrics"]["score"] = candidate.score
                row["metric_sources"] = [
                    {
                        "key": m.key,
                        "value": m.value,
                        "method": m.method,
                        "model_variant": m.model_variant,
                        "condition": m.condition,
                    }
                    for m in candidate.metrics
                ]
                # Ambiguous metric variants must be addressed by their full name.
                counts: dict[str, int] = defaultdict(int)
                for m in candidate.metrics:
                    counts[m.key] += 1
                for m in candidate.metrics:
                    row["metrics"][f"{m.key}:{m.method}:{m.model_variant}:{m.condition}"] = m.value
                    if counts[m.key] == 1:
                        row["metrics"][m.key] = m.value
                    else:
                        row["metrics"].pop(m.key, None)
    for key, payload in groups.items():
        if key not in existing:
            session.add(
                WorkflowResult(
                    id=uuid.uuid5(job.id, key),
                    job_id=job.id,
                    project_id=job.project_id,
                    result_key=key,
                    payload=json_safe(payload),
                )
            )
    job.runtime_spec = {**job.runtime_spec, "result_manifest": {"version": 1, "ports": port_counts}}
    session.flush()


def latest_gate(session, job_id, edge_id, *, preview=False, workflow_id=None):
    return session.scalar(
        select(GateEvaluation)
        .where(
            GateEvaluation.target_job_id == job_id,
            GateEvaluation.edge_id == edge_id,
            GateEvaluation.preview == preview,
            *([GateEvaluation.workflow_run_id == workflow_id] if workflow_id else []),
        )
        .order_by(GateEvaluation.revision.desc())
        .limit(1)
    )


def next_revision(session, workflow_id, edge_id, target_job_id):
    # Callers serialize allocation using the workflow row lock.
    return (
        session.scalar(
            select(func.max(GateEvaluation.revision)).where(
                GateEvaluation.workflow_run_id == workflow_id,
                GateEvaluation.edge_id == edge_id,
                GateEvaluation.target_job_id == target_job_id,
            )
        )
        or 0
    ) + 1


def ensure_gate(session, target, source, edge):
    gate = latest_gate(session, target.id, edge["id"])
    if gate is not None:
        return gate
    gate = GateEvaluation(
        project_id=target.project_id,
        workflow_run_id=target.workflow_run_id,
        target_job_id=target.id,
        edge_id=edge["id"],
        status="waiting",
        revision=next_revision(session, target.workflow_run_id, edge["id"], target.id),
        snapshot={
            "edge": edge,
            "workflow_version": target.runtime_spec.get("workflow_version"),
            "source_attempt": source.attempt_number,
            "source_job_id": str(source.id),
            "output_policy": (source.runtime_spec.get("configuration") or {}).get("output_policy"),
            "script_sha256": hashlib.sha256((edge.get("gate", {}).get("script") or "").encode()).hexdigest(),
        },
    )
    session.add(gate)
    session.flush()
    ComputeRepository(session).enqueue("gate.evaluate", gate.id, project_id=gate.project_id)
    return gate


def gate_inputs(session, job, parents, by_key):
    """Return ready/waiting/empty. Both validation and dispatch use the frozen graph."""
    selected, inputs = [], []
    counts: dict[str, set[str]] = {}
    edges = job.runtime_spec.get("workflow_edges", [])
    empty_ports = set()
    for edge in edges:
        if edge["target"] != job.runtime_spec["node_key"]:
            continue
        if edge["source"] not in parents:
            if edge.get("gate", {}).get("mode") != "dependency":
                counts.setdefault(edge["source"], set())
                empty_ports.add(edge.get("target_port"))
            continue
        policy = GatePolicy.model_validate(edge.get("gate") or {})
        if policy.mode == "dependency":
            continue
        gate = ensure_gate(session, job, by_key[edge["source"]], edge)
        if gate.status not in {"released", "empty"}:
            return "waiting"
        if gate.status == "empty":
            empty_ports.add(edge.get("target_port"))
        inputs.extend(gate.inputs)
        selected.extend(gate.selected_ids)
        counts.setdefault(edge["source"], set()).update(gate.selected_ids)
    from ..registry.ports import parse_input_ports

    ports = parse_input_ports((job.runtime_spec.get("plugin_snapshot") or {}).get("input_ports", []))
    provided = {i["port"] for i in inputs} | {
        i["port"]
        for i in (job.runtime_spec.get("input_manifest_template") or job.runtime_spec.get("input_manifest") or {}).get(
            "inputs", []
        )
    }
    for port in ports:
        if port.required and port.name in empty_ports and port.name not in provided:
            if not port.exclusive_group or not any(
                p.name in provided for p in ports if p.exclusive_group == port.exclusive_group
            ):
                return "empty"
    manifest = dict(job.runtime_spec.get("input_manifest_template") or job.runtime_spec.get("input_manifest") or {})
    manifest["inputs"] = unique_input_names([*manifest.get("inputs", []), *inputs])
    manifest["pending_inputs"] = []
    job.runtime_spec = {
        **job.runtime_spec,
        "input_manifest": manifest,
        "selected_result_ids": sorted(set(selected)),
        "gate_selected_counts": {k: len(v) for k, v in counts.items()},
    }
    return "ready"


def unique_input_names(inputs):
    """Prevent files sharing an input port/name from overwriting each other during staging."""
    from collections import Counter

    counts = Counter((item.get("port"), Path(item.get("filename") or "input").name) for item in inputs)
    result = []
    for index, item in enumerate(inputs):
        name = Path(item.get("filename") or "input").name
        if counts[(item.get("port"), name)] > 1:
            name = f"{index:04d}-{item.get('artifact_id') or 'result'}-{name}"
        result.append({**item, "filename": name})
    return result


def _script_decisions(source, records):
    """Untrusted Python runs without network, mounts or credentials in a bounded container."""
    import os

    import docker

    payload = json.dumps(records, allow_nan=False)
    wrapper = (
        "import json\nrecords = json.loads("
        + repr(payload)
        + ")\n"
        + source
        + "\nprint(json.dumps(screen(records), allow_nan=False))\n"
    )
    client = docker.from_env()
    container = client.containers.create(
        os.environ.get("BDA_GATE_SCRIPT_IMAGE", "python:3.13-slim"),
        ["python", "-I", "-c", "import sys; size=int(sys.stdin.buffer.readline()); exec(sys.stdin.buffer.read(size))"],
        stdin_open=True,
        detach=True,
        network_disabled=True,
        read_only=True,
        user="65534:65534",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        mem_limit="256m",
        nano_cpus=1000000000,
        pids_limit=32,
        tmpfs={"/tmp": "size=16m,noexec,nosuid"},
        log_config=docker.types.LogConfig(type="json-file", config={"max-size": "16m", "max-file": "1"}),
    )
    try:
        import socket

        connection = container.attach_socket(params={"stdin": 1, "stream": 1})
        try:
            container.start()
            transport: Any = getattr(connection, "_sock", connection)
            transport.settimeout(60)
            script_bytes = wrapper.encode()
            transport.sendall(str(len(script_bytes)).encode() + b"\n" + script_bytes)
            transport.shutdown(socket.SHUT_WR)
        finally:
            response = getattr(connection, "_response", None)
            if response is not None:
                response.close()
            else:
                connection.close()
        status = container.wait(timeout=60)
        if status.get("StatusCode") != 0:
            raise ValueError("gate_script_failed")
        answer = json.loads(container.logs(stdout=True, stderr=False).decode())
        ids = {r["id"] for r in records}
        if (
            not isinstance(answer, list)
            or len(answer) != len(ids)
            or {r.get("id") for r in answer} != ids
            or any(type(r.get("passed")) is not bool or not isinstance(r.get("reason", ""), str) for r in answer)
        ):
            raise ValueError("gate_script_result_contract_invalid")
        return answer
    finally:
        container.remove(force=True)


def run_gate(session, gate, storage=None):
    storage = storage or ObjectStorage()
    if gate.status in {"released", "empty", "awaiting_review", "previewed", "superseded", "error"}:
        return
    source_id = uuid.UUID(gate.snapshot["source_job_id"])
    policy = GatePolicy.model_validate(gate.snapshot["edge"]["gate"])
    rows = list(session.scalars(select(WorkflowResult).where(WorkflowResult.job_id == source_id)))
    port = gate.snapshot["edge"]["source_port"]
    records = [
        {**row.payload, "id": str(row.id)} for row in rows if any(f["port"] == port for f in row.payload["files"])
    ]
    if policy.mode == "integrity":
        # Reference/parameter data isn't candidate data: exact files, never an implicit data-edge bypass.
        artifacts = ComputeRepository(session).produced_artifacts(source_id)
        records = [
            {
                "id": str(a.id),
                "key": a.filename,
                "metrics": {},
                "files": [{"artifact_id": str(a.id), "port": port, "selector": {"format": "reference"}}],
            }
            for a in artifacts
            if (a.lineage or {}).get("output_port") == port
        ]
    else:
        for record in records:
            errors = [
                f["selector"]["error"] for f in record["files"] if f["port"] == port and f["selector"].get("error")
            ]
            if errors:
                raise ValueError("upstream_result_format_unsupported: " + "; ".join(errors))
    if not records:
        source = session.get(Job, source_id)
        port_counts = (source.runtime_spec.get("result_manifest") or {}).get("ports", {}) if source else {}
        if port in port_counts and port_counts[port] == 0:
            gate.decisions, gate.selected_ids, gate.inputs = [], [], []
            gate.snapshot = {**gate.snapshot, "records": []}
            gate.status = "previewed" if gate.preview else "empty"
            gate.version += 1
            return
        raise ValueError("upstream_result_manifest_missing")
    if gate.status != "materializing":
        gate.status = "evaluating"
        inherited = gate.snapshot.get("output_policy") if policy.mode != "integrity" else None
        policies = [GatePolicy.model_validate(inherited)] if inherited else []
        policies.append(policy)
        decisions = [{"id": r["id"], "passed": True, "reasons": [], "metrics": r.get("metrics", {})} for r in records]
        for current in policies:
            eligible_ids = {d["id"] for d in decisions if d["passed"]}
            active_records = [r for r in records if r["id"] in eligible_ids]
            if not active_records:
                break
            if current.structure:
                from .structure_metrics import structure_metrics

                for record in active_records:
                    structure = next(
                        (f for f in record["files"] if f["selector"].get("format") == "whole"),
                        None,
                    )
                    if structure is None:
                        record["needs_attention"] = True
                        record["error"] = "structure_coordinates_unavailable"
                        continue
                    artifact = session.get(Artifact, uuid.UUID(structure["artifact_id"]))
                    try:
                        body = read_verified(artifact, storage)
                        filename = artifact.filename
                        member = structure["selector"].get("member")
                        if member:
                            import io
                            import zipfile

                            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                                body = archive.read(member)
                                filename = member
                        metrics = structure_metrics(filename, body, current.structure)
                        record["metrics"] = {
                            **record.get("metrics", {}),
                            **{k: v for k, v in metrics.items() if isinstance(v, (int, float))},
                        }
                        record["structure_method"] = metrics
                    except ValueError as exc:
                        record["needs_attention"] = True
                        record["error"] = str(exc)
            filter_policy = current.model_copy(update={"rules": current.rules.model_copy(update={"top_n": None})})
            outcomes = {d["id"]: d for d in evaluate(active_records, filter_policy)}
            if current.script:
                import base64

                script_records = []
                total_bytes = 0
                for record in active_records:
                    files = []
                    for file in record["files"]:
                        artifact = session.get(Artifact, uuid.UUID(file["artifact_id"]))
                        if artifact is None or artifact.project_id != gate.project_id:
                            raise ValueError("gate_source_artifact_unavailable")
                        raw = read_verified(artifact, storage)
                        body = (
                            raw
                            if file["selector"]["format"] in {"reference", "unsupported"}
                            else subset_file(artifact.filename, raw, [file["selector"]])
                        )
                        total_bytes += len(body)
                        if total_bytes > MAX_FILE:
                            raise ValueError("gate_script_input_too_large")
                        files.append(
                            {**file, "filename": artifact.filename, "content_base64": base64.b64encode(body).decode()}
                        )
                    script_records.append({**record, "files": files})
                custom = {d["id"]: d for d in _script_decisions(current.script, script_records)}
                for key, d in outcomes.items():
                    d["passed"] = d["passed"] and custom[key]["passed"]
                    if not custom[key]["passed"]:
                        d["reasons"].append(custom[key].get("reason") or "script_rejected")
            if current.rules.top_n is not None:
                survivors = [r for r in active_records if outcomes[r["id"]]["passed"]]
                outcomes.update({d["id"]: d for d in evaluate(survivors, current)})
            for d in decisions:
                outcome = outcomes.get(d["id"])
                if outcome is None:
                    continue
                d["passed"] = d["passed"] and outcome["passed"]
                d["reasons"].extend(outcome["reasons"])
                d["metrics"] = outcome["metrics"]
                d["needs_attention"] = outcome.get("needs_attention", False)
        gate.decisions = decisions
        gate.snapshot = {**gate.snapshot, "records": records}
        passed = [d["id"] for d in decisions if d["passed"]]
        if not passed and any(d.get("needs_attention") for d in decisions):
            gate.status = "error"
            gate.error_message = "structure_data_needs_attention"
            gate.version += 1
            return
        if gate.preview:
            gate.status = "previewed"
            gate.version += 1
            return
        if policy.mode in {"manual", "review"} and passed:
            gate.status = "awaiting_review"
            gate.version += 1
            return
        gate.selected_ids = passed
    else:
        records = gate.snapshot["records"]
    gate.inputs = materialize(session, gate, records, storage) if gate.selected_ids else []
    gate.status = "released" if gate.selected_ids else "empty"
    gate.version += 1


def read_verified(artifact, storage):
    if artifact is None or artifact.deleted_at is not None or artifact.status != "available":
        raise ValueError("gate_source_artifact_unavailable")
    data = storage.read_bytes(artifact.object_key, max_bytes=MAX_FILE)
    if len(data) != artifact.size_bytes or hashlib.sha256(data).hexdigest() != artifact.checksum_sha256:
        raise ValueError("gate_source_integrity_failed")
    return data


def materialize(session, gate, records, storage):
    grouped = defaultdict(list)
    for row in records:
        if row["id"] in gate.selected_ids:
            for file in row["files"]:
                if file["port"] == gate.snapshot["edge"]["source_port"]:
                    grouped[file["artifact_id"]].append(file["selector"])
    inputs = []
    for artifact_id, selectors in grouped.items():
        source = session.get(Artifact, uuid.UUID(artifact_id))
        if source is None or source.project_id != gate.project_id or source.deleted_at is not None:
            raise ValueError("gate_source_artifact_unavailable")
        original = read_verified(source, storage)
        if all(s["format"] == "reference" for s in selectors):
            artifact = source
        else:
            data = subset_file(source.filename, original, selectors)
            checksum = hashlib.sha256(data).hexdigest()
            artifact_id = uuid.uuid5(gate.id, str(source.id) + checksum)
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                object_key = f"projects/{gate.project_id}/gates/{gate.id}/{checksum}/{Path(source.filename).name}"
                storage.put_bytes(object_key, data, source.content_type)
                artifact = Artifact(
                    id=artifact_id,
                    project_id=gate.project_id,
                    created_by=source.created_by,
                    artifact_type=source.artifact_type,
                    filename=source.filename,
                    content_type=source.content_type,
                    object_key=object_key,
                    size_bytes=len(data),
                    checksum_sha256=checksum,
                    lineage={
                        "gate_id": str(gate.id),
                        "selected_ids": gate.selected_ids,
                        "source_artifact_id": str(source.id),
                    },
                )
                session.add(artifact)
                session.flush()
                session.add(
                    ArtifactLineageEdge(
                        project_id=gate.project_id,
                        parent_artifact_id=source.id,
                        child_artifact_id=artifact.id,
                        relation="gate_subset",
                        details={"gate_id": str(gate.id)},
                    )
                )
        inputs.append(_manifest_entry(gate.snapshot["edge"]["target_port"], artifact))
    return inputs


def execute_gate(gate_id: str):
    from ..compute.service import schedule_ready_jobs
    from ..core.database import session_scope

    with session_scope() as session:
        gate = session.scalar(select(GateEvaluation).where(GateEvaluation.id == uuid.UUID(gate_id)).with_for_update())
        if gate is None or gate.status not in {"waiting", "evaluating", "materializing", "released", "empty"}:
            return
        if gate.status == "waiting":
            gate.status = "evaluating"
            gate.version += 1
    with session_scope() as session:
        gate = session.scalar(select(GateEvaluation).where(GateEvaluation.id == uuid.UUID(gate_id)).with_for_update())
        if gate is None or gate.status in {"superseded", "error"}:
            return
        target = session.get(Job, gate.target_job_id) if gate.target_job_id else None
        if not gate.preview and (target is None or target.status != "pending"):
            return
        try:
            with session.begin_nested():
                run_gate(session, gate)
        except Exception as exc:
            gate.status = "error"
            gate.error_message = str(exc)[:2000]
            gate.version += 1
        target_id = gate.target_job_id if not gate.preview else None
    # Never acquire the workflow lock while holding a gate lock: preview/retry
    # and the scheduler take workflow -> gate order.
    if target_id is not None:
        with session_scope() as session:
            target = session.get(Job, target_id)
            if target is not None:
                submission = session.get(JobSubmission, target.submission_id)
                workflow = session.get(WorkflowRun, target.workflow_run_id)
                if submission is not None and workflow is not None:
                    schedule_ready_jobs(session, submission, workflow)
