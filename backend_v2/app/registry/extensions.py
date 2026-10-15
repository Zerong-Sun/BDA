"""Read-only integration readiness from recorded declarations, without probes."""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .models import ComputeNode, LLMProvider, ModelPlugin
from .qualification import model_qualification_issues
from .runtime_validation import runtime_validation_is_current
from .site_runtime import resolve_plugin_runtime


class ExtensionRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    title_zh: str
    boundary: str


class ExtensionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    version: Literal["1.0.0"]
    title: str
    title_zh: str
    description: str
    description_zh: str
    function_ids: list[str]
    adapter: Literal["builtin", "model_registry", "provider_registry", "planned"]
    resources: str
    license_boundary: str
    data_boundary: str
    rollout_trigger: str
    effort: str
    sources: list[str]
    requirements: list[ExtensionRequirement]


class ExtensionAssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_plugin_id: uuid.UUID | None = None
    compute_node_id: uuid.UUID | None = None
    llm_provider_id: uuid.UUID | None = None
    license_review_ref: str = Field(default="", max_length=500)
    data_review_ref: str = Field(default="", max_length=500)
    validation_plan_ref: str = Field(default="", max_length=500)
    budget_review_ref: str = Field(default="", max_length=500)


class ReadinessCheck(BaseModel):
    id: str
    status: Literal["recorded", "missing", "blocked", "not_checked"]
    message: str


class ModelQualificationSummary(BaseModel):
    id: uuid.UUID
    plugin_key: str
    plugin_version: str
    name: str
    enabled: bool
    declaration_valid: bool
    runtime_proof_current: bool
    manifest_pinned: bool
    qualification_recorded: bool
    blockers: list[str]
    warnings: list[str]


class ExtensionAssessment(BaseModel):
    id: str
    state: Literal["built_in", "needs_configuration", "disabled", "not_installed", "planned"]
    ready_for_trial: bool
    scientific_validation: Literal["not_assessed"] = "not_assessed"
    checks: list[ReadinessCheck]
    blockers: list[str]
    warnings: list[str]
    selected_model: ModelQualificationSummary | None = None


class ExtensionEntry(BaseModel):
    manifest: ExtensionManifest
    assessment: ExtensionAssessment


class ExtensionChoice(BaseModel):
    id: uuid.UUID
    name: str
    enabled: bool


class ExtensionCatalog(BaseModel):
    version: Literal["1.0"] = "1.0"
    manifest_checksum_sha256: str
    assessed_at: datetime
    observation_scope: Literal["registry_declarations_only"] = "registry_declarations_only"
    inventory_truncated: bool
    extensions: list[ExtensionEntry]
    models: list[ModelQualificationSummary]
    compute_nodes: list[ExtensionChoice]
    providers: list[ExtensionChoice]


def manifests() -> tuple[list[ExtensionManifest], str]:
    import json
    raw = Path(__file__).with_name("extension_manifests.json").read_bytes()
    items = [ExtensionManifest.model_validate(item) for item in json.loads(raw)]
    if len({item.id for item in items}) != len(items):
        raise ValueError("Duplicate extension id")
    return items, hashlib.sha256(raw).hexdigest()


def model_assessment(plugin: ModelPlugin) -> ModelQualificationSummary:
    blockers, warnings = model_qualification_issues(plugin)
    return ModelQualificationSummary(
        id=plugin.id, plugin_key=plugin.plugin_key, plugin_version=plugin.plugin_version,
        name=plugin.name, enabled=plugin.enabled, declaration_valid=plugin.validation_status == "valid",
        runtime_proof_current=runtime_validation_is_current(plugin), manifest_pinned=bool(plugin.manifest_checksum),
        qualification_recorded=isinstance(plugin.resources, dict) and "scientific_qualification" in plugin.resources,
        blockers=[item["message"] for item in blockers], warnings=[item["message"] for item in warnings],
    )


def assess(manifest: ExtensionManifest, *, proposal: ExtensionAssessmentCreate | None = None,
           plugin: ModelPlugin | None = None, node: ComputeNode | None = None,
           provider: LLMProvider | None = None) -> ExtensionAssessment:
    """Compare explicit selections to existing records; never execute or probe."""
    requested = proposal or ExtensionAssessmentCreate()
    checks: list[ReadinessCheck] = []
    blockers: list[str] = []
    warnings = ["Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity."]

    def check(key, present, message):
        checks.append(ReadinessCheck(id=key, status="recorded" if present else "missing", message=message))
        if not present:
            blockers.append(message)

    state: Literal["built_in", "needs_configuration", "disabled", "not_installed", "planned"] = "needs_configuration"
    selected_model = model_assessment(plugin) if plugin else None
    resources = plugin.resources if plugin and isinstance(plugin.resources, dict) else {}
    if manifest.adapter == "builtin":
        state = "built_in"
        checks.append(ReadinessCheck(id="adapter", status="recorded", message="Implementation is bundled with BDA; deployment health and performance are not probed."))
    elif manifest.adapter == "planned":
        state = "planned"
        blockers.append("No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.")
        checks.append(ReadinessCheck(id="adapter", status="blocked", message=blockers[-1]))
    elif manifest.adapter == "model_registry":
        state = "not_installed" if plugin is None else ("disabled" if not plugin.enabled else "needs_configuration")
        check("model_plugin", plugin is not None, "Select a registered model plugin.")
        if plugin:
            check("enabled", plugin.enabled, "The selected model plugin must be enabled.")
            check("declaration", plugin.validation_status == "valid", "The model declaration must pass registry validation.")
            check("manifest", bool(plugin.manifest_checksum), "Pin the model runtime to a checksummed plugin manifest.")
            check("runtime_proof", runtime_validation_is_current(plugin), "Record runtime proof matching the current declaration fingerprint.")
            qb, qw = model_qualification_issues(plugin)
            blockers.extend(item["message"] for item in qb)
            warnings.extend(item["message"] for item in qw)
            check("checkpoint_review", "scientific_qualification" in resources, "Record the exact checkpoint, license and intended-use review.")
            if node and isinstance(plugin.resources, dict):
                try:
                    resolve_plugin_runtime(plugin, backend=node.backend, queue=node.queue)
                    checks.append(ReadinessCheck(id="site_runtime", status="recorded", message="Declared site runtime resolves for the selected backend; host files have not been inspected."))
                except DomainError as exc:
                    checks.append(ReadinessCheck(id="site_runtime", status="blocked", message=exc.detail))
                    blockers.append(exc.detail)
        check("compute_node", node is not None, "Select a registered compute node for resource review.")
        if node:
            check("compute_enabled", node.enabled, "The selected compute node must be enabled.")
            if node.backend not in {"lsf", "docker"}:
                blockers.append("A scientific-model trial requires a real LSF or Docker backend; a demo declaration is not execution evidence.")
            check("stored_node_health", node.health_status == "healthy", "The compute node needs a recorded healthy status; this inspector never probes the host.")
            requested_gpu = bool(resources.get("gpu"))
            if requested_gpu:
                available_gpus = node.labels.get("gpu_count") if isinstance(node.labels, dict) else None
                needed_gpus = resources.get("gpu_count", 1)
                compatible_gpus = (isinstance(available_gpus, int) and not isinstance(available_gpus, bool)
                                   and isinstance(needed_gpus, int) and not isinstance(needed_gpus, bool)
                                   and available_gpus >= max(1, needed_gpus))
                check("gpu_resources", compatible_gpus, "The model requests a GPU; the selected node must declare enough gpu_count slots.")
                warnings.append("GPU type, memory, scheduler availability and driver compatibility still need site validation.")
    else:
        state = "not_installed" if provider is None else ("disabled" if not provider.enabled else "needs_configuration")
        check("provider", provider is not None, "Select a registered local model provider.")
        if provider:
            check("provider_enabled", provider.enabled, "The selected model provider must be enabled.")
            check("local_deployment", isinstance(provider.config, dict) and provider.config.get("deployment_kind") == "local", "Provider config must explicitly declare deployment_kind=local; an API-shaped URL alone does not prove local hosting.")
            check("provider_model", bool(provider.model and provider.credential_ref), "Provider model and credential reference must be declared; credentials are not read here.")
            warnings.append("Connection, model identity, inference throughput and data egress require separate provider tests; no call was made.")
    if manifest.adapter != "builtin":
        for name, value, message in (
            ("license_review", requested.license_review_ref, "Supply a reviewed code/weights/dependency license reference."),
            ("data_review", requested.data_review_ref, "Supply the data boundary and retention review reference."),
            ("validation_plan", requested.validation_plan_ref, "Supply the scoped benchmark/acceptance plan reference."),
            ("budget_review", requested.budget_review_ref, "Supply the reviewed labor/compute/experiment budget reference."),
        ):
            check(name, bool(value.strip()), message)
        warnings.append("Supplied review references are declarations, not independently verified documents or spending approvals.")
    # Built-in means shipped, never operationally or scientifically validated.
    return ExtensionAssessment(id=manifest.id, state=state, ready_for_trial=not blockers and manifest.adapter == "model_registry",
                               checks=checks, blockers=list(dict.fromkeys(blockers)), warnings=list(dict.fromkeys(warnings)), selected_model=selected_model)


def extension_catalog(session: Session) -> ExtensionCatalog:
    definitions, checksum = manifests()
    # Only public names/IDs/status reach the response: no endpoints, filesystem
    # locations, commands, environment values or credential references.
    models = list(session.scalars(select(ModelPlugin).order_by(ModelPlugin.plugin_key, ModelPlugin.plugin_version).limit(501)))
    nodes = list(session.scalars(select(ComputeNode).order_by(ComputeNode.name).limit(501)))
    providers = list(session.scalars(select(LLMProvider).order_by(LLMProvider.name).limit(501)))
    entries = []
    for definition in definitions:
        assessment = assess(definition)
        observed: list[ModelPlugin | LLMProvider] = []
        if definition.adapter == "model_registry":
            observed.extend(models)
        elif definition.adapter == "provider_registry":
            observed.extend(item for item in providers if isinstance(item.config, dict) and item.config.get("deployment_kind") == "local")
        if observed:
            assessment.state = "needs_configuration" if any(item.enabled for item in observed) else "disabled"
            assessment.checks.insert(0, ReadinessCheck(id="inventory", status="recorded",
                                                       message=f"{len(observed)} matching registry declarations exist. Select exact resources for a scoped assessment; a record does not prove installation."))
        entries.append(ExtensionEntry(manifest=definition, assessment=assessment))
    return ExtensionCatalog(manifest_checksum_sha256=checksum, assessed_at=datetime.now(UTC),
                            inventory_truncated=any(len(items) > 500 for items in (models, nodes, providers)),
                            extensions=entries,
                            models=[model_assessment(item) for item in models[:500]],
                            compute_nodes=[ExtensionChoice(id=item.id, name=item.name, enabled=item.enabled) for item in nodes[:500]],
                            providers=[ExtensionChoice(id=item.id, name=item.name, enabled=item.enabled) for item in providers[:500]])


def assess_extension(session: Session, extension_id: str, proposal: ExtensionAssessmentCreate) -> ExtensionAssessment:
    definition = next((item for item in manifests()[0] if item.id == extension_id), None)
    if definition is None:
        raise DomainError("extension_not_found", "Extension definition was not found.", status_code=404)

    def resource(model, identifier):
        if identifier is None:
            return None
        row = session.get(model, identifier)
        if row is None:
            raise DomainError("extension_resource_not_found", "A selected registry resource was not found.", status_code=404)
        return row

    return assess(definition, proposal=proposal,
                  plugin=resource(ModelPlugin, proposal.model_plugin_id),
                  node=resource(ComputeNode, proposal.compute_node_id),
                  provider=resource(LLMProvider, proposal.llm_provider_id))
