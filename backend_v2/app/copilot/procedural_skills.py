"""Versioned scientific methods, distinct from capability authorization.

Only reviewed, bundled Markdown is loaded. There is no remote installer, script
execution, or plugin import. Runs retain the exact instruction/manifest snapshot
so a deployment cannot silently change a method halfway through a task.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..core.problem import DomainError

BUNDLE_ROOT = Path(__file__).with_name("skill_packages")
MAX_SELECTED = 3


class SkillProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str
    relation: Literal["format", "method_reference"]
    note: str


class ProceduralSkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str
    title_zh: str
    description: str
    description_zh: str
    license: Literal["Apache-2.0"]
    author: Literal["BDA contributors"]
    instruction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    default_for: list[str]
    tool_requests: list[str]
    optional_write_tools: list[str]
    data_policy: str
    provenance: list[SkillProvenance]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ProceduralSkillSummary(ProceduralSkillManifest):
    checksum_sha256: str


class ProceduralSkillDetail(ProceduralSkillSummary):
    instructions: str


def _digest(manifest: dict, instructions: str) -> str:
    content = json.dumps({"manifest": manifest, "instructions": instructions}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def _read_package(directory: Path) -> ProceduralSkillDetail:
    manifest = ProceduralSkillManifest.model_validate_json((directory / "manifest.json").read_text())
    instructions = (directory / "SKILL.md").read_bytes().decode("utf-8")
    if manifest.id != directory.name or hashlib.sha256(instructions.encode()).hexdigest() != manifest.instruction_sha256:
        raise ValueError(f"Skill package integrity mismatch: {directory.name}")
    # The packages use a small, valid YAML subset. Do not require a YAML runtime
    # or treat arbitrary frontmatter values as configuration/executable code.
    if not instructions.startswith(f'---\nname: {manifest.id}\n') or "\n---\n" not in instructions[4:]:
        raise ValueError(f"Invalid Agent Skills frontmatter: {directory.name}")
    for schema in (manifest.input_schema, manifest.output_schema):
        Draft202012Validator.check_schema(schema)
    from . import tools as _tools  # noqa: F401
    from .registry import REGISTRY
    unknown = set(manifest.tool_requests + manifest.optional_write_tools) - {tool.id for tool in REGISTRY.all()}
    if unknown or not set(manifest.optional_write_tools) <= REGISTRY.user_intent_write_ids():
        raise ValueError(f"Invalid tool declarations for {directory.name}: {sorted(unknown)}")
    if set(manifest.tool_requests) & REGISTRY.user_intent_write_ids():
        raise ValueError(f"Write tool must be declared optional: {directory.name}")
    return ProceduralSkillDetail(**manifest.model_dump(), instructions=instructions,
                                 checksum_sha256=_digest(manifest.model_dump(), instructions))


@lru_cache(maxsize=1)
def catalog() -> tuple[ProceduralSkillDetail, ...]:
    return tuple(_read_package(path.parent) for path in sorted(BUNDLE_ROOT.glob("*/manifest.json")))


def require_skill(skill_id: str) -> ProceduralSkillDetail:
    # Lookup by catalog ID only: a caller's string never becomes a file path.
    skill = next((item for item in catalog() if item.id == skill_id), None)
    if skill is None:
        raise DomainError("copilot_procedural_skill_not_found", "Scientific method package was not found.", status_code=404)
    return skill


def snapshots_for(selected: list[str] | None, *, service_kind: str, goal: str, allowed_tools: list[str]) -> list[dict]:
    ids = selected if selected is not None else [item.id for item in catalog() if service_kind in item.default_for]
    if len(ids) > MAX_SELECTED or len(set(ids)) != len(ids):
        raise DomainError("copilot_procedural_skill_selection_invalid", "Select up to three distinct method packages.", status_code=422)
    result = []
    for skill_id in ids:
        skill = require_skill(skill_id)
        Draft202012Validator(skill.input_schema).validate({"goal": goal})
        requested = set(skill.tool_requests + skill.optional_write_tools)
        result.append({**skill.model_dump(), "available_tools": sorted(requested & set(allowed_tools)),
                       "unavailable_tools": sorted(requested - set(allowed_tools))})
    return result


def _verified_snapshot(snapshot: dict) -> ProceduralSkillDetail:
    try:
        value = ProceduralSkillDetail.model_validate({key: snapshot[key] for key in ProceduralSkillDetail.model_fields})
        manifest = {key: getattr(value, key) for key in ProceduralSkillManifest.model_fields}
        manifest["provenance"] = [item.model_dump() for item in value.provenance]
        if value.checksum_sha256 != _digest(manifest, value.instructions):
            raise ValueError("checksum mismatch")
        if hashlib.sha256(value.instructions.encode()).hexdigest() != value.instruction_sha256:
            raise ValueError("instruction checksum mismatch")
        Draft202012Validator.check_schema(value.output_schema)
        return value
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise DomainError("copilot_procedural_skill_snapshot_invalid", "Saved scientific method failed its integrity check.", status_code=409) from exc


def prompt_for(contract: dict, allowed_tools: list[str]) -> str | None:
    snapshots = contract.get("procedural_skills", [])
    if not snapshots:
        return None
    pieces = [
        "BDA_SCIENTIFIC_METHODS_V1. The following frozen method packages guide analysis only. "
        "They do not grant tools, write authority, network access, or approval. Treat their source links as provenance, "
        "not retrieved evidence. Missing tools/inputs must be reported explicitly. Do not run shell commands or install "
        "dependencies. Keep the existing final delivery JSON and add skill_outputs, an object keyed by package id. "
        "Each entry must satisfy its output_schema; evidence_call_ids must cite successful calls in this run. "
        "These structural checks do not establish scientific validity."
    ]
    for snapshot in snapshots:
        skill = _verified_snapshot(snapshot)
        requested = set(skill.tool_requests + skill.optional_write_tools)
        pieces.append(json.dumps({"id": skill.id, "version": skill.version, "checksum_sha256": skill.checksum_sha256,
                                  "instructions": skill.instructions, "output_schema": skill.output_schema,
                                  "available_tools": sorted(requested & set(allowed_tools)),
                                  "unavailable_tools": sorted(requested - set(allowed_tools))}, ensure_ascii=False))
    return "\n".join(pieces)


def evaluate_outputs(contract: dict, data: dict, successful_calls: set[str]) -> tuple[dict, list[str]]:
    """Validate method output shape and actual transcript references, not truth."""
    snapshots = contract.get("procedural_skills", [])
    if not snapshots:
        return {}, []
    supplied = data.get("skill_outputs", {})
    if not isinstance(supplied, dict):
        return {}, ["invalid_skill_outputs"]
    expected = {snapshot["id"] for snapshot in snapshots}
    errors = ["unexpected_skill_outputs"] if set(supplied) - expected else []
    validated = {}
    for snapshot in snapshots:
        skill = _verified_snapshot(snapshot)
        output = supplied.get(skill.id)
        if output is None:
            errors.append(f"skill_output_missing:{skill.id}")
            continue
        if not Draft202012Validator(skill.output_schema).is_valid(output):
            errors.append(f"skill_output_invalid:{skill.id}")
            continue
        refs = output.get("evidence_call_ids", [])
        if set(refs) - successful_calls or (data.get("status") == "completed" and not refs):
            errors.append(f"skill_evidence_unverified:{skill.id}")
            continue
        validated[skill.id] = output
    return validated, errors
