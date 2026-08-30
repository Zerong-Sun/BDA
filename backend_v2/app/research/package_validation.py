from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SUPPORTED_SCHEMA_VERSIONS = {"1.0", "1.1"}
TRUSTED_VERIFICATION_STATUSES = {"verified_europe_pmc"}
TRUSTED_BUILTIN_PACKAGE_CHECKSUMS = {
    "pd1-demo-v1": "34b9618a8c5d44148267ae907a91a6eb5c16a2062e2c91e64616ddb64d6a0fdd",
}
TRUSTED_REFERENCE_HOSTS = {
    "doi.org",
    "dx.doi.org",
    "europepmc.org",
    "www.ebi.ac.uk",
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
}
IDENTIFIER_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
PDB_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
PMID_PATTERN = re.compile(r"[1-9]\d{0,8}")
DOI_PATTERN = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)

LocalizedText = str | dict[str, str]


class ResearchPackageValidationError(ValueError):
    pass


class _PackageModel(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


def _canonical_identifier(value: str, field: str) -> str:
    if value != value.strip() or not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be a canonical identifier without surrounding whitespace")
    return value


def _bounded_localized(value: LocalizedText, maximum: int, field: str) -> LocalizedText:
    texts = value.values() if isinstance(value, dict) else [value]
    if any(len(text) > maximum for text in texts):
        raise ValueError(f"{field} must be at most {maximum} characters in each language")
    return value


class ResearchPrimaryTarget(_PackageModel):
    name: LocalizedText
    gene: str = Field(max_length=80)
    uniprot: str = Field(max_length=32)
    organism: str = Field(max_length=200)
    pdb_id: str | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def bounded_name(cls, value: LocalizedText) -> LocalizedText:
        return _bounded_localized(value, 200, "primary target name")


class ResearchStructure(_PackageModel):
    pdb_id: str = Field(min_length=1, max_length=20)
    name: LocalizedText
    method: str = Field(max_length=100)
    resolution: int | float | None
    role: LocalizedText
    reference_id: str = Field(min_length=1, max_length=200)
    url: str = ""
    rcsb_url: str = ""

    @field_validator("pdb_id")
    @classmethod
    def canonical_pdb_id(cls, value: str) -> str:
        if value != value.strip() or not PDB_ID_PATTERN.fullmatch(value):
            raise ValueError("pdb_id must be canonical and contain no surrounding whitespace")
        return value

    @field_validator("reference_id")
    @classmethod
    def canonical_reference_id(cls, value: str) -> str:
        return _canonical_identifier(value, "reference_id")


class ResearchProject(_PackageModel):
    id: str = Field(min_length=1, max_length=80)
    name: LocalizedText
    project_type: str = Field(min_length=1, max_length=80)
    summary: LocalizedText
    project_review: LocalizedText
    primary_target: ResearchPrimaryTarget
    structures: list[ResearchStructure]
    # Optional per-project override of the package-level methods entry, for
    # projects whose methodology differs from the shared evidence contract.
    methods: LocalizedText = ""

    @field_validator("id")
    @classmethod
    def canonical_id(cls, value: str) -> str:
        return _canonical_identifier(value, "project id")

    @field_validator("name")
    @classmethod
    def bounded_name(cls, value: LocalizedText) -> LocalizedText:
        return _bounded_localized(value, 200, "project name")

    @field_validator("summary")
    @classmethod
    def bounded_summary(cls, value: LocalizedText) -> LocalizedText:
        return _bounded_localized(value, 5000, "project summary")

    @field_validator("project_review")
    @classmethod
    def bounded_review(cls, value: LocalizedText) -> LocalizedText:
        return _bounded_localized(value, 100_000, "project review")

    @field_validator("methods")
    @classmethod
    def bounded_methods(cls, value: LocalizedText) -> LocalizedText:
        return _bounded_localized(value, 100_000, "project methods")


class ResearchReference(_PackageModel):
    ref_id: str = Field(min_length=1, max_length=200)
    project_ids: list[str] = Field(min_length=1)
    role: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    authors: str = ""
    journal: str = ""
    year: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    url: str = ""
    doi_url: str = ""
    pubmed_url: str = ""
    pmc_url: str = ""
    source_url: str = ""
    verification_status: str
    is_open_access: str = "N"

    @field_validator("ref_id")
    @classmethod
    def canonical_id(cls, value: str) -> str:
        return _canonical_identifier(value, "reference id")

    @field_validator("project_ids")
    @classmethod
    def canonical_project_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            _canonical_identifier(value, "reference project id")
        if len(values) != len(set(values)):
            raise ValueError("reference project IDs must be unique")
        return values


class ResearchEdge(_PackageModel):
    claim_id: str = Field(min_length=1, max_length=200)
    project: str = Field(min_length=1, max_length=80)
    subject: str
    predicate: str
    object: str
    context: LocalizedText
    assertion: str
    grade: str
    ref_id: str = Field(min_length=1, max_length=200)
    summary: LocalizedText
    source_url: str
    metadata_verification: str

    @field_validator("claim_id", "project", "ref_id")
    @classmethod
    def canonical_ids(cls, value: str, info) -> str:
        return _canonical_identifier(value, info.field_name)

    @model_validator(mode="after")
    def bounded_title(self) -> ResearchEdge:
        if len(f"{self.subject} —{self.predicate}→ {self.object}") > 300:
            raise ValueError("edge subject, predicate, and object exceed the persisted title limit")
        return self


class ResearchCandidate(_PackageModel):
    candidate_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(default="", max_length=80)
    group: LocalizedText = ""
    target: LocalizedText
    gene: str = Field(max_length=80)
    protein_type: LocalizedText
    localization: LocalizedText
    axis: LocalizedText
    weighted_score: int | float
    evidence: int | float
    novelty: int | float
    tractability: int | float
    human: int | float
    specificity: int | float
    safety: int | float
    reference_ids: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_group_name(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "pain_group" not in value:
            return value
        candidate = dict(value)
        legacy_group = candidate.pop("pain_group")
        candidate.setdefault("group", legacy_group)
        return candidate

    @field_validator("candidate_id")
    @classmethod
    def canonical_id(cls, value: str) -> str:
        return _canonical_identifier(value, "candidate identifier")

    @field_validator("project_id")
    @classmethod
    def canonical_project_id(cls, value: str) -> str:
        return _canonical_identifier(value, "candidate project identifier") if value else value

    @field_validator("reference_ids")
    @classmethod
    def canonical_reference_ids(cls, value: str) -> str:
        parts = value.split(";")
        if not parts or any(not part or part != part.strip() for part in parts):
            raise ValueError("candidate reference IDs must be canonical semicolon-separated identifiers")
        for part in parts:
            _canonical_identifier(part, "candidate reference id")
        if len(parts) != len(set(parts)):
            raise ValueError("candidate reference IDs must be unique")
        return value

    @field_validator("target")
    @classmethod
    def bounded_target(cls, value: LocalizedText) -> LocalizedText:
        return _bounded_localized(value, 240, "candidate target")


class ResearchPackage(_PackageModel):
    package_id: str = Field(min_length=1, max_length=240)
    schema_version: str
    version: str = Field(min_length=1, max_length=80)
    as_of: str = ""
    title: LocalizedText = ""
    description: LocalizedText = ""
    projects: list[ResearchProject] = Field(min_length=1)
    methods: LocalizedText = ""
    search_strategy: LocalizedText = ""
    database_schema: LocalizedText = ""
    references: list[ResearchReference] = Field(min_length=1)
    edges: list[ResearchEdge]
    candidates: list[ResearchCandidate]
    bibliometrics: list[dict[str, Any]] = Field(default_factory=list)
    identifiers: list[dict[str, Any]] = Field(default_factory=list)
    search_log: list[dict[str, Any]] = Field(default_factory=list)
    field_dictionary: list[dict[str, Any]] = Field(default_factory=list)
    ontology_relations: list[dict[str, Any]] = Field(default_factory=list)
    display_data: dict[str, Any] = Field(default_factory=dict)
    validation_report: LocalizedText = ""
    generation_template: dict[str, Any] = Field(default_factory=dict)

    @field_validator("package_id")
    @classmethod
    def canonical_package_id(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("package ID must not contain surrounding whitespace")
        return value


def package_schema_version(package: dict) -> str:
    if "schema_version" not in package:
        return "1.0"
    version = package["schema_version"]
    if not isinstance(version, str) or version not in SUPPORTED_SCHEMA_VERSIONS:
        display = version if version not in (None, "") else "<empty>"
        raise ResearchPackageValidationError(f"Unsupported research package schema_version: {display}")
    return version


def _localized(value: object, language: str) -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("zh-CN") or value.get("en") or value.get("zh") or "")
    return str(value or "")


def _valid_trusted_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED_REFERENCE_HOSTS:
        return False
    path = unquote(parsed.path).strip("/")
    if not path:
        return False
    if parsed.hostname in {"doi.org", "dx.doi.org"}:
        return bool(DOI_PATTERN.fullmatch(path))
    if parsed.hostname == "pubmed.ncbi.nlm.nih.gov":
        return bool(PMID_PATTERN.fullmatch(path.split("/", 1)[0]))
    return True


def _has_reference_locator(reference: dict) -> bool:
    pmid = str(reference.get("pmid") or "")
    doi = str(reference.get("doi") or "")
    if pmid and PMID_PATTERN.fullmatch(pmid):
        return True
    if doi and DOI_PATTERN.fullmatch(doi):
        return True
    return any(
        _valid_trusted_url(str(reference.get(field) or ""))
        for field in ("url", "pubmed_url", "doi_url", "pmc_url", "source_url")
    )


def _validate_bibliography(
    project: dict,
    expected_reference_ids: set[str],
) -> None:
    project_id = str(project["id"])
    for language, heading in (("zh", "## 参考文献"), ("en", "## References")):
        review = _localized(project.get("project_review"), language)
        lines = review.splitlines()
        if lines.count(heading) != 1:
            raise ResearchPackageValidationError(
                f"Project {project_id} {language} review must contain exactly one {heading} heading"
            )
        section = "\n".join(lines[lines.index(heading) + 1 :])
        section = re.split(r"(?m)^##\s+", section, maxsplit=1)[0]
        occurrences = Counter(re.findall(r"(?m)^([A-Za-z][A-Za-z0-9_-]*)\.\s", section))
        if set(occurrences) != expected_reference_ids or any(count != 1 for count in occurrences.values()):
            raise ResearchPackageValidationError(
                f"Project {project_id} {language} bibliography must list each visible reference exactly once"
            )


def normalize_research_package(package: dict) -> tuple[dict, str]:
    schema_version = package_schema_version(package)
    candidate = {**package, "schema_version": schema_version}
    try:
        normalized = ResearchPackage.model_validate(candidate).model_dump(mode="python")
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ResearchPackageValidationError(f"Invalid research package field {location}: {first['msg']}") from exc

    projects = normalized["projects"]
    project_ids = [item["id"] for item in projects]
    if len(project_ids) != len(set(project_ids)):
        raise ResearchPackageValidationError("Project IDs must be non-empty and unique")
    project_id_set = set(project_ids)

    references_by_id: dict[str, dict] = {}
    for reference in normalized["references"]:
        ref_id = reference["ref_id"]
        if ref_id in references_by_id:
            raise ResearchPackageValidationError("Reference IDs must be non-empty and unique")
        assigned = reference["project_ids"]
        if any(project_id not in project_id_set for project_id in assigned):
            raise ResearchPackageValidationError(
                f"Reference {ref_id} must belong to one or more unique declared projects"
            )
        if not _has_reference_locator(reference):
            raise ResearchPackageValidationError(
                f"Reference {ref_id} must provide a valid PMID, DOI, or trusted HTTPS source URL"
            )
        verification_status = reference["verification_status"].lower()
        if verification_status not in TRUSTED_VERIFICATION_STATUSES:
            raise ResearchPackageValidationError(
                f"Reference {ref_id} verification status must be one of {sorted(TRUSTED_VERIFICATION_STATUSES)}"
            )
        references_by_id[ref_id] = reference

    for project in projects:
        project_id = project["id"]
        expected = {
            ref_id
            for ref_id, reference in references_by_id.items()
            if project_id in reference["project_ids"]
        }
        if not expected:
            raise ResearchPackageValidationError(f"Project {project_id} must have at least one visible reference")
        if schema_version == "1.1":
            _validate_bibliography(project, expected)

    def require_reference(ref_id: object, project_id: str, source: str) -> None:
        key = str(ref_id or "")
        reference = references_by_id.get(key)
        if reference is None or project_id not in reference["project_ids"]:
            raise ResearchPackageValidationError(
                f"{source} references {key or '<empty>'}, which is not visible in project {project_id}"
            )

    claim_ids: set[str] = set()
    for edge in normalized["edges"]:
        claim_id = edge["claim_id"]
        if claim_id in claim_ids:
            raise ResearchPackageValidationError("Edge claim IDs must be non-empty and unique")
        claim_ids.add(claim_id)
        project_id = edge["project"]
        if project_id not in project_id_set:
            raise ResearchPackageValidationError(f"Edge {claim_id} has an unknown project")
        require_reference(edge["ref_id"], project_id, f"Edge {claim_id}")

    for project in projects:
        project_id = project["id"]
        pdb_ids: set[str] = set()
        for structure in project["structures"]:
            pdb_id = structure["pdb_id"].upper()
            if pdb_id in pdb_ids:
                raise ResearchPackageValidationError(f"Project {project_id} structure PDB IDs must be unique")
            pdb_ids.add(pdb_id)
            require_reference(structure["reference_id"], project_id, f"Structure {pdb_id}")
        primary_pdb_id = project["primary_target"].get("pdb_id")
        if primary_pdb_id and primary_pdb_id.upper() not in pdb_ids:
            raise ResearchPackageValidationError(
                f"Project {project_id} primary target PDB ID must exist in project structures"
            )

    candidate_ids: set[str] = set()
    for candidate_item in normalized["candidates"]:
        candidate_id = candidate_item["candidate_id"]
        if candidate_id in candidate_ids:
            raise ResearchPackageValidationError("Candidate IDs must be non-empty and unique")
        candidate_ids.add(candidate_id)
        project_id = candidate_item["project_id"]
        reference_ids = candidate_item["reference_ids"].split(";")
        if not project_id:
            visible_projects = set(project_id_set)
            for ref_id in reference_ids:
                reference = references_by_id.get(ref_id)
                if reference is None:
                    visible_projects.clear()
                    break
                visible_projects.intersection_update(reference["project_ids"])
            if len(visible_projects) != 1:
                raise ResearchPackageValidationError(
                    f"Candidate {candidate_id} must declare project_id when its references "
                    "do not identify exactly one project"
                )
            project_id = visible_projects.pop()
            candidate_item["project_id"] = project_id
        if project_id not in project_id_set:
            raise ResearchPackageValidationError(
                f"Candidate {candidate_id} references unknown project {project_id}"
            )
        for ref_id in reference_ids:
            require_reference(ref_id, project_id, f"Candidate {candidate_id}")

    return normalized, schema_version


def validate_research_package(package: dict) -> str:
    _, schema_version = normalize_research_package(package)
    return schema_version


def _numeric_canonical(value: object) -> object:
    if isinstance(value, dict):
        return {key: _numeric_canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_numeric_canonical(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def research_package_checksum(package: dict) -> str:
    """Hash the semantic content of a normalized research package.

    Whole-number floats are folded to ints before hashing. The browser posts the
    bundled package after `JSON.stringify`, which has no float/int distinction,
    so a `76.0` in the committed file arrives here as `76`. Hashing the raw
    serialization would make the package we ship fail its own trust check, and
    `76` and `76.0` carry no different meaning to any consumer of the package.
    """
    return hashlib.sha256(
        json.dumps(
            _numeric_canonical(package),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
