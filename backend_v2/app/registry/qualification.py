"""Recorded model/checkpoint use review; never a substitute for runtime proof."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..core.problem import DomainError


class ScientificQualification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    plugin_key: str = Field(min_length=1, max_length=200)
    plugin_version: str = Field(min_length=1, max_length=80)
    code_reference: str = Field(min_length=1, max_length=500)
    code_license: str = Field(min_length=1, max_length=200)
    checkpoint_identifier: str = Field(min_length=1, max_length=500)
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_license: str = Field(min_length=1, max_length=200)
    license_reference: str = Field(pattern=r"^https://[^\s]+$", max_length=1000)
    license_mode: Literal["open", "restricted", "research_only", "unknown"]
    intended_use: Literal["research", "commercial"]
    allowed_uses: list[Literal["research", "commercial"]] = Field(default_factory=list, max_length=2)
    review_status: Literal["pending", "approved", "rejected"]
    reviewer: str = Field(default="", max_length=200)
    reviewed_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    validation_scope: str = Field(min_length=1, max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def approval_has_record(self):
        if self.review_status == "approved" and (not self.reviewer.strip() or not self.reviewed_at):
            raise ValueError("Approved qualifications need a reviewer and review timestamp")
        if len(set(self.allowed_uses)) != len(self.allowed_uses):
            raise ValueError("Allowed uses must be distinct")
        return self


def validate_qualification_resources(resources: dict) -> None:
    if not isinstance(resources, dict):
        raise DomainError("model_qualification_invalid", "Model resources must be an object.", status_code=422)
    if "scientific_qualification" not in resources:
        return
    try:
        ScientificQualification.model_validate(resources["scientific_qualification"])
    except ValidationError as exc:
        raise DomainError("model_qualification_invalid", "Model qualification must follow the versioned checkpoint/use-review contract.", status_code=422,
                          errors=exc.errors(include_input=False, include_context=False)) from exc


def model_qualification_issues(plugin, *, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """Return (blockers, warnings), with code/message/plugin identity fields.

    Legacy declarations without a qualification receive a warning. An explicit
    qualification is load-bearing: pending/rejected/restricted use cannot pass.
    Only administrators can change registry resources; approval here records
    their reviewed decision, not a license interpretation performed by BDA.
    """
    identity = {"plugin_id": str(plugin.id), "plugin_key": plugin.plugin_key, "plugin_version": plugin.plugin_version}

    def issue(code, message):
        return {"code": code, "message": message, **identity}

    resources = plugin.resources or {}
    if not isinstance(resources, dict):
        return [issue("model_qualification_invalid", "Model resources are malformed; review the registry declaration.")], []
    if "scientific_qualification" not in resources:
        return [], [issue("model_qualification_missing", "No versioned checkpoint/use review is recorded. Confirm exact code, weights and intended-use terms before scientific deployment.")]
    try:
        review = ScientificQualification.model_validate(resources["scientific_qualification"])
    except ValidationError:
        return [issue("model_qualification_invalid", "The recorded checkpoint/use-review contract is invalid.")], []
    blockers = []
    instant = now or datetime.now(UTC)
    if (review.plugin_key, review.plugin_version) != (plugin.plugin_key, plugin.plugin_version):
        blockers.append(issue("model_qualification_identity_mismatch", "Qualification belongs to a different plugin key or version."))
    if review.review_status != "approved":
        blockers.append(issue("model_qualification_not_approved", "Checkpoint/use review is pending or rejected."))
    if review.license_mode == "unknown" or review.intended_use not in review.allowed_uses:
        blockers.append(issue("model_qualification_use_restricted", "Intended use is not covered by the recorded license review."))
    if review.license_mode == "research_only" and review.intended_use == "commercial":
        blockers.append(issue("model_qualification_research_only", "Research-only checkpoint terms do not authorize commercial use."))
    if review.reviewed_at and review.reviewed_at > instant:
        blockers.append(issue("model_qualification_future_review", "Review timestamp is in the future."))
    if review.expires_at and review.expires_at <= instant:
        blockers.append(issue("model_qualification_expired", "The recorded checkpoint/use review has expired."))
    warnings = [issue("model_qualification_scope", "Recorded use review is scoped to: " + review.validation_scope + ". It does not establish scientific validity or prove which files were loaded at runtime.")]
    return blockers, warnings
