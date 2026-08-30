from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..candidates.models import Candidate
from ..compute.models import OutboxEvent
from ..core.problem import DomainError
from ..identity.models import User
from ..knowledge.models import KnowledgeEntry
from ..literature.models import LiteratureDocument
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..projects.repository import ProjectRepository
from ..projects.schemas import ProjectCreate
from ..projects.service import create_project, soft_delete_builtin_research_duplicates
from ..targets.models import Target
from ..targets.repository import TargetRepository
from .models import ResearchBrief, ResearchFinding
from .package_validation import (
    TRUSTED_BUILTIN_PACKAGE_CHECKSUMS,
    ResearchPackageValidationError,
    normalize_research_package,
    research_package_checksum,
)
from .schemas import (
    ResearchPackageImportCreate,
    ResearchPackageImportResponse,
    ResearchPackageProjectResult,
)

BUILTIN_RESEARCH_PACKAGE_PREFIXES = ("pd1-demo",)


def _builtin_package_family(package_id: str) -> str | None:
    return next((prefix for prefix in BUILTIN_RESEARCH_PACKAGE_PREFIXES if package_id.startswith(prefix)), None)


def _localized(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        zh = str(value.get("zh") or value.get("zh-CN") or value.get("en") or "")
        en = str(value.get("en") or value.get("zh") or value.get("zh-CN") or "")
        return {"zh": zh, "en": en}
    text = str(value or "")
    return {"zh": text, "en": text}


def _text(value: object, language: str = "zh") -> str:
    return _localized(value)[language]


def _update_versioned(row: object, **values: object) -> bool:
    changed = False
    for field, value in values.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True
    if changed and getattr(row, "id", None) is not None:
        row.version += 1  # type: ignore[attr-defined]
    return changed


def _reference_projects(reference: dict, projects: list[dict]) -> list[str]:
    explicit = reference.get("project_ids")
    available = {str(item.get("id")) for item in projects}
    return [str(item) for item in explicit if str(item) in available] if isinstance(explicit, list) else []


def _candidate_card(project_review: object, candidate_id: str, language: str) -> str:
    content = _text(project_review, language)
    match = re.search(
        rf"(?ms)^##\s+{re.escape(candidate_id)}\b.*?(?=^##\s+|\Z)",
        content,
    )
    return match.group(0).strip() if match else ""


def _is_builtin_package_id(package_id: str) -> bool:
    return _builtin_package_family(package_id) is not None


def _managed_package_match(value: object, package_id: str) -> bool:
    row_package_id = str(value or "")
    if row_package_id == package_id:
        return True
    family = _builtin_package_family(package_id)
    return family is not None and row_package_id.startswith(family)


def _project_package_meta(project: Project) -> dict:
    localized = project.localized_content if isinstance(project.localized_content, dict) else {}
    package = localized.get("package", {})
    return package if isinstance(package, dict) else {}


def _project_completeness_score(session: Session, project: Project) -> tuple[int, int, int, int, int, int, str, str]:
    def count(model, *criteria) -> int:
        return int(session.scalar(select(func.count(model.id)).where(*criteria)) or 0)

    candidates = count(Candidate, Candidate.project_id == project.id, Candidate.candidate_kind == "research_target")
    structures = count(
        Artifact,
        Artifact.project_id == project.id,
        Artifact.artifact_type == "target_structure",
        Artifact.deleted_at.is_(None),
    )
    references = count(LiteratureDocument, LiteratureDocument.project_id == project.id)
    findings = count(ResearchFinding, ResearchFinding.project_id == project.id)
    knowledge = count(KnowledgeEntry, KnowledgeEntry.project_id == project.id)
    return (
        candidates,
        structures,
        references,
        findings,
        knowledge,
        int(project.primary_target_id is not None),
        project.updated_at.isoformat(),
        str(project.id),
    )


def _versioned_package_project(
    session: Session,
    organization_id: uuid.UUID,
    package_id: str,
    project_key: str,
) -> Project | None:
    if not _is_builtin_package_id(package_id):
        return None
    rows = list(
        session.scalars(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
                Project.source_project_key == project_key,
                or_(*(Project.source_package_id.startswith(prefix) for prefix in BUILTIN_RESEARCH_PACKAGE_PREFIXES)),
            )
        )
    )
    return max(rows, key=lambda item: _project_completeness_score(session, item)) if rows else None


def _legacy_package_project(
    session: Session,
    organization_id: uuid.UUID,
    package_id: str,
    source: dict,
) -> Project | None:
    names = {value for value in _localized(source.get("name")).values() if value}
    if not names:
        return None
    candidates = list(
        session.scalars(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
                Project.source_package_id.is_(None),
                Project.name.in_(names),
            )
        )
    )
    for project in candidates:
        findings = session.scalars(select(ResearchFinding).where(ResearchFinding.project_id == project.id))
        if any((finding.evidence or {}).get("package_id") == package_id for finding in findings):
            project.source_package_id = package_id
            project.source_project_key = str(source.get("id") or "")
            project.version += 1
            return project
    return None


def _package_claim_lineage_project(
    session: Session,
    organization_id: uuid.UUID,
    package: dict,
    project_key: str,
) -> Project | None:
    """Reuse a user-owned project that already carries this package's claims.

    Builtin imports must not create a duplicate research project when an
    existing user/design/copilot project has already adopted the curated package
    content for the same topic. A project is adopted when it carries at least one
    finding tagged to this package family and either:

      * a claim-level lineage match (the finding's claim_id belongs to this
        package project), or
      * the project name matches the package project name (covers projects whose
        package-tagged content was created by the copilot flow without claim_ids).

    Adopted projects keep their own name, summary, project type and primary target,
    and are flagged so later imports reconcile content without mutating identity.
    """
    package_id = str(package["package_id"])
    source = next((item for item in package.get("projects", []) if str(item.get("id")) == project_key), None)
    project_names = {value for value in _localized(source.get("name")).values() if value} if source else set()
    desired_claims = {
        str(edge["claim_id"])
        for edge in package.get("edges", [])
        if str(edge.get("project")) == project_key
    }
    if not desired_claims and not project_names:
        return None
    rows = list(
        session.scalars(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
            )
        )
    )
    for project in rows:
        if project.source_package_id == package_id or _is_builtin_package_id(str(project.source_package_id or "")):
            continue
        findings = session.scalars(select(ResearchFinding).where(ResearchFinding.project_id == project.id))
        managed = [
            finding
            for finding in findings
            if _managed_package_match((finding.evidence or {}).get("package_id"), package_id)
        ]
        if not managed:
            continue
        covered = {
            str((finding.evidence or {}).get("claim_id"))
            for finding in managed
            if (finding.evidence or {}).get("claim_id")
        }
        matched = bool(desired_claims.intersection(covered))
        if not matched and project_names:
            lower = {name.casefold() for name in project_names}
            matched = (project.name or "").strip().casefold() in lower
        if matched:
            localized = dict(project.localized_content) if isinstance(project.localized_content, dict) else {}
            localized["adopted_user_project"] = True
            project.localized_content = localized
            project.version += 1
            return project
    return None


def _upsert_target(session: Session, project: Project, payload: dict) -> Target:
    repo = TargetRepository(session)
    target = repo.by_project(project.id)
    if target is None:
        target = Target(project_id=project.id, name=_text(payload.get("name")))
        repo.add(target)
    accession = str(payload.get("uniprot") or "") or None
    _update_versioned(
        target,
        name=_text(payload.get("name")),
        uniprot_accession=accession,
        organism=str(payload.get("organism") or "") or None,
        identity_status="confirmed" if accession else "unconfirmed",
    )
    if project.primary_target_id != target.id:
        project.primary_target_id = target.id
        project.version += 1
    return target


def _upsert_brief(session: Session, project: Project, package_id: str, source: dict) -> None:
    rows = list(session.scalars(select(ResearchBrief).where(ResearchBrief.project_id == project.id)))
    brief = next((row for row in rows if _managed_package_match(row.scope.get("package_id"), package_id)), None)
    localized = {
        "title": {
            "zh": f"{_text(source.get('name'), 'zh')} — 项目综述",
            "en": f"{_text(source.get('name'), 'en')} — Project Review",
        },
        "content": _localized(source.get("project_review")),
    }
    scope = {"package_id": package_id, "source_project_key": source.get("id"), "localized_content": localized}
    if brief is None:
        session.add(
            ResearchBrief(
                project_id=project.id,
                title=f"{_text(source.get('name'))} — Project Review",
                content=localized["content"]["zh"],
                scope=scope,
                status="accepted",
                created_by=project.owner_id,
            )
        )
    else:
        _update_versioned(
            brief,
            title=f"{_text(source.get('name'))} — Project Review",
            content=localized["content"]["zh"],
            scope=scope,
            status="accepted",
        )


def _upsert_findings(
    session: Session,
    project: Project,
    package: dict,
    source_project_key: str,
) -> int:
    package_id = str(package["package_id"])
    rows = list(session.scalars(select(ResearchFinding).where(ResearchFinding.project_id == project.id)))
    by_claim = {
        str(row.evidence.get("claim_id")): row
        for row in rows
        if _managed_package_match(row.evidence.get("package_id"), package_id) and row.evidence.get("claim_id")
    }
    count = 0
    for edge in package.get("edges", []):
        if str(edge.get("project")) != source_project_key:
            continue
        claim_id = str(edge.get("claim_id"))
        localized = {
            "title": {
                "zh": f"{edge.get('subject')} —{edge.get('predicate')}→ {edge.get('object')}",
                "en": f"{edge.get('subject')} —{edge.get('predicate')}→ {edge.get('object')}",
            },
            "content": {
                "zh": f"{_text(edge.get('summary'), 'zh')}\n\nContext: {_text(edge.get('context'), 'zh')}",
                "en": f"{_text(edge.get('summary'), 'en')}\n\nContext: {_text(edge.get('context'), 'en')}",
            },
        }
        evidence = {
            "package_id": package_id,
            "package_schema_version": package.get("schema_version") or "1.0",
            "package_version": package.get("version"),
            "claim_id": claim_id,
            "subject": edge.get("subject"),
            "predicate": edge.get("predicate"),
            "object": edge.get("object"),
            "evidence_level": edge.get("grade"),
            "assertion_class": edge.get("assertion"),
            "source_refs": [edge.get("source_url")],
            "reference_ids": [edge.get("ref_id")],
            "ref_id": edge.get("ref_id"),
            "localized_subject": _localized(edge.get("subject")),
            "localized_object": _localized(edge.get("object")),
            "localized_summary": _localized(edge.get("summary")),
            "localized_context": _localized(edge.get("context")),
            "metadata_verification": edge.get("metadata_verification"),
            "review_status": "pending_review" if edge.get("assertion") == "hypothesis" else "accepted",
            "localized_content": localized,
        }
        row = by_claim.get(claim_id)
        if row is None:
            session.add(
                ResearchFinding(
                    project_id=project.id,
                    finding_type="target_mechanism_structure",
                    title=localized["title"]["zh"],
                    content=localized["content"]["zh"],
                    evidence=evidence,
                    created_by=project.owner_id,
                )
            )
        else:
            _update_versioned(
                row,
                title=localized["title"]["zh"],
                content=localized["content"]["zh"],
                evidence=evidence,
            )
        count += 1
    return count


def _upsert_candidates(session: Session, project: Project, package: dict, project_source: dict) -> int:
    project_candidates = [
        item
        for item in package.get("candidates", [])
        if str(item.get("project_id") or "") == str(project.source_project_key or "")
    ]
    rows = list(session.scalars(select(Candidate).where(Candidate.project_id == project.id)))
    by_key = {row.candidate_key: row for row in rows}
    bibliometrics = {str(item.get("id")): item for item in package.get("bibliometrics", [])}
    ranked = sorted(project_candidates, key=lambda item: float(item.get("weighted_score", 0)), reverse=True)
    rank_by_key = {str(item.get("candidate_id")): index + 1 for index, item in enumerate(ranked)}
    for item in project_candidates:
        key = str(item.get("candidate_id"))
        localized = {
            "name": _localized(item.get("target")),
            # The public workspace API retains the historical `pain_group`
            # field name for compatibility; package schema uses the generic
            # `group` term and maps it at this boundary.
            "pain_group": _localized(item.get("group")),
            "protein_type": _localized(item.get("protein_type")),
            "localization": _localized(item.get("localization")),
            "axis": _localized(item.get("axis")),
            "research_card": {
                "zh": _candidate_card(project_source.get("project_review"), key, "zh"),
                "en": _candidate_card(project_source.get("project_review"), key, "en"),
            },
        }
        properties = {
            "pain_group": _text(item.get("group")),
            "rank_in_group": item.get("rank_in_group"),
            "gene": item.get("gene"),
            "protein_type": _text(item.get("protein_type")),
            "localization": _text(item.get("localization")),
            "axis": _text(item.get("axis")),
            "reference_ids": str(item.get("reference_ids") or "").split(";"),
            "bibliometrics": bibliometrics.get(key, {}),
            "scored_at": item.get("scored_at"),
            "rubric_version": item.get("rubric_version"),
            "localized_content": localized,
            "source_package_id": package.get("package_id"),
            "source_package_schema_version": package.get("schema_version") or "1.0",
        }
        scores = {
            "evidence": item.get("evidence"),
            "novelty": item.get("novelty"),
            "tractability": item.get("tractability"),
            "human": item.get("human"),
            "specificity": item.get("specificity"),
            "safety": item.get("safety"),
        }
        row = by_key.get(key)
        if row is None:
            session.add(
                Candidate(
                    project_id=project.id,
                    candidate_key=key,
                    name=_text(item.get("target")),
                    candidate_kind="research_target",
                    status="proposed",
                    rank=rank_by_key[key],
                    score=float(item.get("weighted_score", 0)),
                    scores=scores,
                    properties=properties,
                )
            )
        else:
            _update_versioned(
                row,
                name=_text(item.get("target")),
                candidate_kind="research_target",
                status="proposed",
                rank=rank_by_key[key],
                score=float(item.get("weighted_score", 0)),
                scores=scores,
                properties=properties,
            )
    return len(project_candidates)


def _upsert_references(
    session: Session,
    project: Project,
    package: dict,
    project_key: str,
    *,
    trusted_package: bool,
) -> int:
    package_id = str(package["package_id"])
    # LiteratureDocument belongs to one project, so a paper shared by multiple
    # projects is represented once per related project.
    allowed = {
        str(ref.get("ref_id"))
        for ref in package.get("references", [])
        if project_key in _reference_projects(ref, package.get("projects", []))
    }
    rows = list(session.scalars(select(LiteratureDocument).where(LiteratureDocument.project_id == project.id)))
    by_external = {str(row.external_id): row for row in rows if row.external_id}
    count = 0
    for ref in package.get("references", []):
        ref_id = str(ref.get("ref_id"))
        if ref_id not in allowed:
            continue
        metadata = {
            **ref,
            "package_id": package_id,
            "package_schema_version": package.get("schema_version") or "1.0",
            "source_project_key": project_key,
            "server_verification": (
                "trusted_builtin_checksum" if trusted_package else "pending_human_review"
            ),
        }
        document_status = "verified" if trusted_package else "pending_review"
        row = by_external.get(ref_id)
        if row is None:
            session.add(
                LiteratureDocument(
                    project_id=project.id,
                    title=str(ref.get("title") or ref_id),
                    source="research_package",
                    external_id=ref_id,
                    metadata_json=metadata,
                    status=document_status,
                )
            )
        else:
            _update_versioned(
                row,
                title=str(ref.get("title") or ref_id),
                metadata_json=metadata,
                status=document_status,
            )
        count += 1
    return count


def _upsert_knowledge(
    session: Session,
    project: Project,
    package: dict,
    project_key: str,
    source: dict,
) -> int:
    package_id = str(package["package_id"])
    entries = {
        # A project may override the shared methods entry with its own
        # methodology; every other entry is package-wide.
        "methods": source.get("methods") or package.get("methods"),
        "search_strategy": package.get("search_strategy"),
        "database_schema": package.get("database_schema"),
        "identifiers": package.get("identifiers", []),
        "search_log": package.get("search_log", []),
        "field_dictionary": package.get("field_dictionary", []),
        "ontology_relations": package.get("ontology_relations", []),
        "validation_report": package.get("validation_report"),
    }
    rows = list(session.scalars(select(KnowledgeEntry).where(KnowledgeEntry.project_id == project.id)))
    by_key = {
        str(row.source.get("entry_key")): row
        for row in rows
        if _managed_package_match(row.source.get("package_id"), package_id) and row.source.get("entry_key")
    }
    for key, value in entries.items():
        is_dataset = isinstance(value, list)
        localized = _localized(value) if not is_dataset else {"zh": "", "en": ""}
        serialized = json.dumps(value, ensure_ascii=False, indent=2) if is_dataset else localized["zh"]
        source = {
            "package_id": package_id,
            "package_schema_version": package.get("schema_version") or "1.0",
            "package_version": package.get("version"),
            "source_project_key": project_key,
            "entry_key": key,
            "localized_content": {"content": localized},
            "data": value if is_dataset else None,
            "display_data": (
                (package.get("display_data") or {}).get(key)
                if is_dataset and isinstance(package.get("display_data"), dict)
                else None
            ),
        }
        row = by_key.get(key)
        title = key.replace("_", " ").title()
        if row is None:
            session.add(
                KnowledgeEntry(
                    project_id=project.id,
                    title=title,
                    content=serialized,
                    entry_type=key,
                    source=source,
                    tags=["research-package", project_key.lower()],
                    created_by=project.owner_id,
                )
            )
        else:
            _update_versioned(row, title=title, content=serialized, source=source)
    return len(entries)


def _reconcile_managed_project(
    session: Session,
    project: Project,
    package: dict,
    project_key: str,
) -> None:
    package_id = str(package["package_id"])
    desired_claims = {
        str(edge["claim_id"])
        for edge in package["edges"]
        if edge["project"] == project_key
    }
    desired_candidates = {
        str(candidate["candidate_id"])
        for candidate in package["candidates"]
        if str(candidate.get("project_id") or "") == project_key
    }
    desired_references = {
        str(reference["ref_id"])
        for reference in package["references"]
        if project_key in reference["project_ids"]
    }
    desired_structures = {
        str(structure["pdb_id"]).upper()
        for source in package["projects"]
        if source["id"] == project_key
        for structure in source["structures"]
    }

    for finding in session.scalars(select(ResearchFinding).where(ResearchFinding.project_id == project.id)):
        evidence = finding.evidence or {}
        if (
            _managed_package_match(evidence.get("package_id"), package_id)
            and evidence.get("claim_id")
            and str(evidence["claim_id"]) not in desired_claims
        ):
            session.delete(finding)

    for candidate in session.scalars(select(Candidate).where(Candidate.project_id == project.id)):
        properties = candidate.properties or {}
        if _managed_package_match(properties.get("source_package_id"), package_id) and candidate.candidate_key not in (
            desired_candidates
        ):
            session.delete(candidate)

    for document in session.scalars(select(LiteratureDocument).where(LiteratureDocument.project_id == project.id)):
        metadata = document.metadata_json or {}
        if _managed_package_match(metadata.get("package_id"), package_id) and str(document.external_id or "") not in (
            desired_references
        ):
            session.delete(document)

    now = datetime.now(UTC)
    primary_target = session.get(Target, project.primary_target_id) if project.primary_target_id else None
    for artifact in session.scalars(
        select(Artifact).where(
            Artifact.project_id == project.id,
            Artifact.artifact_type == "target_structure",
            Artifact.deleted_at.is_(None),
        )
    ):
        lineage = artifact.lineage or {}
        if _managed_package_match(lineage.get("source_package_id"), package_id) and str(
            lineage.get("pdb_id") or ""
        ).upper() not in desired_structures:
            artifact.deleted_at = now
            artifact.version += 1
            if primary_target is not None and primary_target.structure_artifact_id == artifact.id:
                primary_target.structure_artifact_id = None
                primary_target.structure_status = "missing"
                primary_target.version += 1

    for operation in session.scalars(
        select(Operation).where(
            Operation.project_id == project.id,
            Operation.kind == "target.structure.import",
            Operation.status == "pending",
        )
    ):
        progress = operation.progress or {}
        if _managed_package_match(progress.get("source_package_id"), package_id) and str(
            progress.get("pdb_id") or ""
        ).upper() not in desired_structures:
            event = session.get(OutboxEvent, operation.id)
            if event is not None and event.published_at is None:
                session.delete(event)
            operation.status = "cancelled"
            operation.finished_at = now
            operation.version += 1


def _structure_operations(
    session: Session,
    project: Project,
    target: Target,
    source: dict,
    package: dict,
    user: User,
) -> list[uuid.UUID]:
    existing_by_pdb = {
        str(item.lineage.get("pdb_id", "")).upper(): item
        for item in session.scalars(
            select(Artifact).where(
                Artifact.project_id == project.id,
                Artifact.artifact_type == "target_structure",
                Artifact.deleted_at.is_(None),
            )
        )
    }
    pending = {
        str(item.progress.get("pdb_id", "")).upper()
        for item in session.scalars(
            select(Operation).where(
                Operation.project_id == project.id,
                Operation.kind == "target.structure.import",
                Operation.status.in_(["pending", "running"]),
            )
        )
    }
    primary = str(source.get("primary_target", {}).get("pdb_id") or "").upper()
    operation_ids: list[uuid.UUID] = []
    for structure in source.get("structures", []):
        pdb_id = str(structure.get("pdb_id") or "").upper()
        if not pdb_id:
            continue
        localized_content = {
            "name": _localized(structure.get("name")),
            "role": _localized(structure.get("role")),
        }
        existing = existing_by_pdb.get(pdb_id)
        if existing is not None:
            _update_versioned(
                existing,
                lineage={
                    **(existing.lineage or {}),
                    "name": structure.get("name"),
                    "method": structure.get("method"),
                    "resolution": structure.get("resolution"),
                    "role": structure.get("role"),
                    "reference_id": structure.get("reference_id"),
                    "rcsb_url": structure.get("rcsb_url"),
                    "source_package_id": package.get("package_id"),
                    "source_package_schema_version": package.get("schema_version"),
                    "source_project_key": source.get("id"),
                    "localized_content": localized_content,
                },
            )
            continue
        if pdb_id in pending:
            continue
        attach = pdb_id == primary
        operation = enqueue_operation(
            session,
            topic="target.structure.import",
            resource_type="target",
            resource_id=target.id,
            project_id=project.id,
            organization_id=project.organization_id,
            user=user,
            payload={
                "target_id": str(target.id),
                "source": "pdb",
                "pdb_id": pdb_id,
                "format": "cif",
                "attach_to_target": attach,
                "metadata": {
                    "name": structure.get("name"),
                    "method": structure.get("method"),
                    "resolution": structure.get("resolution"),
                    "role": structure.get("role"),
                    "reference_id": structure.get("reference_id"),
                    "rcsb_url": structure.get("rcsb_url"),
                    "source_package_id": package.get("package_id"),
                    "source_package_schema_version": package.get("schema_version"),
                    "source_project_key": source.get("id"),
                    "localized_content": localized_content,
                },
            },
        )
        operation.progress = {
            "pdb_id": pdb_id,
            "attach_to_target": attach,
            "source_package_id": package.get("package_id"),
            "source_project_key": source.get("id"),
        }
        operation_ids.append(operation.id)
    return operation_ids


def import_research_package(
    session: Session,
    payload: ResearchPackageImportCreate,
    user: User,
) -> ResearchPackageImportResponse:
    try:
        package, schema_version = normalize_research_package(payload.package)
    except ResearchPackageValidationError as exc:
        raise DomainError("invalid_research_package", str(exc), status_code=422) from exc
    package_id = package["package_id"]
    version = package["version"]
    package_checksum = research_package_checksum(package)
    trusted_package = TRUSTED_BUILTIN_PACKAGE_CHECKSUMS.get(package_id) == package_checksum

    project_results: list[ResearchPackageProjectResult] = []
    counts = {
        "projects": 0,
        "candidates": 0,
        "findings": 0,
        "references": len(package.get("references", [])),
        "reference_links": 0,
        "knowledge": 0,
        "structures": 0,
    }
    operation_ids: list[uuid.UUID] = []
    repo = ProjectRepository(session)

    for source in package["projects"]:
        key = str(source.get("id") or "").strip()
        project = repo.by_research_source(payload.organization_id, package_id, key)
        if project is None:
            project = _versioned_package_project(session, payload.organization_id, package_id, key)
        if project is None:
            project = _legacy_package_project(session, payload.organization_id, package_id, source)
        if project is None:
            project = _package_claim_lineage_project(session, payload.organization_id, package, key)
        state = "updated"
        if project is None:
            project = create_project(
                session,
                ProjectCreate(
                    organization_id=payload.organization_id,
                    name=_text(source.get("name")),
                    project_type=str(source.get("project_type") or "research"),
                    summary=_text(source.get("summary")),
                    prompt=_text(source.get("summary")) or f"Imported project: {_text(source.get('name'))}",
                    source_package_id=package_id,
                    source_project_key=key,
                    localized_content={},
                ),
                user,
            )
            state = "created"
        adopted = state != "created" and bool((project.localized_content or {}).get("adopted_user_project"))
        previous_package = (project.localized_content or {}).get("package", {})
        if state != "created" and previous_package.get("content_checksum") == package_checksum:
            state = "unchanged"
        localized_content = {
            "name": _localized(source.get("name")),
            "summary": _localized(source.get("summary")),
            "primary_target": {"name": _localized(source.get("primary_target", {}).get("name"))},
            "package": {
                "id": package_id,
                "schema_version": schema_version,
                "version": version,
                "as_of": package.get("as_of"),
                "content_checksum": package_checksum,
                "candidate_count": sum(
                    str(candidate.get("project_id") or "") == key
                    for candidate in package.get("candidates", [])
                ),
                "finding_count": sum(1 for edge in package.get("edges", []) if edge.get("project") == key),
                "reference_count": sum(
                    1
                    for reference in package.get("references", [])
                    if key in _reference_projects(reference, package.get("projects", []))
                ),
                "knowledge_count": 8,
                "structure_count": len(source.get("structures", [])),
            },
        }
        if adopted:
            localized = dict(project.localized_content) if isinstance(project.localized_content, dict) else {}
            localized["adopted_user_project"] = True
            _update_versioned(project, localized_content=localized)
        else:
            _update_versioned(
                project,
                name=_text(source.get("name")),
                summary=_text(source.get("summary")),
                project_type=str(source.get("project_type") or "research"),
                source_package_id=package_id,
                source_project_key=key,
                localized_content=localized_content,
            )
        _reconcile_managed_project(session, project, package, key)
        if adopted:
            target = session.get(Target, project.primary_target_id) if project.primary_target_id else None
        else:
            target = _upsert_target(session, project, source.get("primary_target", {}))
        _upsert_brief(session, project, package_id, source)
        counts["findings"] += _upsert_findings(session, project, package, key)
        counts["candidates"] += _upsert_candidates(session, project, package, source)
        counts["reference_links"] += _upsert_references(
            session,
            project,
            package,
            key,
            trusted_package=trusted_package,
        )
        counts["knowledge"] += _upsert_knowledge(session, project, package, key, source)
        if not adopted:
            assert target is not None  # only the `adopted` branch can leave target unset
            operations = _structure_operations(session, project, target, source, package, user)
            counts["structures"] += len(source.get("structures", []))
            operation_ids.extend(operations)
        counts["projects"] += 1
        project_results.append(
            ResearchPackageProjectResult(source_project_key=key, project_id=project.id, status=state)
        )

    conflicts = soft_delete_builtin_research_duplicates(session, payload.organization_id, user)
    return ResearchPackageImportResponse(
        package_id=package_id,
        version=version,
        projects=project_results,
        counts=counts,
        pdb_operation_ids=operation_ids,
        conflicts=conflicts,
    )
