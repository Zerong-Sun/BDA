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
