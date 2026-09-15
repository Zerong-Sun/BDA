"""Patent records, read as records, and what a set of them says as a landscape.

The copilot has always been told not to state patent conclusions: the policy
forbids a "patent-risk conclusion" without supplied evidence, and the grounded
answer check rejects "USPTO search found nothing" by pattern. That rule was
right and left a hole - there was no way to supply the evidence, so patent
questions could only be answered by a model's memory, which is exactly what the
rule forbids.

Patents now come through the same pipeline as papers: an audited Europe PMC
search (`SRC:PAT`), a saved document per hit, a retrieval trace, and an indexed
abstract with a checksum. A patent cited in an answer therefore carries the same
evidence tag a paper does. This module is the part that knows what a patent
record is.

Europe PMC indexes patent publications from the EPO's collection, including
Chinese (CN), US, European (EP), PCT (WO), Japanese and Korean documents - over
half a million CN publications alone. It does **not** carry legal status, and
that single absence shapes everything below: this can say what was published,
by whom, when and in which class, and it cannot say whether anything is in
force. The landscape states that limit in its own output, so a reader cannot
receive the numbers without it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any
from urllib.parse import quote

#: Offices a search can be narrowed to. Named for the reader, keyed by the
#: publication-number prefix Europe PMC's `EXT_ID` field filters on.
JURISDICTIONS: dict[str, str] = {
    "CN": "China (CNIPA)",
    "US": "United States (USPTO)",
    "EP": "Europe (EPO)",
    "WO": "PCT international application (WIPO)",
    "JP": "Japan (JPO)",
    "KR": "Korea (KIPO)",
}

#: The ordinary patent term from filing. Used only to *estimate*; see `landscape`.
TERM_YEARS = 20

LIMITS: tuple[str, ...] = (
    "Legal status is not verified. A publication may have lapsed, been withdrawn or "
    "refused, or never been granted; kind codes such as A1 are applications, not grants.",
    "Term is estimated as application date plus 20 years. Patent term extensions "
    "(PTE/SPC), terminal disclaimers, fee lapses and national-phase differences are "
    "not applied.",
    "Europe PMC's patent index is not a complete worldwide collection. A patent that "
    "does not appear here has not been shown not to exist.",
    "Records are publications, not families: one invention filed in several offices "
    "appears once per publication.",
    "This is a landscape for orientation. It is not a freedom-to-operate or "
    "validity opinion, which needs claims read by a qualified practitioner.",
)


class PatentQueryError(ValueError):
    """The request cannot be turned into a patent search."""


def is_patent_row(row: Mapping[str, Any]) -> bool:
    """Whether a Europe PMC search result is a patent publication."""
    return str(row.get("source") or "").upper() == "PAT"


def _as_list(value: Any) -> list[Any]:
    """Europe PMC returns one item as an object and several as a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def espacenet_url(publication_number: str) -> str:
    """Where a person reads the publication, its claims and its family."""
    return f"https://worldwide.espacenet.com/patent/search?q=pn%3D{quote(publication_number)}"


def publication_stage(country_code: str | None, kind_code: str | None) -> str:
    """What kind of document a publication is, from its office and kind code.

    The distinction that matters most in a landscape and is most often missed:
    most publications are **applications**. Reading a CN...A or US...A1 as a
    granted patent overstates how much is actually protected.

    Kind codes differ by office, so this names only what is unambiguous and
    returns "unknown" otherwise rather than guessing.
    """
    country = (country_code or "").upper()
    kind = (kind_code or "").upper()
    if not kind:
        return "unknown"
    if country == "WO":
        # A PCT publication is never a grant; protection arises only in the
        # national or regional offices it later enters.
        return "pct_application"
    if country == "CN" and kind[0] in {"U", "Y"}:
        return "utility_model"
    if country == "US":
        if kind[0] == "S":
            return "design"
        if kind == "A":
            # Before 2001 the USPTO published only grants, under kind A.
            return "granted"
        if kind == "E":
            return "granted"
    if kind[0] in {"B", "C"}:
        return "granted"
    if kind[0] == "A":
        return "application"
    return "unknown"


def patent_details(row: Mapping[str, Any]) -> dict[str, Any]:
    """The fields of a Europe PMC patent record a landscape is built from."""
    details = row.get("patentDetails") or {}
    number = str(row.get("id") or "").strip()
    classifiers = _as_list((details.get("classifierList") or {}).get("classifier"))
    ipc = sorted(
        {
            str(item.get("classification"))
            for item in classifiers
            if isinstance(item, Mapping)
            and item.get("classificationType") == "IPC"
            and item.get("classification")
        }
    )
    cpc = sorted(
        {
            str(item.get("classification"))
            for item in classifiers
            if isinstance(item, Mapping)
            and item.get("classificationType") in {"EPO", "CPC"}
            and item.get("classification")
        }
    )
    application = details.get("application") or {}
    priorities = [
        {"number": item.get("priorityNumber"), "date": item.get("priorityDate")}
        for item in _as_list((details.get("priorityList") or {}).get("priority"))
        if isinstance(item, Mapping)
    ]
    priority_dates = sorted(str(item["date"]) for item in priorities if item.get("date"))
    country = str(details.get("countryCode") or number[:2]).upper() or None
    kind = details.get("typeCode")
    return {
        "publication_number": number,
        "country_code": country,
        "kind_code": kind,
        "kind_description": details.get("typeDescription"),
        "stage": publication_stage(country, kind),
        # Europe PMC puts the applicant in `affiliation` and the inventors in
        # `authorString` for patent records. Kept apart: the applicant is who
        # holds the rights, the inventors are who made the invention.
        "applicant": (str(row.get("affiliation") or "").strip() or None),
        "inventors": (str(row.get("authorString") or "").strip().rstrip(".") or None),
        "application_number": application.get("applicationNumber"),
        "application_date": application.get("applicationDate"),
        "priority": priorities,
        "earliest_priority_date": priority_dates[0] if priority_dates else None,
        "publication_date": row.get("firstPublicationDate"),
        "ipc": ipc,
        "cpc": cpc,
        "url": espacenet_url(number) if number else None,
    }


def jurisdiction_codes(jurisdictions: Sequence[str]) -> list[str]:
    """Office codes, validated and de-duplicated in the order they were given."""
    codes: list[str] = []
    for code in jurisdictions:
        normalised = str(code or "").strip().upper()
        if normalised not in JURISDICTIONS:
            known = ", ".join(sorted(JURISDICTIONS))
            raise PatentQueryError(f"Unknown jurisdiction {code!r}. Known: {known}.")
        if normalised not in codes:
            codes.append(normalised)
    return codes


def patent_query(topic: str, jurisdictions: Sequence[str] = ()) -> str:
    """A Europe PMC query restricted to patents, and optionally to offices.

    The topic is passed through as the person wrote it - Europe PMC's own
    syntax is the interface, and rewriting it would make the recorded query
    something nobody typed.
    """
    text = (topic or "").strip()
    if not text:
        raise PatentQueryError("A patent search needs a topic.")
    codes = jurisdiction_codes(jurisdictions)
    query = f"SRC:PAT AND ({text})"
    if codes:
        query += " AND (" + " OR ".join(f"EXT_ID:{code}*" for code in codes) + ")"
    return query


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 February
        return value.replace(year=value.year + years, day=28)


def _parse_date(text: Any) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except (TypeError, ValueError):
        return None


def landscape(records: Iterable[Mapping[str, Any]], *, today: date, top: int = 10) -> dict[str, Any]:
    """Counts across a set of patent records, with their limits attached.

    `records` are `patent_details` outputs. Every aggregate here is a count of
    publications found by a recorded search - never a statement about what
    exists, what is granted, or what is in force.
    """
    rows = [dict(record) for record in records]
    by_country = Counter(row.get("country_code") or "unknown" for row in rows)
    by_stage = Counter(row.get("stage") or "unknown" for row in rows)
    applicants = Counter(
        " ".join(str(row["applicant"]).upper().split()) for row in rows if row.get("applicant")
    )
    subclasses = Counter(code[:4] for row in rows for code in (row.get("ipc") or []) if len(code) >= 4)
    years = Counter(
        str(row.get("earliest_priority_date") or row.get("application_date") or "")[:4]
        for row in rows
        if row.get("earliest_priority_date") or row.get("application_date")
    )

    unexpired = expired = undated = 0
    for row in rows:
        filed = _parse_date(row.get("application_date"))
        if filed is None:
            undated += 1
        elif _add_years(filed, TERM_YEARS) > today:
            unexpired += 1
        else:
            expired += 1

    return {
        "publications": len(rows),
        "by_jurisdiction": [
            {"code": code, "office": JURISDICTIONS.get(code, code), "count": count}
            for code, count in by_country.most_common()
        ],
        "by_stage": dict(sorted(by_stage.items())),
        "top_applicants": [{"applicant": name, "count": count} for name, count in applicants.most_common(top)],
        "top_ipc_subclasses": [{"subclass": code, "count": count} for code, count in subclasses.most_common(top)],
        "priority_years": dict(sorted(years.items())),
        "estimated_term": {
            "basis": f"application date + {TERM_YEARS} years, as of {today.isoformat()}",
            "within_estimated_term": unexpired,
            "past_estimated_term": expired,
            "no_application_date": undated,
        },
        "limits": list(LIMITS),
    }
