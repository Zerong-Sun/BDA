import uuid
from types import SimpleNamespace

from backend_v2.app.projects.models import Project
from backend_v2.app.projects.service import dedupe_builtin_research_projects, require_project
from backend_v2.app.research.workspace import _references
from backend_v2.tests.test_compute_service import compute_session as compute_session


def test_historical_project_keeps_its_direct_link_while_portfolio_has_one_entry(compute_session):
    session, user, canonical, _ = compute_session
    historical = Project(organization_id=canonical.organization_id, owner_id=user.id,
                         name="Historical source", project_type="research", localized_content={
                             "portfolio_consolidation": {"role": "historical_source", "canonical_project_id": str(canonical.id)},
                         })
    session.add(historical)
    session.flush()
    assert dedupe_builtin_research_projects(session, [canonical, historical]) == [canonical]
    assert require_project(session, historical.id, user).id == historical.id
    # Pagination may omit the canonical row; an existing root still wins.
    assert dedupe_builtin_research_projects(session, [historical]) == []
    historical.localized_content = {"portfolio_consolidation": {"role": "historical_source", "canonical_project_id": str(uuid.uuid4())}}
    assert dedupe_builtin_research_projects(session, [historical]) == [historical]


def document(project_id, **metadata):
    return SimpleNamespace(id=uuid.uuid4(), project_id=project_id, title="Same publication", external_id="12345678",
                           abstract=None, status="available", metadata_json=metadata)


def test_consolidated_reference_retains_aliases_for_unique_notes_and_old_citations():
    project_id=uuid.uuid4()
    canonical=document(project_id, ref_id="R1")
    other=document(project_id, ref_id="OLD", presentation_duplicate_of=str(canonical.id))
    refs=_references([canonical, other])
    assert len(refs)==1
    assert refs[0].document_id==canonical.id
    assert refs[0].metadata["consolidated_document_ids"]==[str(other.id)]
    assert refs[0].metadata["consolidated_ref_ids"]==["OLD"]
    # A bad cross-project pointer must not make a paper disappear.
    other.project_id=uuid.uuid4()
    assert len(_references([canonical, other]))==2
