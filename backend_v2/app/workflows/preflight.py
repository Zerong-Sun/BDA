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
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..compute.binding import binding_blockers, edge_port_blockers
from ..registry.models import ModelPlugin
from ..registry.ports import parse_output_ports
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
        deferred = set((getattr(node, "configuration", None) or {}).get("parameter_links", {}))
        schema = {
            **plugin.parameter_schema,
            "required": [k for k in plugin.parameter_schema.get("required", []) if k not in deferred],
        }
        parameters = {k: v for k, v in (node.parameters or {}).items() if k not in deferred}
        errors = sorted(
            Draft202012Validator(schema).iter_errors(parameters),
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

    from pydantic import ValidationError

    from ..core.problem import DomainError
    from .assistance import validate_configuration
    from .gate_schemas import GatePolicy

    for node in nodes:
        try:
            plugin = session.get(ModelPlugin, node.model_plugin_id) if node.model_plugin_id else None
            validate_configuration(node.configuration or {}, plugin)
            for name, link in (node.configuration or {}).get("parameter_links", {}).items():
                if not any(
                    b.get("source") == "upstream" and b.get("from_node") == link["from_node"]
                    for b in node.input_bindings
                ):
                    raise ValueError(f"Parameter {name} must reference a connected upstream node")
        except (ValueError, DomainError) as exc:
            blockers.append({"code": "node_configuration_invalid", "node_key": node.node_key, "message": str(exc)})
    by_key = {n.node_key: n for n in nodes}
    signatures = {
        (e.get("source"), e.get("target"), e.get("source_port"), e.get("target_port"))
        for e in workflow.graph.get("edges", [])
        if e.get("gate", {}).get("mode") != "dependency"
    }
    for node in nodes:
        for b in node.input_bindings:
            if (
                b.get("source") == "upstream"
                and (b.get("from_node"), node.node_key, b.get("from_port"), b.get("port")) not in signatures
            ):
                blockers.append(
                    {
                        "code": "binding_connection_missing",
                        "node_key": node.node_key,
                        "message": "Input binding requires a matching data connection and gate",
                    }
                )
    for edge in workflow.graph.get("edges", []):
        if getattr(by_key.get(edge.get("target")), "execution_mode", "dispatch") == "manual":
            continue
        try:
            policy = GatePolicy.model_validate(edge.get("gate") or {})
            source = by_key.get(edge.get("source"))
            inherited = (
                (source.configuration or {}).get("output_policy") if source and policy.mode != "integrity" else None
            )
            if not edge.get("id") or not policy.configured:
                raise ValueError("Configure the connection gate before submitting")
            if policy.mode != "dependency" and not (edge.get("source_port") and edge.get("target_port")):
                raise ValueError("Connect explicit input/output ports")
            if policy.mode != "dependency":
                target = by_key.get(edge.get("target"))
                if target is None or not any(
                    b.get("source") == "upstream"
                    and b.get("from_node") == edge["source"]
                    and b.get("from_port") == edge.get("source_port")
                    and b.get("port") == edge.get("target_port")
                    for b in target.input_bindings
                ):
                    raise ValueError("Data connection requires a matching input binding")
            if policy.mode == "integrity":
                source_plugin = (
                    session.get(ModelPlugin, source.model_plugin_id) if source and source.model_plugin_id else None
                )
                from ..registry.ports import parse_output_ports

                out = next(
                    (
                        p
                        for p in parse_output_ports(getattr(source_plugin, "output_ports", []))
                        if p.name == edge.get("source_port")
                    ),
                    None,
                )
                if not out or (
                    out.kind not in {"params", "msa", "ligand"}
                    and (source is None or source.node_type not in {"target_intake", "interface_constraints"})
                ):
                    raise ValueError(
                        "Candidate outputs require candidate screening; integrity gates are for reference inputs"
                    )
            from .gate_service import script_preview_valid

            if not script_preview_valid(session, workflow, edge, inherited):
                raise ValueError("Preview this script and policy on an upstream result set before enabling it")
            inherited_rules = GatePolicy.model_validate(inherited) if inherited else None
            inherited_configured = (
                inherited_rules
                and inherited_rules.configured
                and (
                    inherited_rules.rules.conditions
                    or inherited_rules.rules.top_n
                    or inherited_rules.structure
                    or inherited_rules.script
                )
            )
            if policy.mode == "automatic" and not (
                policy.rules.conditions
                or policy.rules.top_n
                or policy.structure
                or policy.script
                or inherited_configured
            ):
                raise ValueError("Automatic candidate gates require an output standard or a screening rule")
        except (ValueError, ValidationError) as exc:
            blockers.append(
                {
                    "code": "connection_gate_unconfigured",
                    "node_key": edge.get("target"),
                    "edge_id": edge.get("id"),
                    "message": str(exc),
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
    warnings.extend(unroutable_output_warnings(workflow, plugins))
    warnings.extend(queue_capability_warnings(session, nodes, plugins))

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



def unroutable_output_warnings(workflow: WorkflowRun, plugins: dict[str, Any]) -> list[dict]:
    """Connections whose source port can never be attached to a collected file.

    Collection tags an output with a port in one of two ways: the file sits under
    ``outputs/<port>/``, or its name matches the port's ``filename_glob``. A glob of
    ``*`` is deliberately not matched - it would claim every file for whichever port
    happened to be declared first - so a port left at the default can only ever be
    filled by the directory route.

    When neither applies the artifact is stored untyped, the gate finds no records on
    that port and settles as ``error``, and the downstream node waits forever. That is
    the state a real run reached on 2026-09-11: ProteinMPNN succeeded on the cluster,
    three outputs were collected and verified, and the gate could not see any of them.
    """
    findings: dict[str, dict] = {}
    for edge in workflow.graph.get("edges", []):
        if (edge.get("gate") or {}).get("mode") == "dependency":
            continue
        source_key, port_name = edge.get("source"), edge.get("source_port")
        plugin = plugins.get(str(source_key))
        if not port_name or plugin is None:
            continue
        port = next(
            (item for item in parse_output_ports(plugin.output_ports) if item.name == port_name), None
        )
        if port is None or port.filename_glob not in {"", "*"}:
            continue
        findings[f"{plugin.plugin_key}:{port_name}"] = {
            "code": "output_port_unroutable",
            "message": (
                f"Plugin '{plugin.plugin_key}' declares output port '{port_name}' with no filename "
                f"pattern, so a collected file can only be attached to it by being written to "
                f"outputs/{port_name}/. If the model writes elsewhere the gate on this connection "
                f"will find no results and stop with an error."
            ),
            "plugin_key": plugin.plugin_key,
            "plugin_id": str(plugin.id),
            "port": str(port_name),
        }
    return [findings[key] for key in sorted(findings)]


def queue_capability_warnings(session: Session, nodes: list, plugins: dict[str, Any]) -> list[dict]:
    """A node whose queue contradicts what its plugin says it needs.

    The platform cannot tell a GPU queue from a CPU one by its name - ``63``, ``v3-64``
    and ``4v100-16-e5`` are all just strings. It can tell when the deployment has said
    so: a ``compute_nodes`` row names a queue and labels its ``gpu_count``. Nothing is
    reported for a queue nobody registered, so this is silent until it can be right.

    Both directions matter and both have been paid for here. A GPU plugin on a queue with
    no GPUs pends or dies. A CPU-only stage on a GPU queue holds an exclusive card it
    never uses, which this project treats as a violation rather than a notice - and the
    queue can merge that request in on its own, so an absent ``-gpu`` line is no defence.
    """
    from ..registry.models import ComputeNode

    registered = session.scalars(select(ComputeNode).where(ComputeNode.enabled.is_(True))).all()
    by_queue = {node.queue: node for node in registered if node.queue}
    if not by_queue:
        return []
    findings: list[dict] = []
    for node in nodes:
        if getattr(node, "execution_mode", "dispatch") == "manual" or not node.queue:
            continue
        plugin = plugins.get(node.node_key)
        target = by_queue.get(node.queue)
        if plugin is None or target is None:
            continue
        labels = target.labels if isinstance(target.labels, dict) else {}
        available = labels.get("gpu_count")
        if not isinstance(available, int):
            continue
        resources = plugin.resources if isinstance(plugin.resources, dict) else {}
        wanted = int(resources.get("gpu_count") or 1) if resources.get("gpu") else 0
        if wanted and not available:
            message = (
                f"Plugin '{plugin.plugin_key}' declares {wanted} GPU(s) but queue '{node.queue}' is "
                f"registered with none; the job will ask for hardware the queue cannot give it."
            )
        elif available and not wanted:
            message = (
                f"Plugin '{plugin.plugin_key}' declares no GPU but queue '{node.queue}' is registered "
                f"with {available}; the queue can attach one anyway and the job would hold it unused."
            )
        else:
            continue
        findings.append(
            {
                "code": "node_queue_capability_mismatch",
                "message": message,
                "node_key": node.node_key,
                "node_id": str(node.id),
                "queue": node.queue,
                "plugin_key": plugin.plugin_key,
            }
        )
    return findings


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
