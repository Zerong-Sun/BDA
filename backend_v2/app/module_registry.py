"""Single source of truth for domain registration.

The registry stores import paths instead of importing domains at module load time.
API, Alembic and Celery can consume the same descriptors without cross-domain cycles.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from fastapi import APIRouter


@dataclass(frozen=True, slots=True)
class ModuleDescriptor:
    name: str
    model_modules: tuple[str, ...] = ()
    router_modules: tuple[str, ...] = ()
    task_modules: tuple[str, ...] = ()
    permission_actions: tuple[str, ...] = ()
    metric_prefixes: tuple[str, ...] = ()


MODULES = (
    ModuleDescriptor("identity", ("backend_v2.app.identity.models",), ("backend_v2.app.identity.api", "backend_v2.app.identity.organizations_api"), permission_actions=("organization:manage",)),
    ModuleDescriptor("projects", ("backend_v2.app.projects.models",), ("backend_v2.app.projects.api",), ("backend_v2.app.projects.tasks",), ("project:read", "project:write")),
    ModuleDescriptor("targets", ("backend_v2.app.targets.models",), ("backend_v2.app.targets.api",), ("backend_v2.app.targets.tasks",), ("project:write",)),
    ModuleDescriptor("workflows", ("backend_v2.app.workflows.models",), ("backend_v2.app.workflows.api",), permission_actions=("project:write",)),
    ModuleDescriptor("compute", ("backend_v2.app.compute.models",), ("backend_v2.app.compute.api",), ("backend_v2.app.compute.tasks",), ("compute",), ("bda_v2_job", "bda_v2_outbox")),
    ModuleDescriptor("candidates", ("backend_v2.app.candidates.models",), ("backend_v2.app.candidates.api",), permission_actions=("project:read",)),
    ModuleDescriptor("campaigns", ("backend_v2.app.campaigns.models",), ("backend_v2.app.campaigns.api",), ("backend_v2.app.campaigns.tasks",), ("project:write",)),
    ModuleDescriptor("delivery", ("backend_v2.app.delivery.models",), ("backend_v2.app.delivery.api",), ("backend_v2.app.delivery.tasks",), ("artifact",)),
    ModuleDescriptor("artifacts", ("backend_v2.app.artifacts.models",), ("backend_v2.app.artifacts.api",), permission_actions=("artifact",), metric_prefixes=("bda_v2_artifact",)),
    ModuleDescriptor("autopilot", ("backend_v2.app.autopilot.models",), ("backend_v2.app.autopilot.api",), ("backend_v2.app.autopilot.tasks",), ("autopilot",)),
    ModuleDescriptor("audit", ("backend_v2.app.audit.models",), ("backend_v2.app.audit.api",), permission_actions=("project:read",)),
    ModuleDescriptor("experiments", ("backend_v2.app.experiments.models",), ("backend_v2.app.experiments.api",), ("backend_v2.app.experiments.tasks",), ("experiment",)),
    ModuleDescriptor("knowledge", ("backend_v2.app.knowledge.models",), ("backend_v2.app.knowledge.api",), permission_actions=("project:write",)),
    ModuleDescriptor("literature", ("backend_v2.app.literature.models",), ("backend_v2.app.literature.api",), ("backend_v2.app.literature.tasks",), ("research",)),
    ModuleDescriptor("intelligence", ("backend_v2.app.intelligence.models",), ("backend_v2.app.intelligence.api",), ("backend_v2.app.intelligence.tasks",), ("research",)),
    ModuleDescriptor("registry", ("backend_v2.app.registry.models",), ("backend_v2.app.registry.api",), ("backend_v2.app.registry.tasks",), ("registry:manage",)),
    ModuleDescriptor("research", ("backend_v2.app.research.models",), ("backend_v2.app.research.api",), ("backend_v2.app.research.tasks",), ("research",), ("bda_v2_research",)),
    ModuleDescriptor("timeline", ("backend_v2.app.timeline.models",), ("backend_v2.app.timeline.api",), permission_actions=("project:read",)),
    ModuleDescriptor("copilot", ("backend_v2.app.copilot.models",), ("backend_v2.app.copilot.api",), ("backend_v2.app.copilot.tasks",), ("research",), ("bda_v2_copilot",)),
    ModuleDescriptor("ligands", ("backend_v2.app.ligands.models",), ("backend_v2.app.ligands.api",), ("backend_v2.app.ligands.tasks",), ("research",)),
    ModuleDescriptor("platform", ("backend_v2.app.platform.models",), ("backend_v2.app.platform.api",), permission_actions=("platform:manage",), metric_prefixes=("bda_v2_database_pool", "bda_v2_worker")),
    ModuleDescriptor("wetlab", ("backend_v2.app.wetlab.models",), ("backend_v2.app.wetlab.api",), permission_actions=("experiment",)),
)


def _distinct(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def model_modules() -> tuple[str, ...]:
    return _distinct(path for descriptor in MODULES for path in descriptor.model_modules)


def task_modules() -> tuple[str, ...]:
    return _distinct(path for descriptor in MODULES for path in descriptor.task_modules)


def register_models() -> None:
    for path in model_modules():
        import_module(path)


def routers() -> Iterable[APIRouter]:
    for descriptor in MODULES:
        for path in descriptor.router_modules:
            module: Any = import_module(path)
            router = getattr(module, "router", None)
            if not isinstance(router, APIRouter):
                raise RuntimeError(f"{path} must export an APIRouter named router")
            yield router
