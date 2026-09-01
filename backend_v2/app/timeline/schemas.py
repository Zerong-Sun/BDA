from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import ENTRY_TYPES, LANES, OUTCOMES

# Keys allowed inside `provenance`. Restricted so a caller cannot invent a fifth spelling
# of "job_ids" that no reader will ever look for; unknown keys are rejected loudly rather
# than stored and forgotten.
PROVENANCE_KEYS = frozenset(
    {
        "job_ids",
        "candidate_ids",
        "artifact_ids",
        "workflow_run_ids",
        "finding_ids",
        # The wet half. Without these two a bench decision had nowhere to put the assay
        # it rested on or the construct it was about, so it went into `body` as prose and
        # stopped being queryable - which is how the wet-lab protocols ended up with zero
        # entries pointing at them.
        "experiment_result_ids",
        "protein_ids",
        "external_refs",
    }
)

#: The provenance keys that count as *bench* evidence. A decision that claims to rest on
#: wet work has to name at least one of them; see `check_lane_evidence`.
WET_PROVENANCE_KEYS = frozenset({"experiment_result_ids", "protein_ids"})


def _check_entry_type(value: str) -> str:
    if value not in ENTRY_TYPES:
        raise ValueError(f"entry_type must be one of {sorted(ENTRY_TYPES)}")
    return value


def _check_outcome(value: str) -> str:
    if value not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
    return value


def _check_lane(value: str) -> str:
    if value not in LANES:
        raise ValueError(f"lane must be one of {sorted(LANES)}")
    return value


def _check_provenance(value: dict) -> dict:
    unknown = set(value) - PROVENANCE_KEYS
    if unknown:
        raise ValueError(f"unknown provenance key(s) {sorted(unknown)}; allowed: {sorted(PROVENANCE_KEYS)}")
    for key, items in value.items():
        if not isinstance(items, list):
            raise ValueError(f"provenance['{key}'] must be a list")
    return value


def check_lane_evidence(entry_type: str, lane: str, outcome: str, provenance: dict) -> None:
    """A *settled* bench decision must name the bench evidence it rests on.

    Three conditions, and each exclusion is load-bearing:

    * ``decision`` only. A `plan` is written before any data exists, and a `result`
      carries its evidence in whichever half produced it; it is the judgement that closes
      an option which has to say what closed it.
    * ``wet`` / ``both`` only. A dry decision's evidence keys are already the common case.
    * ``outcome`` other than ``unspecified``. An open branch has closed nothing yet -
      requiring it to cite bench evidence would make it impossible to write down a
      question before answering it, which is precisely what the tree bootstrap needs to
      do, and would push open questions back into prose where they came from.

    Enforced here rather than left to reviewers because the six provenance keys had been
    available since the table was created and the two seeders between them filled
    ``job_ids`` once - an optional field is a field nobody fills.

    Raises ValueError so the Pydantic layer turns it into a 422 with the other field
    errors; the service calls it again on update, where the merged row is what matters.
    """
    if entry_type != "decision" or lane not in ("wet", "both") or outcome == "unspecified":
        return
    if not any(provenance.get(key) for key in WET_PROVENANCE_KEYS):
        raise ValueError(
            f"a settled {lane}-lane decision must cite bench evidence: provenance needs a non-empty "
            f"{' or '.join(sorted(WET_PROVENANCE_KEYS))}"
        )


class Alternative(BaseModel):
    """A branch that was considered and closed off.

    `rejected_because` is required and non-empty on purpose: an alternative listed
    without a reason is decoration, and re-reading it later tells you nothing about
    whether the reason still holds.
    """

    option: str = Field(min_length=1, max_length=300)
    rejected_because: str = Field(min_length=1, max_length=2000)


class CodeRef(BaseModel):
    """A script or module a step actually used."""

    path: str = Field(min_length=1, max_length=400)
    role: str = Field(default="", max_length=200)


class TimelineEntryCreate(BaseModel):
    occurred_at: datetime
    #: Stable per-project identifier for entries generated from a source file, so a
    #: seeder can be re-run without duplicating history. Left unset for hand-written
    #: entries, which have no natural key.
    entry_key: str | None = Field(default=None, max_length=160)
    entry_type: str = "decision"
    #: The project's own decision number ("D064", "C012"). Only meaningful on a
    #: `decision`; unique within the project.
    decision_ref: str | None = Field(default=None, max_length=40)
    lane: str = "unspecified"
    phase: str = Field(default="", max_length=80)
    title: str = Field(min_length=1, max_length=300)
    summary: str = ""
    body: str = ""
    outcome: str = "unspecified"
    provenance: dict = Field(default_factory=dict)
    alternatives: list[Alternative] = Field(default_factory=list)
    code_refs: list[CodeRef] = Field(default_factory=list)
    supersedes_id: uuid.UUID | None = None
    caused_by_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("entry_type")
    @classmethod
    def _known_entry_type(cls, value: str) -> str:
        return _check_entry_type(value)

    @field_validator("lane")
    @classmethod
    def _known_lane(cls, value: str) -> str:
        return _check_lane(value)

    @field_validator("outcome")
    @classmethod
    def _known_outcome(cls, value: str) -> str:
        return _check_outcome(value)

    @field_validator("provenance")
    @classmethod
    def _known_provenance_keys(cls, value: dict) -> dict:
        return _check_provenance(value)

    @field_validator("decision_ref")
    @classmethod
    def _trimmed_decision_ref(cls, value: str | None) -> str | None:
        # "" and "  " are how an empty form field arrives; storing them would make two
        # blank entries collide on the unique constraint. NULL is the real "no number".
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def _bench_decision_cites_bench_evidence(self) -> TimelineEntryCreate:
        check_lane_evidence(self.entry_type, self.lane, self.outcome, self.provenance)
        return self


class TimelineEntryUpdate(BaseModel):
    occurred_at: datetime | None = None
    entry_type: str | None = None
    decision_ref: str | None = Field(default=None, max_length=40)
    lane: str | None = None
    phase: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    summary: str | None = None
    body: str | None = None
    outcome: str | None = None
    provenance: dict | None = None
    alternatives: list[Alternative] | None = None
    code_refs: list[CodeRef] | None = None
    supersedes_id: uuid.UUID | None = None
    caused_by_id: uuid.UUID | None = None
    tags: list[str] | None = None

    # Same rules as on create, reusing the same functions rather than a second copy -
    # a validator that drifts between create and update is how an invalid row gets in
    # through the side door. None means "field not being changed", so it is left alone.
    @field_validator("entry_type")
    @classmethod
    def _known_entry_type(cls, value: str | None) -> str | None:
        return None if value is None else _check_entry_type(value)

    @field_validator("outcome")
    @classmethod
    def _known_outcome(cls, value: str | None) -> str | None:
        return None if value is None else _check_outcome(value)

    @field_validator("lane")
    @classmethod
    def _known_lane(cls, value: str | None) -> str | None:
        return None if value is None else _check_lane(value)

    @field_validator("provenance")
    @classmethod
    def _known_provenance_keys(cls, value: dict | None) -> dict | None:
        return None if value is None else _check_provenance(value)

    @field_validator("decision_ref")
    @classmethod
    def _trimmed_decision_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    occurred_at: datetime
    entry_key: str | None
    entry_type: str
    decision_ref: str | None
    lane: str
    phase: str
    title: str
    summary: str
    body: str
    outcome: str
    provenance: dict
    alternatives: list
    code_refs: list
    supersedes_id: uuid.UUID | None
    caused_by_id: uuid.UUID | None
    tags: list
    created_by: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class TimelineEntryPage(BaseModel):
    items: list[TimelineEntryResponse]
    next_cursor: str | None = None


class TimelineEntryDeleteResponse(BaseModel):
    id: uuid.UUID
    deleted: bool = True
