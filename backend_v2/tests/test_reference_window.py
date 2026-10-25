"""A returned literature page must not be mistaken for the document's total."""
from __future__ import annotations

import json

from backend_v2.app.copilot import tools as _tools  # noqa: F401
from backend_v2.app.copilot.registry import REGISTRY, ToolContext
from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.literature.models import LiteratureChunk, LiteratureDocument
from backend_v2.app.projects.models import Project

pytest_plugins = ["backend_v2.tests.test_v2_domains"]


def _reference(session, project_id, count: int, ref_id: str = "R66") -> LiteratureDocument:
    document = LiteratureDocument(
        project_id=project_id, title="Synthetic stored excerpt pagination", source="synthetic_test",
        external_id=ref_id, metadata_json={"ref_id": ref_id}, status="available",
    )
    session.add(document)
    session.flush()
    session.add_all([
        LiteratureChunk(document_id=document.id, position=position, content=f"Synthetic saved chunk {position}.")
        for position in range(count)
    ])
    session.flush()
    return document


def test_reference_pages_report_fifty_of_sixty_six_then_remaining_sixteen(domain_client) -> None:
    _, ids = domain_client
    with ids["session_factory"]() as session:
        project = session.get(Project, ids["project"])
        document = _reference(session, project.id, 66)
        research = ResearchContextService(session, project)
        context = ToolContext(project_id=project.id, user_id=ids["user"], session=session, research=research,
                              allowed_capabilities=frozenset({"research-read"}))

        first = REGISTRY.execute("get_reference_content", context, {"reference_id": "R66", "limit": 50})

        assert isinstance(first, list) and len(first) == 50
        window = first[0]["data"]["read_window"]
        assert window == {
            "scope": "saved_indexed_chunks", "offset": 0, "returned_count": 50, "total_count": 66,
            "has_more": True, "next_offset": 50, "truncated": True,
        }
        assert all(row["data"]["document_id"] == str(document.id) for row in first)
        assert first[-1]["data"]["position"] == 49

        second = REGISTRY.execute("get_reference_content", context,
                                  {"reference_id": str(document.id), "offset": window["next_offset"], "limit": 50})

        assert isinstance(second, list) and len(second) == 16
        assert second[0]["data"]["read_window"] == {
            "scope": "saved_indexed_chunks", "offset": 50, "returned_count": 16, "total_count": 66,
            "has_more": False, "next_offset": None, "truncated": True,
        }
        assert second[0]["data"]["position"] == 50 and second[-1]["data"]["position"] == 65
        assert len({row["id"] for row in first + second}) == 66


def test_complete_small_window_and_empty_window_keep_list_compatibility(domain_client) -> None:
    _, ids = domain_client
    with ids["session_factory"]() as session:
        project = session.get(Project, ids["project"])
        _reference(session, project.id, 2)
        _reference(session, project.id, 0, "EMPTY")
        research = ResearchContextService(session, project)

        rows = research.get_reference_content("R66", offset=-3, limit=50)

        assert rows[0]["data"]["read_window"] == {
            "scope": "saved_indexed_chunks", "offset": 0, "returned_count": 2, "total_count": 2,
            "has_more": False, "next_offset": None, "truncated": False,
        }
        assert research.get_reference_content("R66", offset=2, limit=50) == []
        assert research.get_reference_content("EMPTY") == []
        assert research.get_reference_content("MISSING") == []


def test_reference_window_never_counts_or_exposes_another_projects_chunks(domain_client) -> None:
    _, ids = domain_client
    with ids["session_factory"]() as session:
        project = session.get(Project, ids["project"])
        _reference(session, project.id, 66)
        other = Project(organization_id=ids["organization"], owner_id=ids["user"],
                        name="Other project with private chunks", project_type="research")
        session.add(other)
        session.flush()
        foreign = _reference(session, other.id, 7)
        research = ResearchContextService(session, project)

        rows = research.get_reference_content("R66", limit=50)

        assert rows[0]["data"]["read_window"]["total_count"] == 66
        assert str(foreign.id) not in json.dumps(rows)
        assert research.get_reference_content(str(foreign.id), limit=50) == []
