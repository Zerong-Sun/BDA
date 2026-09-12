"""Reviewable parameter suggestions and static script imports. Imports never execute."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex

from ..core.problem import DomainError
from .gate_schemas import GatePolicy, ScriptImport


def parse_script(payload: ScriptImport) -> dict:
    parameters, warnings = {}, []
    commands: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []
    if payload.language == "python":
        try:
            tree = ast.parse(payload.source)
        except SyntaxError as exc:
            raise DomainError("script_syntax_invalid", str(exc), status_code=422) from exc
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    value = ast.literal_eval(node.value)
                    json.dumps(value, allow_nan=False)
                    parameters[node.targets[0].id] = value
                except (ValueError, TypeError):
                    warnings.append(f"Dynamic assignment: {node.targets[0].id}")
        for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            name = ast.unparse(call.func)
            if (
                name
                in {
                    "subprocess.run",
                    "subprocess.call",
                    "subprocess.check_call",
                    "subprocess.check_output",
                    "subprocess.Popen",
                    "os.system",
                }
                and call.args
            ):
                try:
                    command = ast.literal_eval(call.args[0])
                    if isinstance(command, str) or (
                        isinstance(command, list) and all(isinstance(v, str) for v in command)
                    ):
                        commands.append(command if isinstance(command, str) else shlex.join(command))
                except (ValueError, TypeError):
                    warnings.append("Dynamic command requires a manual declaration")
            if name == "open" and call.args:
                try:
                    filename = ast.literal_eval(call.args[0])
                    mode_node = (
                        call.args[1]
                        if len(call.args) > 1
                        else next((k.value for k in call.keywords if k.arg == "mode"), ast.Constant("r"))
                    )
                    mode = ast.literal_eval(mode_node)
                    if isinstance(filename, str) and isinstance(mode, str):
                        (outputs if any(c in mode for c in "wax+") else inputs).append(filename)
                except (ValueError, TypeError):
                    warnings.append("Dynamic file path requires an input/output declaration")
    else:
        for line in payload.source.splitlines():
            match = re.fullmatch(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*", line)
            if match:
                key, raw = match.groups()
                if "$" in raw or "`" in raw or ";" in raw:
                    warnings.append(f"Dynamic assignment: {key}")
                    continue
                try:
                    tokens = shlex.split(raw, comments=True)
                    value = tokens[0] if len(tokens) == 1 else ""
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        pass
                    parameters[key] = value
                except ValueError:
                    warnings.append(f"Unparsed assignment: {key}")
            elif line.strip() and not line.lstrip().startswith("#"):
                try:
                    tokens = shlex.split(line, comments=True)
                    if tokens:
                        commands.append(line.strip())
                    for i, token in enumerate(tokens[:-1]):
                        if token in {"--input", "-i", "<"}:
                            inputs.append(tokens[i + 1])
                        if token in {"--output", "-o", ">", ">>"}:
                            outputs.append(tokens[i + 1])
                except ValueError:
                    warnings.append("Unparsed shell command requires a manual declaration")
    warnings.append("Confirm plugin runtime, input/output ports and output parser before binding this script.")
    return {
        **payload.model_dump(),
        "checksum_sha256": hashlib.sha256(payload.source.encode()).hexdigest(),
        "parameters": parameters,
        "commands": commands,
        "inputs": list(dict.fromkeys(inputs)),
        "outputs": list(dict.fromkeys(outputs)),
        "warnings": warnings,
    }


def validate_configuration(configuration: dict, plugin=None):
    policy = configuration.get("output_policy")
    if policy is not None:
        try:
            GatePolicy.model_validate(policy)
        except ValueError as exc:
            raise DomainError("output_policy_invalid", str(exc), status_code=422) from exc
    script = configuration.get("script")
    if script:
        parsed = parse_script(ScriptImport.model_validate(script))
        if parsed["checksum_sha256"] != script.get("checksum_sha256"):
            raise DomainError(
                "script_checksum_mismatch", "Script content changed; import this version again", status_code=422
            )
        if plugin is not None and (not plugin.output_ports or not plugin.output_parser or not plugin.command):
            raise DomainError(
                "script_contract_incomplete",
                "Declare runtime, output ports and result parser on the plugin",
                status_code=422,
            )
    links = configuration.get("parameter_links", {})
    if not isinstance(links, dict):
        raise DomainError("parameter_links_invalid", "Parameter links must be a mapping", status_code=422)
    for name, link in links.items():
        if not isinstance(link, dict):
            raise DomainError("parameter_link_invalid", f"Parameter link {name} must be an object", status_code=422)
        if link.get("source") not in {"upstream_parameter", "selected_count"} or not link.get("from_node"):
            raise DomainError("parameter_link_invalid", f"Invalid parameter link: {name}", status_code=422)
        if link["source"] == "upstream_parameter" and not link.get("parameter"):
            raise DomainError("parameter_link_invalid", f"Missing source parameter: {name}", status_code=422)
        if plugin and name not in (plugin.parameter_schema or {}).get("properties", {}):
            raise DomainError("parameter_link_unknown", f"Plugin does not declare {name}", status_code=422)


def node_command(node, plugin):
    script = (getattr(node, "configuration", None) or {}).get("script")
    if not script:
        return (plugin.command if plugin else None) or node.command or ""
    validate_configuration(node.configuration, plugin)
    parameters = getattr(node, "parameters", {}) or {}
    adapted = script["source"]
    if script["language"] == "python":
        tree = ast.parse(adapted)
        for statement in tree.body:
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
            ):
                name = statement.targets[0].id
                if name in parameters:
                    try:
                        ast.literal_eval(statement.value)
                    except (ValueError, TypeError):
                        continue
                    statement.value = ast.parse(repr(parameters[name]), mode="eval").body
        adapted = ast.unparse(ast.fix_missing_locations(tree))
    else:
        lines = []
        parsed = parse_script(ScriptImport.model_validate(script))
        for line in adapted.splitlines():
            match = re.fullmatch(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*", line)
            if match and match.group(1) in parsed["parameters"] and match.group(1) in parameters:
                name = match.group(1)
                value = parameters[name]
                value = json.dumps(value) if not isinstance(value, str) else value
                line = ("export " if line.lstrip().startswith("export ") else "") + name + "=" + shlex.quote(value)
            lines.append(line)
        adapted = "\n".join(lines)
    interpreter = "python3" if script["language"] == "python" else "bash"
    marker = "BDA_NODE_" + hashlib.sha256(adapted.encode()).hexdigest()
    return f"{interpreter} - <<'{marker}'\n{adapted}\n{marker}"


def context_fingerprint(workflow, nodes):
    return hashlib.sha256(
        json.dumps(
            {
                "version": workflow.version,
                "nodes": [
                    {
                        "id": str(n.id),
                        "version": n.version,
                        "parameters": n.parameters,
                        "configuration": n.configuration,
                    }
                    for n in nodes
                ],
            },
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


def suggest_parameters(workflow, node, nodes, plugin, project, session=None):
    by_key = {n.node_key: n for n in nodes}
    properties = (getattr(plugin, "parameter_schema", {}) or {}).get("properties", {})
    suggestions = []
    # Plugin authors explicitly declare semantic links; identical field names aren't evidence.
    mappings = (getattr(plugin, "parameter_schema", {}) or {}).get("x-bda-upstream-parameters", {})
    for target, mapping in mappings.items():
        if target not in properties:
            continue
        binding = next(
            (b for b in node.input_bindings if b.get("source") == "upstream" and b.get("port") == mapping.get("port")),
            None,
        )
        source = by_key.get(binding.get("from_node")) if binding else None
        if source and mapping.get("parameter") in source.parameters:
            suggestions.append(
                {
                    "parameter": target,
                    "current": node.parameters.get(target),
                    "value": source.parameters[mapping["parameter"]],
                    "source": f"{source.node_key}.{mapping['parameter']}",
                    "reason": "Explicit plugin upstream parameter mapping",
                }
            )
    for name, schema in properties.items():
        if (
            isinstance(schema, dict)
            and "default" in schema
            and name not in node.parameters
            and not any(s["parameter"] == name for s in suggestions)
        ):
            suggestions.append(
                {
                    "parameter": name,
                    "current": None,
                    "value": schema["default"],
                    "source": "plugin.parameter_schema",
                    "reason": "Declared default for this plugin version",
                }
            )
    upstream_results = []
    if session is not None:
        from sqlalchemy import select

        from ..compute.models import Job
        from .models import WorkflowResult

        source_workflows = [workflow.id, *([workflow.derived_from_id] if workflow.derived_from_id else [])]
        for binding in node.input_bindings:
            source_node = by_key.get(binding.get("from_node"))
            if binding.get("source") != "upstream" or source_node is None:
                continue
            jobs = session.scalars(
                select(Job)
                .where(Job.workflow_run_id.in_(source_workflows), Job.status == "succeeded")
                .order_by(Job.created_at.desc())
            )
            job = next(
                (
                    j
                    for j in jobs
                    if j.runtime_spec.get("node_key") == source_node.node_key
                    and (j.runtime_spec.get("plugin_snapshot") or {}).get("id") == str(source_node.model_plugin_id)
                ),
                None,
            )
            if job is None:
                continue
            records = [
                r
                for r in session.scalars(select(WorkflowResult).where(WorkflowResult.job_id == job.id))
                if any(f["port"] == binding["from_port"] for f in r.payload.get("files", []))
            ]
            upstream_results.append(
                {
                    "node_key": source_node.node_key,
                    "port": binding["from_port"],
                    "job_id": str(job.id),
                    "attempt": job.attempt_number,
                    "count": len(records),
                    "metrics": sorted({k for r in records for k in r.payload.get("metrics", {})}),
                }
            )
    return {
        "upstream_results": upstream_results,
        "fingerprint": context_fingerprint(workflow, nodes),
        "workflow_version": workflow.version,
        "objective": getattr(project, "summary", None) or project.name,
        "suggestions": suggestions,
        "inputs": node.input_bindings,
        "parameter_links": node.configuration.get("parameter_links", {}),
    }


def resolve_parameter_links(job, by_key):
    from jsonschema import Draft202012Validator

    parameters = dict(job.runtime_spec.get("parameters", {}))
    for name, link in job.runtime_spec.get("configuration", {}).get("parameter_links", {}).items():
        source = by_key.get(link["from_node"])
        if source is None:
            raise ValueError(f"parameter_source_missing:{link['from_node']}")
        if link["source"] == "selected_count":
            counts = job.runtime_spec.get("gate_selected_counts", {})
            if link["from_node"] not in counts:
                raise ValueError("selected_count_source_not_connected")
            parameters[name] = counts[link["from_node"]]
        else:
            values = source.runtime_spec.get("parameters", {})
            if link["parameter"] not in values:
                raise ValueError(f"upstream_parameter_missing:{link['parameter']}")
            parameters[name] = values[link["parameter"]]
    schema = (job.runtime_spec.get("plugin_snapshot") or {}).get("parameter_schema")
    if schema:
        Draft202012Validator(schema).validate(parameters)
    manifest = {**job.runtime_spec.get("input_manifest", {}), "parameters": parameters}
    job.runtime_spec = {**job.runtime_spec, "parameters": parameters, "input_manifest": manifest}
    if job.runtime_spec.get("configuration", {}).get("script"):
        from types import SimpleNamespace

        snapshot = job.runtime_spec.get("plugin_snapshot")
        plugin = SimpleNamespace(**snapshot) if snapshot else None
        node = SimpleNamespace(
            parameters=parameters,
            configuration=job.runtime_spec["configuration"],
            command=job.runtime_spec.get("command"),
        )
        command = node_command(node, plugin)
        job.runtime_spec = {
            **job.runtime_spec,
            "command": command,
            "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        }
