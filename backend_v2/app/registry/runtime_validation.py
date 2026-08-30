"""Reusable runtime-proof fingerprints for model plugins.

Runtime validation is expensive because it needs a real cluster execution. The proof is
reusable while the executable declaration and the externally supplied rule/environment
fingerprints are unchanged. A changed command, image/environment, schema, port contract,
resource declaration, parser, adapter, runtime setup, ruleset, or environment invalidates
the proof automatically.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

DECLARATION_FIELDS = (
    "plugin_key",
    "plugin_version",
    "container_image",
    "command",
    "parameter_schema",
    "output_schema",
    "input_ports",
    "output_ports",
    "resources",
    "runtime_mode",
    "runtime_setup",
    "output_parser",
    "input_adapter",
)


def plugin_declaration_fingerprint(plugin: Any) -> str:
    payload = {field: getattr(plugin, field, None) for field in DECLARATION_FIELDS}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def runtime_validation_is_current(plugin: Any) -> bool:
    if getattr(plugin, "runtime_validation_status", "unproven") != "proven":
        return False
    evidence = getattr(plugin, "runtime_validation_evidence", None)
    if not isinstance(evidence, dict):
        return False
    recorded = evidence.get("declaration_fingerprint")
    return isinstance(recorded, str) and recorded == plugin_declaration_fingerprint(plugin)
