from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from backend_v2.app import all_models  # noqa: F401
from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.copilot.research_context import ResearchContextService
from backend_v2.app.core.models import Base
from backend_v2.app.identity.models import Organization, User
from backend_v2.app.projects.models import Project
from backend_v2.app.research import workspace
from backend_v2.app.research.models import ResearchBrief
from backend_v2.app.targets.models import Target
from backend_v2.tests._sqlite import drop_all, enforce_foreign_keys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def finding(
    *,
    finding_type: str = "references_reading",
    title: str = "Reference reading",
    content: str = "Reviewed source",
    evidence: dict | None = None,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        finding_type=finding_type,
        title=title,
        content=content,
        evidence=evidence or {},
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_review_sources_are_available_as_references_without_literature_rows() -> None:
    pubmed = "https://pubmed.ncbi.nlm.nih.gov/23268147/"
    rows = [
        finding(
            title="B. cinerea chitin synthase genetics",
            evidence={
                "sources": [
                    pubmed,
                    "https://www.rcsb.org/structure/2O9U",
                    "UniProt P02881",
                    "Project-specific source still required",
                ],
                "source_metadata": {
                    pubmed: {
                        "title": "Curated article title",
                        "authors": "A. Author; B. Author",
                        "doi": "10.1000/curated",
                    }
                },
                "review_status": "accepted",
            },
        )
    ]

    references = workspace._finding_references(uuid.uuid4(), rows, [])

    assert {item.ref_id for item in references} == {"PMID 23268147", "PDB 2O9U", "UniProt P02881"}
    article = next(item for item in references if item.pmid)
    assert article.title.default == "Curated article title"
    assert article.authors == "A. Author; B. Author"
    assert article.doi == "10.1000/curated"
    assert article.url == pubmed


def test_generic_article_url_uses_enriched_canonical_identifier() -> None:
    article_url = "https://publisher.example/articles/123"
    rows = [
        finding(
            title="Publisher route",
            evidence={
                "sources": [article_url],
                "source_metadata": {
                    article_url: {
                        "title": "Canonical article",
                        "doi": "10.1000/canonical",
                        "url": "https://doi.org/10.1000/canonical",
                    }
                },
            },
        )
    ]

    reference = workspace._finding_references(uuid.uuid4(), rows, [])[0]

    assert reference.ref_id == "DOI 10.1000/canonical"
    assert reference.doi == "10.1000/canonical"
    assert reference.url == "https://doi.org/10.1000/canonical"


def test_pdb_id_backfills_structure_reference_and_rcsb_url(monkeypatch) -> None:
    monkeypatch.setattr(
        workspace,
        "ObjectStorage",
        lambda: SimpleNamespace(download_url=lambda key: f"https://objects.test/{key}"),
    )
    row = SimpleNamespace(
        id=uuid.uuid4(),
        filename="1ABC.pdb",
        object_key="structures/1ABC.pdb",
        status="available",
        lineage={"pdb_id": "1abc", "name": "Example protein"},
    )

    structure = workspace._structures([row])[0]

    assert structure.pdb_id == "1ABC"
    assert structure.reference_id == "PDB 1ABC"
    assert structure.rcsb_url == "https://www.rcsb.org/structure/1ABC"
    assert structure.download_url == "https://objects.test/structures/1ABC.pdb"


@pytest.mark.parametrize(
    ("value", "fallback", "expected"),
    [
        (None, {"zh": "结构", "en": "Structure"}, {"zh": "结构", "en": "Structure", "default": "结构"}),
        ({"en": "Reviewed structure"}, {"zh": "结构", "en": "Structure"},
         {"zh": "结构", "en": "Reviewed structure", "default": "结构"}),
        ({"zh-CN": "已核对结构"}, {"zh": "结构", "en": "Structure", "default": "Source name"},
         {"zh": "已核对结构", "en": "Structure", "default": "Source name"}),
        ({"default": "Reviewed name"}, {"en": "Structure"},
         {"zh": None, "en": "Structure", "default": "Reviewed name"}),
        ({"en": ""}, {"en": "Structure"}, {"zh": None, "en": "Structure", "default": "Structure"}),
        ("Explicit name", {"zh": "结构", "en": "Structure"},
         {"zh": "结构", "en": "Structure", "default": "Explicit name"}),
        ({"zh": "结构"}, "Original source", {"zh": "结构", "en": None, "default": "Original source"}),
        (None, None, {"zh": None, "en": None, "default": ""}),
    ],
)
def test_localized_fallback_keeps_stored_languages_and_default_precedence(value, fallback, expected) -> None:
    assert workspace._localized(value, fallback).model_dump() == expected


def test_bilingual_artifact_lineage_reaches_copilot_as_a_readable_structure_citation(monkeypatch) -> None:
    monkeypatch.setattr(workspace, "ObjectStorage", lambda: SimpleNamespace(
        download_url=lambda key: f"https://objects.test/{key}",
    ))
    engine = enforce_foreign_keys(create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    ))
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user = User(username="structure-owner", display_name="Structure Owner", role="admin", enabled=True)
            organization = Organization(name="Structure Org")
            session.add_all([user, organization])
            session.flush()
            project = Project(organization_id=organization.id, owner_id=user.id,
                              name="Structure project", project_type="research")
            session.add(project)
            session.flush()
            lineage = {
                "pdb_id": "1abc", "name": {"zh": "复合物结构", "en": "Complex structure"},
                "role": {"zh": "靶标", "en": "Target"}, "reference_ids": ["R036"],
                "localized_content": {"name": {"en": "Reviewed complex structure"}},
            }
            artifact = Artifact(
                project_id=project.id, created_by=user.id, artifact_type="target_structure",
                filename="1ABC.pdb", content_type="chemical/x-pdb", object_key="test/1ABC.pdb",
                size_bytes=4, checksum_sha256="a" * 64, status="available", lineage=lineage,
            )
            session.add(artifact)
            session.commit()
            session.expire_all()

            context = ResearchContextService(session, project)
            item = context.search_research("1ABC", allowed_kinds={"structure"})[0]
            citation = context.citation_for_item(item)
            assert item["data"]["name"] == {
                "zh": "复合物结构", "en": "Reviewed complex structure", "default": "复合物结构",
            }
            assert item["data"]["role"] == {"zh": "靶标", "en": "Target", "default": "靶标"}
            assert citation["label"] == "复合物结构"
            assert citation["entity_id"] == str(artifact.id)
            assert citation["workspace_type"] == "structure"
            assert citation["url"] == "https://www.rcsb.org/structure/1ABC"
            assert artifact.lineage == lineage
    finally:
        drop_all(engine, Base.metadata)


@pytest.mark.parametrize(("has_primary", "candidate_count"), [(True, 0), (False, 1), (False, 0)])
def test_overview_distinguishes_primary_target_from_candidate_count(has_primary, candidate_count) -> None:
    engine = enforce_foreign_keys(create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    ))
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user = User(username="scope-owner", display_name="Owner", role="admin", enabled=True)
            organization = Organization(name="Scope Org")
            session.add_all([user, organization])
            session.flush()
            project = Project(organization_id=organization.id, owner_id=user.id,
                              name="Scope project", project_type="protein_design")
            session.add(project)
            session.flush()
            if has_primary:
                target = Target(project_id=project.id, name="Confirmed target", identity_status="confirmed")
                session.add(target)
                session.flush()
                project.primary_target_id = target.id
            for index in range(candidate_count):
                session.add(Candidate(project_id=project.id, candidate_key=f"target-{index}", name="Research target",
                                      candidate_kind="research_target"))
            session.add(Candidate(project_id=project.id, candidate_key="design", name="Binder design"))
            session.flush()

            result = ResearchContextService(session, project).research_overview()

            assert result["primary_target_present"] is has_primary
            assert (result["project"]["primary_target"] is not None) is has_primary
            assert result["counts"]["research_targets"] == candidate_count
            assert "Candidate records" in result["counts_scope"]["research_targets"]
            assert "primary_target" in result["counts_scope"]["research_targets"]
    finally:
        drop_all(engine, Base.metadata)


def test_seeded_boilerplate_is_not_rendered_as_a_review_finding() -> None:
    rows = [
        finding(
            finding_type="meaning_application",
            title="Project significance and application",
            content=next(iter(workspace.BOILERPLATE_FINDING_CONTENT)),
        ),
        finding(
            finding_type="meaning_application",
            title="Project-specific significance",
            content="This finding contains project-specific evidence.",
        ),
    ]

    sections = workspace._review_sections(rows)

    assert len(sections) == 1
    assert [item.content.default for item in sections[0].items] == [
        "This finding contains project-specific evidence."
    ]


def test_confirmed_findings_read_before_unsettled_ones_in_a_track() -> None:
    rows = [
        finding(
            finding_type="design_strategy",
            title="Still being argued",
            content="Pending claim.",
            evidence={"review_status": "pending_review"},
        ),
        finding(
            finding_type="design_strategy",
            title="No status at all",
            content="Unmarked claim.",
        ),
        finding(
            finding_type="design_strategy",
            title="Settled by a reviewer",
            content="Accepted claim.",
            evidence={"review_status": "accepted"},
        ),
        finding(
            finding_type="design_strategy",
            title="Corrected on a person's instruction",
            content="Corrected claim.",
            evidence={"review_status": "human_directed_correction"},
        ),
    ]

    items = workspace._review_sections(rows)[0].items

    # Both settled rows first, in the order they were written; neither unsettled row
    # is promoted above them, and the two tiers stay chronological inside themselves.
    assert [item.title.default for item in items] == [
        "Settled by a reviewer",
        "Corrected on a person's instruction",
        "Still being argued",
        "No status at all",
    ]


def test_accepted_review_outranks_a_newer_draft_status_note() -> None:
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user = User(username="brief-owner", display_name="Brief Owner", role="admin", enabled=True)
            organization = Organization(name="Brief Org")
            session.add_all([user, organization])
            session.flush()
            reviewed = Project(
                organization_id=organization.id, owner_id=user.id,
                name="Reviewed project", project_type="research",
            )
            drafts_only = Project(
                organization_id=organization.id, owner_id=user.id,
                name="Drafts only", project_type="research",
            )
            session.add_all([reviewed, drafts_only])
            session.flush()
            opened = datetime(2026, 9, 1, tzinfo=UTC)
            session.add_all([
                ResearchBrief(
                    project_id=reviewed.id, created_by=user.id, title="Accepted review",
                    content="# Project Review", status="accepted", created_at=opened,
                ),
                ResearchBrief(
                    project_id=reviewed.id, created_by=user.id, title="Latest progress note",
                    content="本轮状态：报告所列本步完成。", status="draft",
                    created_at=opened + timedelta(days=13),
                ),
                ResearchBrief(
                    project_id=drafts_only.id, created_by=user.id, title="Older draft",
                    content="First import.", status="draft", created_at=opened,
                ),
                ResearchBrief(
                    project_id=drafts_only.id, created_by=user.id, title="Newer draft",
                    content="Second import.", status="draft",
                    created_at=opened + timedelta(days=2),
                ),
            ])
            session.commit()

            # The accepted review wins even though a draft note is twelve days newer.
            chosen = workspace.preferred_review_brief(session, reviewed.id)
            assert chosen is not None and chosen.title == "Accepted review"

            # With nothing accepted, the newest draft is still shown rather than nothing.
            fallback = workspace.preferred_review_brief(session, drafts_only.id)
            assert fallback is not None and fallback.title == "Newer draft"
    finally:
        drop_all(engine, Base.metadata)


def test_a_reviewed_seed_stub_does_not_displace_a_newer_note() -> None:
    """`reviewed` marks the seeding shells, so it must not outrank a real note.

    A project seeded with a short placeholder `reviewed` brief can hold its actual
    content in a later draft. Giving `reviewed` precedence shows the placeholder and hides
    the note, which is why only `accepted` ranks.
    """
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user = User(username="stub-owner", display_name="Stub Owner", role="admin", enabled=True)
            organization = Organization(name="Stub Org")
            session.add_all([user, organization])
            session.flush()
            project = Project(
                organization_id=organization.id, owner_id=user.id,
                name="Seeded project", project_type="research",
            )
            session.add(project)
            session.flush()
            opened = datetime(2026, 7, 5, tzinfo=UTC)
            session.add_all([
                ResearchBrief(
                    project_id=project.id, created_by=user.id,
                    title="Scaffold repair research review",
                    content="A seeded shell with no project content.",
                    status="reviewed", created_at=opened,
                ),
                ResearchBrief(
                    project_id=project.id, created_by=user.id,
                    title="2026-09-12 下一步执行",
                    content="The note that actually describes where the project stands." * 8,
                    status="draft", created_at=opened + timedelta(days=69),
                ),
            ])
            session.commit()

            chosen = workspace.preferred_review_brief(session, project.id)
            assert chosen is not None and chosen.title == "2026-09-12 下一步执行"
    finally:
        drop_all(engine, Base.metadata)


def test_briefs_sharing_a_timestamp_resolve_to_one_stable_choice() -> None:
    """A tie must not leave the displayed review up to the database's row order."""
    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user = User(username="tie-owner", display_name="Tie Owner", role="admin", enabled=True)
            organization = Organization(name="Tie Org")
            session.add_all([user, organization])
            session.flush()
            project = Project(
                organization_id=organization.id, owner_id=user.id,
                name="Tied project", project_type="research",
            )
            session.add(project)
            session.flush()
            same_moment = datetime(2026, 7, 25, tzinfo=UTC)
            first = ResearchBrief(
                project_id=project.id, created_by=user.id, title="Duplicate review A",
                content="# Project Review", status="accepted", created_at=same_moment,
            )
            second = ResearchBrief(
                project_id=project.id, created_by=user.id, title="Duplicate review B",
                content="# Project Review", status="accepted", created_at=same_moment,
            )
            session.add_all([first, second])
            session.commit()

            picked = {
                workspace.preferred_review_brief(session, project.id).id for _ in range(5)
            }
            assert picked == {max(first.id, second.id)}
    finally:
        drop_all(engine, Base.metadata)


def test_the_project_summary_shows_the_same_brief_as_the_research_page() -> None:
    """Two endpoints must not disagree about which brief is the project's brief.

    The literature panel reads `brief.scope.source_material` from the project research
    summary and project search indexes its title and content, so a summary that returned
    the newest status note fed both of those from the wrong row.
    """
    from backend_v2.app.projects.service import project_research_summary

    engine = enforce_foreign_keys(
        create_engine(
            "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    )
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(engine, expire_on_commit=False)() as session:
            user = User(username="sum-owner", display_name="Sum Owner", role="admin", enabled=True)
            organization = Organization(name="Sum Org")
            session.add_all([user, organization])
            session.flush()
            project = Project(
                organization_id=organization.id, owner_id=user.id,
                name="Summarized project", project_type="research",
            )
            session.add(project)
            session.flush()
            opened = datetime(2026, 9, 1, tzinfo=UTC)
            session.add_all([
                ResearchBrief(
                    project_id=project.id, created_by=user.id, title="Accepted review",
                    content="# Project Review", status="accepted", created_at=opened,
                    scope={"source_material": [{"id": "S1"}]},
                ),
                ResearchBrief(
                    project_id=project.id, created_by=user.id, title="Latest status note",
                    content="Round status.", status="draft",
                    created_at=opened + timedelta(days=13),
                    scope={"portfolio_review_key": "review-round-1"},
                ),
            ])
            session.commit()

            summary = project_research_summary(session, project)

            assert summary.brief is not None
            assert summary.brief["title"] == "Accepted review"
            # The field the literature panel actually reads survives the change.
            assert summary.brief["scope"]["source_material"] == [{"id": "S1"}]
    finally:
        drop_all(engine, Base.metadata)
