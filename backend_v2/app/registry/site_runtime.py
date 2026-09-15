"""Resolve portable plugin declarations once, before preview or submission.

Workers consume the frozen result, never today's registry/site configuration.
Legacy jobs without a resolved runtime retain their existing adapter behaviour.
"""
from __future__ import annotations

import copy
import re
import shlex

from pydantic import ValidationError

from ..core.problem import DomainError
from .schemas import PluginSiteOverrides


def resolve_plugin_runtime(plugin, *, image=None, queue=None, default_queue="", backend="lsf") -> dict:
    mode = str(getattr(plugin, "runtime_mode", None) or "container")
    reference = image or getattr(plugin, "container_image", None)
    setup = list(getattr(plugin, "runtime_setup", None) or [])
    resources = copy.deepcopy(getattr(plugin, "resources", None) or {})
    raw = getattr(plugin, "site_overrides", None) or {}
    try:
        site = PluginSiteOverrides.model_validate(raw)
    except ValidationError as exc:
        raise DomainError("plugin_site_invalid", "Plugin site overrides are invalid", status_code=422) from exc
    logical = isinstance(reference, str) and reference.startswith("site://")
    if logical and backend == "docker":
        raise DomainError("plugin_site_backend_invalid", "A site runtime requires a host/cluster backend", status_code=422)
    if site.queue and not re.fullmatch(r"[A-Za-z0-9_.+-]+", site.queue):
        raise DomainError("plugin_site_invalid", "Site queue must be a single scheduler identifier", status_code=422)
    if any(key.startswith("BDA_") for key in site.environment):
        raise DomainError("plugin_site_invalid", "Site environment cannot replace platform BDA_* variables; use runtime_root", status_code=422)
    if any(name.startswith("site://") for name in site.module_names):
        raise DomainError("plugin_site_unresolved", "module_names must contain real site module names, not logical site URIs", status_code=422)
    if logical and not (site.runtime_root or site.module_names or setup):
        raise DomainError("plugin_site_unresolved", "Set a runtime_root, module_names or manifest runtime setup for the site runtime", status_code=422)
    if logical and mode == "container":
        raise DomainError("plugin_site_invalid", "A container runtime requires a concrete image", status_code=422)
    if mode == "container" and (site.runtime_root or site.module_names or site.environment):
        raise DomainError("plugin_site_invalid", "Host site setup cannot be applied to a container runtime", status_code=422)

    prefix = []
    if site.runtime_root:
        prefix.append(f"export BDA_PLUGIN_ROOT={shlex.quote(site.runtime_root)}")
    prefix.extend(f"module load {shlex.quote(name)}" for name in site.module_names)
    if logical and mode == "conda" and not setup:
        if not site.runtime_root:
            raise DomainError("plugin_site_unresolved", "A logical conda runtime requires runtime_root or explicit setup", status_code=422)
        prefix.extend(['eval "$(conda shell.bash hook)"', f"conda activate {shlex.quote(site.runtime_root)}"])
    if not logical and (prefix or site.environment) and not setup:
        # Preserve the old automatic activation when adding site exports.
        if mode == "module" and reference and not site.module_names:
            prefix.append(f"module load {shlex.quote(reference)}")
        elif mode == "conda" and reference:
            prefix.extend(['eval "$(conda shell.bash hook)"', f"conda activate {shlex.quote(reference)}"])
    setup = prefix + setup + [f"export {key}={shlex.quote(value)}" for key, value in sorted(site.environment.items())]

    limits = site.resource_limits
    if limits:
        requested = {
            "cpu_cores": resources.get("cpus", 1),
            "memory_mb": resources.get("memory_gb", 0) * 1024,
            "gpu_count": (resources.get("gpu_count") or 1) if resources.get("gpu") else 0,
            "walltime_seconds": resources.get("walltime_minutes", 0) * 60,
        }
        for name, maximum in limits.model_dump(exclude_none=True).items():
            value = requested[name]
            if not isinstance(value, int | float) or value > maximum:
                raise DomainError("plugin_site_resource_limit", f"Plugin request exceeds site {name} limit", status_code=422)

    return {
        "schema_version": "1",
        "runtime_mode": mode,
        "reference": reference,
        # Never pass a site URI to module load/conda activate.
        "image": None if logical else reference,
        "runtime_setup": setup,
        "resources": resources,
        "queue": queue or site.queue or default_queue,
        "site_overrides": site.model_dump(exclude_none=True),
    }
