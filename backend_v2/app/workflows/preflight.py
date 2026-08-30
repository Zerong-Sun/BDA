"""Shared submission readiness check.

The preflight endpoint and ``create_submission`` call the same function, so what the UI
shows as "ready" and what submission accepts can never drift apart. Previously preflight
was advisory only: a workflow whose nodes had no registry plugin reported a blocker but
still submitted, and the job then ran whatever free-text command the node carried.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import _Error as _JsonSchemaError
from sqlalchemy.orm import Session

from ..compute.binding import binding_blockers, edge_port_blockers
from ..registry.models import ModelPlugin
from ..registry.runtime_validation import runtime_validation_is_current
from .models import WorkflowRun
from .repository import WorkflowRepository


def _parameter_error_message(error: _JsonSchemaError) -> str:
    """Keep schema diagnostics stable across jsonschema releases."""
    path = "/".join(str(part) for part in error.path) or "(root)"
    if error.validator == "maxLength" and error.validator_value == 0:
        return f"{path}: must be empty"
    return f"{path}: {error.message}"


def parameter_blockers(node: Any, plugin: Any) -> list[dict]:
    """Validate node parameters against the plugin's declared JSON Schema."""
    if plugin is None or not isinstance(plugin.parameter_schema, dict) or not plugin.parameter_schema:
        return []
    try:
        # check_schema must be explicit: constructing a validator does not verify the
        # schema, so a malformed one would otherwise surface as an unhandled error
        # during iter_errors and turn preflight into a 500.
        Draft202012Validator.check_schema(plugin.parameter_schema)
        errors = sorted(
            Draft202012Validator(plugin.parameter_schema).iter_errors(node.parameters or {}),
            key=lambda item: list(item.path),
        )
    except (SchemaError, _JsonSchemaError):
        # A malformed schema is the plugin's defect, reported by registry validation.
        # Do not punish the workflow author for it.
        return []
    return [
        {
            "code": "node_parameters_invalid",
            "message": _parameter_error_message(error),
            "node_key": node.node_key,
            "node_id": str(node.id),
        }
        for error in errors
    ]


def order_pair_blockers(node: Any, plugin: Any) -> list[dict]:
    """Check field pairs a JSON Schema cannot: e.g. ``min_x <= max_x``.

    Draft 2020-12 has no arithmetic between sibling properties, so plugins that need an
    ordering constraint (ProteinHunter's protein length, BindCraft's binder length)
    declare it out-of-band as ``x-bda-order-pairs``: a list of ``[low_key, high_key]``
    pairs that must satisfy ``low <= high`` whenever both are present.
    """
    if plugin is None or not isinstance(plugin.parameter_schema, dict):
        return []
    pairs = plugin.parameter_schema.get("x-bda-order-pairs") or []
    parameters = node.parameters or {}
    blockers = []
    for low_key, high_key in pairs:
        low, high = parameters.get(low_key), parameters.get(high_key)
        if isinstance(low, int | float) and isinstance(high, int | float) and low > high:
            blockers.append(
                {
                    "code": "parameter_order_invalid",
                    "message": f"{low_key} ({low}) must be <= {high_key} ({high})",
                    "node_key": node.node_key,
                    "node_id": str(node.id),
                }
            )
    return blockers


def evaluate_preflight(session: Session, workflow: WorkflowRun) -> tuple[list[dict], list[dict], dict]:
    """Returns (blockers, warnings, checks)."""
    nodes = WorkflowRepository(session).nodes(workflow.id)
    blockers: list[dict] = []
    warnings: list[dict] = []

    if not nodes:
        blockers.append({"code": "workflow_empty", "message": "Workflow has no executable nodes"})
    elif all(getattr(node, "execution_mode", "dispatch") == "manual" for node in nodes):
        # Otherwise submission would succeed and create zero jobs, reporting "submitted"
        # for a run that will never produce anything.
        blockers.append(
            {
                "code": "workflow_all_manual",
                "message": "Every node is a manual stage; there is nothing to submit",
            }
        )

    # Route authors use this flag for a stronger, project-specific readiness gate:
    # inputs may be described in the method yet not be present as immutable artifacts.
    # It must be enforced by the same preflight used by submission; leaving it as canvas
    # metadata allowed a user to dispatch an RFdiffusion node without its scaffold or a
    # ProteinMPNN node without the fixed-position map.
    not_ready = [node.node_key for node in nodes if (node.parameters or {}).get("execution_ready") is False]
    if not_ready:
        blockers.append(
            {
                "code": "route_not_execution_ready",
                "message": "Route is explicitly marked execution_ready=false; bind and verify required inputs first",
                "node_keys": not_ready,
            }
        )

    plugins: dict[str, Any] = {}
    manual_nodes: list[str] = []
    # Plugin-level facts are true of the plugin, not of each node using it. Reported once
    # per plugin: a nine-node route on three plugins was emitting the same two sentences
    # nine times, which is how ten real binding blockers ended up looking like noise.
    plugin_warnings: dict[tuple[str, str], dict] = {}
    for node in nodes:
        # A manual stage is part of the route but is not run here - target intake, a
        # hand-built hotspot map, a scientist reviewing candidates. Requiring a registry
        # plugin for those blocked whole workflows that were otherwise ready, which is why
        # legacy routes ran as hand-written LSF instead of through the platform.
        # The blocker itself stays: it is what stops an unvalidated free-text command from
        # reaching the cluster.
        if getattr(node, "execution_mode", "dispatch") == "manual":
            # Not a warning: a manual stage is the normal, intended state for target
            # intake and candidate review. Listing one per node alongside real problems
            # buried the blockers in a wall of text that read as errors.
            manual_nodes.append(node.node_key)
            continue
        plugin = session.get(ModelPlugin, node.model_plugin_id) if node.model_plugin_id else None
        plugins[node.node_key] = plugin
        if plugin is None:
            blockers.append(
                {
                    "code": "plugin_snapshot_missing",
                    "message": f"Node '{node.node_key}' has no registry plugin",
                    "node_key": node.node_key,
                    "node_id": str(node.id),
                }
            )
            continue
        if not plugin.enabled:
            blockers.append(
                {
                    "code": "plugin_disabled",
                    "message": f"Plugin '{plugin.plugin_key}' is disabled",
                    "node_key": node.node_key,
                    "node_id": str(node.id),
                }
            )
        if plugin.validation_status != "valid":
            plugin_warnings[("plugin_unvalidated", str(plugin.id))] = {
                "code": "plugin_unvalidated",
                "message": (
                    f"Plugin '{plugin.plugin_key}' declaration status is "
                    f"'{plugin.validation_status}'; run registry validation"
                ),
                "plugin_key": plugin.plugin_key,
                "plugin_id": str(plugin.id),
                "plugin_version": plugin.plugin_version,
            }
        # Distinct from the above and more consequential: the declaration can be perfect
        # while the model has never been run. Reported separately so "the record is tidy"
        # is never mistaken for "this is known to work".
        if not runtime_validation_is_current(plugin):
            plugin_warnings[("plugin_runtime_unproven", str(plugin.id))] = {
                "code": "plugin_runtime_unproven",
                "message": (
                    f"Plugin '{plugin.plugin_key}' has no current runtime proof for this "
                    f"declaration; verify parameters and outputs once, then reuse the fingerprinted proof"
                ),
                "plugin_key": plugin.plugin_key,
                "plugin_id": str(plugin.id),
                "plugin_version": plugin.plugin_version,
            }
        blockers.extend(binding_blockers(node, plugin))
        blockers.extend(parameter_blockers(node, plugin))
        blockers.extend(order_pair_blockers(node, plugin))

    nodes_by_key = {node.node_key: node for node in nodes}
    upstream_blockers, checked_edges = _upstream_binding_blockers(nodes_by_key, plugins)
    blockers.extend(upstream_blockers)
    blockers.extend(_edge_blockers(workflow, nodes_by_key, plugins, skip=checked_edges))
    warnings.extend(plugin_warnings[key] for key in sorted(plugin_warnings))

    return (
        blockers,
        warnings,
        {
            "node_count": len(nodes),
            "status": workflow.status,
            "blocker_count": len(blockers),
            # Stated positively so the UI can show "6 of 19 stages are manual" rather than
            # six lines that look like faults.
            "manual_node_count": len(manual_nodes),
            "manual_nodes": manual_nodes,
            "dispatch_node_count": len(nodes) - len(manual_nodes),
        },
    )


def _upstream_binding_blockers(
    nodes: dict[str, Any], plugins: dict[str, Any]
) -> tuple[list[dict], set[tuple[str, str, str, str]]]:
    """Type-check the dataflow declared on nodes, even when graph edges are unported.

    ``input_bindings`` is what submission actually stages. Limiting type checks to graph
    edges let a route display a harmless ordering edge while its real binding connected a
    sequence output to a structure-only input.
    """
    blockers: list[dict] = []
    checked: set[tuple[str, str, str, str]] = set()
    for target_key, target in nodes.items():
        # Manual stages are never submitted and therefore stage no inputs. Their graph
        # relationships document review/order only; treating those annotations as model
        # bindings would reintroduce blockers for the very nodes preflight exempts above.
        if getattr(target, "execution_mode", "dispatch") == "manual":
            continue
        bindings = target.input_bindings if isinstance(target.input_bindings, list) else []
        for binding in bindings:
            if not isinstance(binding, dict) or binding.get("source") != "upstream":
                continue
            source_key = str(binding.get("from_node") or "")
            source_port = str(binding.get("from_port") or "")
            target_port = str(binding.get("port") or "")
            if not (source_key and source_port and target_port):
                # ``binding_blockers`` owns incomplete-binding diagnostics.
                continue
            signature = (source_key, target_key, source_port, target_port)
            checked.add(signature)
            source = nodes.get(source_key)
            if source is None:
                blockers.append(
                    {
                        "code": "input_binding_upstream_node_unknown",
                        "message": f"Upstream node '{source_key}' does not exist",
                        "node_key": target_key,
                        "node_id": str(target.id),
                        "port": target_port,
                    }
                )
                continue
            source_plugin = plugins.get(source_key)
            target_plugin = plugins.get(target_key)
            if target_plugin is None:
                # ``plugin_snapshot_missing`` and ``binding_blockers`` already explain
                # why a dispatch target with no declaration cannot be checked.
                continue
            if source_plugin is None and getattr(source, "execution_mode", "dispatch") != "manual":
                # The source node's own ``plugin_snapshot_missing`` is the actionable
                # error. Reporting every one of its outputs as unknown adds no evidence.
                continue
            port_blockers = edge_port_blockers(
                source_node=source,
                target_node=target,
                source_plugin=source_plugin,
                target_plugin=target_plugin,
                source_port=source_port,
                target_port=target_port,
            )
            # ``binding_blockers`` owns target-port spelling and emits ``input_port_unknown``.
            # Keep source-port and compatibility findings here without duplicating it.
            blockers.extend(item for item in port_blockers if item["code"] != "edge_target_port_unknown")
    return blockers, checked


def _edge_blockers(
    workflow: WorkflowRun,
    nodes: dict[str, Any],
    plugins: dict[str, Any],
    *,
    skip: set[tuple[str, str, str, str]] | None = None,
) -> list[dict]:
    blockers: list[dict] = []
    checked = skip or set()
    for edge in workflow.graph.get("edges", []):
        source_key, target_key = edge.get("source"), edge.get("target")
        source_port, target_port = edge.get("source_port"), edge.get("target_port")
        if not (source_port and target_port):
            # Unported edges express ordering only; that stays valid.
            continue
        source, target = nodes.get(source_key), nodes.get(target_key)
        if source is None or target is None:
            continue
        if getattr(target, "execution_mode", "dispatch") == "manual":
            continue
        if (str(source_key), str(target_key), str(source_port), str(target_port)) in checked:
            continue
        blockers.extend(
            edge_port_blockers(
                source_node=source,
                target_node=target,
                source_plugin=plugins.get(source_key),
                target_plugin=plugins.get(target_key),
                source_port=str(source_port),
                target_port=str(target_port),
            )
        )
    return blockers
