"""Small provider protocol checks. These qualify task mechanics, not scientific validity."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..registry.models import LLMProvider
from .models import CopilotConfig
from .provider import completion_message
from .provider_selection import select_provider

REQUIREMENTS = {
    "brief": {"structured_output", "tools"},
    "literature": {"structured_output", "evidence", "tools"},
    "planning": {"structured_output", "routing", "tools"},
    "execution": {"structured_output", "tools"},
    "interpretation": {"structured_output", "evidence", "tools"},
}


def fingerprint(provider: LLMProvider) -> str:
    return hashlib.sha256(json.dumps([str(provider.id), provider.version, provider.endpoint, provider.model,
                                     provider.credential_ref, provider.config], sort_keys=True).encode()).hexdigest()


def readiness(session: Session, project_id) -> dict:
    provider = select_provider(session, project_id=project_id)
    row = session.scalar(select(CopilotConfig).where(CopilotConfig.project_id == project_id))
    saved = (row.settings or {}).get("task_qualification", {}) if row else {}
    valid = False
    if provider and saved.get("fingerprint") == fingerprint(provider):
        try:
            valid = datetime.fromisoformat(saved["checked_at"]) > datetime.now(UTC) - timedelta(days=7)
        except (ValueError, TypeError, KeyError):
            pass
    checks = saved.get("checks", {}) if valid else {}
    return {"model": provider.model if provider else "", "checked_at": saved.get("checked_at") if valid else None,
            "checks": checks, "eligible_services": [key for key, required in REQUIREMENTS.items() if all(checks.get(c) is True for c in required)],
            "reason": saved.get("reason") if valid else "Run task checks for the current model before starting a guided task."}


def assess(session: Session, project_id) -> dict:
    provider = select_provider(session, project_id=project_id)
    if not provider:
        return readiness(session, project_id)
    checks = {"structured_output": False, "evidence": False, "routing": False, "tools": False}
    reason = None
    try:
        response = completion_message(provider, [{"role": "user", "content": (
            'Protocol test, no external actions. Return JSON only with fields objective, success_criteria, missing, '
            'source_id, value, route_id. Task: compare recorded affinity; success is a cited comparison; '
            'missing: control experiment. The only evidence is {"source_id":"bda-check-source","value":7}. '
            'Routes: route-ready is available; route-missing lacks a required plugin. Select the available route. '
            'Copy source_id and value exactly; do not add unsupported claims. objective and success_criteria are strings, missing is an array.'
        )}])
        value = json.loads(str(response.get("content") or ""))
        checks["structured_output"] = isinstance(value, dict) and all(isinstance(value.get(k), str) and value[k].strip() for k in ("objective", "success_criteria")) and isinstance(value.get("missing"), list) and bool(value["missing"])
        if isinstance(value, dict):
            checks["evidence"] = value.get("source_id") == "bda-check-source" and value.get("value") == 7
            checks["routing"] = value.get("route_id") == "route-ready"
    except Exception as exc:
        reason = type(exc).__name__  # Provider messages may contain credentials or echoed private inputs.
    try:
        response = completion_message(provider, [{"role": "user", "content": 'Call bda_protocol_check exactly once with {"value":7}. This is a protocol test.'}], tools=[{
            "type": "function", "function": {"name": "bda_protocol_check", "description": "A test-only function; never executes a domain action.",
            "parameters": {"type": "object", "properties": {"value": {"type": "integer", "enum": [7]}}, "required": ["value"], "additionalProperties": False}}}])
        calls = response.get("tool_calls", [])
        checks["tools"] = len(calls) == 1 and calls[0]["function"]["name"] == "bda_protocol_check" and json.loads(calls[0]["function"]["arguments"]) == {"value": 7}
    except Exception as exc:
        reason = type(exc).__name__
    row = session.scalar(select(CopilotConfig).where(CopilotConfig.project_id == project_id))
    if row is None:
        row = CopilotConfig(project_id=project_id, settings={}, enabled_skills=["research"])
        session.add(row)
        session.flush()
    row.settings = {**(row.settings or {}), "task_qualification": {"fingerprint": fingerprint(provider), "checked_at": datetime.now(UTC).isoformat(), "checks": checks, "reason": reason}}
    row.version += 1
    session.flush()
    return readiness(session, project_id)
