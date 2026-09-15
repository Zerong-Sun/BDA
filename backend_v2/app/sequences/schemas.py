"""The codon-optimisation contract.

The response carries the DNA, which is the one thing the copilot tools must
never return: a tool call's result is written into the transcript, so a
construct handed back there becomes a second plaintext copy of what
`wetlab.models.Protein` keeps in one place. Over HTTP it goes to the
authenticated person who asked for it and is not stored, which is the same
boundary `ProteinRead` draws by exposing the digest instead of the sequence.

Every measurement the optimiser used is part of the contract rather than a
free-form blob, so a client can show a reviewer why a construct looks the way
it does: which sites were avoided, where the GC band was left, which residue
had to be re-spelled.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .codon import GC_MAX, GC_MIN, GC_WINDOW, MAX_HOMOPOLYMER

_BASES = frozenset("ACGT")


class CodonHostRead(BaseModel):
    """An expression host, with the evidence its weights rest on."""

    key: str
    label: str
    organism: str
    taxon_id: int
    translation_table: int
    accessions: list[str]
    #: How many coding sequences were counted. A table from 14 genes and one
    #: from 4297 are not the same kind of claim, so the number travels with it.
    cds_counted: int
    codons_counted: int
    note: str


class CodonOptimiseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Exactly one source. The sequence is read from the record; it is never
    #: pasted in, for the same reason the analysis tool takes ids only.
    candidate_id: uuid.UUID | None = None
    target_id: uuid.UUID | None = None
    protein_id: uuid.UUID | None = None

    host: str = Field(min_length=1, max_length=80)
    #: Enzyme name -> recognition sequence. Omitted means the default set.
    avoid_sites: dict[str, str] | None = Field(default=None, max_length=32)
    prefix: str = Field(default="", max_length=300)
    suffix: str = Field(default="", max_length=300)
    add_stop: bool = True
    max_homopolymer: int = Field(default=MAX_HOMOPOLYMER, ge=3, le=20)

    @field_validator("prefix", "suffix")
    @classmethod
    def _dna_only(cls, value: str) -> str:
        text = value.upper()
        if text and not set(text) <= _BASES:
            raise ValueError("A flank must be A, C, G and T only.")
        return text

    @field_validator("avoid_sites")
    @classmethod
    def _sites_are_dna(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        cleaned: dict[str, str] = {}
        for name, site in value.items():
            text = site.upper()
            if not text or not set(text) <= _BASES:
                raise ValueError(f"Site {name!r} must be A, C, G and T only.")
            if len(text) > 30:
                raise ValueError(f"Site {name!r} is longer than any recognition sequence.")
            cleaned[name] = text
        return cleaned


class SiteHit(BaseModel):
    enzyme: str
    site: str
    #: Which strand the site reads on. A site on either strand still cuts.
    strand: str
    start: int
    end: int


class GcWindowRead(BaseModel):
    start: int
    end: int
    #: The most extreme GC fraction in the merged span.
    extreme: float
    direction: str


class HomopolymerRunRead(BaseModel):
    base: str
    start: int
    end: int
    length: int


class RareCodonRead(BaseModel):
    position: int
    codon: str
    weight: float


class GcBandRead(BaseModel):
    window: int = GC_WINDOW
    min: float = GC_MIN
    max: float = GC_MAX


class CodonAssessmentRead(BaseModel):
    length_nt: int
    cai: float
    gc: float
    gc3: float
    gc_windows_outside_band: list[GcWindowRead]
    gc_band: GcBandRead
    forbidden_sites: list[SiteHit]
    homopolymer_runs: list[HomopolymerRunRead]
    rare_codons: list[RareCodonRead]
    rare_codon_threshold: float


class CodonCompromiseRead(BaseModel):
    """A position where no synonymous codon could satisfy the constraints."""

    position: int
    residue: str
    codon: str
    reason: str


class CodonRespellRead(BaseModel):
    """A position re-spelled so the next residue could avoid a site."""

    position: int
    residue: str
    from_codon: str
    to_codon: str
    reason: str


class CodonSourceRead(BaseModel):
    """Where the protein came from. Never the residues themselves."""

    kind: str
    id: str | None = None
    name: str | None = None
    sequence_sha256: str


class CodonHostSummary(BaseModel):
    key: str
    label: str
    organism: str
    taxon_id: int
    translation_table: int
    cds_counted: int
    codons_counted: int


class CodonOptimiseResponse(BaseModel):
    dna: str
    host: CodonHostSummary
    source: CodonSourceRead
    protein_length: int
    flanks: dict[str, str | bool]
    compromises: list[CodonCompromiseRead]
    respelled: list[CodonRespellRead]
    assessment: CodonAssessmentRead
