"""Domain rules for the wet-lab bench.

Everything sequence-derived is computed here and stored, so that a read never
touches the plaintext and a number used in a recorded calculation stays
reproducible even if the kernel's rounding changes later.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from ..core.problem import DomainError
from .kernels import calculators
from .models import Protein
from .repository import ProteinRepository
from .schemas import (
    ConcentrationRequest,
    ConcentrationResult,
    DilutionRequest,
    DilutionResult,
    DilutionStepRead,
    FastaImportItem,
    FastaImportResult,
    ProteinCreate,
    ProteinRead,
    ProteinUpdate,
    UnitConversionRequest,
    UnitConversionResult,
)

#: How much of the digest identifies a construct in the API. Twelve hex
#: characters is 48 bits - collision-free for any realistic library, and short
#: enough to read out loud in a lab.
FINGERPRINT_CHARS = 12


def sequence_digest(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def to_read(protein: Protein) -> ProteinRead:
    """Project a row onto the wire, dropping the sequence.

    The only place a `Protein` becomes API output. Keeping it single means the
    redaction cannot be forgotten at one call site.
    """
    return ProteinRead(
        id=protein.id,
        project_id=protein.project_id,
        name=protein.name,
        fingerprint=protein.sequence_sha256[:FINGERPRINT_CHARS],
        length=protein.length,
        molecular_weight=protein.molecular_weight,
        ext_coeff_reduced=protein.ext_coeff_reduced,
        ext_coeff_oxidized=protein.ext_coeff_oxidized,
        candidate_id=protein.candidate_id,
        tags=list(protein.tags or []),
        notes=protein.notes,
        version=protein.version,
        created_at=protein.created_at,
        updated_at=protein.updated_at,
    )


def _derive(sequence: str) -> dict[str, float]:
    """Mass and extinction coefficients, computed locally from the sequence.

    Mass comes from `calc_mw` rather than the `mw` field of `calc_ext_coeff`:
    that one is rounded to one decimal for display, and this value is stored and
    then divided into every concentration computed against this construct.
    """
    stats = calculators.calc_ext_coeff(sequence)
    return {
        "molecular_weight": float(calculators.calc_mw(sequence)),
        "ext_coeff_reduced": float(stats["ext_red"]),
        "ext_coeff_oxidized": float(stats["ext_ox"]),
    }


def create_protein(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID, payload: ProteinCreate
) -> Protein:
    repository = ProteinRepository(session)
    sequence = payload.sequence
    digest = sequence_digest(sequence)
    if repository.by_digest(project_id, digest) is not None:
        raise DomainError(
            "protein_duplicate_sequence",
            "This project already holds a protein with the same sequence.",
            status_code=409,
        )
    derived = _derive(sequence)
    protein = Protein(
        project_id=project_id,
        name=payload.name,
        sequence=sequence,
        sequence_sha256=digest,
        length=len(sequence),
        candidate_id=payload.candidate_id,
        tags=list(payload.tags),
        notes=payload.notes,
        created_by=user_id,
        **derived,
    )
    return repository.add(protein)


def update_protein(session: Session, protein: Protein, payload: ProteinUpdate) -> Protein:
    """Metadata only.

    The sequence is deliberately immutable: mass, extinction coefficient and
    every concentration already recorded against this row were derived from it,
    so editing it in place would silently invalidate past results. A corrected
    sequence is a new construct.
    """
    if payload.name is not None:
        protein.name = payload.name
    if payload.tags is not None:
        protein.tags = list(payload.tags)
    if payload.notes is not None:
        protein.notes = payload.notes
    if payload.candidate_id is not None:
        protein.candidate_id = payload.candidate_id
    protein.version += 1
    session.flush()
    return protein


def parse_fasta(content: str) -> list[tuple[str, str]]:
    """FASTA into (name, sequence) pairs, tolerating CRLF and blank lines."""
    entries: list[tuple[str, str]] = []
    name: str | None = None
    chunks: list[str] = []
    for raw in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if name is not None:
                entries.append((name, "".join(chunks)))
            name = line[1:].strip() or "unnamed"
            chunks = []
        else:
            chunks.append(line)
    if name is not None:
        entries.append((name, "".join(chunks)))
    return entries


def import_fasta(
    session: Session,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    tags: list[str],
) -> FastaImportResult:
    """Register a batch, reporting per-record outcomes instead of failing the batch.

    A pasted FASTA routinely contains one construct already in the library or one
    with a stray character. Raising on the first would discard the good records
    and give no way to tell which entry was the problem.
    """
    from .schemas import ProteinCreate as _Create  # local: validation lives on the schema

    items: list[FastaImportItem] = []
    created = duplicates = rejected = 0
    for name, sequence in parse_fasta(content):
        try:
            payload = _Create(name=name[:200], sequence=sequence, tags=list(tags))
        except ValueError as error:
            rejected += 1
            items.append(FastaImportItem(name=name, fingerprint="", status="rejected", detail=str(error)))
            continue
        digest = sequence_digest(payload.sequence)
        try:
            create_protein(session, project_id, user_id, payload)
        except DomainError:
            duplicates += 1
            items.append(
                FastaImportItem(
                    name=name,
                    fingerprint=digest[:FINGERPRINT_CHARS],
                    status="duplicate",
                    detail="already in this project",
                )
            )
            continue
        created += 1
        items.append(
            FastaImportItem(name=name, fingerprint=digest[:FINGERPRINT_CHARS], status="created")
        )
    return FastaImportResult(
        created=created, duplicates=duplicates, rejected=rejected, items=items
    )


def concentration(
    session: Session, project_id: uuid.UUID, payload: ConcentrationRequest
) -> ConcentrationResult:
    epsilon = payload.ext_coeff
    mw = payload.molecular_weight
    if payload.protein_id is not None:
        protein = ProteinRepository(session).get(payload.protein_id)
        if protein is None or protein.project_id != project_id:
            raise DomainError(
                "protein_not_found",
                "No such protein in this project.",
                status_code=404,
            )
        epsilon = (
            protein.ext_coeff_oxidized
            if payload.cystines == "oxidized"
            else protein.ext_coeff_reduced
        )
        mw = protein.molecular_weight
    if not epsilon or not mw:
        raise DomainError(
            "concentration_inputs_missing",
            "Provide a protein_id, or both ext_coeff and molecular_weight. "
            "A sequence with no W, Y or C has no A280 signal to quantify.",
            status_code=422,
        )
    result = calculators.calc_conc(payload.a280, epsilon, mw, payload.path_length_cm)
    return ConcentrationResult(**result)


def convert_units(payload: UnitConversionRequest) -> UnitConversionResult:
    try:
        value = calculators.convert_concentration(
            payload.value, payload.from_unit, payload.to_unit, payload.molecular_weight
        )
    except ValueError as error:
        raise DomainError(
            "unit_conversion_failed", str(error), status_code=422
        ) from error
    return UnitConversionResult(value=value, unit=payload.to_unit)


def dilution_series(payload: DilutionRequest) -> DilutionResult:
    try:
        steps = calculators.calc_dilution_series(
            payload.stock_conc_uM,
            payload.start_conc_uM,
            payload.dilution_factor,
            payload.n_steps,
            payload.vol_per_well_uL,
            payload.extra_dead_vol_uL,
        )
    except ValueError as error:
        raise DomainError("dilution_invalid", str(error), status_code=422) from error
    return DilutionResult(
        steps=[
            DilutionStepRead(
                step=step.step,
                conc_uM=step.conc_uM,
                stock_vol_uL=step.stock_vol_uL,
                buffer_vol_uL=step.buffer_vol_uL,
                total_vol_uL=step.total_vol_uL,
            )
            for step in steps
        ]
    )


def promote_candidate(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID, candidate_id: uuid.UUID
) -> Protein:
    """Register a designed candidate as a construct on the bench.

    This is the join the platform existed either side of but never across: a
    design stops being a prediction here and becomes something that can be
    expressed and measured, and the measurement finds its way back to the
    candidate because the construct keeps `candidate_id`.

    The sequence comes from the candidate's own properties, where the ProteinMPNN
    and ProteinHunter parsers put it. A candidate with no sequence - a fold-only
    result, say - cannot be made, and says so rather than creating an empty row.
    """
    from ..candidates.repository import CandidateRepository

    candidate = CandidateRepository(session).get(candidate_id)
    if candidate is None or candidate.project_id != project_id:
        raise DomainError(
            "candidate_not_found",
            "No such candidate in this project.",
            status_code=404,
        )
    sequence = str((candidate.properties or {}).get("sequence") or "").strip().upper()
    if not sequence:
        raise DomainError(
            "candidate_has_no_sequence",
            (
                "This candidate carries no sequence, so there is nothing to make. "
                "Structure-only results have to be paired with a sequence first."
            ),
            status_code=422,
        )

    digest = sequence_digest(sequence)
    existing = ProteinRepository(session).by_digest(project_id, digest)
    if existing is not None:
        # Already on the bench. Record which design it came from if that was not
        # known before, and hand back the same construct rather than refusing:
        # promoting twice is a repeated click, not an error worth blocking on.
        if existing.candidate_id is None:
            existing.candidate_id = candidate_id
            existing.version += 1
            session.flush()
        return existing

    return create_protein(
        session,
        project_id,
        user_id,
        ProteinCreate(
            name=candidate.name or candidate.candidate_key,
            sequence=sequence,
            tags=["from-design"],
            notes=f"Promoted from candidate {candidate.candidate_key}.",
            candidate_id=candidate_id,
        ),
    )
