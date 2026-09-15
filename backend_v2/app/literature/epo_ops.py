"""EPO Open Patent Services: search records, families and legal events, read as records.

Europe PMC's patent index answers "what was published". It cannot answer the two
questions a landscape is asked next - is this one invention filed in several
offices, and what has happened to it since - because it carries neither patent
families nor legal status. EPO OPS carries both: a DOCDB family id on every
record, and INPADOC legal events.

This module is the part that knows what an OPS response means. It does no IO:
`epo_ops_client` fetches and audits, and the literature tasks save.

Two readings are refused here, in code, because they are the natural misreadings
of this data:

* **An INPADOC event is not a status.** Offices report events late or not at
  all, a European application's events are per designated state (PG25 "lapsed
  in a contracting state" names one country, not the patent), and nothing here
  sees court decisions or licences. The summary reports the most recent event
  *per country*, with its date and INPADOC's own influence flag, and never says
  "in force", "lapsed" or "valid" of a patent.
* **Events belong to an application, not a publication.** In OPS, EP 1537878 B1
  carries no events; its 257 events hang off the family member for application
  EP 03741154. A lookup that matched on the publication alone would report a
  granted, opposed and appealed patent as having no history at all.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from .patents import PatentQueryError, espacenet_url, jurisdiction_codes, publication_stage

BASE_URL = "https://ops.epo.org/3.2"

#: OPS rejects long CQL; a query this long is a pasted document, not a search.
MAX_QUERY_LENGTH = 500

#: OPS serves at most 100 records per search request.
MAX_SEARCH_RANGE = 100

#: Events kept verbatim per lookup. The per-country summary covers all of them.
MAX_EVENTS_LISTED = 60

LEGAL_LIMITS: tuple[str, ...] = (
    "Events are INPADOC legal-status records exchanged to the EPO by national and "
    "regional offices. They arrive late, and some offices report few events or none.",
    "The most recent event in a country is not a determination that a right is in "
    "force, lapsed or valid there: fee payments, oppositions, SPCs, licences and court "
    "decisions may be missing or not yet reported.",
    "The influence flag (positive / negative) is INPADOC's own classification of an event, not a legal assessment.",
    "Events are attached to the application. A publication with no events here has an "
    "unreported history, not a clean one.",
    "This is orientation for a reader, not a freedom-to-operate or validity opinion.",
)

# A CQL field followed by a relation: the person wrote OPS syntax, and it is
# passed through as written. Anything else is plain words.
_CQL_RELATION = re.compile(
    r"\b(?:ta|ti|ab|txt|pa|in|ia|pn|ap|pr|num|pd|ct|cpc|ipc|cl|famn)\s*(?:=|all\b|any\b|within\b)",
    re.IGNORECASE,
)
_BOOLEAN_WORDS = {"AND", "OR", "NOT"}
_PUBLICATION = re.compile(r"^([A-Z]{2})([A-Z0-9]*?[0-9])([A-Z][0-9]?)?$")
_KIND = re.compile(r"^[A-Z][0-9]?$")
_IPC = re.compile(r"^([A-H][0-9]{2}[A-Z])\s*([0-9]{1,4})\s*/\s*([0-9]{1,6})")


@dataclass(frozen=True)
class PublicationRef:
    """A publication as DOCDB names it: office, number and (when known) kind."""

    country: str
    number: str
    kind: str | None = None

    @property
    def docdb(self) -> str:
        """The `CC.number.kind` form OPS addresses a publication by."""
        return ".".join(part for part in (self.country, self.number, self.kind) if part)

    @property
    def publication_number(self) -> str:
        """Office and number without the kind - the form Europe PMC records use."""
        return f"{self.country}{self.number}"


def publication_reference(publication_number: str, kind_code: str | None = None) -> PublicationRef:
    """Parse a saved publication number into the reference OPS is asked about.

    Strict on purpose: the parts are placed into a URL path, so anything that is
    not an office code, a publication number and a kind code is refused rather
    than escaped.
    """
    text = re.sub(r"[\s.\-/]", "", str(publication_number or "")).upper()
    kind = str(kind_code or "").strip().upper() or None
    if kind is not None and not _KIND.fullmatch(kind):
        raise PatentQueryError(f"Unrecognised kind code {kind_code!r}.")
    if kind and text.endswith(kind) and len(text) > len(kind) + 2 and text[-len(kind) - 1].isdigit():
        text = text[: -len(kind)]
    match = _PUBLICATION.fullmatch(text)
    if match is None or len(match.group(2)) > 24:
        raise PatentQueryError(f"Unrecognised publication number {publication_number!r}.")
    country, number, parsed_kind = match.groups()
    return PublicationRef(country=country, number=number, kind=kind or parsed_kind)


def cql_query(topic: str, jurisdictions: Sequence[str] = ()) -> str:
    """An OPS CQL query for a topic, optionally restricted to offices.

    CQL the person wrote is kept as written, like Europe PMC syntax is: the
    recorded query must be one somebody typed. Plain words become an all-words
    title-or-abstract search, with bare AND/OR/NOT dropped - `ta all` already
    requires every word, and a boolean word left inside the phrase would be
    searched for as a term and find nothing.
    """
    text = " ".join((topic or "").split())
    if not text:
        raise PatentQueryError("A patent search needs a topic.")
    codes = jurisdiction_codes(jurisdictions)
    if _CQL_RELATION.search(text):
        query = text
    else:
        terms = [term for term in text.replace('"', " ").replace("(", " ").replace(")", " ").split()]
        terms = [term for term in terms if term not in _BOOLEAN_WORDS]
        if not terms:
            raise PatentQueryError("A patent search needs a topic.")
        query = 'ta all "' + " ".join(terms) + '"'
    if codes:
        query = f"({query}) and (" + " or ".join(f"pn={code}" for code in codes) + ")"
    if len(query) > MAX_QUERY_LENGTH:
        raise PatentQueryError(f"A patent search query must be at most {MAX_QUERY_LENGTH} characters.")
    return query


def _as_list(value: Any) -> list[Any]:
    """OPS JSON returns one item as an object and several as a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("$")
    return " ".join(str(value).split()) if value is not None else ""


def _iso(value: str) -> str | None:
    digits = value.replace("-", "")
    if len(digits) != 8 or not digits.isdigit():
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])).isoformat()
    except ValueError:
        return None


def _docdb(ids: Any) -> Mapping[str, Any] | None:
    for item in _as_list(ids):
        if isinstance(item, Mapping) and item.get("@document-id-type") == "docdb":
            return item
    return None


def _by_language(items: Any) -> str:
    """English when the office supplied it, otherwise the first language given."""
    candidates = [item for item in _as_list(items) if isinstance(item, Mapping)]
    chosen = next((item for item in candidates if str(item.get("@lang") or "").lower() == "en"), None)
    if chosen is None and candidates:
        chosen = candidates[0]
    if chosen is None:
        return ""
    if "p" in chosen:
        return " ".join(_text(part) for part in _as_list(chosen.get("p")) if _text(part))
    return _text(chosen)


def _party_names(parties: Any, role: str, name_key: str) -> str | None:
    rows = [row for row in _as_list(parties) if isinstance(row, Mapping)]
    # `epodoc` names are the EPO's normalised Latin spelling; `original` is the
    # office's own (Chinese for a CN record). Normalised first, so one applicant
    # is counted once across offices.
    for data_format in ("epodoc", "original"):
        names = [
            _text((row.get(name_key) or {}).get("name"))
            for row in rows
            if row.get("@data-format") == data_format and isinstance(row.get(name_key), Mapping)
        ]
        names = [name.rstrip(",").strip() for name in names if name]
        if names:
            return "; ".join(dict.fromkeys(names))
    return None


def _ipc_codes(bibliographic: Mapping[str, Any]) -> list[str]:
    texts = [
        _text(item.get("text"))
        for item in _as_list((bibliographic.get("classifications-ipcr") or {}).get("classification-ipcr"))
        if isinstance(item, Mapping)
    ]
    texts += [_text(item) for item in _as_list((bibliographic.get("classification-ipc") or {}).get("text"))]
    codes = set()
    for text in texts:
        match = _IPC.match(text)
        if match:
            codes.add(f"{match.group(1)}{match.group(2)}/{match.group(3)}")
    return sorted(codes)


def _cpc_codes(bibliographic: Mapping[str, Any]) -> list[str]:
    codes = set()
    for item in _as_list((bibliographic.get("patent-classifications") or {}).get("patent-classification")):
        if not isinstance(item, Mapping):
            continue
        scheme = str((item.get("classification-scheme") or {}).get("@scheme") or "")
        if not scheme.startswith("CPC"):
            continue
        parts = [_text(item.get(key)) for key in ("section", "class", "subclass", "main-group", "subgroup")]
        if all(parts):
            codes.add(f"{parts[0]}{parts[1]}{parts[2]}{parts[3]}/{parts[4]}")
    return sorted(codes)


def exchange_document_details(document: Mapping[str, Any]) -> dict[str, Any]:
    """The fields of an OPS record, under the same keys `patents.patent_details` uses.

    One shape for both sources means one landscape: a record does not count
    differently because of the index that found it.
    """
    bibliographic = document.get("bibliographic-data") or {}
    country = str(document.get("@country") or "").upper() or None
    number = str(document.get("@doc-number") or "").strip()
    kind = str(document.get("@kind") or "").strip().upper() or None
    publication = _docdb((bibliographic.get("publication-reference") or {}).get("document-id")) or {}
    application = _docdb((bibliographic.get("application-reference") or {}).get("document-id")) or {}
    priorities = []
    for claim in _as_list((bibliographic.get("priority-claims") or {}).get("priority-claim")):
        if not isinstance(claim, Mapping):
            continue
        reference = _docdb(claim.get("document-id")) or {}
        if reference:
            priorities.append(
                {
                    "number": f"{_text(reference.get('country'))}{_text(reference.get('doc-number'))}",
                    "date": _iso(_text(reference.get("date"))),
                }
            )
    priority_dates = sorted(str(item["date"]) for item in priorities if item["date"])
    parties = bibliographic.get("parties") or {}
    publication_number = f"{country or ''}{number}"
    return {
        "publication_number": publication_number,
        "country_code": country,
        "kind_code": kind,
        "kind_description": None,
        "stage": publication_stage(country, kind),
        "applicant": _party_names((parties.get("applicants") or {}).get("applicant"), "applicant", "applicant-name"),
        "inventors": _party_names((parties.get("inventors") or {}).get("inventor"), "inventor", "inventor-name"),
        "application_number": (
            f"{_text(application.get('country'))}{_text(application.get('doc-number'))}" if application else None
        ),
        "application_date": _iso(_text(application.get("date"))) if application else None,
        "priority": priorities,
        "earliest_priority_date": priority_dates[0] if priority_dates else None,
        "publication_date": _iso(_text(publication.get("date"))),
        "ipc": _ipc_codes(bibliographic),
        "cpc": _cpc_codes(bibliographic),
        "family_id": str(document.get("@family-id") or "").strip() or None,
        "url": espacenet_url(f"{publication_number}{kind or ''}") if number else None,
    }


def search_total(payload: Mapping[str, Any]) -> int | None:
    search = (payload.get("ops:world-patent-data") or {}).get("ops:biblio-search") or {}
    try:
        return int(str(search.get("@total-result-count")))
    except ValueError:
        return None


def search_results(payload: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    """OPS search records in the shape `retrieval.europe_pmc_results` returns.

    The literature task saves either source through the same code, so the
    fields a paper has and a patent does not are present and empty rather than
    absent.
    """
    search = (payload.get("ops:world-patent-data") or {}).get("ops:biblio-search") or {}
    wrappers = _as_list((search.get("ops:search-result") or {}).get("exchange-documents"))
    results: list[dict[str, Any]] = []
    for rank, wrapper in enumerate(wrappers[:limit], start=1):
        if not isinstance(wrapper, Mapping):
            continue
        document = wrapper.get("exchange-document")
        if not isinstance(document, Mapping) or document.get("@status"):
            # `@status` is how OPS marks a record it could not serve ("not found").
            continue
        details = exchange_document_details(document)
        bibliographic = document.get("bibliographic-data") or {}
        title = _by_language(bibliographic.get("invention-title"))
        if not details["publication_number"] or not title:
            continue
        results.append(
            {
                "rank": rank,
                "source": "epo_ops",
                # With the kind: an application and its grant are two publications,
                # and saving them as one document would count the grant twice or not at all.
                "external_id": f"{details['publication_number']}{details['kind_code'] or ''}",
                "title": title,
                "abstract": _by_language(document.get("abstract")),
                "doi": "",
                "pmid": "",
                "pmcid": "",
                "authors": details["inventors"] or "",
                "journal": "",
                "year": str(details["publication_date"] or "")[:4],
                "is_open_access": False,
                "in_epmc": False,
                "cited_by_count": None,
                "publication_types": {},
                "patent": details,
            }
        )
    return results


def _member_publication(member: Mapping[str, Any]) -> tuple[PublicationRef, str | None] | None:
    reference = _docdb((member.get("publication-reference") or {}).get("document-id"))
    if reference is None:
        return None
    country, number = _text(reference.get("country")).upper(), _text(reference.get("doc-number")).upper()
    if not country or not number:
        return None
    kind = _text(reference.get("kind")).upper() or None
    return PublicationRef(country, number, kind), _iso(_text(reference.get("date")))


def _member_application(member: Mapping[str, Any] | None) -> tuple[str, str] | None:
    if member is None:
        return None
    reference = _docdb((member.get("application-reference") or {}).get("document-id"))
    if reference is None:
        return None
    country, number = _text(reference.get("country")).upper(), _text(reference.get("doc-number")).upper()
    return (country, number) if country and number else None


def legal_event(raw: Any) -> dict[str, Any] | None:
    """One INPADOC event, with the country it is about rather than the office that sent it.

    For a European application the office is always EP, and the designated
    state an event concerns - where a fee was paid, where it lapsed - sits in
    the event's own `L501EP`. Reading the office instead would put every
    national lapse on the whole European patent.
    """
    if not isinstance(raw, Mapping):
        return None
    code = str(raw.get("@code") or "").strip()
    if not code:
        return None
    extra = raw.get("ops:L500EP")
    extra = extra if isinstance(extra, Mapping) else {}
    influence = {"+": "positive", "-": "negative"}.get(str(raw.get("@infl") or "").strip(), "neutral")
    return {
        "code": code,
        "description": _text(raw.get("@desc")),
        "influence": influence,
        "country": _text(extra.get("ops:L501EP")).upper() or _text(raw.get("ops:L001EP")).upper() or None,
        "gazette_date": _iso(_text(raw.get("ops:L007EP"))),
        "effective_date": _iso(_text(extra.get("ops:L525EP"))),
        "national_code": _text(extra.get("ops:L502EP")) or None,
        "detail": _text(extra.get("ops:L510EP"))[:200] or None,
    }


def family_legal_summary(payload: Mapping[str, Any], publication: PublicationRef) -> dict[str, Any]:
    """Family membership and the legal events of one publication's application.

    Events are collected from every family member filed under the same
    application as the publication asked about, because OPS attaches them to one
    of those members and not necessarily to the one that was asked about.
    """
    family = (payload.get("ops:world-patent-data") or {}).get("ops:patent-family")
    family = family if isinstance(family, Mapping) else {}
    members = [member for member in _as_list(family.get("ops:family-member")) if isinstance(member, Mapping)]

    publications: list[tuple[PublicationRef, str | None]] = []
    family_ids: list[str] = []
    exact: Mapping[str, Any] | None = None
    same_number: Mapping[str, Any] | None = None
    for member in members:
        parsed = _member_publication(member)
        if parsed is None:
            continue
        reference, _ = parsed
        publications.append(parsed)
        family_id = str(member.get("@family-id") or "").strip()
        if family_id and family_id not in family_ids:
            family_ids.append(family_id)
        if reference.country == publication.country and reference.number == publication.number:
            if publication.kind is None or reference.kind == publication.kind:
                exact = exact or member
            else:
                # A kind recorded differently by another index (Europe PMC's B
                # for OPS's B2, say) is still this publication's application.
                same_number = same_number or member
    target = exact or same_number
    application = _member_application(target)

    events: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    if application is not None:
        for member in members:
            if _member_application(member) != application:
                continue
            for raw in _as_list(member.get("ops:legal")):
                event = legal_event(raw)
                if event is None:
                    continue
                key = tuple(event.values())
                if key not in seen:
                    seen.add(key)
                    events.append(event)
    events.sort(key=lambda event: (event["gazette_date"] or "", event["code"]))

    countries: dict[str, dict[str, Any]] = {}
    for event in events:
        country = event["country"] or "unknown"
        row = countries.setdefault(
            country,
            {
                "country": country,
                "events": 0,
                "positive": 0,
                "negative": 0,
                "latest_event": None,
                "latest_flagged_event": None,
            },
        )
        row["events"] += 1
        row["latest_event"] = event
        if event["influence"] != "neutral":
            row[event["influence"]] += 1
            row["latest_flagged_event"] = event

    offices = Counter(reference.country for reference, _ in publications)
    return {
        "family_id": family_ids[0] if family_ids else None,
        "family_publications": len(publications),
        "family_offices": dict(sorted(offices.items())),
        "family_members": [
            {"publication": f"{reference.publication_number}{reference.kind or ''}", "date": published}
            for reference, published in publications[:100]
        ],
        "matched_publication": target is not None,
        "application": f"{application[0]}{application[1]}" if application else None,
        "event_count": len(events),
        "events": events[-MAX_EVENTS_LISTED:],
        "events_truncated": len(events) > MAX_EVENTS_LISTED,
        "by_country": [countries[key] for key in sorted(countries)],
        "limits": list(LEGAL_LIMITS),
    }
