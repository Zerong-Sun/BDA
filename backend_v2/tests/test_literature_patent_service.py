"""Saved patents -> landscape: what gets counted, and what gets refused.

The kernel's counting is tested in test_literature_patents.py. What matters
here is the selection in front of it: only this project's saved patent
documents, only those carrying patent details, filtered the way the caller
asked - and every listed record pointing back at the trace that retrieved it.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.core.models import Base
from backend_v2.app.core.problem import DomainError
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.literature import patent_service
from backend_v2.app.literature.models import LiteratureDocument
from backend_v2.app.projects.models import Project
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as opened:
        yield opened
    drop_all(engine, Base.metadata)


_counter = itertools.count()


def _project(session: Session) -> uuid.UUID:
    n = next(_counter)
    user = User(username=f"pat-{n}", display_name="Pat", role="editor", enabled=True)
    organization = Organization(name=f"Pat Org {n}")
    session.add_all([user, organization])
    session.flush()
    project = Project(
        organization_id=organization.id, owner_id=user.id, name=f"pat-{n}", project_type="protein_design"
    )
    session.add(project)
    session.flush()
    return project.id


def _patent(
    session: Session,
    project_id: uuid.UUID,
    number: str,
    *,
    country: str,
    kind: str,
    stage: str,
    run_id: str = "run-1",
    source: str = patent_service.PATENT_SOURCE,
    with_details: bool = True,
) -> LiteratureDocument:
    metadata = {
        "search_run_id": run_id,
        "search_query": 'SRC:PAT AND ("PD-1" AND antibody)',
        "content_provenance": {"retrieval_trace_id": f"trace-{number}"},
    }
    if with_details:
        metadata["patent"] = {
            "publication_number": number,
            "country_code": country,
            "kind_code": kind,
            "stage": stage,
            "applicant": "EXAMPLE PHARMA",
            "application_date": "2015-01-01",
            "ipc": ["C07K16/28"],
            "url": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{number}",
        }
    document = LiteratureDocument(
        project_id=project_id,
        title=f"Title {number}",
        source=source,
        external_id=number,
        metadata_json=metadata,
        status="available",
    )
    session.add(document)
    session.flush()
    return document


def test_the_landscape_counts_saved_patents_and_lists_their_traces(session: Session) -> None:
    project_id = _project(session)
    _patent(session, project_id, "CN1000001B", country="CN", kind="B", stage="granted")
    _patent(session, project_id, "WO2015000001", country="WO", kind="A1", stage="pct_application")

    result = patent_service.project_landscape(session, project_id)

    assert result["records_matched"] == 2
    assert result["landscape"]["by_stage"] == {"granted": 1, "pct_application": 1}
    assert {record["retrieval_trace_id"] for record in result["records"]} == {
        "trace-CN1000001B",
        "trace-WO2015000001",
    }
    assert result["searches"] == ['SRC:PAT AND ("PD-1" AND antibody)']
    assert result["landscape"]["limits"], "a landscape must never arrive without its limits"


def test_papers_and_other_projects_are_not_counted(session: Session) -> None:
    project_id = _project(session)
    other_project = _project(session)
    _patent(session, project_id, "US9000001B2", country="US", kind="B2", stage="granted")
    _patent(session, project_id, "38000001", country="", kind="", stage="", source="europe_pmc")
    _patent(session, other_project, "EP3000001B1", country="EP", kind="B1", stage="granted")

    result = patent_service.project_landscape(session, project_id)

    assert [record["publication_number"] for record in result["records"]] == ["US9000001B2"]


def test_a_saved_document_without_patent_details_is_not_counted(session: Session) -> None:
    """Counting it would put an unknown-office row into a table about offices."""
    project_id = _project(session)
    _patent(session, project_id, "CN1000002A", country="CN", kind="A", stage="application", with_details=False)

    assert patent_service.project_landscape(session, project_id)["records_matched"] == 0


def test_it_filters_by_office_and_by_search_run(session: Session) -> None:
    project_id = _project(session)
    _patent(session, project_id, "CN1000003A", country="CN", kind="A", stage="application", run_id="run-a")
    _patent(session, project_id, "US9000002A1", country="US", kind="A1", stage="application", run_id="run-a")
    run_b = str(uuid.uuid4())
    _patent(session, project_id, "CN1000004B", country="CN", kind="B", stage="granted", run_id=run_b)

    chinese = patent_service.project_landscape(session, project_id, jurisdictions=("cn",))
    one_run = patent_service.project_landscape(session, project_id, search_run_id=uuid.UUID(run_b))

    assert sorted(record["publication_number"] for record in chinese["records"]) == ["CN1000003A", "CN1000004B"]
    assert chinese["filters"]["jurisdictions"] == ["CN"]
    assert [record["publication_number"] for record in one_run["records"]] == ["CN1000004B"]


def test_an_unknown_office_is_a_422_not_an_empty_landscape(session: Session) -> None:
    """An empty result would read as 'no patents there'."""
    project_id = _project(session)

    with pytest.raises(DomainError) as error:
        patent_service.project_landscape(session, project_id, jurisdictions=("XX",))

    assert error.value.status_code == 422
    assert error.value.error_code == "patent_jurisdiction_unknown"


def _owner(session: Session, project_id: uuid.UUID) -> tuple[Project, User]:
    project = session.get(Project, project_id)
    assert project is not None
    user = session.get(User, project.owner_id)
    assert user is not None
    return project, user


def _with(document: LiteratureDocument, session: Session, **metadata) -> LiteratureDocument:
    patent = {**(document.metadata_json or {}).get("patent", {}), **metadata.pop("patent", {})}
    document.metadata_json = {**(document.metadata_json or {}), "patent": patent, **metadata}
    session.flush()
    return document


LOOKED_UP = {
    "status": "completed",
    "family_id": "30117379",
    "application": "EP03741154",
    "matched_publication": True,
    "event_count": 5,
    "family_publications": 65,
    "retrieved_at": "2026-09-15T12:00:00+00:00",
    "retrieval_trace_id": "trace-legal",
    "by_country": [
        {
            "country": "DE",
            "events": 2,
            "positive": 1,
            "negative": 0,
            "latest_event": {"code": "PB01"},
            "latest_flagged_event": {"code": "PGFP"},
        },
        {"country": "EP", "events": 3, "positive": 2, "negative": 1, "latest_flagged_event": {"code": "27O"}},
    ],
}


def test_a_publication_saved_by_both_indexes_is_counted_once_keeping_the_richer_copy(session: Session) -> None:
    project_id = _project(session)
    _patent(session, project_id, "EP1537878", country="EP", kind="B1", stage="granted")
    ops = _with(
        _patent(session, project_id, "EP1537878", country="EP", kind="B1", stage="granted", source=patent_service.OPS_PATENT_SOURCE),
        session,
        patent={"family_id": "30117379"},
    )

    result = patent_service.project_landscape(session, project_id)

    assert result["records_matched"] == 1
    assert result["duplicate_copies_merged"] == 1
    assert result["records"][0]["document_id"] == str(ops.id)
    assert result["databases"] == ["EPO Open Patent Services (DOCDB)"]
    assert patent_service.publication_key({"publication_number": "EP1537878B1", "kind_code": "B1"}) == "EP1537878B1"


def test_families_are_counted_by_id_and_a_record_without_one_is_not_its_own_family(session: Session) -> None:
    project_id = _project(session)
    for number in ("US9000010B2", "EP3000010B1"):
        _with(
            _patent(session, project_id, number, country=number[:2], kind=number[-2:], stage="granted", source=patent_service.OPS_PATENT_SOURCE),
            session,
            patent={"family_id": "F-1"},
        )
    _patent(session, project_id, "CN1000010A", country="CN", kind="A", stage="application")

    families = patent_service.project_landscape(session, project_id)["families"]

    assert families["distinct"] == 1
    assert families["publications_without_family_id"] == 1


def test_legal_events_are_shown_per_country_and_only_for_a_completed_lookup(session: Session) -> None:
    project_id = _project(session)
    looked_up = _with(
        _patent(session, project_id, "EP1537878", country="EP", kind="B1", stage="granted"),
        session,
        patent_legal_status=LOOKED_UP,
    )
    failed = _with(
        _patent(session, project_id, "US7595048", country="US", kind="B2", stage="granted"),
        session,
        patent_legal_status={"status": "failed", "error": "epo_ops.family_legal_failed", "retrieval_trace_id": "t-2"},
    )
    untouched = _patent(session, project_id, "WO2004004771", country="WO", kind="A1", stage="pct_application")

    result = patent_service.project_landscape(session, project_id)
    records = {record["document_id"]: record for record in result["records"]}

    assert result["legal_events"]["looked_up"] == 1
    assert result["legal_events"]["lookup_gaps"] == 1
    assert result["legal_events"]["not_looked_up"] == 1
    assert result["legal_events"]["limits"], "events never arrive without their limits"
    view = records[str(looked_up.id)]["legal_events"]
    assert [row["country"] for row in view["countries"]] == ["DE", "EP"]
    assert view["retrieval_trace_id"] == "trace-legal"
    assert view["countries"][0]["latest_event"] == {"code": "PB01"}
    assert "positive" not in view["countries"][0], "the per-country counts stay in the lookup"
    assert records[str(failed.id)]["legal_events"] == {
        "status": "failed",
        "error": "epo_ops.family_legal_failed",
        "retrieval_trace_id": "t-2",
    }
    assert records[str(untouched.id)]["legal_events"] is None
    # A family id learned by a lookup counts, even on a Europe PMC record.
    assert records[str(looked_up.id)]["family_id"] == "30117379"
    assert result["families"]["distinct"] == 1


def test_a_legal_status_lookup_is_queued_for_this_projects_saved_patents(session: Session, monkeypatch) -> None:
    from backend_v2.app.compute.models import OutboxEvent
    from backend_v2.app.platform.models import Operation

    monkeypatch.setattr(patent_service, "credential_available", lambda reference: True)
    project_id = _project(session)
    project, user = _owner(session, project_id)
    document = _patent(session, project_id, "EP1537878", country="EP", kind="B1", stage="granted")

    result = patent_service.create_legal_status_lookup(session, project, [document.id, document.id], user)

    assert result["status"] == "pending" and result["documents"] == 1
    operation = session.get(Operation, uuid.UUID(result["operation_id"]))
    assert operation is not None
    assert operation.kind == patent_service.LEGAL_STATUS_TOPIC
    assert operation.resource_id == uuid.UUID(result["lookup_id"])
    event = session.get(OutboxEvent, operation.id)
    assert event is not None
    assert event.payload["document_ids"] == [str(document.id)]
    assert event.payload["requested_by"] == str(user.id)
    assert event.payload["project_id"] == str(project.id)


def test_a_lookup_that_could_only_fail_is_refused_before_it_is_queued(session: Session, monkeypatch) -> None:
    project_id = _project(session)
    other_project = _project(session)
    project, user = _owner(session, project_id)
    patent = _patent(session, project_id, "EP1537878", country="EP", kind="B1", stage="granted")
    paper = _patent(session, project_id, "38000002", country="", kind="", stage="", source="europe_pmc")
    foreign = _patent(session, other_project, "EP3000020B1", country="EP", kind="B1", stage="granted")

    def refused(ids: list[uuid.UUID]) -> DomainError:
        with pytest.raises(DomainError) as raised:
            patent_service.create_legal_status_lookup(session, project, ids, user)
        return raised.value

    monkeypatch.setattr(patent_service, "credential_available", lambda reference: False)
    assert refused([patent.id]).error_code == "epo_ops_not_configured"

    monkeypatch.setattr(patent_service, "credential_available", lambda reference: True)
    assert refused([]).error_code == "patent_documents_required"
    assert refused([uuid.uuid4() for _ in range(26)]).error_code == "patent_documents_too_many"
    assert refused([patent.id, foreign.id]).error_code == "patent_document_not_found"
    assert refused([patent.id, paper.id]).error_code == "patent_document_not_a_patent"
