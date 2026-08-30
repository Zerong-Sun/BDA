"""External contract for the wet-lab bench.

The one rule that shapes this file: **a protein sequence never leaves the
server.** Sequences are intellectual property, and the platform's own principle
is that anything derived from a sequence (mass, extinction coefficient,
concentration) is computed locally and only the derived number is handed out.

So there is no `sequence` field on any read model. `ProteinRead` carries
`fingerprint` - the first 12 hex characters of the SHA-256 - which is enough to
tell two constructs apart, cite one in a report, or match one across systems,
and is not the sequence. Adding a sequence field to a read model would defeat
the redaction at its only choke point, so don't.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: The 20 canonical amino acids. Anything else is rejected rather than silently
#: stripped: a sequence with unexpected characters is usually the wrong paste,
#: and quietly discarding them would compute a mass for a construct nobody has.
_CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")


class ProteinCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sequence: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    candidate_id: uuid.UUID | None = None

    @field_validator("sequence")
    @classmethod
    def _canonical(cls, value: str) -> str:
        cleaned = "".join(value.split()).upper().replace("*", "")
        if not cleaned:
            raise ValueError("sequence is empty")
        bad = sorted(set(cleaned) - _CANONICAL_AA)
        if bad:
            raise ValueError(f"sequence contains non-standard residues: {''.join(bad)}")
        return cleaned


class ProteinUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tags: list[str] | None = None
    notes: str | None = None
    candidate_id: uuid.UUID | None = None


class ProteinRead(BaseModel):
    """A library entry as the outside world sees it - without the sequence."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    #: First 12 hex characters of the sequence SHA-256. Identity without disclosure.
    fingerprint: str
    length: int
    molecular_weight: float | None
    ext_coeff_reduced: float | None
    ext_coeff_oxidized: float | None
    candidate_id: uuid.UUID | None
    tags: list[str]
    notes: str
    version: int
    created_at: datetime
    updated_at: datetime


class ProteinPage(BaseModel):
    items: list[ProteinRead]
    next_cursor: str | None = None


class FastaImportRequest(BaseModel):
    """Bulk registration. Records that parse but duplicate an existing digest are
    reported rather than raising, so one repeated entry does not lose the batch."""

    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class FastaImportItem(BaseModel):
    name: str
    fingerprint: str
    status: str  # "created" | "duplicate" | "rejected"
    detail: str = ""


class FastaImportResult(BaseModel):
    created: int
    duplicates: int
    rejected: int
    items: list[FastaImportItem]


class ConcentrationRequest(BaseModel):
    """Beer-Lambert, against a stored construct or an explicit epsilon."""

    a280: float = Field(ge=0)
    protein_id: uuid.UUID | None = None
    ext_coeff: float | None = Field(default=None, gt=0)
    molecular_weight: float | None = Field(default=None, gt=0)
    path_length_cm: float = Field(default=1.0, gt=0)
    #: Which extinction coefficient to use when reading it off a stored protein.
    cystines: str = Field(default="reduced", pattern="^(reduced|oxidized)$")


class ConcentrationResult(BaseModel):
    a280: float
    path_length_cm: float
    epsilon: float
    mw: float
    molar_conc_uM: float
    molar_conc_nM: float
    molar_conc_M: float
    mass_conc_mg_mL: float
    mass_conc_ug_mL: float
    mass_conc_ng_uL: float


class UnitConversionRequest(BaseModel):
    value: float
    from_unit: str
    to_unit: str
    #: Required only when crossing molar <-> mass.
    molecular_weight: float | None = Field(default=None, gt=0)


class UnitConversionResult(BaseModel):
    value: float
    unit: str


class DilutionRequest(BaseModel):
    stock_conc_uM: float = Field(gt=0)
    start_conc_uM: float = Field(gt=0)
    dilution_factor: float = Field(gt=1)
    n_steps: int = Field(ge=1, le=24)
    vol_per_well_uL: float = Field(gt=0)
    extra_dead_vol_uL: float = Field(default=0.0, ge=0)


class DilutionStepRead(BaseModel):
    step: int
    conc_uM: float
    stock_vol_uL: float
    buffer_vol_uL: float
    total_vol_uL: float


class DilutionResult(BaseModel):
    steps: list[DilutionStepRead]


# --- Instrument analysis -----------------------------------------------------
# Each takes an artifact id, never a file body: uploads go browser-direct to
# object storage, and the artifact is also the immutable raw snapshot the
# recorded result points back at.


class BliAnalysisRequest(BaseModel):
    artifact_id: uuid.UUID
    #: Which sample in the file. Defaults to the one with the most curves.
    sample_id: str | None = None
    #: Phase boundaries. Worth passing whenever the run declares them - the
    #: fallback reads them off the smoothed curve, which is fine for a look and
    #: not what you want behind a recorded number.
    t_assoc: float | None = None
    t_dissoc: float | None = None
    #: Set to tie the measurement back to the design it tests.
    candidate_id: uuid.UUID | None = None


class AktaAnalysisRequest(BaseModel):
    artifact_id: uuid.UUID
    #: Defaults to a UV trace; an export also carries conductivity and pressure.
    channel: str | None = None
    candidate_id: uuid.UUID | None = None


class EnzymeAnalysisRequest(BaseModel):
    artifact_id: uuid.UUID
    subtract_background: bool = True
    candidate_id: uuid.UUID | None = None


class AnalysisResponse(BaseModel):
    """The recorded row, plus enough of the analysis to render without refetching."""

    experiment_result_id: uuid.UUID
    experiment_type: str
    analysis_version: str
    value: float | None
    unit: str | None
    source_artifact_id: uuid.UUID
    summary: dict
