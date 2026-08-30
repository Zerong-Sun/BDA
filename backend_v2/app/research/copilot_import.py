from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..candidates.models import Candidate
from ..core.problem import DomainError
from ..identity.models import User
from ..literature.models import LiteratureDocument
from ..projects.repository import ProjectRepository
from ..projects.schemas import ProjectCreate
from ..projects.service import create_project, require_project
from ..targets.models import Target
from .models import ResearchBrief, ResearchFinding
from .schemas import (
    CopilotResearchImportResponse,
    CopilotResearchResult,
    CopilotResearchResultCreate,
    CopilotResearchValidationResponse,
)


def _path(location: tuple[str | int, ...]) -> str:
    result = "$"
    for part in location:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def _issue(kind: str, path: str, message: str, *, reference: str | None = None) -> dict[str, str]:
    issue = {"kind": kind, "path": path, "message": message}
    if reference is not None:
        issue["reference"] = reference
    return issue


def _extract_json(value: str | dict) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError(
            "invalid_copilot_research_result",
            "Copilot research JSON could not be parsed",
            status_code=422,
            errors=[
                _issue(
                    "json_syntax",
                    "$",
                    exc.msg,
                )
                | {"line": str(exc.lineno), "column": str(exc.colno)}
            ],
        ) from exc
    if not isinstance(parsed, dict):
        raise DomainError(
            "invalid_copilot_research_result",
            "Copilot research JSON must be an object",
            status_code=422,
            errors=[_issue("schema", "$", "Expected a JSON object")],
        )
    return parsed


def _duplicate_issues(values: list[str], path: str, label: str) -> list[dict[str, str]]:
    seen: dict[str, int] = {}
    issues: list[dict[str, str]] = []
    for index, value in enumerate(values):
        if value in seen:
            issues.append(
                _issue(
                    "duplicate_id",
                    f"{path}[{index}].id",
                    f"Duplicate {label} ID; first declared at {path}[{seen[value]}].id",
                    reference=value,
                )
            )
        else:
            seen[value] = index
    return issues


def _reference_issues(result: CopilotResearchResult) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    issues.extend(_duplicate_issues([item.id for item in result.references], "$.references", "reference"))
    issues.extend(_duplicate_issues([item.id for item in result.nodes], "$.nodes", "node"))
    issues.extend(_duplicate_issues([item.id for item in result.edges], "$.edges", "edge"))
    issues.extend(_duplicate_issues([item.id for item in result.candidates], "$.candidates", "candidate"))

    references = {item.id for item in result.references}
    nodes = {item.id for item in result.nodes}
    for index, reference in enumerate(result.references):
        base = f"$.references[{index}]"
        if not any((reference.pmid, reference.doi, reference.url)):
            issues.append(
                _issue(
                    "citation_identifier",
                    base,
                    "At least one of pmid, doi, or url is required",
                    reference=reference.id,
                )
            )
        if reference.pmid and not re.fullmatch(r"\d{1,12}", reference.pmid):
            issues.append(_issue("citation_identifier", f"{base}.pmid", "PMID must contain digits only", reference=reference.id))
        if reference.doi and not re.fullmatch(r"10\.\d{4,9}/\S+", reference.doi, flags=re.IGNORECASE):
            issues.append(_issue("citation_identifier", f"{base}.doi", "DOI must use the 10.xxxx/suffix form", reference=reference.id))
        if reference.url and not re.match(r"^https?://[^\s]+$", reference.url, flags=re.IGNORECASE):
            issues.append(_issue("citation_identifier", f"{base}.url", "URL must be an absolute HTTP(S) URL", reference=reference.id))

    def check_reference_list(values: list[str], path: str) -> None:
        for ref_index, reference_id in enumerate(values):
            if reference_id not in references:
                issues.append(
                    _issue(
                        "unknown_reference",
                        f"{path}[{ref_index}]",
                        "Referenced citation is not declared in $.references",
                        reference=reference_id,
                    )
                )

    for index, node in enumerate(result.nodes):
        check_reference_list(node.reference_ids, f"$.nodes[{index}].reference_ids")
    for index, edge in enumerate(result.edges):
        if edge.source not in nodes:
            issues.append(_issue("unknown_node", f"$.edges[{index}].source", "Source node is not declared in $.nodes", reference=edge.source))
        if edge.target not in nodes:
            issues.append(_issue("unknown_node", f"$.edges[{index}].target", "Target node is not declared in $.nodes", reference=edge.target))
        check_reference_list(edge.reference_ids, f"$.edges[{index}].reference_ids")
    for index, candidate in enumerate(result.candidates):
        check_reference_list(candidate.reference_ids, f"$.candidates[{index}].reference_ids")
    return issues


def validate_copilot_research_result(payload: CopilotResearchResultCreate) -> tuple[CopilotResearchResult, str]:
    raw = _extract_json(payload.result)
    try:
        result = CopilotResearchResult.model_validate(raw)
    except ValidationError as exc:
        issues = [
            _issue("schema", _path(tuple(error["loc"])), str(error["msg"]))
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise DomainError(
            "invalid_copilot_research_result",
            "Copilot research result does not match schema version 1.0",
            status_code=422,
            errors=issues,
        ) from exc
    issues = _reference_issues(result)
    if issues:
        raise DomainError(
            "invalid_copilot_research_references",
            "Copilot research result contains invalid fields or references",
            status_code=422,
            errors=issues,
        )
    canonical = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return result, hashlib.sha256(canonical.encode()).hexdigest()


def _counts(result: CopilotResearchResult) -> dict[str, int]:
    return {
        "projects": 1,
        "references": len(result.references),
        "nodes": len(result.nodes),
        "edges": len(result.edges),
        "candidates": len(result.candidates),
    }


def validation_response(payload: CopilotResearchResultCreate) -> CopilotResearchValidationResponse:
    result, checksum = validate_copilot_research_result(payload)
    return CopilotResearchValidationResponse(
        checksum=checksum,
        project_name=result.project.name,
        counts=_counts(result),
        normalized=result,
    )


def _citation_url(reference: Any) -> str | None:
    if reference.url:
        return reference.url
    if reference.pmid:
        return f"https://pubmed.ncbi.nlm.nih.gov/{reference.pmid}/"
    if reference.doi:
        return f"https://doi.org/{reference.doi}"
    return None


def import_copilot_research_result(
    session: Session,
    payload: CopilotResearchResultCreate,
    user: User,
) -> CopilotResearchImportResponse:
    # Validation is deliberately completed before the first ORM mutation. The request
    # session rolls back any later failure, so an invalid or failed import is atomic.
    result, checksum = validate_copilot_research_result(payload)
    package_id = f"copilot-research:{checksum}"
    repo = ProjectRepository(session)
    existing = repo.by_research_source(payload.organization_id, package_id, result.project.key)
    if existing is not None:
        require_project(session, existing.id, user)
        return CopilotResearchImportResponse(
            project_id=existing.id,
            project_name=existing.name,
            status="unchanged",
            checksum=checksum,
            counts=_counts(result),
        )

    project = create_project(
        session,
        ProjectCreate(
            organization_id=payload.organization_id,
            name=result.project.name,
            project_type=result.project.project_type,
            summary=result.project.summary,
            prompt=result.project.summary or f"Imported project: {result.project.name}",
            source_package_id=package_id,
            source_project_key=result.project.key,
            localized_content={
                "copilot_research": {
                    "schema_version": result.schema_version,
                    "checksum": checksum,
                    "research_question": result.project.research_question,
                    "counts": _counts(result),
                    "review_status": "pending_review",
                }
            },
        ),
        user,
    )

    if result.primary_target is not None:
        target = Target(
            project_id=project.id,
            name=result.primary_target.name,
            uniprot_accession=result.primary_target.uniprot,
            organism=result.primary_target.organism,
            identity_status="unconfirmed",
        )
        session.add(target)
        session.flush()
        project.primary_target_id = target.id
        project.version += 1

    evidence_relations = {
        "schema_version": result.schema_version,
        "nodes": [item.model_dump(mode="json") for item in result.nodes],
        "edges": [item.model_dump(mode="json") for item in result.edges],
    }
    brief = ResearchBrief(
        project_id=project.id,
        title=f"{result.project.name} — Project Review",
        status="draft",
        content=result.project.project_review,
        scope={
            "source": "copilot_research",
            "checksum": checksum,
            "research_question": result.project.research_question,
            "methods": result.project.methods,
            "evidence_relations": evidence_relations,
            "review_status": "pending_review",
        },
        created_by=user.id,
    )
    session.add(brief)
    session.flush()

    references = {reference.id: reference for reference in result.references}
    for reference in result.references:
        external_id = reference.pmid or reference.doi or reference.id
        session.add(
            LiteratureDocument(
                project_id=project.id,
                title=reference.title,
                source="copilot_research",
                external_id=external_id,
                metadata_json={
                    **reference.model_dump(mode="json"),
                    "citation_id": reference.id,
                    "checksum": checksum,
                    "review_status": "pending_review",
                },
                status="pending_review",
            )
        )

    node_labels = {node.id: node.label for node in result.nodes}
    for node in result.nodes:
        source_refs = [url for ref_id in node.reference_ids if (url := _citation_url(references[ref_id]))]
        session.add(
            ResearchFinding(
                project_id=project.id,
                brief_id=brief.id,
                finding_type="evidence_entity",
                title=node.label,
                content=node.description or node.label,
                evidence={
                    "relation_element": "entity",
                    "node_id": node.id,
                    "node_kind": node.kind,
                    "reference_ids": node.reference_ids,
                    "source_refs": source_refs,
                    "review_status": "pending_review",
                    "checksum": checksum,
                },
                created_by=user.id,
            )
        )

    for edge in result.edges:
        source_refs = [url for ref_id in edge.reference_ids if (url := _citation_url(references[ref_id]))]
        session.add(
            ResearchFinding(
                project_id=project.id,
                brief_id=brief.id,
                finding_type="evidence_statement",
                title=f"{node_labels[edge.source]} —{edge.predicate}→ {node_labels[edge.target]}",
                content=edge.summary,
                evidence={
                    "relation_element": "statement",
                    "edge_id": edge.id,
                    "source": edge.source,
                    "target": edge.target,
                    "predicate": edge.predicate,
                    "assertion_class": edge.assertion,
                    "evidence_level": edge.evidence_grade,
                    "reference_ids": edge.reference_ids,
                    "source_refs": source_refs,
                    "review_status": "pending_review",
                    "checksum": checksum,
                },
                created_by=user.id,
            )
        )

    for rank, candidate in enumerate(result.candidates, start=1):
        session.add(
            Candidate(
                project_id=project.id,
                candidate_key=candidate.id,
                name=candidate.name,
                candidate_kind="research_target",
                status="proposed",
                rank=rank,
                score=candidate.score,
                scores={},
                properties={
                    "summary": candidate.summary,
                    "reference_ids": candidate.reference_ids,
                    "source_package_id": package_id,
                    "review_status": "pending_review",
                },
            )
        )

    session.flush()
    return CopilotResearchImportResponse(
        project_id=project.id,
        project_name=project.name,
        status="created",
        checksum=checksum,
        counts=_counts(result),
    )
