"""Patent records: the misreadings a landscape is most prone to.

The fixture below is the shape Europe PMC actually returns for a patent record
(taken from a live `SRC:PAT` search, trimmed). The tests are about the ways a
patent summary goes wrong while looking right: an application read as a grant,
a PCT publication read as protection, the applicant confused with the
inventors, a term stated as fact, and a landscape handed over without its
limits.
"""

from __future__ import annotations

from datetime import date

import pytest
from backend_v2.app.literature import patents

WO_RECORD = {
    "id": "WO2011110621",
    "source": "PAT",
    "title": "BIOLOGICAL PRODUCTS: HUMANISED AGONISTIC ANTI-PD-1 ANTIBODIES",
    "authorString": "TYSON KERRY LOUISE.",
    "affiliation": "UCB PHARMA SA",
    "firstPublicationDate": "2011-03-10",
    "patentDetails": {
        "countryCode": "WO",
        "typeCode": "A1",
        "typeDescription": "Publ.of the Int.Appl. with Int.search report",
        "classifierList": {
            "classifier": [
                {"classification": "C07K16/28A18", "classificationType": "EPO"},
                {"classification": "C07K16/28", "classificationType": "IPC"},
                {"classification": "C12N15/13", "classificationType": "IPC"},
            ]
        },
        "application": {"applicationNumber": "WO2011EP53597", "applicationDate": "2011-03-10"},
        "priorityList": {"priority": [{"priorityNumber": "US20100312702P", "priorityDate": "2010-03-11"}]},
    },
}

# One priority returned as an object, not a list - Europe PMC does both.
CN_RECORD = {
    "id": "CN101818129",
    "source": "PAT",
    "title": "Hybridoma cell line",
    "authorString": "LI MING.",
    "affiliation": "TIANJIN INSPECTION CENTER",
    "patentDetails": {
        "countryCode": "CN",
        "typeCode": "B",
        "application": {"applicationNumber": "CN2010123", "applicationDate": "2010-04-01"},
        "priorityList": {"priority": {"priorityNumber": "CN2010123", "priorityDate": "2010-04-01"}},
        "classifierList": {"classifier": {"classification": "C12N5/20", "classificationType": "IPC"}},
    },
}


def test_a_record_is_read_with_its_office_stage_and_classes() -> None:
    details = patents.patent_details(WO_RECORD)

    assert details["publication_number"] == "WO2011110621"
    assert details["country_code"] == "WO"
    assert details["ipc"] == ["C07K16/28", "C12N15/13"]
    assert details["cpc"] == ["C07K16/28A18"]
    assert details["earliest_priority_date"] == "2010-03-11"
    assert details["url"].endswith("pn%3DWO2011110621")


def test_the_applicant_and_the_inventors_are_not_confused() -> None:
    """Who holds the rights is not who made the invention."""
    details = patents.patent_details(WO_RECORD)

    assert details["applicant"] == "UCB PHARMA SA"
    assert details["inventors"] == "TYSON KERRY LOUISE"


def test_a_single_object_where_a_list_was_expected_is_still_read() -> None:
    details = patents.patent_details(CN_RECORD)

    assert details["priority"] == [{"number": "CN2010123", "date": "2010-04-01"}]
    assert details["ipc"] == ["C12N5/20"]


@pytest.mark.parametrize(
    ("country", "kind", "stage"),
    [
        ("WO", "A1", "pct_application"),  # never a grant
        ("CN", "A", "application"),
        ("CN", "B", "granted"),
        ("CN", "U", "utility_model"),
        ("US", "A1", "application"),
        ("US", "B2", "granted"),
        ("US", "A", "granted"),  # pre-2001 USPTO grants
        ("US", "S1", "design"),
        ("EP", "A1", "application"),
        ("EP", "B1", "granted"),
        ("JP", None, "unknown"),
    ],
)
def test_publication_stage_follows_the_office_and_kind_code(country, kind, stage) -> None:
    assert patents.publication_stage(country, kind) == stage


def test_a_query_is_restricted_to_patents_and_to_the_offices_asked_for() -> None:
    query = patents.patent_query('"PD-1" AND antibody', ["cn", "US", "CN"])

    assert query == 'SRC:PAT AND ("PD-1" AND antibody) AND (EXT_ID:CN* OR EXT_ID:US*)'


def test_an_unknown_office_is_refused_rather_than_silently_dropped() -> None:
    """Dropping it would record a search narrower than the one requested."""
    with pytest.raises(patents.PatentQueryError) as error:
        patents.patent_query("antibody", ["XX"])

    assert "XX" in str(error.value)


def test_an_empty_topic_is_refused() -> None:
    with pytest.raises(patents.PatentQueryError):
        patents.patent_query("   ")


def test_the_landscape_counts_by_office_and_stage() -> None:
    rows = [patents.patent_details(WO_RECORD), patents.patent_details(CN_RECORD)]

    result = patents.landscape(rows, today=date(2026, 9, 15))

    assert result["publications"] == 2
    assert {entry["code"] for entry in result["by_jurisdiction"]} == {"WO", "CN"}
    assert result["by_stage"] == {"granted": 1, "pct_application": 1}
    # C12N appears in both records, C07K in one: subclass counts are per class
    # code, so the shared subclass leads.
    assert result["top_ipc_subclasses"] == [
        {"subclass": "C12N", "count": 2},
        {"subclass": "C07K", "count": 1},
    ]


def test_the_term_is_an_estimate_relative_to_a_stated_date() -> None:
    rows = [patents.patent_details(WO_RECORD), patents.patent_details(CN_RECORD)]

    before = patents.landscape(rows, today=date(2029, 1, 1))["estimated_term"]
    after = patents.landscape(rows, today=date(2031, 6, 1))["estimated_term"]

    assert before["within_estimated_term"] == 2
    assert after["past_estimated_term"] == 2
    assert "2031-06-01" in after["basis"]


def test_the_landscape_never_arrives_without_its_limits() -> None:
    """A count of publications read as a statement about protection is the failure."""
    result = patents.landscape([patents.patent_details(WO_RECORD)], today=date(2026, 9, 15))

    text = " ".join(result["limits"])
    assert "Legal status is not verified" in text
    assert "not a freedom-to-operate" in text
    assert "has not been shown not to exist" in text


def test_only_patent_rows_are_recognised_as_patents() -> None:
    assert patents.is_patent_row(WO_RECORD)
    assert not patents.is_patent_row({"id": "12345", "source": "MED"})


def test_search_results_carry_patent_details_only_for_patent_hits() -> None:
    """A paper and a patent come back from the same search normaliser."""
    from backend_v2.app.literature.retrieval import europe_pmc_results

    payload = {
        "resultList": {
            "result": [
                WO_RECORD,
                {"id": "38000001", "source": "MED", "pmid": "38000001", "title": "A paper"},
            ]
        }
    }

    results = europe_pmc_results(payload, limit=10)

    assert results[0]["patent"]["publication_number"] == "WO2011110621"
    assert results[0]["patent"]["stage"] == "pct_application"
    assert results[1]["patent"] is None
