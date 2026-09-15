"""Druggability runs end to end: what is refused, what is saved, what is read.

The evidence service is replaced with a fake that returns the shapes the real
sources returned for PD-1; the database is real (SQLite), so what is tested is
the run's life: refused before queueing when the target cannot be identified,
saved with one audited evidence row per section, readable only as what it is,
and not duplicated when the worker delivers the same message twice.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.intelligence import druggability_service
from backend_v2.app.intelligence import tasks as intelligence_tasks
from backend_v2.app.intelligence.models import IntelligenceEvidence, IntelligenceReport, IntelligenceRun
from backend_v2.app.projects.models import Project
from backend_v2.app.research import evidence_tools
from backend_v2.app.targets.models import Target
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from backend_v2.tests.test_intelligence_druggability import OPEN_TARGETS_PDCD1, UNIPROT_Q15116
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class _FakeEvidenceTools:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get_uniprot(self, accession: str) -> evidence_tools.EvidenceToolResult:
        return evidence_tools.EvidenceToolResult(data=UNIPROT_Q15116, audit={"tool": "uniprot.entry"})

    def get_open_targets_druggability(self, ensembl_id: str) -> evidence_tools.EvidenceToolResult:
        return evidence_tools.EvidenceToolResult(
            data={"data": OPEN_TARGETS_PDCD1}, audit={"tool": "open_targets.druggability"}
        )

    def count_clinical_trials(
        self, term: str, *, phase: str | None = None, start_year: int | None = None
    ) -> evidence_tools.EvidenceToolResult:
        return evidence_tools.EvidenceToolResult(
            data={"totalCount": 40 if phase is None and start_year is None else 4},
            audit={"tool": "clinical_trials.count", "phase": phase, "start_year": start_year},
        )

    def list_clinical_trial_sponsors(
        self, term: str, *, page_token: str | None = None
    ) -> evidence_tools.EvidenceToolResult:
        return evidence_tools.EvidenceToolResult(
            data={
                "studies": [
                    {"protocolSection": {"sponsorCollaboratorsModule": {"leadSponsor": {"class": "INDUSTRY", "name": "Merck"}}}}
                ],
                "nextPageToken": None,
            },
            audit={"tool": "clinical_trials.sponsors"},
        )

    def close(self) -> None:
        pass


@pytest.fixture
def factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker]:
    engine = enforce_foreign_keys(
        create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(engine, expire_on_commit=False)

    @contextmanager
    def scope():
        with maker() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    monkeypatch.setattr(intelligence_tasks, "session_scope", scope)
    monkeypatch.setattr(evidence_tools, "EvidenceToolService", _FakeEvidenceTools)
    yield maker
    drop_all(engine, Base.metadata)


_counter = itertools.count()


def _project(session: Session) -> tuple[Project, User]:
    n = next(_counter)
    user = User(username=f"drug-{n}", display_name="D", role="editor", enabled=True)
    organization = Organization(name=f"Drug Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"drug-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    return project, user


def _queued_run(maker: sessionmaker, *, accession: str | None = "Q15116") -> tuple[uuid.UUID, uuid.UUID]:
    with maker() as session:
        project, user = _project(session)
        target = Target(project_id=project.id, name="PD-1", uniprot_accession=accession)
        session.add(target)
        session.flush()
        run = druggability_service.create_druggability_run(session, project, target.id, user)
        session.commit()
        return project.id, run.id


def test_a_target_without_a_uniprot_accession_is_refused_before_anything_is_queued(factory) -> None:
    """Resolving it by name is the failure the charter forbids."""
    with pytest.raises(DomainError) as error:
        _queued_run(factory, accession=None)

    assert error.value.status_code == 422
    assert error.value.error_code == "target_uniprot_missing"
    with factory() as session:
        assert session.scalars(select(IntelligenceRun)).all() == []


def test_another_projects_target_is_a_404(factory) -> None:
    with factory() as session:
        project, user = _project(session)
        other, _ = _project(session)
        foreign = Target(project_id=other.id, name="Elsewhere", uniprot_accession="Q15116")
        session.add(foreign)
        session.flush()

        with pytest.raises(DomainError) as error:
            druggability_service.create_druggability_run(session, project, foreign.id, user)

    assert error.value.status_code == 404


def test_the_task_saves_a_report_and_one_audited_evidence_row_per_section(factory) -> None:
    _, run_id = _queued_run(factory)

    outcome = intelligence_tasks.druggability_assessment.run(str(run_id))

    assert outcome["status"] == "succeeded"
    with factory() as session:
        report = session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == run_id))
        evidence = session.scalars(select(IntelligenceEvidence).where(IntelligenceEvidence.run_id == run_id)).all()
    assert report is not None
    assert report.content["clinical_candidates"]["approved"] == 2
    assert "no druggability probability" in report.summary.lower()
    assert {row.evidence_type for row in evidence} == {
        "druggability_tractability",
        "druggability_clinical_candidates",
        "druggability_safety_liabilities",
        "druggability_trial_activity",
        "druggability_market_landscape",
    }
    assert all(row.citation.get("retrieval") for row in evidence)
    assert all(row.review_status == "pending" for row in evidence)


def test_a_redelivered_message_does_not_duplicate_the_report(factory) -> None:
    _, run_id = _queued_run(factory)

    intelligence_tasks.druggability_assessment.run(str(run_id))
    again = intelligence_tasks.druggability_assessment.run(str(run_id))

    assert again["status"] == "succeeded"
    with factory() as session:
        evidence = session.scalars(select(IntelligenceEvidence).where(IntelligenceEvidence.run_id == run_id)).all()
    assert len(evidence) == 5


def test_reading_before_the_run_finishes_says_so_instead_of_returning_an_empty_report(factory) -> None:
    project_id, run_id = _queued_run(factory)

    with factory() as session:
        pending = druggability_service.read_assessment(session, project_id, run_id)

    assert pending["report"] is None
    assert pending["note"]


def test_a_finished_run_reads_back_in_full(factory) -> None:
    project_id, run_id = _queued_run(factory)
    intelligence_tasks.druggability_assessment.run(str(run_id))

    with factory() as session:
        done = druggability_service.read_assessment(session, project_id, run_id)

    assert done["status"] == "succeeded"
    assert done["report"]["ensembl_id"] == "ENSG00000188389"
    assert done["report"]["limits"]


def test_a_target_intelligence_run_is_not_readable_as_a_druggability_report(factory) -> None:
    """Otherwise a report about something else would be read as this one."""
    with factory() as session:
        project, user = _project(session)
        target = Target(project_id=project.id, name="PD-1", uniprot_accession="Q15116")
        session.add(target)
        session.flush()
        other_kind = IntelligenceRun(project_id=project.id, target_id=target.id, created_by=user.id, query={})
        session.add(other_kind)
        session.flush()

        with pytest.raises(DomainError) as error:
            druggability_service.read_assessment(session, project.id, other_kind.id)

    assert error.value.status_code == 404


def test_another_projects_assessment_is_a_404(factory) -> None:
    _, run_id = _queued_run(factory)
    with factory() as session:
        stranger, _ = _project(session)
        session.commit()
        stranger_id = stranger.id

    with factory() as session, pytest.raises(DomainError) as error:
        druggability_service.read_assessment(session, stranger_id, run_id)

    assert error.value.status_code == 404


# --- What the audit found: a run that breaks must not stay running -----------


def test_a_run_whose_gathering_breaks_ends_failed_with_the_reason_saved(
    factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-source failures are gaps; this is the gathering itself breaking.

    Without containment the run sits at "running" for ever: no report, no
    error, and nothing to tell a reader whether to wait or to start again.
    """
    _, run_id = _queued_run(factory)

    def explode(*args, **kwargs):
        raise RuntimeError("open_targets.druggability_failed")

    monkeypatch.setattr(intelligence_tasks, "gather_druggability", explode)

    outcome = intelligence_tasks.druggability_assessment.run(str(run_id))

    assert outcome["status"] == "failed"
    with factory() as session:
        run = session.get(IntelligenceRun, run_id)
        report = session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == run_id))
    assert run is not None and run.status == "failed"
    # The reason is readable: IntelligenceRun has no error column, so it lives
    # in the report the reader already fetches.
    assert report is not None
    assert "open_targets.druggability_failed" in report.content["error"]
    assert "could not be completed" in report.summary


def test_the_projects_own_saved_evidence_is_counted_into_the_report(factory) -> None:
    """The report cites public sources; this says what the project itself can cite."""
    from backend_v2.app.literature.models import LiteratureDocument
    from backend_v2.app.literature.patent_service import PATENT_SOURCE

    project_id, run_id = _queued_run(factory)
    with factory() as session:
        session.add_all(
            [
                LiteratureDocument(
                    project_id=project_id, title="PD-1 blockade in NSCLC", source="europe_pmc",
                    external_id="MED/1", status="indexed",
                ),
                LiteratureDocument(
                    project_id=project_id, title="Anti-PD-1 antibody", source=PATENT_SOURCE,
                    external_id="CN1", status="indexed",
                ),
                LiteratureDocument(
                    project_id=project_id, title="Second patent", source=PATENT_SOURCE,
                    external_id="CN2", status="indexed",
                ),
            ]
        )
        session.commit()

    intelligence_tasks.druggability_assessment.run(str(run_id))

    with factory() as session:
        report = session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == run_id))
    assert report is not None
    signal = report.content["literature_signal"]
    assert (signal["saved_papers"], signal["saved_patents"]) == (1, 2)
    # The paper is listed; patents are counted but not mixed into the reading list.
    assert [item["title"] for item in signal["recent"]] == ["PD-1 blockade in NSCLC"]
    assert "1 papers and 2 patents saved in this project" in report.summary
    assert not any("saved no papers or patents" in gap for gap in report.content["gaps"])


def test_a_project_with_nothing_saved_gets_an_actionable_gap(factory) -> None:
    _, run_id = _queued_run(factory)

    intelligence_tasks.druggability_assessment.run(str(run_id))

    with factory() as session:
        report = session.scalar(select(IntelligenceReport).where(IntelligenceReport.run_id == run_id))
    assert report is not None
    assert any("saved no papers or patents" in gap for gap in report.content["gaps"])


def test_a_supplied_trial_term_that_is_too_long_names_the_term(factory) -> None:
    with factory() as session:
        project, user = _project(session)
        target = Target(project_id=project.id, name="PD-1", uniprot_accession="Q15116")
        session.add(target)
        session.flush()

        with pytest.raises(DomainError) as error:
            druggability_service.create_druggability_run(
                session, project, target.id, user, trial_term="x" * 201
            )

    assert error.value.error_code == "trial_term_too_long"


def test_a_target_name_too_long_to_search_by_blames_the_name_not_the_term(factory) -> None:
    """The caller passed no term, so an error about their 'trial term' sends them looking for an argument they never gave."""
    with factory() as session:
        project, user = _project(session)
        target = Target(project_id=project.id, name="P" * 201, uniprot_accession="Q15116")
        session.add(target)
        session.flush()

        with pytest.raises(DomainError) as error:
            druggability_service.create_druggability_run(session, project, target.id, user)

    assert error.value.error_code == "target_name_too_long"
    assert "Supply a shorter trial_term" in error.value.detail


def test_a_target_with_no_name_and_no_term_says_what_is_missing(factory) -> None:
    with factory() as session:
        project, user = _project(session)
        target = Target(project_id=project.id, name="", uniprot_accession="Q15116")
        session.add(target)
        session.flush()

        with pytest.raises(DomainError) as error:
            druggability_service.create_druggability_run(session, project, target.id, user)

    assert error.value.error_code == "trial_term_missing"
