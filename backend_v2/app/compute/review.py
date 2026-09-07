"""Bind a reviewed script to its plugin declaration, inputs and execution site."""

from __future__ import annotations

import hashlib
import json

from ..core.config import get_settings
from ..registry.runtime_validation import plugin_declaration_fingerprint
from .scripts import preview_context, render_script


def render_review(node, plugin, backend: str, manifest: dict) -> tuple[str, str]:
    command = (plugin.command if plugin else None) or node.command or ""
    script = render_script(preview_context(node, plugin, backend, command, manifest["parameters"]))
    settings = get_settings()
    site = (
        {"host": settings.lsf_ssh_host, "root": settings.lsf_remote_root, "staging": settings.lsf_staging_mode}
        if backend == "lsf"
        else {"host": settings.docker_host}
        if backend == "docker"
        else {}
    )
    material = {
        "node_id": str(node.id),
        "backend": backend,
        "script": script,
        "manifest": manifest,
        "site": site,
        "plugin": plugin_declaration_fingerprint(plugin) if plugin else None,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return script, digest
