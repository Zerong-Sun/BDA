"""Citation resource IDs refer to chunks, independently of their ordinal position."""
from __future__ import annotations

import uuid

from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.literature.models import LiteratureChunk, LiteratureDocument
from backend_v2.app.projects.models import Project

pytest_plugins = ["backend_v2.tests.test_v2_domains"]


def test_excerpt_identity_preserves_provenance_with_sparse_positions(domain_client) -> None:
    _client, ids = domain_client
    with ids["session_factory"]() as session:
        document = LiteratureDocument(
            project_id=ids["project"], title="Saved paper", source="pubmed", external_id="paper-1",
            metadata_json={"content_provenance": {"content_kind": "database_abstract", "content_checksum_sha256": "a" * 64}},
        )
        session.add(document)
        session.flush()
        chunks = [LiteratureChunk(document_id=document.id, position=position, content=f"Excerpt {position}")
                  for position in (5, 37)]
        session.add_all(chunks)
        session.flush()
        context = ResearchContextService(session, session.get(Project, ids["project"]))

        direct = context.get_reference_excerpt(str(chunks[1].id))
        paged = context.get_reference_content(str(document.id), offset=1, limit=1)[0]

        assert direct is not None
        assert direct["data"]["position"] == 37
        assert direct["data"]["content_provenance"] == document.metadata_json["content_provenance"]
        assert context.citation_for_item(direct) == context.citation_for_item(paged)
        paged["data"].pop("read_window")
        assert direct == paged


def test_excerpt_identity_rejects_foreign_unlisted_and_invalid_ids(domain_client) -> None:
    _client, ids = domain_client
    with ids["session_factory"]() as session:
        other = Project(organization_id=ids["organization"], owner_id=ids["user"],
                        name="Other project", project_type="protein_design")
        session.add(other)
        session.flush()
        documents = [LiteratureDocument(project_id=project_id, title="Paper", source="pubmed")
                     for project_id in (ids["project"], other.id)]
        session.add_all(documents)
        session.flush()
        chunks = [LiteratureChunk(document_id=document.id, position=0, content="Saved excerpt") for document in documents]
        session.add_all(chunks)
        session.flush()
        context = ResearchContextService(session, session.get(Project, ids["project"]))

        assert context.get_reference_excerpt(str(chunks[0].id)) is not None
        assert context.get_reference_excerpt(str(chunks[1].id)) is None
        assert context.get_reference_excerpt(str(uuid.uuid4())) is None
        assert context.get_reference_excerpt("not-a-uuid") is None
        context.workspace["references"] = []
        assert context.get_reference_excerpt(str(chunks[0].id)) is None
