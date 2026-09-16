"""EPO OPS records and legal events: the misreadings this data invites.

The fixtures are real OPS 3.2 JSON - a CN search record, and the EP 1537878
family (Ono/Honjo, anti-PD-1) with its INPADOC legal events - fetched on
2026-09-15 and trimmed to the members and events the tests need.

What goes wrong while looking right: an OPS record counted differently from a
Europe PMC one, a patent's events looked for on the publication instead of the
application, one country's lapse read as the patent's, a kind code one index
spells differently treated as a different publication, and a publication
number placed into a URL path unchecked.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from backend_v2.app.literature import epo_ops, patents
from backend_v2.app.literature.epo_ops import PublicationRef
from backend_v2.app.literature.patents import PatentQueryError
from backend_v2.app.literature.schemas import LiteratureSearchCreate
from backend_v2.tests.test_literature_patents import WO_RECORD
from pydantic import ValidationError

CN_SEARCH_DOC: dict[str, Any] = {"@system": "ops.epo.org", "@family-id": "100642550", "@country": "CN", "@doc-number": "122461492", "@kind": "A", "bibliographic-data": {"publication-reference": {"document-id": [{"@document-id-type": "docdb", "country": {"$": "CN"}, "doc-number": {"$": "122461492"}, "kind": {"$": "A"}, "date": {"$": "20260728"}}, {"@document-id-type": "epodoc", "doc-number": {"$": "CN122461492"}, "date": {"$": "20260728"}}]}, "classifications-ipcr": {"classification-ipcr": [{"@sequence": "1", "text": {"$": "A61K  31/   506            A I"}}, {"@sequence": "2", "text": {"$": "A61K  38/    16            A I"}}]}, "patent-classifications": {}, "application-reference": {"@doc-id": "653338306", "document-id": [{"@document-id-type": "docdb", "country": {"$": "CN"}, "doc-number": {"$": "202610690957"}, "kind": {"$": "A"}, "date": {"$": "20260519"}}, {"@document-id-type": "epodoc", "doc-number": {"$": "CN202610690957"}, "date": {"$": "20260519"}}, {"@document-id-type": "original", "doc-number": {"$": "202610690957.6"}}]}, "priority-claims": {"priority-claim": {"@sequence": "1", "@kind": "national", "document-id": [{"@document-id-type": "docdb", "country": {"$": "CN"}, "doc-number": {"$": "202610690957"}, "kind": {"$": "A"}, "date": {"$": "20260519"}}, {"@document-id-type": "epodoc", "doc-number": {"$": "CN202610690957"}, "date": {"$": "20260519"}}]}}, "parties": {"applicants": {"applicant": [{"@sequence": "1", "@data-format": "epodoc", "applicant-name": {"name": {"$": "SHANDONG UNIV"}}}, {"@sequence": "1", "@data-format": "original", "applicant-name": {"name": {"$": "山东大学"}}}]}, "inventors": {"inventor": [{"@sequence": "1", "@data-format": "epodoc", "inventor-name": {"name": {"$": "TAN HAINING"}}}, {"@sequence": "2", "@data-format": "epodoc", "inventor-name": {"name": {"$": "DI YUHAN"}}}, {"@sequence": "1", "@data-format": "original", "inventor-name": {"name": {"$": "谭海宁"}}}]}}, "invention-title": [{"$": "Preparation method and application of double immune checkpoint inhibitor modified glycosyl nanoparticles", "@lang": "en"}, {"$": "双免疫检查点抑制剂修饰糖基纳米粒的制备方法与应用", "@lang": "ol"}]}, "abstract": [{"@lang": "en", "p": {"$": "The invention discloses a preparation method and application of double immune checkpoint i"}}, {"@lang": "ol", "p": {"$": "[0001]    本发明公开了双免疫检查点抑制剂修饰糖基纳米粒的制备方法与应用"}}]}  # noqa: E501

FAMILY_LEGAL: dict[str, Any] = {"ops:world-patent-data": {"ops:patent-family": {"@legal": "true", "@total-result-count": "65", "ops:family-member": [{"@family-id": "30117379", "publication-reference": {"document-id": [{"@document-id-type": "docdb", "country": {"$": "EP"}, "doc-number": {"$": "1537878"}, "kind": {"$": "A1"}, "date": {"$": "20050608"}}, {"@document-id-type": "epodoc", "doc-number": {"$": "EP1537878"}, "date": {"$": "20050608"}}]}, "application-reference": {"@doc-id": "16054118", "@is-representative": "YES", "document-id": {"@document-id-type": "docdb", "country": {"$": "EP"}, "doc-number": {"$": "03741154"}, "kind": {"$": "A"}, "date": {"$": "20030702"}}}, "ops:legal": [{"@code": "17P ", "@desc": "REQUEST FOR EXAMINATION FILED", "@infl": "+", "ops:L001EP": {"$": "EP", "@desc": "Country Code"}, "ops:L003EP": {"$": "03741154", "@desc": "Document Number"}, "ops:L004EP": {"$": "A", "@desc": "Kind Code"}, "ops:L007EP": {"$": "2005-06-08", "@desc": "Gazette DATE"}, "ops:L008EP": {"$": "17P", "@desc": "Legal Event Code 1"}, "ops:L500EP": {"ops:L525EP": {"$": "20050103", "@desc": "Effective DATE"}}}, {"@code": "26  ", "@desc": "OPPOSITION FILED", "@infl": "-", "ops:L001EP": {"$": "EP", "@desc": "Country Code"}, "ops:L003EP": {"$": "03741154", "@desc": "Document Number"}, "ops:L004EP": {"$": "A", "@desc": "Kind Code"}, "ops:L007EP": {"$": "2011-07-27", "@desc": "Gazette DATE"}, "ops:L008EP": {"$": "26", "@desc": "Legal Event Code 1"}, "ops:L500EP": {"ops:L519EP": {"$": "MERCK & CO.", "@desc": "OPPONENT"}, "ops:L525EP": {"$": "20110620", "@desc": "Effective DATE"}}}, {"@code": "27O ", "@desc": "OPPOSITION REJECTED", "@infl": "+", "ops:L001EP": {"$": "EP", "@desc": "Country Code"}, "ops:L003EP": {"$": "03741154", "@desc": "Document Number"}, "ops:L004EP": {"$": "A", "@desc": "Kind Code"}, "ops:L007EP": {"$": "2018-01-17", "@desc": "Gazette DATE"}, "ops:L008EP": {"$": "27O", "@desc": "Legal Event Code 1"}, "ops:L500EP": {"ops:L525EP": {"$": "20170126", "@desc": "Effective DATE"}}}, {"@code": "PGFP", "@desc": "ANNUAL FEE PAID TO NATIONAL OFFICE  [ANNOUNCED VIA POSTGRANT INFORMATION FROM NATIONAL OFFICE TO EPO]", "@infl": "+", "ops:L001EP": {"$": "EP", "@desc": "Country Code"}, "ops:L003EP": {"$": "03741154", "@desc": "Document Number"}, "ops:L004EP": {"$": "A", "@desc": "Kind Code"}, "ops:L007EP": {"$": "2022-10-31", "@desc": "Gazette DATE"}, "ops:L008EP": {"$": "PGFP", "@desc": "Legal Event Code 1"}, "ops:L500EP": {"ops:L501EP": {"$": "DE", "@desc": "Ref Country Code"}, "ops:L518EP": {"$": "20220531", "@desc": "Payment DATE"}, "ops:L520EP": {"$": "20", "@desc": "Year of Fee Payment"}}}, {"@code": "REG ", "@desc": "REFERENCE TO A NATIONAL CODE", "@infl": " ", "ops:L001EP": {"$": "EP", "@desc": "Country Code"}, "ops:L003EP": {"$": "03741154", "@desc": "Document Number"}, "ops:L004EP": {"$": "A", "@desc": "Kind Code"}, "ops:L007EP": {"$": "2011-06-01", "@desc": "Gazette DATE"}, "ops:L008EP": {"$": "REG", "@desc": "Legal Event Code 1"}, "ops:L500EP": {"ops:L501EP": {"$": "DE", "@desc": "Ref Country Code"}, "ops:L502EP": {"$": "8328", "@desc": "Ref Legal Event Code", "@descData": "CHANGE IN THE PERSON/NAME/ADDRESS OF THE AGENT", "@infl": " "}, "ops:L503EP": {"$": "60334303", "@desc": "Ref Document Number"}, "ops:L504EP": {"$": "DE", "@desc": "Country of Ref Document"}, "ops:L517EP": {"$": "GRUENECKER, KINKELDEY, STOCKMAIR & SCHWANHAEUSSER,", "@desc": "REPRESENTATIVE"}}}]}, {"@family-id": "30117379", "publication-reference": {"document-id": [{"@document-id-type": "docdb", "country": {"$": "EP"}, "doc-number": {"$": "1537878"}, "kind": {"$": "B1"}, "date": {"$": "20100922"}}, {"@document-id-type": "epodoc", "doc-number": {"$": "EP1537878"}, "date": {"$": "20100922"}}]}, "application-reference": {"@doc-id": "16054118", "@is-representative": "YES", "document-id": {"@document-id-type": "docdb", "country": {"$": "EP"}, "doc-number": {"$": "03741154"}, "kind": {"$": "A"}, "date": {"$": "20030702"}}}}, {"@family-id": "30117379", "publication-reference": {"document-id": [{"@document-id-type": "docdb", "country": {"$": "US"}, "doc-number": {"$": "7595048"}, "kind": {"$": "B2"}, "date": {"$": "20090929"}}, {"@document-id-type": "epodoc", "doc-number": {"$": "US7595048"}, "date": {"$": "20090929"}}]}, "application-reference": {"@doc-id": "51521568", "document-id": {"@document-id-type": "docdb", "country": {"$": "US"}, "doc-number": {"$": "51992505"}, "kind": {"$": "A"}, "date": {"$": "20050103"}}}}]}}}  # noqa: E501


def _search_payload(*documents: dict[str, Any]) -> dict[str, Any]:
    return {
        "ops:world-patent-data": {
            "ops:biblio-search": {
                "@total-result-count": "3191",
                "ops:search-result": {"exchange-documents": [{"exchange-document": item} for item in documents]},
            }
        }
    }


def test_an_ops_record_is_read_under_the_keys_a_europe_pmc_record_uses() -> None:
    """One shape for both indexes, so a record does not count differently by where it was found."""
    results = epo_ops.search_results(_search_payload(CN_SEARCH_DOC), limit=10)

    assert len(results) == 1
    result = results[0]
    assert result["source"] == "epo_ops"
    # With the kind: an application and its grant are two publications.
    assert result["external_id"] == "CN122461492A"
    assert result["title"].startswith("Preparation method and application")
    assert result["abstract"].startswith("The invention discloses"), "English is preferred over the original"
    patent = result["patent"]
    assert set(patents.patent_details(WO_RECORD)) <= set(patent)
    assert patent["publication_number"] == "CN122461492"
    assert patent["kind_code"] == "A"
    assert patent["stage"] == "application"
    assert patent["family_id"] == "100642550"
    # The normalised name, so one applicant is one row across offices.
    assert patent["applicant"] == "SHANDONG UNIV"
    assert patent["inventors"] == "TAN HAINING; DI YUHAN"
    assert patent["application_number"] == "CN202610690957"
    assert patent["application_date"] == "2026-05-19"
    assert patent["earliest_priority_date"] == "2026-05-19"
    assert patent["publication_date"] == "2026-07-28"
    assert patent["ipc"] == ["A61K31/506", "A61K38/16"]
    assert epo_ops.search_total(_search_payload(CN_SEARCH_DOC)) == 3191


def test_a_record_ops_could_not_serve_is_skipped_not_saved_empty() -> None:
    untitled = copy.deepcopy(CN_SEARCH_DOC)
    untitled["bibliographic-data"].pop("invention-title")
    payload = _search_payload({"@status": "not found", "@country": "EP", "@doc-number": "1"}, untitled)
    payload["ops:world-patent-data"]["ops:biblio-search"]["ops:search-result"]["exchange-documents"].append("junk")

    assert epo_ops.search_results(payload, limit=10) == []
    assert epo_ops.search_total({}) is None


def test_an_office_that_supplied_no_english_keeps_its_own_language() -> None:
    record = copy.deepcopy(CN_SEARCH_DOC)
    record["bibliographic-data"]["invention-title"] = {"$": "双免疫检查点抑制剂", "@lang": "ol"}
    record["abstract"] = {"@lang": "ol", "p": [{"$": "第一段"}, {"$": "第二段"}]}
    record["bibliographic-data"]["parties"]["applicants"]["applicant"] = {
        "@data-format": "original",
        "applicant-name": {"name": {"$": "山东大学"}},
    }

    result = epo_ops.search_results(_search_payload(record), limit=1)[0]

    assert result["title"] == "双免疫检查点抑制剂"
    assert result["abstract"] == "第一段 第二段"
    assert result["patent"]["applicant"] == "山东大学"


def test_cpc_classes_are_assembled_from_their_parts_and_other_schemes_ignored() -> None:
    record = copy.deepcopy(CN_SEARCH_DOC)
    part = {"section": {"$": "A"}, "class": {"$": "61"}, "subclass": {"$": "K"}}
    record["bibliographic-data"]["patent-classifications"] = {
        "patent-classification": [
            {"classification-scheme": {"@scheme": "CPCI"}, **part, "main-group": {"$": "39"}, "subgroup": {"$": "39591"}},
            {"classification-scheme": {"@scheme": "FI"}, **part, "main-group": {"$": "1"}, "subgroup": {"$": "2"}},
            {"classification-scheme": {"@scheme": "CPCI"}, **part},
            "junk",
        ]
    }
    record["bibliographic-data"]["classification-ipc"] = {"text": {"$": "A61K6/027"}}

    patent = epo_ops.exchange_document_details(record)

    assert patent["cpc"] == ["A61K39/39591"]
    assert "A61K6/027" in patent["ipc"]


@pytest.mark.parametrize(
    ("topic", "jurisdictions", "expected"),
    [
        ("PD-1 antibody", (), 'ta all "PD-1 antibody"'),
        # Europe PMC syntax handed to OPS: the boolean word would be a search term.
        ('"PD-1" AND (antibody)', (), 'ta all "PD-1 antibody"'),
        # CQL somebody wrote is recorded as written.
        ('ta="PD-1" and pa=merck', (), 'ta="PD-1" and pa=merck'),
        ("PD-1 antibody", ("cn", "US", "CN"), '(ta all "PD-1 antibody") and (pn=CN or pn=US)'),
    ],
)
def test_a_topic_becomes_cql_with_offices_applied_after_it(
    topic: str, jurisdictions: tuple[str, ...], expected: str
) -> None:
    assert epo_ops.cql_query(topic, jurisdictions) == expected


@pytest.mark.parametrize(
    ("topic", "jurisdictions"),
    [
        ("   ", ()),
        ("AND OR", ()),
        ("PD-1", ("DE",)),
        ("x" * 600, ()),
        # OPS answers 400 to these; refusing here costs no request from the quota.
        ('ta all "programmed death 1" and ta all antibody', ()),
        ("ta any pd1", ()),
    ],
)
def test_a_query_that_cannot_be_a_search_is_refused(topic: str, jurisdictions: tuple[str, ...]) -> None:
    with pytest.raises(PatentQueryError):
        epo_ops.cql_query(topic, jurisdictions)


@pytest.mark.parametrize(
    ("number", "kind", "docdb"),
    [
        ("EP1537878B1", None, "EP.1537878.B1"),
        ("EP1537878", "B1", "EP.1537878.B1"),
        ("EP1537878B1", "b1", "EP.1537878.B1"),
        ("WO2011110621", "A1", "WO.2011110621.A1"),
        ("CN101818129", "B", "CN.101818129.B"),
        ("US 7595048", "B2", "US.7595048.B2"),
        ("JPWO2004004771A1", None, "JP.WO2004004771.A1"),
        ("ATE481985T1", None, "AT.E481985.T1"),
        ("WO2011110621", None, "WO.2011110621"),
    ],
)
def test_a_saved_publication_number_becomes_the_reference_ops_is_asked_about(
    number: str, kind: str | None, docdb: str
) -> None:
    reference = epo_ops.publication_reference(number, kind)

    assert reference.docdb == docdb
    assert reference.publication_number == docdb.split(".")[0] + docdb.split(".")[1]


@pytest.mark.parametrize(
    ("number", "kind"),
    [("", None), ("1537878", None), ("EP1537878;DROP", None), ("EP%2F1537878", None), ("EP1537878", "B12"), ("EP" + "1" * 30, None)],
)
def test_anything_that_is_not_a_publication_number_is_refused_before_it_reaches_a_url(
    number: str, kind: str | None
) -> None:
    with pytest.raises(PatentQueryError):
        epo_ops.publication_reference(number, kind)


def test_a_grants_events_are_found_through_its_application_not_its_publication() -> None:
    """EP 1537878 B1 carries no events in OPS; they hang off the A1 member of the same application."""
    summary = epo_ops.family_legal_summary(FAMILY_LEGAL, PublicationRef("EP", "1537878", "B1"))

    assert summary["matched_publication"] is True
    assert summary["application"] == "EP03741154"
    assert summary["event_count"] == 5
    assert summary["family_id"] == "30117379"
    assert summary["family_publications"] == 3
    assert summary["family_offices"] == {"EP": 2, "US": 1}
    assert {row["publication"] for row in summary["family_members"]} == {"EP1537878A1", "EP1537878B1", "US7595048B2"}
    assert summary["limits"] == list(epo_ops.LEGAL_LIMITS)


def test_another_family_members_events_are_not_attributed_to_a_different_application() -> None:
    summary = epo_ops.family_legal_summary(FAMILY_LEGAL, PublicationRef("US", "7595048", "B2"))

    assert summary["matched_publication"] is True
    assert summary["application"] == "US51992505"
    assert summary["event_count"] == 0 and summary["by_country"] == []


def test_events_are_summarised_per_country_and_never_as_a_verdict_on_the_patent() -> None:
    """A fee paid in Germany and an opposition before the EPO are different facts about different places."""
    summary = epo_ops.family_legal_summary(FAMILY_LEGAL, PublicationRef("EP", "1537878", "B1"))
    countries = {row["country"]: row for row in summary["by_country"]}

    assert set(countries) == {"DE", "EP"}
    assert countries["DE"]["events"] == 2
    assert countries["DE"]["latest_flagged_event"]["code"] == "PGFP"
    assert countries["DE"]["latest_flagged_event"]["gazette_date"] == "2022-10-31"
    # The national code event is newer than nothing flagged, and is kept, but it
    # carries no influence and so is never the flagged event.
    assert countries["DE"]["positive"] == 1 and countries["DE"]["negative"] == 0
    assert countries["EP"]["negative"] == 1
    assert countries["EP"]["latest_flagged_event"]["description"] == "OPPOSITION REJECTED"
    assert countries["EP"]["latest_flagged_event"]["influence"] == "positive"
    # There is no field that states a status, only events.
    assert not {"status", "in_force", "valid", "lapsed", "expired"} & set(summary)
    events = {event["code"]: event for event in summary["events"]}
    assert events["17P"]["effective_date"] == "2005-01-03"
    assert events["26"]["country"] == "EP", "a code padded with spaces is read without them"
    assert events["REG"]["national_code"] == "8328"
    assert events["REG"]["influence"] == "neutral"
    assert [event["gazette_date"] for event in summary["events"]] == sorted(
        event["gazette_date"] for event in summary["events"]
    )


def test_a_kind_code_one_index_spells_differently_is_still_the_same_publication() -> None:
    summary = epo_ops.family_legal_summary(FAMILY_LEGAL, PublicationRef("EP", "1537878", "B"))

    assert summary["matched_publication"] is True
    assert summary["event_count"] == 5


def test_a_publication_outside_the_family_gets_no_events_rather_than_the_familys() -> None:
    summary = epo_ops.family_legal_summary(FAMILY_LEGAL, PublicationRef("EP", "9999999", "B1"))

    assert summary["matched_publication"] is False
    assert summary["application"] is None
    assert summary["events"] == [] and summary["family_publications"] == 3

    empty = epo_ops.family_legal_summary({}, PublicationRef("EP", "1537878", "B1"))
    assert empty["matched_publication"] is False and empty["family_id"] is None


def test_events_repeated_on_two_members_of_one_application_are_counted_once() -> None:
    payload = copy.deepcopy(FAMILY_LEGAL)
    members = payload["ops:world-patent-data"]["ops:patent-family"]["ops:family-member"]
    members[1]["ops:legal"] = copy.deepcopy(members[0]["ops:legal"]) + [None, {"@code": "  "}]

    summary = epo_ops.family_legal_summary(payload, PublicationRef("EP", "1537878", "B1"))

    assert summary["event_count"] == 5


def test_a_long_history_is_listed_in_part_and_counted_in_full() -> None:
    payload = copy.deepcopy(FAMILY_LEGAL)
    member = payload["ops:world-patent-data"]["ops:patent-family"]["ops:family-member"][0]
    member["ops:legal"] = [
        {"@code": "PGFP", "@infl": "+", "ops:L007EP": {"$": f"20{10 + index // 12:02d}-{index % 12 + 1:02d}-01"},
         "ops:L500EP": {"ops:L501EP": {"$": "FR"}, "ops:L520EP": {"$": str(index)}}, "ops:L001EP": {"$": "EP"},
         "@desc": f"ANNUAL FEE PAID {index}"}
        for index in range(70)
    ]

    summary = epo_ops.family_legal_summary(payload, PublicationRef("EP", "1537878", "B1"))

    assert summary["event_count"] == 70
    assert len(summary["events"]) == epo_ops.MAX_EVENTS_LISTED and summary["events_truncated"] is True
    assert summary["by_country"][0]["events"] == 70


def test_an_event_without_a_code_is_not_an_event() -> None:
    assert epo_ops.legal_event(None) is None
    assert epo_ops.legal_event({"@code": "   "}) is None
    assert epo_ops.legal_event({"@code": "X", "ops:L007EP": {"$": "not-a-date"}})["gazette_date"] is None
    assert epo_ops.legal_event({"@code": "X", "ops:L007EP": {"$": "2023-02-30"}})["gazette_date"] is None


def test_a_patent_search_names_one_source_and_offices_only_restrict_patents() -> None:
    search = LiteratureSearchCreate(query="PD-1 antibody", sources=["epo_ops_patents"], jurisdictions=["CN", "CN", "US"])
    assert search.jurisdictions == ["CN", "US"]

    with pytest.raises(ValidationError, match="exactly one source"):
        LiteratureSearchCreate(query="PD-1 antibody", sources=["europe_pmc", "epo_ops_patents"])
    with pytest.raises(ValidationError, match="restrict a patent search only"):
        LiteratureSearchCreate(query="PD-1 antibody", sources=["europe_pmc"], jurisdictions=["CN"])


def test_an_unquoted_cql_operand_is_refused_with_the_correction() -> None:
    """The message has to say what to write: the model that wrote it reads it."""
    with pytest.raises(PatentQueryError, match=r'write all "antibody"'):
        epo_ops.cql_query('ta all "programmed death 1" and ta all antibody')

    # The quoted form is CQL OPS accepts, and is passed through as written.
    quoted = 'ta all "programmed death 1" and ta all "antibody"'
    assert epo_ops.cql_query(quoted) == quoted


def test_cql_operator_words_inside_a_quoted_operand_are_not_reparsed():
    query = 'ta all "bind all receptors" and pa any "Example Company"'
    assert epo_ops.cql_query(query) == query
