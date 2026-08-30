"""Instrument file -> analysed -> recorded.

The point of these is the wiring, not the maths: the kernels are covered in
test_wetlab_kernels.py. What matters here is that a result lands with its
analysis version, points back at the artifact it came from, and that
re-analysing never edits a previous row.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import struct
import uuid
import zipfile
from collections.abc import Iterator

import numpy as np
import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.wetlab import analysis
from backend_v2.tests._sqlite import drop_all
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


_counter = itertools.count()


def _project(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    n = next(_counter)
    user = User(username=f"lab-{n}", display_name="Lab", role="editor", enabled=True)
    organization = Organization(name=f"Lab Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"lab-{n}",
        project_type="protein_design",
    )
    session.add(project)
    session.flush()
    return project.id, user.id


def _artifact(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID, filename: str, body: bytes = b""
) -> Artifact:
    """A completed artifact row. Size and checksum come from the body, as they
    would after a real upload completes."""
    artifact = Artifact(
        project_id=project_id,
        created_by=user_id,
        artifact_type="instrument_export",
        filename=filename,
        content_type="application/octet-stream",
        object_key=f"projects/{project_id}/{uuid.uuid4()}/{filename}",
        size_bytes=len(body),
        checksum_sha256=hashlib.sha256(body).hexdigest(),
    )
    session.add(artifact)
    session.flush()
    return artifact


# --- Fixtures shaped like the real exports -----------------------------------


def _fortebio_bytes() -> bytes:
    samples = [("S1", 200.0), ("S1", 100.0), ("S1", 50.0)]
    wells = [f"A{i + 1}" for i in range(len(samples))]
    header = [""]
    for index, well in enumerate(wells):
        header += [f"t{index + 1}{well}c1", f"t{index + 1}{well}c2"]
    loc_id, conc = [], []
    for well, (sid, c) in zip(wells, samples, strict=True):
        loc_id += [f"Sample Loc: {well}", f"Sample ID: {sid}"]
        conc += [f"Sample Conc: {c}", ""]
    rows = [["<XmlHeader/>"], header, loc_id, conc, ["units"]]
    koff, kd_nM, rmax = 1e-3, 10.0, 0.5
    kon = koff / kd_nM
    for step in range(300):
        t = float(step)
        line: list[str] = []
        for _, c in samples:
            kobs = kon * c + koff
            req = rmax * kon * c / kobs
            y = req * (1 - np.exp(-kobs * t)) if t <= 120 else (
                req * (1 - np.exp(-kobs * 120)) * np.exp(-koff * (t - 120))
            )
            line += [f"{t}", f"{y:.6f}"]
        rows.append(line)
    return "\n".join(",".join(r) for r in rows).encode()


def _unicorn_bytes() -> bytes:
    volumes = [round(0.025 * s, 4) for s in range(400)]
    amplitudes = [float(100.0 * np.exp(-(((0.025 * s - 5.0) / 0.3) ** 2))) for s in range(400)]

    def block(values: list[float]) -> bytes:
        return b"\x00" * 47 + b"".join(struct.pack("<f", v) for v in values) + b"\x00" * 48

    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("CoordinateData.Volumes", block(volumes))
        archive.writestr("CoordinateData.Amplitudes", block(amplitudes))
    raw = bytearray(inner.getvalue())
    raw[0:9] = b"\x50\x4B\x03\x04\x2D\x00\x00\x00\x08"
    nested = bytes(raw) + b"\x00" * 64

    xml = (
        '<?xml version="1.0"?><Chrom><Curves><Curve><Name>UV 1_280</Name>'
        "<CurveDataType>UV</CurveDataType><AmplitudeUnit>mAU</AmplitudeUnit>"
        "<CurvePoints><CurvePoint><X/><BinaryCurvePointsFileName>Chrom.1_MM_True"
        "</BinaryCurvePointsFileName></CurvePoint></CurvePoints></Curve></Curves>"
        "<EventCurves><EventCurve><Name>Fraction</Name><Events>"
        "<Event><EventVolume>4.5</EventVolume><EventText>A1</EventText></Event>"
        "</Events></EventCurve></EventCurves></Chrom>"
    )
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("Chrom.1.Xml", xml)
        archive.writestr("Chrom.1_MM_True", nested)
    return outer.getvalue()


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch):
    """Stand in for object storage, keyed by object_key."""
    contents: dict[str, bytes] = {}

    class FakeStorage:
        def read_bytes(self, object_key: str, *, max_bytes: int | None = None) -> bytes:
            body = contents[object_key]
            if max_bytes is not None and len(body) > max_bytes:
                raise ValueError("object_too_large")
            return body

    monkeypatch.setattr(analysis, "ObjectStorage", FakeStorage)
    return contents


# --- BLI ---------------------------------------------------------------------


def test_bli_analysis_records_a_kd_against_its_source_artifact(session: Session, stored) -> None:
    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    row, summary = analysis.analyse_bli(
        session, project_id, user_id, artifact.id, t_assoc=0.0, t_dissoc=120.0
    )

    assert row.experiment_type == "bli_affinity"
    assert row.source_artifact_id == artifact.id
    # Built at 10 nM; recorded within a factor of two of it.
    assert row.unit == "nM"
    assert row.value is not None and 5.0 <= row.value <= 20.0
    assert summary["sample_id"] == "S1"


def test_the_analysis_version_is_stored_with_the_result(session: Session, stored) -> None:
    """Without it a stored number cannot be told apart from one the same kernel
    would produce differently after a fix."""
    from backend_v2.app.wetlab.kernels import bli

    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    row, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id, t_assoc=0.0, t_dissoc=120.0)
    assert row.result_metadata["analysis_version"] == bli.BLI_ANALYSIS_VERSION
    assert "params" in row.result_metadata and "results" in row.result_metadata


def test_re_analysing_adds_a_row_rather_than_editing_the_previous_one(
    session: Session, stored
) -> None:
    """A superseded conclusion has to stay visible beside the one that replaced it."""
    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    first, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id, t_assoc=0.0, t_dissoc=120.0)
    second, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id, t_assoc=5.0, t_dissoc=120.0)

    assert first.id != second.id
    rows = list(session.scalars(select(ExperimentResult).where(ExperimentResult.project_id == project_id)))
    assert len(rows) == 2
    assert first.result_metadata["params"]["t_assoc"] == 0.0


def test_a_measurement_can_be_tied_to_the_design_it_tests(session: Session, stored) -> None:
    """The return half of the loop: experiment_results already carries
    candidate_id, so nothing new is needed to trace a KD back to its design."""
    from backend_v2.app.candidates.models import Candidate

    project_id, user_id = _project(session)
    candidate = Candidate(project_id=project_id, candidate_key="d1", name="Design 1")
    session.add(candidate)
    session.flush()
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    row, _ = analysis.analyse_bli(
        session, project_id, user_id, artifact.id,
        t_assoc=0.0, t_dissoc=120.0, candidate_id=candidate.id,
    )
    assert row.candidate_id == candidate.id


def test_an_unknown_sample_is_refused_with_the_ones_that_exist(session: Session, stored) -> None:
    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    with pytest.raises(DomainError) as raised:
        analysis.analyse_bli(session, project_id, user_id, artifact.id, sample_id="nope")
    assert raised.value.error_code == "bli_sample_not_found"
    assert "S1" in raised.value.detail  # says what is available


# --- AKTA --------------------------------------------------------------------


def test_akta_analysis_records_the_peak_table(session: Session, stored) -> None:
    project_id, user_id = _project(session)
    body = _unicorn_bytes()
    artifact = _artifact(session, project_id, user_id, "run.zip", body)
    stored[artifact.object_key] = body

    row, summary = analysis.analyse_akta(session, project_id, user_id, artifact.id)

    assert row.experiment_type == "akta_purification"
    assert summary["channel"] == "UV 1_280"
    assert summary["peak_count"] >= 1
    assert row.result_metadata["results"]["fractions"][0]["label"] == "A1"


def test_akta_defaults_to_a_uv_trace(session: Session, stored) -> None:
    """A purification is read off UV; the export also carries conductivity and
    pressure that nobody picks peaks from."""
    project_id, user_id = _project(session)
    body = _unicorn_bytes()
    artifact = _artifact(session, project_id, user_id, "run.zip", body)
    stored[artifact.object_key] = body
    _, summary = analysis.analyse_akta(session, project_id, user_id, artifact.id)
    assert summary["channel"].startswith("UV")


def test_an_unknown_channel_is_refused_with_the_ones_that_exist(session: Session, stored) -> None:
    project_id, user_id = _project(session)
    body = _unicorn_bytes()
    artifact = _artifact(session, project_id, user_id, "run.zip", body)
    stored[artifact.object_key] = body
    with pytest.raises(DomainError) as raised:
        analysis.analyse_akta(session, project_id, user_id, artifact.id, channel="Cond")
    assert raised.value.error_code == "akta_channel_not_found"


# --- Guards ------------------------------------------------------------------


def test_an_artifact_from_another_project_is_not_readable(session: Session, stored) -> None:
    project_id, user_id = _project(session)
    other_project, other_user = _project(session)
    body = _fortebio_bytes()
    foreign = _artifact(session, other_project, other_user, "run.csv", body)
    stored[foreign.object_key] = body

    with pytest.raises(DomainError) as raised:
        analysis.analyse_bli(session, project_id, user_id, foreign.id)
    assert raised.value.status_code == 404


def test_an_oversized_file_is_refused_rather_than_read_into_memory(
    session: Session, stored, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "huge.csv", body)
    stored[artifact.object_key] = body
    monkeypatch.setattr(analysis, "MAX_INSTRUMENT_BYTES", 10)

    with pytest.raises(DomainError) as raised:
        analysis.analyse_bli(session, project_id, user_id, artifact.id)
    assert raised.value.error_code == "instrument_file_too_large"
    assert raised.value.status_code == 413


def test_a_deleted_artifact_is_not_analysable(session: Session, stored) -> None:
    from datetime import UTC, datetime

    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body
    artifact.deleted_at = datetime.now(UTC)
    session.flush()

    with pytest.raises(DomainError) as raised:
        analysis.analyse_bli(session, project_id, user_id, artifact.id)
    assert raised.value.error_code == "artifact_not_found"


# --- The return half of the loop ---------------------------------------------


def _candidate(session: Session, project_id: uuid.UUID):
    from backend_v2.app.candidates.models import Candidate

    candidate = Candidate(project_id=project_id, candidate_key="d1", name="Design 1")
    session.add(candidate)
    session.flush()
    return candidate


def test_a_measurement_lands_on_the_candidate_as_a_measured_metric(
    session: Session, stored
) -> None:
    """The comparison the merge exists for: predicted and measured in one table,
    telling each other apart by evidence_kind."""
    from backend_v2.app.candidates.models import CandidateMetric

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    row, _ = analysis.analyse_bli(
        session, project_id, user_id, artifact.id,
        t_assoc=0.0, t_dissoc=120.0, candidate_id=candidate.id,
    )

    metric = session.scalar(
        select(CandidateMetric).where(CandidateMetric.candidate_id == candidate.id)
    )
    assert metric is not None
    assert metric.metric_key == "kd"
    assert metric.evidence_kind == "measured"
    assert metric.assessor == "instrument"
    assert metric.unit == "nM"
    assert metric.value == pytest.approx(row.value)
    # A measured number traces to the result that recorded it, not to a job.
    assert metric.source_experiment_result_id == row.id
    assert metric.source_job_id is None


def test_predicted_and_measured_values_coexist_rather_than_overwrite(
    session: Session, stored
) -> None:
    """A design predicted at one KD and measured at another must show both;
    that difference is the whole point of running the assay."""
    from backend_v2.app.candidates.models import CandidateMetric

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id)
    session.add(
        CandidateMetric(
            candidate_id=candidate.id, metric_key="kd", value=12.0,
            method="alphafold2_superfold", model_variant="model_1",
            evidence_kind="predicted", assessor="design_model", unit="nM",
        )
    )
    session.flush()

    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body
    analysis.analyse_bli(
        session, project_id, user_id, artifact.id,
        t_assoc=0.0, t_dissoc=120.0, candidate_id=candidate.id,
    )

    rows = list(
        session.scalars(select(CandidateMetric).where(CandidateMetric.candidate_id == candidate.id))
    )
    kinds = {row.evidence_kind for row in rows}
    assert kinds == {"predicted", "measured"}
    assert len(rows) == 2


def test_re_measuring_updates_in_place_rather_than_accumulating(
    session: Session, stored
) -> None:
    """Re-analysing a run corrects the measurement; it does not add a second one."""
    from backend_v2.app.candidates.models import CandidateMetric

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    analysis.analyse_bli(session, project_id, user_id, artifact.id,
                         t_assoc=0.0, t_dissoc=120.0, candidate_id=candidate.id)
    second, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id,
                                     t_assoc=0.0, t_dissoc=120.0, candidate_id=candidate.id)

    rows = list(
        session.scalars(
            select(CandidateMetric).where(
                CandidateMetric.candidate_id == candidate.id,
                CandidateMetric.evidence_kind == "measured",
            )
        )
    )
    assert len(rows) == 1
    # It points at the newer result.
    assert rows[0].source_experiment_result_id == second.id


def test_no_metric_is_written_when_nothing_ties_it_to_a_design(
    session: Session, stored
) -> None:
    from backend_v2.app.candidates.models import CandidateMetric

    project_id, user_id = _project(session)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body

    analysis.analyse_bli(session, project_id, user_id, artifact.id, t_assoc=0.0, t_dissoc=120.0)

    assert session.scalar(select(CandidateMetric)) is None


def test_an_akta_run_records_peak_area_against_the_candidate(session: Session, stored) -> None:
    from backend_v2.app.candidates.models import CandidateMetric

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id)
    body = _unicorn_bytes()
    artifact = _artifact(session, project_id, user_id, "run.zip", body)
    stored[artifact.object_key] = body

    analysis.analyse_akta(session, project_id, user_id, artifact.id, candidate_id=candidate.id)

    metric = session.scalar(
        select(CandidateMetric).where(CandidateMetric.candidate_id == candidate.id)
    )
    assert metric is not None
    assert (metric.metric_key, metric.evidence_kind) == ("peak_area", "measured")


def test_deleting_the_result_leaves_the_measurement_but_breaks_the_link(
    session: Session, stored
) -> None:
    """SET NULL, not CASCADE: the number was still measured, and losing the row
    that recorded it should not quietly erase the measurement from the design."""
    from backend_v2.app.candidates.models import CandidateMetric

    project_id, user_id = _project(session)
    candidate = _candidate(session, project_id)
    body = _fortebio_bytes()
    artifact = _artifact(session, project_id, user_id, "run.csv", body)
    stored[artifact.object_key] = body
    row, _ = analysis.analyse_bli(session, project_id, user_id, artifact.id,
                                  t_assoc=0.0, t_dissoc=120.0, candidate_id=candidate.id)

    session.delete(row)
    session.flush()
    session.expire_all()

    metric = session.scalar(
        select(CandidateMetric).where(CandidateMetric.candidate_id == candidate.id)
    )
    assert metric is not None
    assert metric.source_experiment_result_id is None


def test_the_response_carries_the_trace_the_browser_has_to_draw() -> None:
    """Plotting belongs to the frontend and the kernels return data, so the
    series has to travel — decimated, because a screen is about a thousand
    pixels wide and a sensorgram is tens of thousands of points."""
    from backend_v2.app.wetlab.analysis import TRACE_POINTS, _decimate

    dense = _decimate(range(10_000), range(10_000))
    assert len(dense) <= TRACE_POINTS + 1
    assert dense[0] == [0.0, 0.0]
    assert dense[-1] == [9999.0, 9999.0], "the end of the run must not be cropped off"

    # A short series is sent whole rather than padded or resampled.
    assert _decimate([0, 1, 2], [3, 4, 5]) == [[0.0, 3.0], [1.0, 4.0], [2.0, 5.0]]


def test_missing_points_are_dropped_rather_than_sent_as_zero() -> None:
    """JSON has no NaN, and a gap the client can see is more honest than a zero
    on a response axis where zero means "no binding"."""
    from backend_v2.app.wetlab.analysis import _decimate

    assert _decimate([0, 1, 2], [1.0, float("nan"), 3.0]) == [[0.0, 1.0], [2.0, 3.0]]
