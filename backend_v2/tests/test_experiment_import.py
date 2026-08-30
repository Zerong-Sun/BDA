"""Manual result upload: candidate linkage and row-level fault tolerance.

Live data showed the defect this covers: results carried a candidate_ref but
candidate_id stayed NULL, so uploaded assay data never joined to the designs it
measured and tested_candidate_count reported zero.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.core.models import Base
from backend_v2.app.experiments import tasks as experiments_tasks
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.experiments.schemas import ExperimentResultBatch
from backend_v2.app.experiments.service import create_results
from backend_v2.app.experiments.tasks import (
    EXPERIMENT_IMPORT_COLUMNS,
    _coerce_experiment_row,
    _experiment_rows,
)
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.tests._sqlite import enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def env() -> Generator[tuple[Session, User, Project, Candidate]]:
    engine = enforce_foreign_keys(create_engine("sqlite+pysqlite://"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(username="lab", display_name="Lab", role="admin", enabled=True)
        org = Organization(name="Lab Org")
        session.add_all([user, org])
        session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        project = Project(organization_id=org.id, owner_id=user.id, name="Assay", project_type="design")
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
        candidate = Candidate(project_id=project.id, candidate_key="PD1Binder_c7239", name="c7239", status="generated")
        session.add(candidate)
        session.commit()
        yield session, user, project, candidate
    engine.dispose()


def test_batch_post_resolves_candidate_ref(env) -> None:
    session, user, project, candidate = env
    results = create_results(
        session,
        project,
        ExperimentResultBatch(
            results=[
                {"candidate_ref": "PD1Binder_c7239", "experiment_type": "binding", "value": 1.2, "unit": "nM"},
                {"candidate_ref": "not-a-candidate", "experiment_type": "binding", "value": 3.4, "unit": "nM"},
            ]
        ),
        user,
    )
    assert results[0].candidate_id == candidate.id
    # An unmatched reference is preserved rather than dropped, and does not fail the batch.
    assert results[1].candidate_id is None
    assert results[1].candidate_ref == "not-a-candidate"


def test_row_coercion_reports_bad_cells_instead_of_failing_the_file() -> None:
    good, error = _coerce_experiment_row(
        {"experiment_type": "binding", "value": "1.5", "unit": "nM", "batch_key": "plate-3"}, 1
    )
    assert error is None
    assert good is not None
    assert good["value"] == 1.5
    # batch_key used to be excluded from the whitelist, so it could never be imported.
    assert good["batch_key"] == "plate-3"
    assert good["pass_status"] == "unknown"

    bad_value, error = _coerce_experiment_row({"experiment_type": "binding", "value": "N/A"}, 7)
    assert bad_value is None
    assert error == {"row": 7, "column": "value", "message": "'N/A' is not a number"}

    missing_type, error = _coerce_experiment_row({"value": "1.0"}, 9)
    assert missing_type is None
    assert error is not None and error["column"] == "experiment_type"


def test_whitelist_covers_the_columns_the_model_actually_has() -> None:
    columns = {column.name for column in ExperimentResult.__table__.columns}
    assert EXPERIMENT_IMPORT_COLUMNS <= columns
    for required in ("batch_key", "failure_reason", "candidate_ref"):
        assert required in EXPERIMENT_IMPORT_COLUMNS


def test_csv_and_json_rows_parse() -> None:
    csv_rows = _experiment_rows(
        "results.csv", "text/csv", b"candidate_ref,experiment_type,value\nc7239,binding,1.5\n"
    )
    assert csv_rows == [{"candidate_ref": "c7239", "experiment_type": "binding", "value": "1.5"}]

    json_rows = _experiment_rows(
        "results.json", "application/json", b'{"results":[{"experiment_type":"binding","value":2}]}'
    )
    assert json_rows == [{"experiment_type": "binding", "value": 2}]

    with pytest.raises(ValueError, match="experiment_format_unsupported"):
        _experiment_rows("results.txt", "text/plain", b"nope")


def test_dry_run_reports_candidate_refs_that_will_not_match(env, monkeypatch, tmp_path) -> None:
    """Catching unmatched references is the whole reason to dry-run before committing."""
    import json as _json

    session, user, project, candidate = env
    session.commit()

    artifact = Artifact(
        project_id=project.id,
        created_by=user.id,
        artifact_type="score_table",
        filename="results.json",
        content_type="application/json",
        object_key="k",
        size_bytes=1,
        checksum_sha256="a" * 64,
        status="available",
    )
    session.add(artifact)
    session.commit()

    rows = [
        {"candidate_ref": candidate.candidate_key, "experiment_type": "binding", "value": 1.0},
        {"candidate_ref": "ghost-candidate", "experiment_type": "binding", "value": 2.0},
        {"experiment_type": "binding", "value": "N/A"},
    ]
    monkeypatch.setattr(experiments_tasks, "SessionFactory", lambda: session)
    monkeypatch.setattr(
        experiments_tasks, "ObjectStorage", lambda: type("S", (), {"read_bytes": staticmethod(lambda *a, **k: _json.dumps({"results": rows}).encode())})()
    )

    report = experiments_tasks.experiment_results_import(str(artifact.id), dry_run=True)

    assert report["status"] == "dry_run"
    assert report["would_import"] == 2
    # The bad numeric cell is a skip; the unmatched reference is a warning.
    assert report["skipped"] == 1
    assert report["unlinked"] == 1
    assert any("ghost-candidate" in item["message"] for item in report["errors"])
    # A dry run writes nothing.
    assert session.query(ExperimentResult).count() == 0


def test_an_empty_workbook_reports_rather_than_crashing() -> None:
    """next() on an empty sheet used to raise StopIteration from deep in the task."""
    import io

    from backend_v2.app.experiments.tasks import _experiment_rows
    from openpyxl import Workbook

    workbook = Workbook()
    buffer = io.BytesIO()
    workbook.save(buffer)
    with pytest.raises(ValueError, match="experiment_workbook_empty"):
        _experiment_rows("empty.xlsx", "application/vnd.ms-excel", buffer.getvalue())
