"""The execution graph and input bindings have one transactional write path."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.problem import DomainError
from ..registry.models import ModelPlugin
from ..registry.ports import parse_input_ports, parse_output_ports, ports_compatible
from .gate_schemas import GatePolicy
from .models import WorkflowRun
from .repository import WorkflowRepository
from .schemas import WorkflowCreate, WorkflowEdgeInput, WorkflowNodeInput
from .service import _require_editable


def canonical_edges(session, nodes, edges, *, strict=True):
    by_key = {n.node_key: n for n in nodes}
    by_id = {str(n.id): n.node_key for n in nodes}
    plugins = {n.node_key: session.get(ModelPlugin, n.model_plugin_id) if n.model_plugin_id else None for n in nodes}
    result = []
    seen = set()
    for raw in edges:
        try:
            edge = WorkflowEdgeInput.model_validate(raw).model_dump(mode="json")
        except ValueError as exc:
            raise DomainError("invalid_connection", str(exc), status_code=422) from exc
        edge["source"] = by_id.get(edge["source"], edge["source"])
        edge["target"] = by_id.get(edge["target"], edge["target"])
        src, dst = edge["source"], edge["target"]
        if src not in by_key or dst not in by_key or src == dst:
            raise DomainError(
                "invalid_connection", "Connection must reference two different workflow nodes", status_code=422
            )
        if edge["id"] in seen:
            raise DomainError("duplicate_connection", "Connection IDs must be unique", status_code=422)
        seen.add(edge["id"])
        if edge["gate"]["mode"] == "dependency":
            if edge.get("source_port") or edge.get("target_port"):
                raise DomainError("invalid_dependency", "A dependency cannot carry data ports", status_code=422)
            edge["gate"]["configured"] = True
            result.append(edge)
            continue
        outputs = parse_output_ports(getattr(plugins[src], "output_ports", []))
        inputs = parse_input_ports(getattr(plugins[dst], "input_ports", []))
        has_binding = any(
            b.get("source") == "upstream" and b.get("from_node") == src for b in by_key[dst].input_bindings
        )
        if (
            not edge.get("source_port")
            and not edge.get("target_port")
            and not has_binding
            and (getattr(by_key[dst], "execution_mode", "dispatch") == "manual" or (not outputs and not inputs))
        ):
            edge["gate"] = GatePolicy(mode="dependency", configured=True).model_dump(mode="json")
            result.append(edge)
            continue
        pairs = [
            (a, b)
            for a in outputs
            for b in inputs
            if ports_compatible(a, b)
            and (not edge.get("source_port") or edge["source_port"] == a.name)
            and (not edge.get("target_port") or edge["target_port"] == b.name)
        ]
        if len(pairs) != 1:
            if strict:
                raise DomainError(
                    "connection_ports_ambiguous",
                    "Choose one compatible output and input port",
                    status_code=422,
                    errors=[{"source_port": a.name, "target_port": b.name} for a, b in pairs],
                )
            edge["gate"]["configured"] = False
        else:
            a, b = pairs[0]
            edge.update(source_port=a.name, target_port=b.name)
            if a.kind in {"params", "msa", "ligand"}:
                edge["gate"] = GatePolicy(mode="integrity", configured=True).model_dump(mode="json")
        result.append(edge)
    # One DAG validator for every graph mutation, including legacy repair.
    try:
        WorkflowCreate(
            name="validate",
            nodes=[
                WorkflowNodeInput(key=n.node_key, node_type=n.node_type, model_plugin=n.model_plugin) for n in nodes
            ],
            edges=result,
        )
    except ValueError as exc:
        raise DomainError("invalid_connection_graph", str(exc), status_code=422) from exc
    return result


def replace_connections(session: Session, workflow: WorkflowRun, edges: list[dict], expected_version: int):
    session.flush()
    session.refresh(workflow, with_for_update=True)
    _require_editable(workflow, expected_version)
    nodes = WorkflowRepository(session).nodes(workflow.id)
    result = canonical_edges(session, nodes, edges)
    bindings = {n.node_key: [b for b in n.input_bindings if b.get("source") != "upstream"] for n in nodes}
    for edge in result:
        if edge["gate"]["mode"] != "dependency":
            bindings[edge["target"]].append(
                {
                    "port": edge["target_port"],
                    "source": "upstream",
                    "from_node": edge["source"],
                    "from_port": edge["source_port"],
                }
            )
    from ..compute.binding import binding_blockers

    for n in nodes:
        plugin = session.get(ModelPlugin, n.model_plugin_id) if n.model_plugin_id else None
        from types import SimpleNamespace

        issues = binding_blockers(SimpleNamespace(node_key=n.node_key, input_bindings=bindings[n.node_key]), plugin)
        # Incomplete drafts are allowed, contradictory bindings are not.
        issues = [i for i in issues if i["code"] not in {"input_binding_unsatisfied", "input_group_unsatisfied"}]
        if issues:
            raise DomainError(
                "invalid_connection_binding", "Connection conflicts with input bindings", status_code=422, errors=issues
            )
    for n in nodes:
        n.input_bindings = bindings[n.node_key]
        n.version += 1
    graph = dict(workflow.graph)
    graph["edges"] = result
    graph["nodes"] = [{**item, "input_bindings": bindings.get(item.get("key"), [])} for item in graph.get("nodes", [])]
    workflow.graph = graph
    workflow.version += 1
    session.flush()
    return result


def initialize_connections(session, workflow):
    nodes = WorkflowRepository(session).nodes(workflow.id)
    edges = canonical_edges(session, nodes, workflow.graph.get("edges", []), strict=False)
    for node in nodes:
        for edge in edges:
            if edge["target"] == node.node_key and edge.get("source_port") and edge.get("target_port"):
                binding = {
                    "port": edge["target_port"],
                    "source": "upstream",
                    "from_node": edge["source"],
                    "from_port": edge["source_port"],
                }
                if binding not in node.input_bindings and not any(
                    b.get("port") == binding["port"] for b in node.input_bindings
                ):
                    node.input_bindings = [*node.input_bindings, binding]
    workflow.graph = {
        **workflow.graph,
        "edges": edges,
        "nodes": [
            {**item, "input_bindings": next((n.input_bindings for n in nodes if n.node_key == item.get("key")), [])}
            for item in workflow.graph.get("nodes", [])
        ],
    }
