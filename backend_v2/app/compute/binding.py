"""Resolve workflow node input bindings into concrete job manifest inputs.

Two resolution moments, because the two binding sources become knowable at different
times:

* ``source="artifact"`` - a specific project artifact. Resolvable at submit.
* ``source="upstream"`` - whatever an upstream node produced on a named output port.
  Only knowable once that node's job has succeeded, so it is resolved in
  ``schedule_ready_jobs`` just before the dependent job is dispatched.

Manifest entries deliberately carry no presigned URL. URLs are minted in
``dispatch_job`` at the moment the manifest is written to object storage, so their
lifetime is measured from dispatch rather than from submit.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..registry.ports import (
    InputPort,
    artifact_accepted,
    output_port_for_artifact,
    parse_input_ports,
    parse_output_ports,
    ports_compatible,
)

BINDING_SOURCES = frozenset({"artifact", "upstream"})


class BindingError(Exception):
    """A binding cannot be satisfied. Carries machine-readable blockers."""

    def __init__(self, blockers: list[dict]) -> None:
        super().__init__("; ".join(item["code"] for item in blockers))
        self.blockers = blockers


def _plugin_ports(plugin: Any) -> tuple[list[InputPort], list]:
    if plugin is None:
        return [], []
    return parse_input_ports(plugin.input_ports), parse_output_ports(plugin.output_ports)


def _normalize(bindings: object) -> list[dict]:
    return [item for item in (bindings if isinstance(bindings, list) else []) if isinstance(item, dict)]


def binding_blockers(node: Any, plugin: Any) -> list[dict]:
    """Static problems with a node's bindings, independent of upstream job state.

    Shared by preflight and submit so the two can never disagree.
    """
    input_ports, _ = _plugin_ports(plugin)
    by_name = {port.name: port for port in input_ports}
    bindings = _normalize(node.input_bindings)
    blockers: list[dict] = []
    seen: set[str] = set()

    for binding in bindings:
        port_name = str(binding.get("port") or "")
        source = str(binding.get("source") or "")
        if port_name not in by_name:
            blockers.append(
                {
                    "code": "input_port_unknown",
                    "message": f"Node binds unknown input port '{port_name}'",
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
            continue
        if source not in BINDING_SOURCES:
            blockers.append(
                {
                    "code": "input_binding_source_invalid",
                    "message": f"Binding for '{port_name}' has invalid source '{source}'",
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
            continue
        if source == "artifact" and not binding.get("artifact_id"):
            blockers.append(
                {
                    "code": "input_binding_artifact_missing",
                    "message": f"Artifact binding for '{port_name}' has no artifact_id",
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
        if source == "upstream" and not (binding.get("from_node") and binding.get("from_port")):
            blockers.append(
                {
                    "code": "input_binding_upstream_incomplete",
                    "message": f"Upstream binding for '{port_name}' needs from_node and from_port",
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
        if port_name in seen and not by_name[port_name].multiple:
            blockers.append(
                {
                    "code": "input_port_not_multiple",
                    "message": f"Input port '{port_name}' accepts a single binding",
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
        seen.add(port_name)

    # A required port inside an exclusive group is satisfied by any member of that
    # group, so it is checked per group rather than per port.
    blockers.extend(
        {
            "code": "input_binding_unsatisfied",
            "message": f"Required input port '{port.name}' has no binding",
            "node_key": node.node_key,
            "port": port.name,
        }
        for port in input_ports
        if port.required and not port.exclusive_group and port.name not in seen
    )
    blockers.extend(_group_blockers(node, input_ports, seen))
    return blockers


def _group_blockers(node: Any, input_ports: list[InputPort], bound: set[str]) -> list[dict]:
    """Enforce 'exactly one of these ports' for each declared exclusive group."""
    groups: dict[str, list[InputPort]] = {}
    for port in input_ports:
        if port.exclusive_group:
            groups.setdefault(port.exclusive_group, []).append(port)

    blockers: list[dict] = []
    for group, ports in groups.items():
        chosen = [port.name for port in ports if port.name in bound]
        names = ", ".join(port.name for port in ports)
        if len(chosen) > 1:
            blockers.append(
                {
                    "code": "input_group_exclusive",
                    "message": f"Bind only one of '{names}' for '{group}', got {len(chosen)}",
                    "node_key": node.node_key,
                    "port": chosen[0],
                    "exclusive_group": group,
                }
            )
        elif not chosen and any(port.required for port in ports):
            blockers.append(
                {
                    "code": "input_group_unsatisfied",
                    "message": f"Bind one of '{names}' for '{group}'",
                    "node_key": node.node_key,
                    "port": ports[0].name,
                    "exclusive_group": group,
                }
            )
    return blockers


def resolve_artifact_bindings(
    session: Session, *, node: Any, plugin: Any, project_id: uuid.UUID
) -> tuple[list[dict], list[dict]]:
    """Resolve ``source="artifact"`` bindings. Returns (manifest_inputs, pending)."""
    input_ports, _ = _plugin_ports(plugin)
    by_name = {port.name: port for port in input_ports}
    inputs: list[dict] = []
    pending: list[dict] = []
    blockers: list[dict] = []

    for binding in _normalize(node.input_bindings):
        port_name = str(binding.get("port") or "")
        port = by_name.get(port_name)
        if port is None:
            continue
        if binding.get("source") == "upstream":
            pending.append(
                {
                    "port": port_name,
                    "from_node": str(binding.get("from_node")),
                    "from_port": str(binding.get("from_port")),
                }
            )
            continue
        artifact = _load_artifact(session, binding.get("artifact_id"), project_id)
        if artifact is None:
            blockers.append(
                {
                    "code": "input_artifact_unavailable",
                    "message": f"Artifact bound to '{port_name}' is missing, deleted, or in another project",
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
            continue
        if not artifact_accepted(port, artifact.artifact_type):
            blockers.append(
                {
                    "code": "input_artifact_type_rejected",
                    "message": (
                        f"Port '{port_name}' does not accept artifact_type '{artifact.artifact_type}' "
                        f"(accepts: {', '.join(port.accepts)})"
                    ),
                    "node_key": node.node_key,
                    "port": port_name,
                }
            )
            continue
        inputs.append(_manifest_entry(port_name, artifact))

    if blockers:
        raise BindingError(blockers)
    return inputs, pending


def resolve_pending_inputs(
    *, pending: list[dict], produced: dict[str, list[Artifact]], plugin: Any
) -> tuple[list[dict], list[dict]]:
    """Resolve ``pending`` upstream bindings against artifacts produced per node key.

    Returns (resolved_inputs, still_pending). Anything still pending means the upstream
    node produced nothing matching that port - the caller decides whether that is fatal.
    """
    _, output_ports = _plugin_ports(plugin)
    resolved: list[dict] = []
    unresolved: list[dict] = []
    for item in pending:
        artifacts = produced.get(item["from_node"], [])
        matched = [
            artifact for artifact in artifacts if _artifact_output_port(artifact, output_ports) == item["from_port"]
        ]
        if not matched:
            unresolved.append(item)
            continue
        resolved.extend(_manifest_entry(item["port"], artifact) for artifact in matched)
    return resolved, unresolved


def edge_port_blockers(
    *, source_node: Any, target_node: Any, source_plugin: Any, target_plugin: Any, source_port: str, target_port: str
) -> list[dict]:
    """Type-check an explicitly ported edge between two nodes."""
    _, source_outputs = _plugin_ports(source_plugin)
    target_inputs, _ = _plugin_ports(target_plugin)
    output = next((port for port in source_outputs if port.name == source_port), None)
    target = next((port for port in target_inputs if port.name == target_port), None)
    if output is None:
        return [
            {
                "code": "edge_source_port_unknown",
                "message": f"Node '{source_node.node_key}' has no output port '{source_port}'",
                "node_key": source_node.node_key,
            }
        ]
    if target is None:
        return [
            {
                "code": "edge_target_port_unknown",
                "message": f"Node '{target_node.node_key}' has no input port '{target_port}'",
                "node_key": target_node.node_key,
            }
        ]
    if not ports_compatible(output, target):
        return [
            {
                "code": "edge_ports_incompatible",
                "message": (
                    f"'{source_node.node_key}.{source_port}' ({output.kind}/{output.artifact_type}) "
                    f"cannot feed '{target_node.node_key}.{target_port}' ({target.kind})"
                ),
                "node_key": target_node.node_key,
            }
        ]
    return []


def _artifact_output_port(artifact: Artifact, output_ports: list) -> str | None:
    """Which output port produced this artifact.

    Prefers the explicit port recorded at collection; falls back to a reverse lookup on
    artifact_type and filename so plugins that predate ports still connect.
    """
    lineage = artifact.lineage if isinstance(artifact.lineage, dict) else {}
    recorded = lineage.get("output_port")
    if recorded:
        return str(recorded)
    port = output_port_for_artifact(output_ports, artifact.artifact_type, artifact.filename)
    return port.name if port else None


def _load_artifact(session: Session, artifact_id: object, project_id: uuid.UUID) -> Artifact | None:
    try:
        parsed = uuid.UUID(str(artifact_id))
    except (ValueError, TypeError):
        return None
    return session.scalar(
        select(Artifact).where(
            Artifact.id == parsed,
            Artifact.project_id == project_id,
            Artifact.status == "available",
            Artifact.deleted_at.is_(None),
        )
    )


def _manifest_entry(port: str, artifact: Artifact) -> dict:
    return {
        "port": port,
        "artifact_id": str(artifact.id),
        "filename": artifact.filename,
        "object_key": artifact.object_key,
        "content_type": artifact.content_type,
        "checksum_sha256": artifact.checksum_sha256,
        "size_bytes": artifact.size_bytes,
    }
