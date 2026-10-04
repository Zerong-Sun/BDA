"""Explicit confidence scales: normalize at ingestion, never guess from magnitude.

Platform pLDDT thresholds use 0-100. Boltz native confidence summaries use 0-1:
https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md#output
Coordinate B-factors are a different representation and are not handled here.
Unknown historical rows remain unresolved until their source scale is declared.
"""
from __future__ import annotations

import math

PERCENT = "percent_0_100"
FRACTION = "fraction_0_1"
PERCENT_SCALE_KEYS = frozenset({"plddt", "plddt_min", "iplddt", "binder_plddt", "design_chain_plddt"})
PERCENT_METHODS = frozenset({"alphafold2_superfold", "alphafold3"})
FRACTION_METHODS = frozenset({"boltz", "boltz2", "proteinhunter_boltz"})


def is_confidence(key: str) -> bool:
    return key.split(":", 1)[0] in PERCENT_SCALE_KEYS


def declared_scale(*, context: dict | None = None, unit: str = "", method: str = "") -> str | None:
    if context is not None and not isinstance(context, dict):
        return "invalid_declaration"
    context = context or {}
    units = {"0-100": PERCENT, "pLDDT_0_100": PERCENT, "%": PERCENT, "0-1": FRACTION}
    unit_scale = units.get(unit, unit) if isinstance(unit, str) else "invalid_declaration"
    if "stored_scale" in context:
        stored = context["stored_scale"]
        if not isinstance(stored, str) or (unit_scale and unit_scale != stored):
            return "conflicting_declarations"
        return stored
    if unit_scale:
        return unit_scale
    if not isinstance(method, str):
        return "invalid_declaration"
    if method in PERCENT_METHODS:
        return PERCENT
    if method in FRACTION_METHODS:
        return FRACTION
    return None


def comparison_issue(key: str, value: object, *, context: dict | None = None,
                     unit: str = "", method: str = "") -> str | None:
    """Return a data issue, not a design verdict; comparisons never rescale values."""
    if not is_confidence(key):
        return None
    if context is not None and not isinstance(context, dict):
        return "scale_conflict"
    status = (context or {}).get("scale_status")
    if status is not None and status != "known":
        return "scale_unknown" if status == "unknown" else "scale_conflict"
    scale = declared_scale(context=context, unit=unit, method=method)
    if scale is None or scale == "unknown":
        return "scale_unknown"
    if scale != PERCENT:
        return "scale_conflict"
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or not 0 <= value <= 100:
        return "scale_conflict"
    return None


def normalize(value: float, scale: str, *, source: str) -> tuple[float, dict]:
    """Keep raw values and declarations even when an invalid declaration blocks use."""
    valid = not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= (1 if scale == FRACTION else 100)
    valid = valid and scale in {FRACTION, PERCENT}
    context = {"reported_value": value, "reported_scale": scale, "scale_source": source,
               "stored_scale": PERCENT if valid else "unknown",
               "scale_status": "known" if valid else "scale_conflict"}
    return (value * 100 if valid and scale == FRACTION else value), context
