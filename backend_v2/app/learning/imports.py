"""Bounded, atomic CSV import from a checksum-verified project artifact."""

from __future__ import annotations

import csv
import hashlib
import io

from sqlalchemy.orm import Session

from ..artifacts.storage import ObjectStorage
from ..core.problem import DomainError
from ..identity.models import User
from ..projects.models import Project
from . import lifecycle, service
from .models import LearningAssay
from .schemas import ObservationCreate, ObservationImport, ObservationImportResult

CSV_COLUMNS = [
    "candidate_id",
    "batch_key",
    "replicate_key",
    "replicate_type",
    "status",
    "value",
    "unit",
    "qc_accepted",
    "note",
    "family_key",
    "observed_at",
    "sample_role",
    "measurement_key",
]


def parse_csv(data: bytes, payload: ObservationImport) -> list[ObservationCreate]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), strict=True)
    headers = reader.fieldnames or []
    if not headers or len(set(headers)) != len(headers) or set(headers) - set(CSV_COLUMNS):
        raise ValueError("CSV headers must be unique supported measurement columns")
    observations = []
    measurement_keys: set[str] = set()
    for index, values in enumerate(reader, start=2):
        if index > 1001:
            raise ValueError("A single import is limited to 1000 results")
        if None in values or any(v is None for v in values.values()):
            raise ValueError(f"CSV row {index} has a different number of columns")
        row = {k: v for k, v in values.items() if v != ""}
        qc = row.get("qc_accepted", "false")
        if qc not in {"true", "false"}:
            raise ValueError(f"CSV row {index}: qc_accepted must be true or false")
        try:
            observation = ObservationCreate.model_validate(
                {
                    **row,
                    "qc_accepted": qc == "true",
                    "assay_id": payload.assay_id,
                    "source_artifact_id": payload.artifact_id,
                }
            )
        except ValueError as exc:
            raise ValueError(f"CSV row {index} does not satisfy the measurement contract: {exc}") from exc
        observations.append(observation)
        if observation.measurement_key:
            if observation.measurement_key in measurement_keys:
                raise ValueError(f"CSV row {index}: duplicate measurement key")
            measurement_keys.add(observation.measurement_key)
    if not observations:
        raise ValueError("CSV contains no observations")
    return observations


def import_observations(
    session: Session, project: Project, user: User, payload: ObservationImport
) -> ObservationImportResult:
    service.require_record(session, LearningAssay, project, payload.assay_id, lock=True)
    artifact = lifecycle._artifact(session, project, payload.artifact_id)
    if artifact.size_bytes > 2 * 1024 * 1024 or not artifact.filename.lower().endswith(".csv"):
        raise DomainError("learning_import_format", "Use a UTF-8 CSV file of at most 2 MiB", status_code=422)
    try:
        data = ObjectStorage().read_bytes(artifact.object_key, max_bytes=2 * 1024 * 1024)
    except ValueError as exc:
        raise DomainError("learning_import_size", "Import file exceeds the size limit", status_code=422) from exc
    if len(data) != artifact.size_bytes or hashlib.sha256(data).hexdigest() != artifact.checksum_sha256:
        raise DomainError(
            "learning_source_integrity", "Source file differs from its verified artifact", status_code=409
        )
    try:
        observations = parse_csv(data, payload)
    except (ValueError, UnicodeError, csv.Error) as exc:
        raise DomainError("learning_import_invalid", str(exc), status_code=422) from exc
    # Validate the entire file before creating anything. Retrying the same file
    # resolves the same observation fingerprints under the assay lock.
    for row in observations:
        service.validate_observation(session, project, row)
    result_ids = (
        [] if payload.dry_run else [service.create_observation(session, project, user, row).id for row in observations]
    )
    return ObservationImportResult(
        dry_run=payload.dry_run, row_count=len(observations), result_ids=result_ids, observations=observations
    )
