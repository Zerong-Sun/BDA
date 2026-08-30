from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.etag import etag, parse_if_match
from ..core.pagination import decode_cursor, encode_cursor
from ..core.problem import DomainError
from ..identity.deps import current_user, require_command
from ..identity.models import User
from ..projects.service import require_project
from .analysis import analyse_akta, analyse_bli, analyse_enzyme
from .repository import ProteinRepository
from .schemas import (
    AktaAnalysisRequest,
    AnalysisResponse,
    BliAnalysisRequest,
    ConcentrationRequest,
    ConcentrationResult,
    DilutionRequest,
    DilutionResult,
    EnzymeAnalysisRequest,
    FastaImportRequest,
    FastaImportResult,
    ProteinCreate,
    ProteinPage,
    ProteinRead,
    ProteinUpdate,
    UnitConversionRequest,
    UnitConversionResult,
)
from .service import (
    concentration,
    convert_units,
    create_protein,
    dilution_series,
    import_fasta,
    promote_candidate,
    to_read,
    update_protein,
)

router = APIRouter(tags=["wetlab"])


@router.get("/projects/{project_id}/proteins", response_model=ProteinPage)
def list_proteins(
    project_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200, description="Match on name."),
    tag: str | None = Query(default=None, max_length=60),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProteinPage:
    require_project(session, project_id, user)
    rows = ProteinRepository(session).list_project(
        project_id, decode_cursor(cursor), limit, search=search, tag=tag
    )
    page = rows[:limit]
    return ProteinPage(
        items=[to_read(row) for row in page],
        next_cursor=encode_cursor(page[-1].id) if len(rows) > limit and page else None,
    )


@router.post(
    "/projects/{project_id}/proteins",
    response_model=ProteinRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "protein.create"},
)
def post_protein(
    project_id: uuid.UUID,
    payload: ProteinCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ProteinRead:
    require_project(session, project_id, user)
    return to_read(create_protein(session, project_id, user.id, payload))


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}/promote-to-bench",
    response_model=ProteinRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "protein.create"},
)
def post_promote_candidate(
    project_id: uuid.UUID,
    candidate_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ProteinRead:
    """Make a designed candidate into a construct on the bench."""
    require_project(session, project_id, user)
    return to_read(promote_candidate(session, project_id, user.id, candidate_id))


@router.post(
    "/projects/{project_id}/proteins/import-fasta",
    response_model=FastaImportResult,
    openapi_extra={"x-permission": "protein.create"},
)
def post_fasta_import(
    project_id: uuid.UUID,
    payload: FastaImportRequest,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> FastaImportResult:
    require_project(session, project_id, user)
    return import_fasta(session, project_id, user.id, payload.content, payload.tags)


def _protein(session: Session, protein_id: uuid.UUID, user: User):
    protein = ProteinRepository(session).get(protein_id)
    if protein is None:
        raise DomainError("protein_not_found", "Protein was not found", status_code=404)
    require_project(session, protein.project_id, user)
    return protein


@router.get("/proteins/{protein_id}", response_model=ProteinRead)
def get_protein(
    protein_id: uuid.UUID,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ProteinRead:
    protein = _protein(session, protein_id, user)
    response.headers["ETag"] = etag(protein.version)
    return to_read(protein)


@router.patch(
    "/proteins/{protein_id}",
    response_model=ProteinRead,
    openapi_extra={"x-permission": "protein.update"},
)
def patch_protein(
    protein_id: uuid.UUID,
    payload: ProteinUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> ProteinRead:
    protein = _protein(session, protein_id, user)
    expected = parse_if_match(if_match)
    if protein.version != expected:
        raise DomainError(
            "version_conflict",
            "Protein was modified by someone else; reload before retrying.",
            status_code=412,
        )
    updated = update_protein(session, protein, payload)
    response.headers["ETag"] = etag(updated.version)
    return to_read(updated)


# --- Bench calculators -------------------------------------------------------
# GET, not POST: each is a pure function of its scalar inputs - same arguments,
# same answer, nothing persisted. That makes them idempotent and cacheable, and
# it keeps them out of the write-permission surface, which is the honest place
# for a calculation a read-only account should be able to run.


@router.get("/projects/{project_id}/wetlab/concentration", response_model=ConcentrationResult)
def get_concentration(
    project_id: uuid.UUID,
    a280: float = Query(ge=0),
    protein_id: uuid.UUID | None = Query(default=None),
    ext_coeff: float | None = Query(default=None, gt=0),
    molecular_weight: float | None = Query(default=None, gt=0),
    path_length_cm: float = Query(default=1.0, gt=0),
    cystines: str = Query(default="reduced", pattern="^(reduced|oxidized)$"),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> ConcentrationResult:
    require_project(session, project_id, user)
    return concentration(
        session,
        project_id,
        ConcentrationRequest(
            a280=a280,
            protein_id=protein_id,
            ext_coeff=ext_coeff,
            molecular_weight=molecular_weight,
            path_length_cm=path_length_cm,
            cystines=cystines,
        ),
    )


@router.get("/wetlab/unit-conversion", response_model=UnitConversionResult)
def get_unit_conversion(
    value: float = Query(),
    from_unit: str = Query(max_length=10),
    to_unit: str = Query(max_length=10),
    molecular_weight: float | None = Query(default=None, gt=0),
    user: User = Depends(current_user),
) -> UnitConversionResult:
    return convert_units(
        UnitConversionRequest(
            value=value, from_unit=from_unit, to_unit=to_unit, molecular_weight=molecular_weight
        )
    )


@router.get("/wetlab/dilution-series", response_model=DilutionResult)
def get_dilution_series(
    stock_conc_uM: float = Query(gt=0),
    start_conc_uM: float = Query(gt=0),
    dilution_factor: float = Query(gt=1),
    n_steps: int = Query(ge=1, le=24),
    vol_per_well_uL: float = Query(gt=0),
    extra_dead_vol_uL: float = Query(default=0.0, ge=0),
    user: User = Depends(current_user),
) -> DilutionResult:
    return dilution_series(
        DilutionRequest(
            stock_conc_uM=stock_conc_uM,
            start_conc_uM=start_conc_uM,
            dilution_factor=dilution_factor,
            n_steps=n_steps,
            vol_per_well_uL=vol_per_well_uL,
            extra_dead_vol_uL=extra_dead_vol_uL,
        )
    )


# --- Instrument analysis -----------------------------------------------------
# POST, unlike the calculators above: these persist an ExperimentResult. The
# body carries an artifact id rather than a file, because uploads go
# browser-direct to object storage and never through this API.


def _analysis_response(row, summary: dict) -> AnalysisResponse:
    return AnalysisResponse(
        experiment_result_id=row.id,
        experiment_type=row.experiment_type,
        analysis_version=str(row.result_metadata.get("analysis_version", "")),
        value=row.value,
        unit=row.unit,
        source_artifact_id=row.source_artifact_id,
        summary=summary,
    )


@router.post(
    "/projects/{project_id}/wetlab/bli-analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "experiment.record"},
)
def post_bli_analysis(
    project_id: uuid.UUID,
    payload: BliAnalysisRequest,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AnalysisResponse:
    """Fit KD from an uploaded ForteBio export and record the result."""
    require_project(session, project_id, user)
    row, summary = analyse_bli(
        session,
        project_id,
        user.id,
        payload.artifact_id,
        sample_id=payload.sample_id,
        t_assoc=payload.t_assoc,
        t_dissoc=payload.t_dissoc,
        candidate_id=payload.candidate_id,
    )
    return _analysis_response(row, summary)


@router.post(
    "/projects/{project_id}/wetlab/akta-analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "experiment.record"},
)
def post_akta_analysis(
    project_id: uuid.UUID,
    payload: AktaAnalysisRequest,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AnalysisResponse:
    """Detect peaks in an uploaded AKTA Unicorn export and record the peak table."""
    require_project(session, project_id, user)
    row, summary = analyse_akta(
        session,
        project_id,
        user.id,
        payload.artifact_id,
        channel=payload.channel,
        candidate_id=payload.candidate_id,
    )
    return _analysis_response(row, summary)


@router.post(
    "/projects/{project_id}/wetlab/enzyme-analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "experiment.record"},
)
def post_enzyme_analysis(
    project_id: uuid.UUID,
    payload: EnzymeAnalysisRequest,
    session: Session = Depends(get_session),
    user: User = Depends(require_command),
) -> AnalysisResponse:
    """Fit per-well rates from an uploaded TECAN plate export and record them."""
    require_project(session, project_id, user)
    row, summary = analyse_enzyme(
        session,
        project_id,
        user.id,
        payload.artifact_id,
        subtract_background=payload.subtract_background,
        candidate_id=payload.candidate_id,
    )
    return _analysis_response(row, summary)
