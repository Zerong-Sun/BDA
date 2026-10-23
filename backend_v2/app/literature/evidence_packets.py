"""Lossless source inventory for project-specific literature evidence.

Extraction is not scientific acceptance. Source rows keep their XML anchors;
figures, reported numbers and a reviewed interpretation have separate states.
"""
from __future__ import annotations

import hashlib
import math
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote, urlparse

SCHEMA = "literature-evidence-packet-v1"
XLINK = "{http://www.w3.org/1999/xlink}href"
REPORTED_NUMBER = re.compile(r"[-+−]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:[eE][-+−]?\d+)?")


def text(element: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", " ".join(element.itertext())).strip() if element is not None else ""


def empty_packet(*, source_url: str = "", content_kind: str = "metadata_only") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "created_at": datetime.now(UTC).isoformat(),
        "source_url": source_url, "content_kind": content_kind,
        "analysis_status": "pending_review", "coverage_status": "partial",
        "arguments": [], "figures": [], "tables": [], "supplements": [],
        "data": [], "passages": [], "gaps": ["project_argument_mapping_pending"],
        "data_policy": "Reported text/table values only; no invented or silently digitized plot values.",
    }


def extract_packet(xml_bytes: bytes, *, source_url: str = "", media_urls: list[str] | None = None) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    # Normalize element names only; retain namespaced xlink attributes.
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    packet = empty_packet(source_url=source_url, content_kind="jats_full_text")
    packet["source_sha256"] = hashlib.sha256(xml_bytes).hexdigest()
    meta = root.find("./front/article-meta")
    packet["identity"] = {
        "title": text(meta.find("./title-group/article-title")) if meta is not None else "",
        "identifiers": {n.get("pub-id-type", "unknown"): text(n) for n in meta.findall("article-id")} if meta is not None else {},
        "article_type": root.get("article-type"),
    }
    packet["license"] = text(meta.find("permissions")) if meta is not None else ""
    parents = {child: parent for parent in root.iter() for child in parent}

    def ancestors(node):
        while node in parents:
            node = parents[node]
            yield node

    def section(node):
        return " / ".join(reversed([text(n.find("title")) for n in ancestors(node) if n.tag == "sec" and text(n.find("title"))]))

    def anchor(node, fallback):
        return node.get("id") or fallback

    catalog = list(dict.fromkeys(media_urls or []))

    def assets(node):
        rows = []
        for child in node.iter():
            href = child.get(XLINK) or child.get("href")
            if child.tag not in {"graphic", "inline-graphic", "media", "ext-link", "supplementary-material"} or not href:
                continue
            stem = unquote(urlparse(href).path).rsplit("/", 1)[-1]
            matches = [u for u in catalog if unquote(urlparse(u).path).rsplit("/", 1)[-1] == stem or unquote(urlparse(u).path).rsplit("/", 1)[-1].rsplit(".", 1)[0] == stem]
            url = matches[0] if len(matches) == 1 else (href if urlparse(href).scheme in {"https", "http"} else None)
            rows.append({"reference": href, "url": url, "status": "linked_not_downloaded" if url else "media_url_unresolved"})
        return rows

    for index, node in enumerate(root.iter("fig")):
        packet["figures"].append({
            "id": anchor(node, f"figure-{index + 1}"), "label": text(node.find("label")),
            "caption": text(node.find("caption")), "section": section(node), "assets": assets(node),
            "visual_review_status": "not_reviewed", "numeric_data_status": "plot_not_digitized",
        })
    for index, node in enumerate(root.iter("table-wrap")):
        rows = []
        for tr in node.iter("tr"):
            rows.append([{"text": text(cell), "header": cell.tag == "th", "rowspan": cell.get("rowspan", "1"), "colspan": cell.get("colspan", "1")} for cell in tr if cell.tag in {"td", "th"}])
        packet["tables"].append({
            "id": anchor(node, f"table-{index + 1}"), "label": text(node.find("label")),
            "caption": text(node.find("caption")), "rows": rows,
            "footnotes": text(node.find("table-wrap-foot")), "assets": assets(node),
            "extraction_status": "reported_cells" if rows else "image_or_external_table_unread",
        })
    for index, node in enumerate(root.iter("supplementary-material")):
        packet["supplements"].append({"id": anchor(node, f"supplement-{index + 1}"), "label": text(node.find("label")), "description": text(node), "assets": assets(node), "content_status": "not_read"})
    for node in root.iter("p"):
        lineage = list(ancestors(node))
        if not any(n.tag in {"body", "abstract"} for n in lineage) or any(n.tag in {"fig", "table-wrap", "ref-list", "supplementary-material"} for n in lineage):
            continue
        value = text(node)
        if value:
            packet["passages"].append({"id": anchor(node, f"paragraph-{len(packet['passages']) + 1}"), "section": section(node) or ("Abstract" if any(n.tag == "abstract" for n in lineage) else "Main text"), "text": value, "figure_table_refs": [x.get("rid") for x in node.iter("xref") if x.get("ref-type") in {"fig", "table", "supplementary-material"}]})
    if not any(n.tag == "body" for n in root.iter()):
        packet["content_kind"] = "jats_abstract_or_metadata"
        packet["gaps"].append("full_text_body_unavailable")
    if any(not a["url"] for f in packet["figures"] for a in f["assets"]):
        packet["gaps"].append("some_figure_media_urls_unresolved")
    if packet["supplements"]:
        packet["gaps"].append("supplement_contents_not_yet_extracted")
    packet["gaps"].append("quantitative_interpretation_pending")
    return packet


def packet_window(packet: dict[str, Any], section: str, offset: int = 0, limit: int = 5) -> dict[str, Any]:
    """Explicit bounded reading; no implied full-paper review from one page."""
    names = {"arguments", "figures", "tables", "supplements", "data", "passages"}
    if section not in names:
        raise ValueError("unknown_evidence_packet_section")
    sections = {key: packet.get(key) or [] for key in names}
    analysis = packet.get("analysis") or {}
    sections["arguments"] = [*sections["arguments"], *[
        {**a, "origin": "model_analysis", "review_status": "pending_review"}
        for a in analysis.get("arguments", [])
    ]]
    rows = sections[section]
    offset, limit = max(0, offset), max(1, min(20, limit))
    items = rows[offset:offset + limit]
    return {"schema": packet.get("schema"), "source_url": packet.get("source_url"), "source_sha256": packet.get("source_sha256"), "retrieval_trace_id": packet.get("retrieval_trace_id"), "raw_content_artifact_id": packet.get("raw_content_artifact_id"), "archive_artifact_id": packet.get("archive_artifact_id"), "content_kind": packet.get("content_kind"), "analysis_status": packet.get("analysis_status"), "coverage_status": packet.get("coverage_status"), "identity": packet.get("identity"), "license": packet.get("license"), "gaps": packet.get("gaps", []), "project_relevance": analysis.get("project_relevance"), "paper_claim": analysis.get("paper_claim"), "section": section, "items": items, "counts": {key: len(sections[key]) for key in sorted(names)}, "read_window": {"offset": offset, "returned_count": len(items), "total_count": len(rows), "has_more": offset + len(items) < len(rows), "next_offset": offset + len(items) if offset + len(items) < len(rows) else None}}


def discover_pmc_media(pmcid: str) -> dict[str, Any]:
    """Resolve actual OA catalog entries, never construct guessed image URLs."""
    import httpx

    if not re.fullmatch(r"PMC[0-9]+", pmcid):
        return {"status": "invalid_pmcid", "urls": []}
    base = "https://pmc-oa-opendata.s3.amazonaws.com"
    result: dict[str, Any] = {"status": "unavailable", "urls": [], "checked_at": datetime.now(UTC).isoformat()}
    try:
        with httpx.Client(timeout=15.0, follow_redirects=False) as client:
            response = client.get(base, params={"list-type": "2", "prefix": pmcid + ".", "delimiter": "/"})
            response.raise_for_status()
            versions = [n.text.rstrip("/") for n in ET.fromstring(response.content).iter()
                        if n.tag.rsplit("}", 1)[-1] == "Prefix" and n.text and re.fullmatch(re.escape(pmcid) + r"\.[0-9]+/?", n.text)]
            if not versions:
                return result
            version = max(versions, key=lambda v: int(v.rsplit(".", 1)[1]))
            response = client.get(f"{base}/metadata/{version}.json")
            response.raise_for_status()
            metadata = response.json()
            if metadata.get("pmcid") != pmcid or metadata.get("is_pmc_openaccess") is not True:
                return result
            urls = []
            for value in metadata.get("media_urls") or []:
                if isinstance(value, str):
                    value = value.replace("s3://pmc-oa-opendata/", base + "/")
                    if urlparse(value).scheme == "https" and urlparse(value).netloc == "pmc-oa-opendata.s3.amazonaws.com":
                        urls.append(value)
            return {**result, "status": "resolved", "urls": urls, "version": version,
                    "source_url": str(response.url), "sha256": hashlib.sha256(response.content).hexdigest(),
                    "license_code": metadata.get("license_code"), "is_retracted": metadata.get("is_retracted")}
    except (httpx.HTTPError, ValueError, ET.ParseError) as exc:
        return {**result, "status": "lookup_failed", "error_type": type(exc).__name__}


def anchored_analysis(packet: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Reject invented locators/values before saving a model interpretation draft."""
    if not isinstance(analysis, dict):
        raise ValueError("analysis_object_required")
    analysis = deepcopy(analysis)
    sources = {p["id"]: p["text"] for p in packet.get("passages", [])}
    sources.update({f["id"]: f["caption"] for f in packet.get("figures", [])})
    sources.update({t["id"]: " ".join([t["caption"]] + [" ".join(c["text"] for c in r) for r in t["rows"]] + [t["footnotes"]]) for t in packet.get("tables", [])})
    for key in ("project_relevance", "paper_claim"):
        if not isinstance(analysis.get(key), str) or not analysis[key].strip():
            raise ValueError(f"analysis_{key}_required")
    for key in ("arguments", "data", "figure_notes", "gaps"):
        if not isinstance(analysis.get(key), list):
            raise ValueError(f"analysis_{key}_list_required")
    if not analysis["arguments"]:
        raise ValueError("at_least_one_project_argument_required")
    if any(not isinstance(gap, str) or not gap.strip() for gap in analysis["gaps"]):
        raise ValueError("analysis_gaps_must_be_nonempty_strings")
    for argument in analysis["arguments"]:
        if not isinstance(argument, dict):
            raise ValueError("argument_object_required")
        ids = argument.get("source_ids") or []
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in sources for i in ids):
            raise ValueError("argument_source_anchor_missing")
        if not isinstance(argument.get("relation"), str) or argument["relation"] not in {"supports", "contradicts", "context", "insufficient"}:
            raise ValueError("argument_relation_invalid")
        if packet.get("retracted") and argument.get("relation") == "supports":
            raise ValueError("retracted_source_cannot_be_positive_support")
        for key in ("project_argument", "paper_claim", "interpretation", "limitations"):
            if not isinstance(argument.get(key), str) or not argument[key].strip():
                raise ValueError(f"argument_{key}_required")
    for item in analysis["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str):
            raise ValueError("quantitative_source_anchor_required")
        source = re.sub(r"\s+", " ", sources.get(item["source_id"], ""))
        quote = re.sub(r"\s+", " ", str(item.get("source_quote") or "")).strip()
        raw_value = item.get("value")
        if (type(raw_value) not in (str, int, float)
                or isinstance(raw_value, float) and not math.isfinite(raw_value)):
            raise ValueError("quantitative_value_invalid")
        value = str(raw_value).strip()
        # A numerical value must be a whole reported number: 21.2 is not 121.2,
        # 0.21.2, -21.2 or 21.2e3. Zero is valid and must not be treated as absent.
        value_found = value in {m.group() for m in REPORTED_NUMBER.finditer(quote)} if REPORTED_NUMBER.fullmatch(value) else bool(
            value and re.search(r"(?<![\w.])" + re.escape(value) + r"(?!\w|\.\d)", quote)
        )
        if not quote or not value or quote not in source or not value_found:
            raise ValueError("quantitative_value_not_found_at_source_anchor")
        if any(key not in item for key in ("measure", "unit", "condition", "comparator", "n", "uncertainty")):
            raise ValueError("quantitative_conditions_or_uncertainty_missing_use_explicit_null")
        item["anchor_verification"] = "exact_text_and_value_match"
    figure_ids = {f["id"] for f in packet.get("figures", [])}
    if any(not isinstance(f, dict) or not isinstance(f.get("id"), str) or f["id"] not in figure_ids for f in analysis["figure_notes"]):
        raise ValueError("unknown_figure_anchor")
    return {**analysis, "analysis_status": "model_draft_pending_review", "source_sha256": packet.get("source_sha256"), "saved_at": datetime.now(UTC).isoformat()}
