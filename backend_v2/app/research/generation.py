from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..candidates.models import Candidate
from ..core.metrics import RESEARCH_DRAFT_VALIDATIONS, RESEARCH_IMPORT_ACCEPTANCE, RESEARCH_TOOL_FAILURES
from ..core.problem import DomainError
from ..identity.models import User
from ..knowledge.models import KnowledgeEntry
from ..literature.models import LiteratureChunk, LiteratureDocument
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from ..projects.schemas import ProjectCreate
from ..projects.service import create_project, require_project
from ..targets.models import Target
from .evidence_tools import EvidenceToolService, titles_match
from .models import ResearchBrief, ResearchFinding, ResearchGeneration
from .schemas import (
    ResearchDraftV2,
    ResearchGenerationAccepted,
    ResearchGenerationCreate,
    ResearchGenerationImportResponse,
)
from .workspace import build_research_workspace

DATASET_KEYS = {"identifiers", "search_log", "field_dictionary", "ontology_relations"}
REQUIRED_DRAFT_CATEGORIES = {"review_sections", "references", "research_targets"}
LOW_QUALITY_REFERENCE_TITLES = (
    "abstracts of ",
    "annual meeting",
    "congress of ",
    "poster presentations",
    "conference abstracts",
)
TOPIC_STOPWORDS = {
    "and", "branches", "draft", "for", "from", "grounded", "in", "of", "pending-review",
    "project", "research", "source", "the", "with",
}


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _localized_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("default") or value.get("zh") or value.get("en") or "")
    return str(value or "")


def _pending(value: Any) -> Any:
    if isinstance(value, dict):
        result = {key: _pending(item) for key, item in value.items() if key != "download_url"}
        if "review_status" in result:
            result["review_status"] = "pending_review"
        return result
    if isinstance(value, list):
        return [_pending(item) for item in value]
    return value


def _topic_terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", value.lower())
        if token not in TOPIC_STOPWORDS and (len(token) >= 3 or any(character.isdigit() for character in token))
    }


def _search_query(topic: str, evidence_cutoff: date | str | None = None) -> str:
    terms = sorted(_topic_terms(topic), key=lambda term: (-any(character.isdigit() for character in term), -len(term)))
    selected = terms[:10]
    topic_query = " OR ".join(f'TITLE_ABS:"{term}"' for term in selected) or topic
    if evidence_cutoff:
        cutoff = evidence_cutoff if isinstance(evidence_cutoff, date) else date.fromisoformat(evidence_cutoff)
        return (
            f"({topic_query})"
            f" AND FIRST_PDATE:[1900-01-01 TO {cutoff.isoformat()}]"
            f" AND PUB_YEAR:[1900 TO {cutoff.year}]"
        )
    return topic_query


def _reference_relevance(topic: str, title: str, abstract: str) -> tuple[bool, list[str]]:
    normalized_title = title.strip().lower()
    if not title or any(pattern in normalized_title for pattern in LOW_QUALITY_REFERENCE_TITLES):
        return False, []
    topic_terms = _topic_terms(topic)
    title_matches = topic_terms & _topic_terms(title)
    abstract_matches = topic_terms & _topic_terms(abstract)
    matched = sorted(title_matches | abstract_matches)
    return bool(title_matches or len(abstract_matches) >= 2), matched


def _reference_identity(reference: dict[str, Any]) -> str:
    pmid = str(reference.get("pmid") or "").strip()
    doi = str(reference.get("doi") or "").strip().lower()
    return f"pmid:{pmid}" if pmid else f"doi:{doi}" if doi else f"ref:{reference.get('ref_id')}"


def _external_references(
    topic: str,
    tools: EvidenceToolService,
    *,
    limit: int = 12,
    evidence_cutoff: date | str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    rejected_references = 0
    try:
        query = _search_query(topic, evidence_cutoff)
        payload = tools.search_europe_pmc(query, page_size=min(25, max(limit * 2, limit))).data
    except RuntimeError as exc:
        return [], [{"kind": "tool_failure", "entity_id": "europe_pmc", "detail": str(exc)}]
    except ValueError as exc:
        return [], [{
            "kind": "invalid_evidence_cutoff",
            "entity_id": "europe_pmc",
            "detail": str(exc),
        }]
    rows = ((payload.get("resultList") or {}).get("result") or [])
    references: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pmid = str(row.get("pmid") or "").strip()
        doi = str(row.get("doi") or "").strip()
        title = str(row.get("title") or "").strip()
        abstract = str(row.get("abstractText") or "").strip()
        if not title or (not pmid and not doi):
            continue
        relevant, matched_terms = _reference_relevance(topic, title, abstract)
        if not relevant or not str(row.get("authorString") or "").strip():
            rejected_references += 1
            continue
        ref_id = f"PMID:{pmid}" if pmid else f"DOI:{doi.lower()}"
        verification_status = "verified_europe_pmc" if pmid else "unverified"
        verification: dict[str, Any] = {"europe_pmc_result": True}
        if doi:
            try:
                crossref = tools.get_crossref(doi).data.get("message") or {}
                matched = isinstance(crossref, dict) and titles_match(title, crossref.get("title"))
                verification["crossref_metadata_match"] = matched
                if matched:
                    verification_status = "verified_crossref"
                elif not pmid:
                    issues.append({
                        "kind": "metadata_mismatch",
                        "entity_id": ref_id,
                        "detail": "Crossref title did not match Europe PMC metadata",
                    })
            except (RuntimeError, ValueError) as exc:
                verification["crossref_error"] = str(exc)
                if not pmid:
                    issues.append({"kind": "tool_failure", "entity_id": ref_id, "detail": str(exc)})
        references.append({
            "document_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"bda:{ref_id}")),
            "ref_id": ref_id,
            "title": {"default": title, "en": title, "zh": None},
            "authors": str(row.get("authorString") or ""),
            "journal": str(row.get("journalTitle") or ""),
            "year": str(row.get("pubYear") or ""),
            "doi": doi,
            "pmid": pmid,
            "pmcid": str(row.get("pmcid") or ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else f"https://doi.org/{doi}",
            "verification_status": verification_status,
            "status": "pending_review",
            "metadata": {
                "source": "europe_pmc",
                "origin": "external_discovery",
                "retrieval_scope": "metadata_only",
                "full_text_retrieved": False,
                "relevance": {"matched_terms": matched_terms, "query": query},
                "verification": verification,
                "review_status": "pending_review",
            },
        })
        if len(references) >= limit:
            break
    if rejected_references:
        issues.append({
            "kind": "irrelevant_references_rejected",
            "entity_id": "europe_pmc",
            "detail": f"{rejected_references} search results failed topic or publication-quality checks",
        })
    return references, issues


def _annotate_source_references(
    session: Session,
    project_id: uuid.UUID,
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents = list(
        session.scalars(select(LiteratureDocument).where(LiteratureDocument.project_id == project_id))
    )
    documents_by_id = {str(document.id): document for document in documents}
    chunk_document_ids = {
        str(document_id)
        for document_id in session.scalars(
            select(LiteratureChunk.document_id)
            .join(LiteratureDocument, LiteratureDocument.id == LiteratureChunk.document_id)
            .where(LiteratureDocument.project_id == project_id)
        )
    }
    result: list[dict[str, Any]] = []
    for reference in references:
        item = dict(reference)
        metadata = dict(item.get("metadata") or {})
        document = documents_by_id.get(str(item.get("document_id") or ""))
        has_full_text = str(item.get("document_id") or "") in chunk_document_ids
        has_abstract = bool(document and document.abstract)
        metadata.update({
            "origin": metadata.get("origin") or "source_project",
            "source_project_id": str(project_id),
            "full_text_retrieved": has_full_text,
            "abstract_available": has_abstract,
            "retrieval_scope": (
                "full_text" if has_full_text else "abstract_or_metadata" if has_abstract else "metadata_only"
            ),
        })
        item["metadata"] = metadata
        result.append(item)
    return result


def _ensure_review_sections(workspace: dict[str, Any]) -> list[dict[str, Any]]:
    sections = workspace.get("review_sections") or []
    if sections:
        return sections
    items: list[dict[str, Any]] = []
    for edge in workspace.get("graph_edges") or []:
        edge_id = str(edge.get("id") or uuid.uuid4())
        source_label = edge.get("source_label") or {"default": str(edge.get("source") or "")}
        target_label = edge.get("target_label") or {"default": str(edge.get("target") or "")}
        summary = edge.get("summary") or edge.get("context") or {
            "default": f"{_localized_text(source_label)} {edge.get('predicate', 'related_to')} {_localized_text(target_label)}"
        }
        items.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"bda:research-generation:review:{edge_id}")),
            "finding_type": "prior_art_landscape",
            "title": summary,
            "content": summary,
            "evidence": {
                "reference_ids": edge.get("reference_ids", []),
                "source_refs": edge.get("source_urls", []),
                "assertion_class": edge.get("assertion"),
                "evidence_level": edge.get("evidence_grade"),
                "derived_from_graph_edge": edge_id,
                "review_status": "pending_review",
            },
            "version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        })
    return [{"track": "prior_art_landscape", "items": items}] if items else []


def _ensure_research_targets(workspace: dict[str, Any], *, limit: int, strata: str) -> list[dict[str, Any]]:
    targets = workspace.get("research_targets") or []
    if targets:
        return targets[:limit]
    connected_references: dict[str, set[str]] = {}
    for edge in workspace.get("graph_edges") or []:
        references = {str(value) for value in edge.get("reference_ids") or []}
        for node_id in (str(edge.get("source") or ""), str(edge.get("target") or "")):
            connected_references.setdefault(node_id, set()).update(references)
    result: list[dict[str, Any]] = []
    for index, node in enumerate((workspace.get("graph_nodes") or [])[:limit], start=1):
        node_id = str(node.get("id") or f"target-{index}")
        label = node.get("label") or {"default": node_id}
        result.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"bda:research-generation:target:{node_id}")),
            "candidate_key": f"R{index:02d}",
            "name": label,
            "pain_group": {"default": strata} if strata else {"default": ""},
            "gene": "",
            "protein_type": {"default": str(node.get("kind") or "evidence_graph_entity")},
            "localization": {"default": ""},
            "axis": node.get("description") or label,
            "score": None,
            "rank": index,
            "scores": {},
            "properties": {
                "derived_from_graph_node": node_id,
                "review_status": "pending_review",
            },
            "reference_ids": sorted(
                {str(value) for value in node.get("reference_ids") or []}
                | connected_references.get(node_id, set())
            ),
            "review_status": "pending_review",
        })
    return result


def _evidence_source_project(session: Session, project: Project) -> Project:
    current = project
    visited = {current.id}
    for _ in range(5):
        localized = current.localized_content or {}
        generated = localized.get("copilot_research") if isinstance(localized, dict) else None
        provenance = generated.get("provenance") if isinstance(generated, dict) else None
        source_id = (
            provenance.get("evidence_source_project_id") or provenance.get("source_project_id")
            if isinstance(provenance, dict)
            else None
        )
        try:
            parsed_id = uuid.UUID(str(source_id))
        except (TypeError, ValueError):
            break
        if parsed_id in visited:
            break
        source = session.get(Project, parsed_id)
        if source is None or source.organization_id != project.organization_id:
            break
        current = source
        visited.add(current.id)
    return current


def _verify_workspace_entities(
    workspace: dict[str, Any],
    tools: EvidenceToolService,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    primary_target = (workspace.get("project") or {}).get("primary_target") or {}
    accession = str(primary_target.get("uniprot_accession") or "").strip()
    if accession:
        try:
            entry = tools.get_uniprot(accession).data
            returned = str(entry.get("primaryAccession") or "").upper()
            if returned == accession.upper():
                primary_target["identity_status"] = "verified_uniprot"
            else:
                issues.append({
                    "kind": "metadata_mismatch",
                    "entity_id": accession,
                    "detail": "UniProt response accession did not match the requested target",
                })
        except (RuntimeError, ValueError) as exc:
            issues.append({"kind": "tool_failure", "entity_id": f"uniprot:{accession}", "detail": str(exc)})
    for structure in workspace.get("structures", []):
        pdb_id = str(structure.get("pdb_id") or "").strip()
        if not pdb_id:
            continue
        try:
            entry = tools.get_rcsb(pdb_id).data
            returned_value = entry.get("rcsb_id")
            if not returned_value and isinstance(entry.get("entry"), dict):
                returned_value = entry["entry"].get("id")
            returned = str(returned_value or "")
            matched = not returned or returned.upper() == pdb_id.upper()
            structure.setdefault("lineage", {})["identifier_verification"] = (
                "verified_rcsb" if matched else "metadata_mismatch"
            )
            if not matched:
                issues.append({
                    "kind": "metadata_mismatch",
                    "entity_id": pdb_id,
                    "detail": "RCSB response entry did not match the requested PDB identifier",
                })
        except (RuntimeError, ValueError) as exc:
            issues.append({"kind": "tool_failure", "entity_id": f"rcsb:{pdb_id}", "detail": str(exc)})
    return issues


def _ensure_datasets(
    datasets: list[dict[str, Any]],
    references: list[dict[str, Any]],
    audits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = list(datasets)
    existing = {str(item.get("key")) for item in result}
    generated = {
        "identifiers": [
            {"ref_id": item.get("ref_id"), "doi": item.get("doi"), "pmid": item.get("pmid")}
            for item in references
        ],
        "search_log": audits,
        "field_dictionary": [
            {"field": "ref_id", "meaning": "Stable citation identifier within this draft"},
            {"field": "verification_status", "meaning": "Identifier and metadata verification outcome"},
            {"field": "review_status", "meaning": "Human review lifecycle state"},
        ],
        "ontology_relations": [],
    }
    for key, data in generated.items():
        if key in existing:
            if key == "search_log":
                for item in result:
                    if item.get("key") == key:
                        item["data"] = data
            continue
        title = key.replace("_", " ").title()
        result.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"bda:research-dataset:{key}")),
            "key": key,
            "title": {"default": title, "en": title, "zh": None},
            "content": {"default": f"Backend-generated {title.lower()} for this draft."},
            "data": data,
            "display_data": None,
            "source": {"generated_by": "research_generation_v2", "review_status": "pending_review"},
            "version": 1,
        })
    return result


def _validate_draft(draft: dict[str, Any]) -> tuple[list[dict[str, str]], float]:
    issues: list[dict[str, str]] = []
    reference_ids = {str(item.get("ref_id")) for item in draft.get("references", [])}
    node_ids = {str(item.get("id")) for item in draft.get("graph_nodes", [])}
    claims: list[tuple[str, list[str]]] = []

    def check_references(entity_id: str, values: Any) -> None:
        refs = [str(item) for item in values] if isinstance(values, list) else ([str(values)] if values else [])
        claims.append((entity_id, refs))
        missing = [item for item in refs if item not in reference_ids]
        if missing:
            issues.append({"kind": "unknown_reference", "entity_id": entity_id, "detail": ",".join(missing)})

    for node in draft.get("graph_nodes", []):
        check_references(str(node.get("id")), node.get("reference_ids"))
    for edge in draft.get("graph_edges", []):
        entity_id = str(edge.get("id"))
        for endpoint in ("source", "target"):
            if str(edge.get(endpoint)) not in node_ids:
                issues.append({
                    "kind": "unknown_node",
                    "entity_id": entity_id,
                    "detail": f"{endpoint}:{edge.get(endpoint)}",
                })
        check_references(entity_id, edge.get("reference_ids"))
    for target in draft.get("research_targets", []):
        check_references(str(target.get("id") or target.get("candidate_key")), target.get("reference_ids"))
    for section in draft.get("review_sections", []):
        for item in section.get("items", []):
            evidence = item.get("evidence") or {}
            check_references(str(item.get("id")), evidence.get("reference_ids") or evidence.get("ref_id"))
    for structure in draft.get("structures", []):
        reference_id = str(structure.get("reference_id") or "")
        if reference_id:
            check_references(str(structure.get("artifact_id") or structure.get("pdb_id")), [reference_id])

    cited = sum(1 for _, refs in claims if refs)
    coverage = cited / len(claims) if claims else 1.0
    return issues, round(coverage, 4)


def create_research_generation(
    session: Session,
    project: Project,
    payload: ResearchGenerationCreate,
    user: User,
) -> ResearchGenerationAccepted:
    row = ResearchGeneration(
        source_project_id=project.id,
        organization_id=project.organization_id,
        conversation_id=payload.conversation_id,
        created_by=user.id,
        request=payload.model_dump(mode="json", exclude={"conversation_id"}),
    )
    session.add(row)
    session.flush()
    operation = enqueue_operation(
        session,
        topic="research.generate",
        resource_type="research_generation",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"generation_id": str(row.id)},
    )
    return ResearchGenerationAccepted(generation_id=row.id, operation_id=operation.id)


def require_research_generation(
    session: Session,
    generation_id: uuid.UUID,
    user: User,
) -> ResearchGeneration:
    row = session.get(ResearchGeneration, generation_id)
    if row is None:
        raise DomainError("research_generation_not_found", "Research generation was not found", status_code=404)
    require_project(session, row.source_project_id, user)
    return row


def finalize_research_generation(session: Session, row: ResearchGeneration) -> ResearchGeneration:
    if row.status in {"ready", "imported"}:
        return row
    project = session.get(Project, row.source_project_id)
    if project is None:
        row.status = "failed"
        row.error = "source_project_not_found"
        row.version += 1
        return row

    evidence_project = _evidence_source_project(session, project)
    workspace = _pending(build_research_workspace(session, evidence_project).model_dump(mode="json"))
    request = row.request or {}
    topic = str(request.get("topic") or project.name)
    candidate_count = int(request.get("candidate_count") or 10)
    references = _annotate_source_references(
        session,
        evidence_project.id,
        workspace.get("references", []),
    )
    issues: list[dict[str, str]] = []
    evidence_tools = EvidenceToolService(max_calls=60)
    if request.get("use_external_evidence", True):
        issues.extend(_verify_workspace_entities(workspace, evidence_tools))
        external_references, external_issues = _external_references(
            topic,
            evidence_tools,
            evidence_cutoff=request.get("evidence_cutoff"),
        )
        existing_refs = {_reference_identity(item) for item in references}
        references.extend(item for item in external_references if _reference_identity(item) not in existing_refs)
        issues.extend(external_issues)
    reference_ids = {str(item.get("ref_id")) for item in references}
    verified_ids = {
        str(item.get("ref_id"))
        for item in references
        if str(item.get("verification_status") or "").lower().startswith("verified")
    }
    graph_edges = workspace.get("graph_edges", [])
    for edge in graph_edges:
        edge_refs = [str(item) for item in edge.get("reference_ids", [])]
        missing = [item for item in edge_refs if item not in reference_ids]
        if missing:
            issues.append({"kind": "unknown_reference", "entity_id": str(edge.get("id")), "detail": ",".join(missing)})
        if edge.get("assertion") == "established_fact" and not any(item in verified_ids for item in edge_refs):
            edge["assertion"] = "evidence_based_inference"
            issues.append({
                "kind": "assertion_downgraded",
                "entity_id": str(edge.get("id")),
                "detail": "No locally verified reference supports established_fact",
            })

    review_sections = _ensure_review_sections(workspace)
    research_targets = _ensure_research_targets(
        workspace,
        limit=candidate_count,
        strata=str(request.get("strata") or ""),
    )
    project_draft = {
        **workspace["project"],
        "name": {"default": topic, request.get("language", "en"): topic},
        "summary": workspace["project"].get("summary") or {"default": topic},
        "source_project_id": str(project.id),
    }
    draft = ResearchDraftV2(
        schema_version="2.0",
        project=project_draft,
        primary_target=workspace["project"].get("primary_target"),
        review_document=workspace.get("review_document"),
        review_sections=review_sections,
        references=references,
        graph_nodes=workspace.get("graph_nodes", []),
        graph_edges=graph_edges,
        structures=workspace.get("structures", []),
        research_targets=research_targets,
        methods=workspace.get("methods", []),
        datasets=_ensure_datasets(workspace.get("datasets", []), references, evidence_tools.audits),
        provenance={
            "generated_at": datetime.now(UTC).isoformat(),
            "source_project_id": str(project.id),
            "evidence_source_project_id": str(evidence_project.id),
            "evidence_cutoff": request.get("evidence_cutoff"),
            "strata": request.get("strata") or "",
            "evidence_policy": "project_evidence_and_allowlisted_tools_only",
            "allowed_external_sources": ["europe_pmc", "crossref", "uniprot", "rcsb", "reactome"],
            "external_queries_executed": evidence_tools.calls,
            "tool_audit": evidence_tools.audits,
            "limitation": (
                "External discovery retrieved citation metadata only; no full text was retrieved for newly discovered records."
                if evidence_tools.calls
                else "External evidence retrieval was disabled; only the source project snapshot was used."
            ),
            "reference_counts": {
                "copied_from_source": sum(
                    1 for item in references if (item.get("metadata") or {}).get("origin") == "source_project"
                ),
                "newly_discovered": sum(
                    1 for item in references if (item.get("metadata") or {}).get("origin") == "external_discovery"
                ),
            },
            "review_status": "pending_review",
        },
        counts={},
    ).model_dump(mode="json")
    draft["counts"] = {
        "review_sections": len(draft["review_sections"]),
        "references": len(draft["references"]),
        "graph_nodes": len(draft["graph_nodes"]),
        "graph_edges": len(draft["graph_edges"]),
        "structures": len(draft["structures"]),
        "research_targets": len(draft["research_targets"]),
        "methods": len(draft["methods"]),
        "datasets": len(draft["datasets"]),
    }
    closure_issues, citation_coverage = _validate_draft(draft)
    issues.extend(closure_issues)
    for issue in issues:
        if issue["kind"] == "tool_failure":
            RESEARCH_TOOL_FAILURES.labels(issue["entity_id"]).inc()
    checksum = hashlib.sha256(_canonical(draft).encode()).hexdigest()
    row.draft = draft
    missing_categories = [
        key
        for key in (
            "review_sections",
            "references",
            "graph_nodes",
            "graph_edges",
            "structures",
            "research_targets",
            "methods",
            "datasets",
        )
        if not draft[key]
    ]
    required_missing = sorted(REQUIRED_DRAFT_CATEGORIES & set(missing_categories))
    issues.extend(
        {
            "kind": "missing_required_category",
            "entity_id": category,
            "detail": f"{category} must contain at least one record before confirmation",
        }
        for category in required_missing
    )
    blocking_issue_kinds = {"invalid_evidence_cutoff", "unknown_reference", "unknown_node"}
    valid = not any(issue["kind"] in blocking_issue_kinds for issue in issues) and not required_missing
    row.validation = {
        "valid": valid,
        "issues": issues,
        "citation_coverage": citation_coverage,
        "external_verification": "source_snapshot",
        "missing_categories": missing_categories,
        "required_missing_categories": required_missing,
        "records_to_create": draft["counts"],
        "source_counts": workspace.get("counts", {}),
    }
    row.checksum = checksum
    row.status = "ready"
    RESEARCH_DRAFT_VALIDATIONS.labels("valid" if valid else "invalid").inc()
    row.error = None if valid else "draft_confirmation_blocked"
    row.version += 1
    evidence_tools.close()
    return row


def import_research_generation(
    session: Session,
    row: ResearchGeneration,
    checksum: str,
    user: User,
) -> ResearchGenerationImportResponse:
    source = require_project(session, row.source_project_id, user)
    if row.imported_project_id:
        project = require_project(session, row.imported_project_id, user)
        RESEARCH_IMPORT_ACCEPTANCE.labels("unchanged").inc()
        return ResearchGenerationImportResponse(
            generation_id=row.id,
            project_id=project.id,
            project_name=project.name,
            status="unchanged",
            checksum=row.checksum or checksum,
            counts=(row.draft or {}).get("counts", {}),
        )
    if row.status != "ready" or not row.checksum:
        raise DomainError("research_generation_not_ready", "Research generation is not ready to import", status_code=409)
    if not (row.validation or {}).get("valid"):
        raise DomainError(
            "research_generation_confirmation_blocked",
            "Research draft is missing required categories or failed validation",
            status_code=422,
        )
    if checksum != row.checksum:
        RESEARCH_IMPORT_ACCEPTANCE.labels("checksum_conflict").inc()
        raise DomainError("research_generation_checksum_conflict", "Research draft changed after preview", status_code=412)

    draft = ResearchDraftV2.model_validate(row.draft).model_dump(mode="json")
    closure_issues, _ = _validate_draft(draft)
    if closure_issues:
        RESEARCH_IMPORT_ACCEPTANCE.labels("validation_failed").inc()
        raise DomainError(
            "research_generation_validation_failed",
            "Research draft contains unresolved citation or graph references",
            status_code=422,
        )
    project_data = draft["project"]
    project_name = _localized_text(project_data.get("name"))
    source_package_id = f"copilot-research-v2:{row.checksum}"
    key_seed = re.sub(r"[^A-Za-z0-9._-]+", "-", project_name).strip("-").lower()[:60] or "research"
    project = create_project(
        session,
        ProjectCreate(
            organization_id=source.organization_id,
            name=project_name,
            project_type=str(project_data.get("project_type") or "research"),
            summary=_localized_text(project_data.get("summary")),
            prompt=_localized_text(project_data.get("summary")) or f"Imported research project: {project_name}",
            source_package_id=source_package_id,
            source_project_key=f"{key_seed}-{str(row.id)[:8]}",
            localized_content={
                "name": project_data.get("name"),
                "summary": project_data.get("summary"),
                "copilot_research": {
                    "schema_version": "2.0",
                    "checksum": row.checksum,
                    "provenance": draft["provenance"],
                    "review_status": "pending_review",
                },
            },
        ),
        user,
    )

    primary = draft.get("primary_target")
    if primary:
        target = Target(
            project_id=project.id,
            name=_localized_text(primary.get("name")),
            uniprot_accession=primary.get("uniprot_accession"),
            organism=primary.get("organism"),
            identity_status="unconfirmed",
        )
        session.add(target)
        session.flush()
        project.primary_target_id = target.id
        project.version += 1

    review = draft.get("review_document") or {}
    brief = ResearchBrief(
        project_id=project.id,
        title=_localized_text(review.get("title")) or f"{project_name} — Project Review",
        content=_localized_text(review.get("content")),
        status="draft",
        scope={
            **(review.get("scope") or {}),
            "localized_content": {"title": review.get("title"), "content": review.get("content")},
            "source": "copilot_research_v2",
            "checksum": row.checksum,
            "review_status": "pending_review",
        },
        created_by=user.id,
    )
    session.add(brief)
    session.flush()

    for section in draft["review_sections"]:
        for item in section.get("items", []):
            session.add(ResearchFinding(
                project_id=project.id,
                brief_id=brief.id,
                finding_type=str(section.get("track") or item.get("finding_type") or "observation"),
                title=_localized_text(item.get("title"))[:300] or "Pending review finding",
                content=_localized_text(item.get("content")) or "Pending review finding",
                evidence={
                    **(item.get("evidence") or {}),
                    "localized_content": {"title": item.get("title"), "content": item.get("content")},
                    "review_status": "pending_review",
                    "checksum": row.checksum,
                },
                created_by=user.id,
            ))

    for node in draft["graph_nodes"]:
        session.add(ResearchFinding(
            project_id=project.id,
            brief_id=brief.id,
            finding_type="evidence_entity",
            title=_localized_text(node.get("label"))[:300] or str(node.get("id")),
            content=_localized_text(node.get("description")) or _localized_text(node.get("label")),
            evidence={
                "relation_element": "entity",
                "node_id": node.get("id"),
                "node_kind": node.get("kind"),
                "reference_ids": node.get("reference_ids", []),
                "review_status": "pending_review",
                "checksum": row.checksum,
            },
            created_by=user.id,
        ))
    node_labels = {str(node.get("id")): _localized_text(node.get("label")) for node in draft["graph_nodes"]}
    for edge in draft["graph_edges"]:
        source_label = node_labels.get(str(edge.get("source")), _localized_text(edge.get("source_label")))
        target_label = node_labels.get(str(edge.get("target")), _localized_text(edge.get("target_label")))
        session.add(ResearchFinding(
            project_id=project.id,
            brief_id=brief.id,
            finding_type="evidence_statement",
            title=f"{source_label} —{edge.get('predicate', 'related_to')}→ {target_label}"[:300],
            content=_localized_text(edge.get("summary")) or "Pending review relation",
            evidence={
                "relation_element": "statement",
                "edge_id": edge.get("id"),
                "source": edge.get("source"),
                "target": edge.get("target"),
                "predicate": edge.get("predicate"),
                "assertion_class": edge.get("assertion"),
                "evidence_level": edge.get("evidence_grade"),
                "reference_ids": edge.get("reference_ids", []),
                "source_refs": edge.get("source_urls", []),
                "localized_summary": edge.get("summary"),
                "localized_context": edge.get("context"),
                "review_status": "pending_review",
                "checksum": row.checksum,
            },
            created_by=user.id,
        ))

    for reference in draft["references"]:
        metadata = {**(reference.get("metadata") or {}), **reference, "review_status": "pending_review"}
        session.add(LiteratureDocument(
            project_id=project.id,
            title=_localized_text(reference.get("title"))[:500] or str(reference.get("ref_id")),
            source="copilot_research_v2",
            external_id=str(reference.get("pmid") or reference.get("doi") or reference.get("ref_id") or ""),
            metadata_json=metadata,
            status="pending_review",
        ))

    for candidate in draft["research_targets"]:
        session.add(Candidate(
            project_id=project.id,
            candidate_key=str(candidate.get("candidate_key") or candidate.get("id")),
            name=_localized_text(candidate.get("name"))[:240],
            candidate_kind="research_target",
            status="proposed",
            rank=candidate.get("rank"),
            score=candidate.get("score"),
            scores=candidate.get("scores") or {},
            properties={
                **(candidate.get("properties") or {}),
                "localized_content": {
                    key: candidate.get(key)
                    for key in ("name", "pain_group", "protein_type", "localization", "axis")
                },
                "reference_ids": candidate.get("reference_ids", []),
                "review_status": "pending_review",
                "checksum": row.checksum,
            },
        ))

    for entry in [*draft["methods"], *draft["datasets"]]:
        key = str(entry.get("key") or "methods")
        session.add(KnowledgeEntry(
            project_id=project.id,
            title=_localized_text(entry.get("title"))[:300] or key,
            content=_localized_text(entry.get("content")),
            entry_type=key,
            source={
                **(entry.get("source") or {}),
                "entry_key": key,
                "localized_content": {"title": entry.get("title"), "content": entry.get("content")},
                "data": entry.get("data"),
                "display_data": entry.get("display_data"),
                "review_status": "pending_review",
                "checksum": row.checksum,
            },
            tags=["copilot-research-v2", "pending-review", "dataset" if key in DATASET_KEYS else "method"],
            created_by=user.id,
        ))

    storage: ObjectStorage | None = None
    for structure in draft["structures"]:
        pdb_id = str(structure.get("pdb_id") or "unknown")
        source_artifact = None
        try:
            source_artifact = session.get(Artifact, uuid.UUID(str(structure.get("artifact_id"))))
        except (TypeError, ValueError):
            pass
        source_artifact_project = (
            session.get(Project, source_artifact.project_id) if source_artifact is not None else None
        )
        can_copy = bool(
            source_artifact
            and source_artifact.status == "available"
            and source_artifact.deleted_at is None
            and source_artifact_project
            and source_artifact_project.organization_id == project.organization_id
        )
        if can_copy and source_artifact:
            object_key = f"projects/{project.id}/sha256/{source_artifact.checksum_sha256}"
            storage = storage or ObjectStorage()
            storage.copy(source_artifact.object_key, object_key)
            filename = source_artifact.filename
            content_type = source_artifact.content_type
            status = "available"
            size_bytes = source_artifact.size_bytes
            checksum_sha256 = source_artifact.checksum_sha256
        else:
            object_key = f"research-generations/{row.id}/structures/{pdb_id}.pending"
            filename = f"{pdb_id}.cif"
            content_type = "chemical/x-mmcif"
            status = "pending"
            size_bytes = 0
            checksum_sha256 = hashlib.sha256(object_key.encode()).hexdigest()
        session.add(Artifact(
            project_id=project.id,
            created_by=user.id,
            artifact_type="target_structure",
            filename=filename,
            content_type=content_type,
            object_key=object_key,
            status=status,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            lineage={
                **(structure.get("lineage") or {}),
                "pdb_id": structure.get("pdb_id"),
                "name": _localized_text(structure.get("name")),
                "role": _localized_text(structure.get("role")),
                "method": _localized_text(structure.get("method")),
                "resolution": structure.get("resolution"),
                "reference_id": structure.get("reference_id"),
                "rcsb_url": structure.get("rcsb_url"),
                "review_status": "pending_review",
                "checksum": row.checksum,
                "source_artifact_id": str(source_artifact.id) if source_artifact else None,
            },
        ))

    session.flush()
    row.status = "imported"
    row.imported_project_id = project.id
    row.version += 1
    RESEARCH_IMPORT_ACCEPTANCE.labels("created").inc()
    return ResearchGenerationImportResponse(
        generation_id=row.id,
        project_id=project.id,
        project_name=project.name,
        status="created",
        checksum=row.checksum,
        counts=draft["counts"],
    )
