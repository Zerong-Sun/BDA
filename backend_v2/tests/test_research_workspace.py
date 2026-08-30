from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from backend_v2.app.research import workspace


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
