"""Registry validation and health probes.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ..core.celery_app import celery_app
from ..core.database import SessionFactory, session_scope
from .runtime_validation import plugin_declaration_fingerprint


def record_runtime_validation(
    session,
    plugin,
    *,
    proven: bool,
    evidence: dict,
) -> None:
    """Record that a plugin was, or was not, observed to run correctly.

    Deliberately not derived from job exit status. A model that does not recognise a
    parameter usually does not crash - it ignores the parameter and returns plausible
    output, which is indistinguishable from success at the scheduler level. So the caller
    has to say what it checked: which parameters were echoed back by the model's own logs,
    which output files matched the declared ports. ``evidence`` is that statement.
    """
    plugin.runtime_validation_status = "proven" if proven else "failed"
    plugin.runtime_validated_at = datetime.now(UTC)
    plugin.runtime_validation_evidence = {
        **evidence,
        # This is the cache key for a real runtime proof. Preflight reuses the proof
        # until the executable declaration changes, avoiding repeated smoke tests while
        # also preventing a proof for an old command/image/port contract from leaking
        # onto a new one.
        "declaration_fingerprint": plugin_declaration_fingerprint(plugin),
    }
    plugin.version += 1


@celery_app.task(name="bda_v2.registry_model_plugin_validate")
def registry_model_plugin_validate(plugin_id: str) -> dict:
    from ..registry.models import ModelPlugin

    parsed = uuid.UUID(plugin_id)
    with session_scope() as session:
        plugin = session.get(ModelPlugin, parsed)
        if plugin is None:
            return {"plugin_id": plugin_id, "status": "missing"}
        errors = _model_plugin_errors(plugin)
        # Results belong in the dedicated columns. They used to be written into
        # parameter_schema['x-bda-validation'], which corrupted the author's schema and
        # left validation_status stuck at 'unknown' for every plugin.
        #
        # This says nothing about whether the plugin runs: nothing here executes. See
        # record_runtime_validation for that, and runtime_validation_status for the answer.
        plugin.validation_status = "valid" if not errors else "invalid"
        plugin.validation_errors = errors
        plugin.validated_at = datetime.now(UTC)
        plugin.version += 1
    return {"plugin_id": plugin_id, "status": "valid" if not errors else "invalid", "errors": errors}


def _model_plugin_errors(plugin) -> list[str]:
    """Everything structurally wrong with a plugin declaration."""
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError

    from ..registry.ports import port_definition_errors

    errors: list[str] = []
    runtime_mode = getattr(plugin, "runtime_mode", "container") or "container"
    if runtime_mode == "container" and (not plugin.container_image or ":" not in plugin.container_image):
        errors.append("container_image_tag_required")
    if runtime_mode in {"module", "conda"} and not plugin.container_image:
        errors.append("environment_name_required")
    if not plugin.command.strip():
        errors.append("command_required")
    if not isinstance(plugin.parameter_schema, dict) or not isinstance(plugin.output_schema, dict):
        errors.append("schema_must_be_object")
    else:
        for label, schema in (("parameter_schema", plugin.parameter_schema), ("output_schema", plugin.output_schema)):
            if not schema:
                continue
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                errors.append(f"{label}_not_valid_json_schema:{exc.message[:120]}")
    errors.extend(port_definition_errors(plugin.input_ports, plugin.output_ports))
    resources = getattr(plugin, "resources", None)
    if resources is not None and not isinstance(resources, dict):
        errors.append("resources_must_be_object")
    return errors


@celery_app.task(name="bda_v2.registry_compute_node_health")
def registry_compute_node_health(node_id: str) -> dict:
    from ..registry.models import ComputeNode

    parsed = uuid.UUID(node_id)
    with session_scope() as session:
        node = session.get(ComputeNode, parsed)
        if node is None:
            return {"node_id": node_id, "status": "missing"}
        configured = node.backend in {"docker", "lsf"} and node.enabled
        node.labels = {**node.labels, "health": "configured" if configured else "disabled"}
        node.version += 1
    return {"node_id": node_id, "status": "configured" if configured else "disabled"}


@celery_app.task(name="bda_v2.registry_server_test")
def registry_server_test(server_id: str) -> dict:
    from urllib.parse import urlparse

    from ..registry.models import RegistryServer

    parsed = uuid.UUID(server_id)
    with SessionFactory() as session:
        server = session.get(RegistryServer, parsed)
        if server is None:
            return {"server_id": server_id, "status": "missing"}
        parsed_endpoint = urlparse(server.endpoint)
        valid = bool(parsed_endpoint.scheme and (parsed_endpoint.hostname or parsed_endpoint.path))
    return {"server_id": server_id, "status": "configured" if valid else "invalid"}
