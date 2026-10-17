from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Outcome = Literal["hypothesis", "supported", "refuted", "inconclusive", "method_invalid", "execution_blocked"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LessonCreate(Contract):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    statement: Text
    conditions: Text
    limitations: Text
    evidence: list[Text] = Field(min_length=1, max_length=30)
    outcome: Outcome
    next_design_change: Text
    supersedes_id: uuid.UUID | None = None


class ReviewItem(Contract):
    key: Key
    disposition: Literal["apply", "test", "not_applicable"]
    rationale: Text
    hypothesis: str = Field(default="", max_length=6000)
    action: str = Field(default="", max_length=6000)
    comparison: str = Field(default="", max_length=6000)
    readout: str = Field(default="", max_length=6000)
    decision_rule: str = Field(default="", max_length=6000)

    @model_validator(mode="after")
    def require_plan(self):
        if self.disposition != "not_applicable" and any(
            not getattr(self, k).strip() for k in ("hypothesis", "action", "comparison", "readout", "decision_rule")
        ):
            raise ValueError(
                "Applicable and uncertain items require a hypothesis, action, comparison, readout and decision rule"
            )
        return self


class ReviewCreate(Contract):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    memory_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    objective: Text
    context: Text
    items: list[ReviewItem] = Field(min_length=6, max_length=1000)


class FeedbackCreate(LessonCreate):
    review_id: uuid.UUID
    item_key: Key
    outcome: Literal["supported", "refuted", "inconclusive", "method_invalid", "execution_blocked"]


class LessonImport(Contract):
    source_id: uuid.UUID
