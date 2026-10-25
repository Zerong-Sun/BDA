from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from backend_v2.app.copilot.task_contracts import (
    DELIVERY_SECTIONS,
    build_contract,
    evaluate_delivery,
    evidence_packet_coverage,
)
from backend_v2.app.literature.evidence_packets import anchored_analysis, extract_packet, packet_window

XML = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<title-group><article-title>Source</article-title></title-group></article-meta></front>
<body><sec><title>Results</title><p id="p1">The control measured 0 nM; the sample measured 121.2 nM.</p>
<fig id="f1"><label>Figure 1</label><caption><p>Binding assay.</p></caption><graphic xlink:href="figure1"/></fig>
<table-wrap id="t1"><caption><p>Measured affinity</p></caption><table><tr><th colspan="2">KD</th></tr>
<tr><td>Sample</td><td>121.2 nM</td></tr></table><table-wrap-foot><p>n = 3</p></table-wrap-foot></table-wrap>
<supplementary-material id="s1" xlink:href="https://example.org/source.csv"><label>Data</label></supplementary-material>
</sec></body></article>'''


def analysis(value=0, quote="The control measured 0 nM"):
    return {
        "project_relevance": "Compare the measured control and sample.", "paper_claim": "Reports a binding assay.",
        "arguments": [{"project_argument": "Use a control", "paper_claim": "Reports a control", "relation": "supports",
                       "source_ids": ["p1"], "interpretation": "Check background", "limitations": "One assay"}],
        "data": [{"source_id": "p1", "source_quote": quote, "measure": "KD", "value": value,
                  "unit": "nM", "condition": None, "comparator": None, "n": None, "uncertainty": None}],
        "figure_notes": [], "gaps": [],
    }


def test_extract_preserves_table_headers_footnotes_and_supplement_root_link():
    packet = extract_packet(XML, media_urls=["https://example.org/figure1.jpg"])
    assert packet["passages"][0]["id"] == "p1"
    assert len(packet["passages"]) == 1  # Captions are not duplicated as body evidence.
    assert packet["figures"][0]["assets"][0]["url"] == "https://example.org/figure1.jpg"
    table = packet["tables"][0]
    assert table["rows"][0][0]["header"] and table["rows"][0][0]["colspan"] == "2"
    assert table["footnotes"] == "n = 3"
    assert packet["supplements"][0]["assets"][0]["url"] == "https://example.org/source.csv"
    assert packet["supplements"][0]["content_status"] == "not_read"


def test_zero_is_anchored_without_mutating_source_or_analysis():
    packet = extract_packet(XML)
    draft = analysis()
    before = deepcopy((packet, draft))
    saved = anchored_analysis(packet, draft)
    assert saved["data"][0]["value"] == 0
    assert saved["analysis_status"] == "model_draft_pending_review"
    assert (packet, draft) == before


@pytest.mark.parametrize("reported", ["121.2", "-21.2", "21.2e3", "21.21"])
def test_substring_is_not_a_reported_numeric_value(reported):
    packet = extract_packet(XML)
    quote = f"KD = {reported} nM"
    packet["passages"][0]["text"] = quote
    with pytest.raises(ValueError, match="not_found"):
        anchored_analysis(packet, analysis(21.2, quote))


def test_tables_can_anchor_quantitative_values_and_retractions_cannot_support_claims():
    packet = extract_packet(XML)
    draft = analysis(121.2, "Sample 121.2 nM")
    draft["data"][0]["source_id"] = "t1"
    draft["arguments"][0]["source_ids"] = ["t1"]
    assert anchored_analysis(packet, draft)["data"][0]["anchor_verification"] == "exact_text_and_value_match"
    packet["retracted"] = True
    with pytest.raises(ValueError, match="retracted"):
        anchored_analysis(packet, draft)


def test_reported_timepoint_phrase_can_end_at_sentence_punctuation():
    packet = extract_packet(XML)
    quote = "Treatment was delivered on days 15, 17, and 19."
    packet['passages'][0]['text'] = quote
    draft = analysis('days 15, 17, and 19', quote)
    assert anchored_analysis(packet, draft)['data'][0]['anchor_verification'] == 'exact_text_and_value_match'
    packet['passages'][0]['text'] = quote.replace('19.', '19.5.')
    draft['data'][0]['source_quote'] = packet['passages'][0]['text']
    with pytest.raises(ValueError, match='not_found'):
        anchored_analysis(packet, draft)


@pytest.mark.parametrize("field,value", [
    ("arguments", [None]), ("data", ["invalid"]), ("figure_notes", [None]), ("gaps", [{}]),
])
def test_malformed_model_rows_are_validation_errors(field, value):
    draft = analysis()
    draft[field] = value
    with pytest.raises(ValueError):
        anchored_analysis(extract_packet(XML), draft)


@pytest.mark.parametrize("value", [None, True, float("inf"), [], {}])
def test_non_values_are_rejected(value):
    with pytest.raises(ValueError, match="value_invalid"):
        anchored_analysis(extract_packet(XML), analysis(value))


def test_invalid_root_and_string_anchor_list_are_rejected():
    with pytest.raises(ValueError, match="object_required"):
        anchored_analysis(extract_packet(XML), [])
    draft = analysis()
    draft["arguments"][0]["source_ids"] = "p1"
    with pytest.raises(ValueError, match="anchor_missing"):
        anchored_analysis(extract_packet(XML), draft)


def test_malformed_relation_is_a_validation_error():
    draft = analysis()
    draft["arguments"][0]["relation"] = []
    with pytest.raises(ValueError, match="relation_invalid"):
        anchored_analysis(extract_packet(XML), draft)


def test_packet_windows_preserve_saved_arguments_and_explicit_pagination():
    packet = extract_packet(XML)
    packet["arguments"] = [{"project_argument": "Curated argument"}]
    packet["analysis"] = analysis()
    first = packet_window(packet, "arguments", limit=1)
    assert first["read_window"]["total_count"] == 2 and first["read_window"]["next_offset"] == 1
    second = packet_window(packet, "arguments", offset=1)
    assert second["items"][0]["origin"] == "model_analysis"
    assert not second["read_window"]["has_more"]


def turn(section, offset=0, count=0, total=0, **extra):
    result = {"schema": "literature-evidence-packet-v1", "document_id": "paper", "source_sha256": "a" * 64,
              "document_version": 1, "section": section, "items": [{}] * count, "gaps": [],
              "retrieval_trace_id": "trace", "read_window": {"offset": offset, "returned_count": count, "total_count": total}, **extra}
    return SimpleNamespace(role="tool", content=json.dumps(result), tool_calls=[{"name": "get_reference_evidence_packet", "tool_call_id": section}])


def test_packet_coverage_requires_all_sections_and_never_counts_overlaps_twice():
    turns = [turn("figures", count=1, total=2), turn("figures", count=1, total=2)]
    assert "figures" in evidence_packet_coverage(turns)[0]["missing_sections"]
    turns += [turn("figures", offset=1, count=1, total=2)]
    turns += [turn(name) for name in ("arguments", "tables", "data", "supplements")]
    assert evidence_packet_coverage(turns)[0]["missing_sections"] == []


@pytest.mark.parametrize("extra", [{"read_window": "bad"}, {"section": []}, {"items": 1}, {"gaps": [None]},
                                    {"read_window": {"offset": -1, "returned_count": 1, "total_count": 0}}])
def test_invalid_windows_never_complete_a_section(extra):
    coverage = evidence_packet_coverage([turn(**{"section": "figures", **extra})])
    assert "figures" in coverage[0]["missing_sections"]


def test_large_unread_total_remains_incomplete_without_materializing_the_range():
    assert "figures" in evidence_packet_coverage([turn("figures", total=10**12)])[0]["missing_sections"]


def test_version_two_requires_figure_data_coverage_but_preserves_historical_contract():
    contract = build_contract("literature", [])
    assert contract["version"] == 2
    discovery = SimpleNamespace(role="tool", content="[]", tool_calls=[{"name": "search_research", "tool_call_id": "search"}])
    excerpts = turn("passages", count=1, total=1)
    answer = {"status": "completed", "summary": "Scoped reading", "sections": {k: "Review pending" for k in DELIVERY_SECTIONS["literature"]},
              "missing": [], "evidence_call_ids": ["search", "passages"], "next_action": "Human review"}
    assert evaluate_delivery(SimpleNamespace(task_contract=contract), json.dumps(answer), [discovery, excerpts])["status"] == "partial"
    turns = [discovery, excerpts] + [turn(s) for s in ("arguments", "figures", "tables", "data", "supplements")]
    answer["evidence_call_ids"].extend(["arguments", "figures", "tables", "data", "supplements"])
    assert evaluate_delivery(SimpleNamespace(task_contract=contract), json.dumps(answer), turns)["status"] == "completed"
    old = {**contract, "version": 1, "steps": contract["steps"][:2]}
    answer["evidence_call_ids"] = ["search", "passages"]
    assert evaluate_delivery(SimpleNamespace(task_contract=old), json.dumps(answer), [discovery, excerpts])["status"] == "completed"
