from __future__ import annotations

import httpx
from backend_v2.scripts.backfill_review_references import _metadata


def test_doi_source_metadata_is_enriched_from_crossref() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": {
                    "DOI": "10.1000/example",
                    "title": ["A complete reference"],
                    "author": [
                        {"given": "Ada", "family": "Author"},
                        {"given": "Ben", "family": "Writer"},
                    ],
                    "container-title": ["Journal of Evidence"],
                    "published-online": {"date-parts": [[2025, 6, 30]]},
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    metadata = _metadata(
        client,
        {
            "key": "doi:10.1000/example",
            "doi": "10.1000/example",
        },
    )

    assert str(requests[0].url).endswith("/works/10.1000%2Fexample")
    assert metadata == {
        "title": "A complete reference",
        "authors": "Ada Author; Ben Writer",
        "journal": "Journal of Evidence",
        "year": "2025",
        "doi": "10.1000/example",
        "url": "https://doi.org/10.1000/example",
    }


def test_blocked_mdpi_source_is_resolved_through_an_exact_crossref_match() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.3390/bios13110960",
                            "title": ["A traceable MDPI article"],
                            "author": [{"given": "Ada", "family": "Author"}],
                            "container-title": ["Biosensors"],
                            "published-online": {"date-parts": [[2023, 11, 1]]},
                            "ISSN": ["2079-6374"],
                            "volume": "13",
                            "issue": "11",
                            "article-number": "960",
                        }
                    ]
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    metadata = _metadata(
        client,
        {
            "key": "url:https://www.mdpi.com/2079-6374/13/11/960",
            "url": "https://www.mdpi.com/2079-6374/13/11/960",
        },
    )

    assert len(requests) == 1
    assert requests[0].url.host == "api.crossref.org"
    assert metadata == {
        "title": "A traceable MDPI article",
        "authors": "Ada Author",
        "journal": "Biosensors",
        "year": "2023",
        "doi": "10.3390/bios13110960",
        "url": "https://doi.org/10.3390/bios13110960",
    }


def test_mdpi_crossref_fallback_rejects_a_nonmatching_article() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.3390/bios13110961",
                            "title": ["The wrong article"],
                            "ISSN": ["2079-6374"],
                            "volume": "13",
                            "issue": "11",
                            "article-number": "961",
                        }
                    ]
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    metadata = _metadata(
        client,
        {
            "key": "url:https://www.mdpi.com/2079-6374/13/11/960",
            "url": "https://www.mdpi.com/2079-6374/13/11/960",
        },
    )

    # No exact Crossref match means the script attempts the original page;
    # the mock response has no citation meta and therefore adds nothing.
    assert metadata == {}
