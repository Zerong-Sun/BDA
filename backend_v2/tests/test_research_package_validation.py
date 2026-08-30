from __future__ import annotations

import copy

import pytest
from backend_v2.app.research.package_validation import (
    ResearchPackageValidationError,
    normalize_research_package,
    research_package_checksum,
    validate_research_package,
)


def minimal_package(*, schema_version: str | None = "1.1") -> dict:
    review = {
        "zh": "# 项目\n\n## 参考文献\n\nR001. 可追溯文献。",
        "en": "# Project\n\n## References\n\nR001. Traceable reference.",
    }
    package = {
        "package_id": "test-package",
        "version": "1.0.0",
        "projects": [
            {
                "id": "BASE",
                "name": "Base project",
                "project_type": "research",
                "summary": "Summary",
                "project_review": review,
                "primary_target": {
                    "name": "Target",
                    "gene": "GENE",
                    "uniprot": "P00001",
                    "organism": "Homo sapiens",
                    "pdb_id": None,
                },
                "structures": [],
            }
        ],
        "references": [
            {
                "ref_id": "R001",
                "project_ids": ["BASE"],
                "role": "supporting",
                "pmid": "1",
                "verification_status": "verified_europe_pmc",
                "title": "Traceable reference",
            }
        ],
        "edges": [],
        "candidates": [],
    }
    if schema_version is not None:
        package["schema_version"] = schema_version
    return package


def duplicate_edges(package: dict) -> None:
    edge = {
        "claim_id": "CL001",
        "project": "BASE",
        "subject": "Target",
        "predicate": "binds",
        "object": "Ligand",
        "context": "Context",
        "assertion": "established_fact",
        "grade": "A",
        "ref_id": "R001",
        "summary": "Summary",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/1/",
        "metadata_verification": "verified_europe_pmc",
    }
    package["edges"] = [edge, copy.deepcopy(edge)]


def duplicate_structures(package: dict) -> None:
    structure = {
        "pdb_id": "1ABC",
        "name": "Structure",
        "method": "X-ray",
        "resolution": 2.0,
        "role": "Binding",
        "reference_id": "R001",
    }
    package["projects"][0]["structures"] = [structure, copy.deepcopy(structure)]


def candidate_payload(*, candidate_id: str = "C01", reference_ids: str = "R001") -> dict:
    return {
        "candidate_id": candidate_id,
        "pain_group": "Neuropathic pain",
        "target": "Target",
        "gene": "GENE",
        "protein_type": "Protein",
        "localization": "Membrane",
        "axis": "Axis",
        "weighted_score": 80.0,
        "evidence": 4.0,
        "novelty": 4.0,
        "tractability": 4.0,
        "human": 4.0,
        "specificity": 4.0,
        "safety": 4.0,
        "reference_ids": reference_ids,
    }


def duplicate_candidates(package: dict) -> None:
    package["projects"][0]["id"] = "PAIN"
    package["references"][0]["project_ids"] = ["PAIN"]
    candidate = candidate_payload()
    package["candidates"] = [candidate, copy.deepcopy(candidate)]


def test_schema_1_0_remains_compatible_without_embedded_bibliography() -> None:
    package = minimal_package(schema_version=None)
    package["projects"][0]["project_review"] = {"zh": "# 旧版项目", "en": "# Legacy project"}

    assert validate_research_package(package) == "1.0"


def test_localized_string_review_and_trusted_url_reference_are_supported() -> None:
    package = minimal_package()
    package["projects"][0]["project_review"] = (
        "# Project\n\n## 参考文献\n\nR001. Reference.\n\n## References\n\nR001. Reference."
    )
    package["references"][0].update(
        pmid="",
        doi="",
        pubmed_url="https://pubmed.ncbi.nlm.nih.gov/1/",
    )

    assert validate_research_package(package) == "1.1"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda package: package.update(schema_version="2.0"), "Unsupported"),
        (lambda package: package.update(projects=[]), "projects"),
        (
            lambda package: package["projects"].append(copy.deepcopy(package["projects"][0])),
            "Project IDs must be",
        ),
        (lambda package: package.update(references="invalid"), "references"),
        (lambda package: package.update(references=["invalid"]), "references.0"),
        (
            lambda package: package["references"].append(copy.deepcopy(package["references"][0])),
            "Reference IDs must be",
        ),
        (
            lambda package: package["references"][0].update(project_ids=["BASE", "BASE"]),
            "project_ids",
        ),
        (
            lambda package: package["references"][0].update(
                pmid="",
                doi="",
                pubmed_url="https://example.com/not-trusted",
                doi_url="",
                pmc_url="",
            ),
            "valid PMID, DOI",
        ),
        (
            lambda package: package["references"][0].update(verification_status="pending"),
            "verification status",
        ),
        (
            lambda package: package["projects"][0]["project_review"].update(
                zh=package["projects"][0]["project_review"]["zh"].replace("## 参考文献", "正文")
            ),
            "exactly one",
        ),
        (
            lambda package: package["projects"][0]["project_review"].update(
                zh=package["projects"][0]["project_review"]["zh"] + "\nR001. Duplicate."
            ),
            "exactly once",
        ),
        (lambda package: package.update(edges={}), "edges"),
        (lambda package: package.update(edges=["invalid"]), "edges.0"),
        (
            lambda package: package["edges"].append(
                {**duplicate_edge_payload(), "project": "UNKNOWN"}
            ),
            "unknown project",
        ),
        (duplicate_edges, "claim IDs must be"),
        (
            lambda package: package["projects"][0].update(structures={}),
            "structures",
        ),
        (
            lambda package: package["projects"][0].update(structures=["invalid"]),
            "structures.0",
        ),
        (duplicate_structures, "structure PDB IDs must be unique"),
        (lambda package: package.update(candidates={}), "candidates"),
        (lambda package: package.update(candidates=["invalid"]), "candidates.0"),
        (duplicate_candidates, "Candidate IDs must be"),
    ],
)
def test_invalid_package_shapes_are_rejected(mutate, message) -> None:
    package = minimal_package()
    mutate(package)

    with pytest.raises(ResearchPackageValidationError, match=message):
        validate_research_package(package)


def test_project_without_references_is_rejected() -> None:
    package = minimal_package()
    project = copy.deepcopy(package["projects"][0])
    project["id"] = "EMPTY"
    project["project_review"] = {"zh": "# 空项目", "en": "# Empty project"}
    package["projects"].append(project)

    with pytest.raises(ResearchPackageValidationError, match="EMPTY must have at least one"):
        validate_research_package(package)


@pytest.mark.parametrize(
    "reference_ids",
    ["", "R001;R001", "R999"],
)
def test_candidate_references_must_be_unique_and_visible(reference_ids: str) -> None:
    package = minimal_package()
    package["projects"][0]["id"] = "PAIN"
    package["references"][0]["project_ids"] = ["PAIN"]
    package["candidates"] = [candidate_payload(reference_ids=reference_ids)]

    with pytest.raises(ResearchPackageValidationError):
        validate_research_package(package)


def test_candidates_require_the_pain_project() -> None:
    package = minimal_package()
    package["candidates"] = [candidate_payload()]

    with pytest.raises(ResearchPackageValidationError, match="require a PAIN project"):
        validate_research_package(package)


def test_primary_target_pdb_must_be_present_in_project_structures() -> None:
    package = minimal_package()
    package["projects"][0]["primary_target"]["pdb_id"] = "1ABC"

    with pytest.raises(ResearchPackageValidationError, match="primary target PDB ID"):
        validate_research_package(package)


def duplicate_edge_payload() -> dict:
    edge_package = minimal_package()
    duplicate_edges(edge_package)
    return edge_package["edges"][0]


@pytest.mark.parametrize("schema_version", ["", None, 1.1, " 1.1 "])
def test_explicit_invalid_schema_versions_are_rejected(schema_version: object) -> None:
    package = minimal_package()
    package["schema_version"] = schema_version

    with pytest.raises(ResearchPackageValidationError, match="Unsupported"):
        validate_research_package(package)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda package: package["projects"][0].update(primary_target=None),
        lambda package: package["candidates"].append(
            {**candidate_payload(), "weighted_score": "not-a-number"}
        ),
        lambda package: package["references"][0].update(
            pmid="not-a-pmid",
            doi="",
            pubmed_url="",
            doi_url="",
            pmc_url="",
            verification_status="verified_by_caller",
        ),
        lambda package: package["references"][0].update(ref_id=" R001 "),
        lambda package: package["projects"][0].update(name="x" * 201),
    ],
)
def test_import_consumed_fields_and_identifiers_are_strictly_validated(mutate) -> None:
    package = minimal_package()
    mutate(package)

    with pytest.raises(ResearchPackageValidationError):
        validate_research_package(package)


def test_project_methods_override_survives_normalization() -> None:
    package = minimal_package()
    package["methods"] = {"zh": "包级方法", "en": "Package methods"}
    package["projects"][0]["methods"] = {"zh": "项目级方法", "en": "Project methods"}

    normalized, _ = normalize_research_package(package)

    assert normalized["projects"][0]["methods"] == {"zh": "项目级方法", "en": "Project methods"}
    assert normalized["methods"] == {"zh": "包级方法", "en": "Package methods"}


def test_projects_without_a_methods_override_normalize_to_empty() -> None:
    package = minimal_package()

    normalized, _ = normalize_research_package(package)

    assert normalized["projects"][0]["methods"] == ""


def test_checksum_folds_whole_number_floats_to_ints() -> None:
    as_float = {"score": 76.0, "nested": {"values": [1.0, 2.5]}}
    as_int = {"score": 76, "nested": {"values": [1, 2.5]}}

    assert research_package_checksum(as_float) == research_package_checksum(as_int)


def test_checksum_distinguishes_non_whole_floats() -> None:
    assert research_package_checksum({"score": 76.5}) != research_package_checksum({"score": 76})


def test_checksum_ignores_key_order() -> None:
    assert research_package_checksum({"a": 1, "b": 2}) == research_package_checksum({"b": 2, "a": 1})


def test_checksum_is_sensitive_to_content_changes() -> None:
    assert research_package_checksum({"a": 1}) != research_package_checksum({"a": 2})
