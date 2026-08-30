"""Pure helpers from `research.package_import`, tested without the data store.

The package-import suite that exercised these needs research working data, so it
skips on CI and on any clone — which left these defensive branches uncovered in
exactly the environment the coverage gate runs in. They are pure functions over
a row, so they need no fixture at all.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.compute.models import OutboxEvent
from backend_v2.app.literature.models import LiteratureDocument
from backend_v2.app.platform.models import Operation
from backend_v2.app.projects.models import Project
from backend_v2.app.research.models import ResearchFinding
from backend_v2.app.research.package_import import (
    BUILTIN_RESEARCH_PACKAGE_PREFIXES,
    _candidate_card,
    _managed_package_match,
    _project_completeness_score,
    _project_package_meta,
    _reconcile_managed_project,
    _structure_operations,
    _upsert_candidates,
)
from backend_v2.app.targets.models import Target


def _project(localized_content: object) -> Project:
    """An in-memory row. Never flushed, so no session and no NOT NULL to satisfy."""
    return Project(localized_content=localized_content)


def test_package_meta_reads_the_nested_package_block() -> None:
    project = _project({"package": {"id": "pkg-1", "version": 3}})
    assert _project_package_meta(project) == {"id": "pkg-1", "version": 3}


def test_package_meta_tolerates_content_that_is_not_a_mapping() -> None:
    """`localized_content` is a JSON column: a row written by an older importer,
    or by hand, can hold a list or a string. Reading it must not raise, because
    the caller is deciding whether to *adopt* that project."""
    for content in ([], "not-a-dict", None, 42):
        assert _project_package_meta(_project(content)) == {}


def test_package_meta_tolerates_a_package_key_that_is_not_a_mapping() -> None:
    assert _project_package_meta(_project({"package": ["wrong", "shape"]})) == {}
    assert _project_package_meta(_project({"package": None})) == {}


def test_package_meta_is_empty_when_there_is_no_package_block() -> None:
    assert _project_package_meta(_project({"name": {"en": "A project"}})) == {}


def test_managed_match_accepts_an_exact_package_id() -> None:
    assert _managed_package_match("pkg-42", "pkg-42") is True
    assert _managed_package_match("pkg-42", "pkg-99") is False


def test_managed_match_treats_versions_in_one_builtin_family_as_managed() -> None:
    """Built-in packages are re-published under changing ids, so a row pinned to
    an older built-in id still belongs to the built-in package being imported."""
    older = f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[0]}-older-build"
    current = f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[0]}-current-build"
    assert _managed_package_match(older, current) is True
    assert _managed_package_match(older, "another-built-in-current") is False
    # A user-uploaded package gets no such latitude.
    assert _managed_package_match(older, "user-uploaded-pkg") is False


def test_managed_match_handles_a_missing_row_value() -> None:
    assert _managed_package_match(None, "pkg-42") is False
    assert _managed_package_match(None, f"{BUILTIN_RESEARCH_PACKAGE_PREFIXES[0]}-x") is False


def test_candidate_card_extracts_one_markdown_section() -> None:
    review = {
        "en": "# Review\n## C-1\nFirst card\n\n## C-2\nSecond card",
        "zh": "# 综述\n## C-1\n第一张卡",
    }

    assert _candidate_card(review, "C-1", "en") == "## C-1\nFirst card"
    assert _candidate_card(review, "missing", "en") == ""


def test_project_completeness_score_is_stable_and_total_ordered() -> None:
    session = Mock()
    session.scalar.side_effect = [3, 2, 4, 5, 6]
    project_id = uuid.uuid4()
    updated_at = datetime(2026, 8, 30, tzinfo=UTC)
    project = Project(id=project_id, primary_target_id=uuid.uuid4(), updated_at=updated_at)

    assert _project_completeness_score(session, project) == (
        3,
        2,
        4,
        5,
        6,
        1,
        updated_at.isoformat(),
        str(project_id),
    )


def _candidate_package() -> tuple[dict, dict]:
    candidate = {
        "candidate_id": "C-1",
        "project_id": "TARGETS",
        "target": {"zh": "候选一", "en": "Candidate one"},
        "group": {"zh": "优先组", "en": "Priority"},
        "protein_type": {"zh": "受体", "en": "Receptor"},
        "localization": {"zh": "膜", "en": "Membrane"},
        "axis": {"zh": "免疫", "en": "Immune"},
        "rank_in_group": 1,
        "gene": "GENE1",
        "reference_ids": "R1;R2",
        "weighted_score": 9.5,
        "evidence": 4,
        "novelty": 3,
        "tractability": 5,
        "human": 4,
        "specificity": 3,
        "safety": 2,
        "scored_at": "2026-08-30",
        "rubric_version": "v1",
    }
    package = {
        "package_id": "private-target-catalog-v1",
        "schema_version": "1.0",
        "candidates": [candidate],
        "bibliometrics": [{"id": "C-1", "paper_count": 7}],
    }
    source = {
        "project_review": {
            "zh": "## C-1\n中文卡片",
            "en": "## C-1\nEnglish card",
        }
    }
    return package, source


def test_candidate_upsert_covers_create_update_and_other_project_paths() -> None:
    package, source = _candidate_package()
    project = Project(id=uuid.uuid4(), source_project_key="TARGETS")
    session = Mock()
    session.scalars.return_value = []

    assert _upsert_candidates(session, project, package, source) == 1
    created = session.add.call_args.args[0]
    assert isinstance(created, Candidate)
    assert created.rank == 1
    assert created.properties["bibliometrics"]["paper_count"] == 7
    assert created.properties["pain_group"] == "优先组"
    assert created.properties["localized_content"]["research_card"]["en"].startswith("## C-1")

    existing = Candidate(
        id=uuid.uuid4(),
        project_id=project.id,
        candidate_key="C-1",
        name="old",
        candidate_kind="design_candidate",
        status="draft",
        rank=9,
        score=1.0,
        scores={},
        properties={},
        version=1,
    )
    session.scalars.return_value = [existing]
    assert _upsert_candidates(session, project, package, source) == 1
    assert existing.name == "候选一"
    assert existing.version == 2

    project.source_project_key = "OTHER"
    assert _upsert_candidates(session, project, package, source) == 0


def test_reconcile_removes_only_stale_package_managed_rows() -> None:
    project_id = uuid.uuid4()
    target = Target(
        id=uuid.uuid4(),
        project_id=project_id,
        name="Target",
        structure_artifact_id=uuid.uuid4(),
        structure_status="available",
        version=1,
    )
    project = Project(id=project_id, primary_target_id=target.id)
    stale_finding = ResearchFinding(
        id=uuid.uuid4(),
        project_id=project_id,
        evidence={"package_id": "pd1-demo-old", "claim_id": "STALE"},
    )
    stale_candidate = Candidate(
        id=uuid.uuid4(),
        project_id=project_id,
        candidate_key="STALE",
        properties={"source_package_id": "pd1-demo-old"},
    )
    stale_document = LiteratureDocument(
        id=uuid.uuid4(),
        project_id=project_id,
        external_id="STALE",
        metadata_json={"package_id": "pd1-demo-old"},
    )
    stale_artifact = Artifact(
        id=target.structure_artifact_id,
        project_id=project_id,
        artifact_type="target_structure",
        deleted_at=None,
        lineage={"source_package_id": "pd1-demo-old", "pdb_id": "OLD1"},
        version=1,
    )
    stale_operation = Operation(
        id=uuid.uuid4(),
        project_id=project_id,
        kind="target.structure.import",
        status="pending",
        progress={"source_package_id": "pd1-demo-old", "pdb_id": "OLD2"},
        version=1,
    )
    event = OutboxEvent(id=stale_operation.id, published_at=None)
    session = Mock()
    session.scalars.side_effect = [
        [stale_finding],
        [stale_candidate],
        [stale_document],
        [stale_artifact],
        [stale_operation],
    ]
    session.get.side_effect = lambda model, _id: target if model is Target else event
    package = {
        "package_id": "pd1-demo-v1",
        "edges": [{"project": "PD1", "claim_id": "CURRENT"}],
        "candidates": [],
        "references": [{"project_ids": ["PD1"], "ref_id": "CURRENT"}],
        "projects": [{"id": "PD1", "structures": [{"pdb_id": "NEW1"}]}],
    }

    _reconcile_managed_project(session, project, package, "PD1")

    deleted = [call.args[0] for call in session.delete.call_args_list]
    assert {stale_finding, stale_candidate, stale_document, event}.issubset(set(deleted))
    assert stale_artifact.deleted_at is not None
    assert target.structure_artifact_id is None
    assert stale_operation.status == "cancelled"


def test_structure_operations_skip_blank_existing_and_pending_structures(monkeypatch) -> None:
    project = Project(id=uuid.uuid4(), organization_id=uuid.uuid4())
    target = Target(id=uuid.uuid4(), project_id=project.id, name="Target")
    existing = Artifact(
        id=uuid.uuid4(),
        project_id=project.id,
        artifact_type="target_structure",
        lineage={"pdb_id": "EXIST"},
        version=1,
    )
    pending = Operation(progress={"pdb_id": "WAIT"})
    session = Mock()
    session.scalars.side_effect = [[existing], [pending]]
    enqueue = Mock()
    monkeypatch.setattr("backend_v2.app.research.package_import.enqueue_operation", enqueue)
    source = {
        "id": "PD1",
        "primary_target": {"pdb_id": "WAIT"},
        "structures": [
            {"pdb_id": ""},
            {"pdb_id": "exist", "name": "Existing", "method": "demo"},
            {"pdb_id": "wait"},
        ],
    }

    result = _structure_operations(
        session,
        project,
        target,
        source,
        {"package_id": "pd1-demo-v1", "schema_version": "1.0"},
        Mock(id=uuid.uuid4()),
    )

    assert result == []
    assert existing.lineage["source_package_id"] == "pd1-demo-v1"
    assert existing.version == 2
    enqueue.assert_not_called()
