from __future__ import annotations

import re
import uuid
from collections import OrderedDict
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..candidates.models import Candidate
from ..knowledge.models import KnowledgeEntry
from ..literature.models import LiteratureDocument
from ..projects.models import Project
from ..targets.models import Target
from .models import ResearchBrief, ResearchFinding
from .schemas import (
    LocalizedResearchText,
    ResearchWorkspaceFinding,
    ResearchWorkspaceGraphEdge,
    ResearchWorkspaceGraphNode,
    ResearchWorkspaceKnowledge,
    ResearchWorkspaceProject,
    ResearchWorkspaceReference,
    ResearchWorkspaceResponse,
    ResearchWorkspaceReviewDocument,
    ResearchWorkspaceSection,
    ResearchWorkspaceStructure,
    ResearchWorkspaceTarget,
)

DATASET_KEYS = {"identifiers", "search_log", "field_dictionary", "ontology_relations"}
METHOD_KEYS = {"methods", "search_strategy", "database_schema", "validation_report"}
KNOWLEDGE_TITLES = {
    "methods": {"zh": "研究方法", "en": "Methods", "default": "Methods"},
    "search_strategy": {"zh": "检索策略", "en": "Search Strategy", "default": "Search Strategy"},
    "database_schema": {"zh": "数据库模式", "en": "Database Schema", "default": "Database Schema"},
    "validation_report": {"zh": "验证报告", "en": "Validation Report", "default": "Validation Report"},
    "identifiers": {"zh": "标识符", "en": "Identifiers", "default": "Identifiers"},
    "search_log": {"zh": "检索日志", "en": "Search Log", "default": "Search Log"},
    "field_dictionary": {"zh": "字段字典", "en": "Field Dictionary", "default": "Field Dictionary"},
    "ontology_relations": {"zh": "本体关系", "en": "Ontology Relations", "default": "Ontology Relations"},
}
BOILERPLATE_FINDING_CONTENT = {
    "Treat the review as an operating contract: every downstream workflow choice should cite the application need, the target evidence, and the validation readout it is meant to improve.",
    "Validation should separate target engagement, mechanism, and developability. A candidate can bind but still fail if competition, specificity, stability, or matrix behavior contradicts the intended use.",
    "Use purification readouts as design feedback, not only manufacturing steps: expression yield, SEC profile, tag-cleavage behavior, and aggregation state should feed the next redesign round.",
    "Before design generation, freeze a target packet containing sequence boundaries, construct choices, modeled or experimental coordinates, protected functional residues, and residues allowed for interface sampling.",
    "Rank binding strategies by physical access and assayability first, then by model score; any design that cannot be purified, presented to the target, or counterscreened should remain a lower-confidence hypothesis.",
    "Keep at least two routes in the plan: one conservative route that preserves known structural constraints and one exploratory route that tests whether generative design adds useful diversity.",
}


def _text(value: object) -> str:
    return str(value) if value is not None else ""


def _localized(value: object, fallback: object = "") -> LocalizedResearchText:
    default = _text(fallback)
    if isinstance(value, dict):
        raw_default = value.get("default")
        zh_value = value.get("zh") or value.get("zh-CN")
        en_value = value.get("en")
        default = _text(raw_default or default or zh_value or en_value)
        return LocalizedResearchText(
            zh=_text(zh_value) or None,
            en=_text(en_value) or None,
            default=default,
        )
    raw = _text(value) or default
    return LocalizedResearchText(default=raw)


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return []


def _finding_localized(row: ResearchFinding, key: str) -> LocalizedResearchText:
    localized = (row.evidence or {}).get("localized_content", {})
    value = localized.get(key) if isinstance(localized, dict) else None
    return _localized(value, getattr(row, key))


def _parse_edge_title(title: str) -> tuple[str, str, str]:
    match = re.match(r"^(.+?)\s+—(.+?)→\s+(.+)$", title.strip())
    if not match:
        return title, "related_to", title
    source, predicate, target = match.groups()
    return _text(source), _text(predicate), _text(target)


def _workspace_finding(row: ResearchFinding) -> ResearchWorkspaceFinding:
    return ResearchWorkspaceFinding(
        id=row.id,
        finding_type=row.finding_type,
        title=_finding_localized(row, "title"),
        content=_finding_localized(row, "content"),
        evidence=row.evidence or {},
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _review_document(brief: ResearchBrief | None) -> ResearchWorkspaceReviewDocument | None:
    if brief is None:
        return None
    localized = (brief.scope or {}).get("localized_content", {})
    if isinstance(localized, dict) and ("title" in localized or "content" in localized):
        title_value = localized.get("title")
        content_value = localized.get("content")
    else:
        title_value = None
        content_value = localized
    return ResearchWorkspaceReviewDocument(
        id=brief.id,
        title=_localized(title_value, brief.title),
        content=_localized(content_value, brief.content),
        status=brief.status,
        scope=brief.scope or {},
        version=brief.version,
        updated_at=brief.updated_at,
    )


def _review_sections(findings: list[ResearchFinding]) -> list[ResearchWorkspaceSection]:
    grouped: OrderedDict[str, list[ResearchWorkspaceFinding]] = OrderedDict()
    for row in findings:
        evidence = row.evidence or {}
        if row.content.strip() in BOILERPLATE_FINDING_CONTENT:
            continue
        if evidence.get("relation_element") or evidence.get("claim_id"):
            continue
        if row.finding_type in {"evidence_entity", "evidence_statement"}:
            continue
        grouped.setdefault(row.finding_type, []).append(_workspace_finding(row))
    return [ResearchWorkspaceSection(track=track, items=items) for track, items in grouped.items()]


def _evidence_relationships(
    findings: list[ResearchFinding], brief: ResearchBrief | None
) -> tuple[list[ResearchWorkspaceGraphNode], list[ResearchWorkspaceGraphEdge]]:
    nodes: OrderedDict[str, ResearchWorkspaceGraphNode] = OrderedDict()
    edges: OrderedDict[str, ResearchWorkspaceGraphEdge] = OrderedDict()
    relations = (brief.scope or {}).get("evidence_relations", {}) if brief else {}
    if isinstance(relations, dict):
        for raw in relations.get("nodes", []):
            if not isinstance(raw, dict):
                continue
            node_id = _text(raw.get("id"))
            if not node_id:
                continue
            nodes[node_id] = ResearchWorkspaceGraphNode(
                id=node_id,
                kind=_text(raw.get("kind")) or "evidence",
                label=_localized(raw.get("localized_label"), raw.get("label")),
                description=_localized(raw.get("localized_description"), raw.get("description")),
                reference_ids=_strings(raw.get("reference_ids")),
                review_status=_text(raw.get("review_status")) or "pending_review",
            )

    for row in findings:
        evidence = row.evidence or {}
        relation_element = evidence.get("relation_element")
        if relation_element == "entity" or row.finding_type == "evidence_entity":
            node_id = _text(evidence.get("node_id")) or str(row.id)
            nodes[node_id] = ResearchWorkspaceGraphNode(
                id=node_id,
                kind=_text(evidence.get("node_kind")) or "evidence",
                label=_finding_localized(row, "title"),
                description=_finding_localized(row, "content"),
                reference_ids=_strings(evidence.get("reference_ids")),
                review_status=_text(evidence.get("review_status")) or "pending_review",
            )
            continue
        if not (
            relation_element == "statement" or row.finding_type == "evidence_statement" or evidence.get("claim_id")
        ):
            continue
        parsed_source, parsed_predicate, parsed_target = _parse_edge_title(row.title)
        edge_id = _text(evidence.get("edge_id") or evidence.get("claim_id")) or str(row.id)
        source = _text(evidence.get("source") or evidence.get("subject")) or parsed_source
        target = _text(evidence.get("target") or evidence.get("object")) or parsed_target
        predicate = _text(evidence.get("predicate")) or parsed_predicate
        source_label = _localized(evidence.get("localized_subject"), parsed_source)
        target_label = _localized(evidence.get("localized_object"), parsed_target)
        nodes.setdefault(
            source, ResearchWorkspaceGraphNode(id=source, kind="evidence", label=source_label, description=source_label)
        )
        nodes.setdefault(
            target, ResearchWorkspaceGraphNode(id=target, kind="evidence", label=target_label, description=target_label)
        )
        content = (
            (evidence.get("localized_content") or {}).get("content")
            if isinstance(evidence.get("localized_content"), dict)
            else None
        )
        context = evidence.get("localized_context")
        edges[edge_id] = ResearchWorkspaceGraphEdge(
            id=edge_id,
            source=source,
            target=target,
            source_label=source_label,
            target_label=target_label,
            predicate=predicate,
            summary=_localized(evidence.get("localized_summary") or content, row.content),
            context=_localized(context, evidence.get("context")),
            assertion=_text(evidence.get("assertion_class") or evidence.get("assertion")) or "evidence_based_inference",
            evidence_grade=_text(evidence.get("evidence_level")) or "D",
            reference_ids=_strings(evidence.get("reference_ids") or evidence.get("ref_id")),
            source_urls=_strings(evidence.get("source_refs")),
            review_status=_text(evidence.get("review_status")) or "pending_review",
        )
    return list(nodes.values()), list(edges.values())


def _references(rows: list[LiteratureDocument]) -> list[ResearchWorkspaceReference]:
    result: list[ResearchWorkspaceReference] = []
    for row in rows:
        meta = row.metadata_json or {}
        url = _text(meta.get("url") or meta.get("pubmed_url") or meta.get("doi_url") or meta.get("pmc_url"))
        result.append(
            ResearchWorkspaceReference(
                document_id=row.id,
                ref_id=_text(meta.get("ref_id") or meta.get("citation_id") or row.external_id or row.id),
                title=_localized(meta.get("localized_title"), row.title),
                authors=_text(meta.get("authors")),
                journal=_text(meta.get("journal")),
                year=_text(meta.get("year")),
                doi=_text(meta.get("doi")),
                pmid=_text(meta.get("pmid")),
                pmcid=_text(meta.get("pmcid")),
                abstract=_text(row.abstract),
                url=url,
                verification_status=_text(meta.get("verification_status") or meta.get("review_status") or row.status),
                status=row.status,
                metadata=meta,
            )
        )
    return result


def _reference_source(value: object) -> dict[str, str] | None:
    source = _text(value).strip()
    if not source:
        return None
    doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", source, re.IGNORECASE)
    pmid_match = re.search(r"(?:pubmed\.ncbi\.nlm\.nih\.gov/|PMID\s*:?\s*)(\d{6,9})", source, re.IGNORECASE)
    pdb_match = re.search(r"(?:rcsb\.org/structure/|PDB\s*:?\s*)([0-9][A-Z0-9]{3})", source, re.IGNORECASE)
    uniprot_match = re.search(
        r"(?:uniprot(?:\.org/uniprotkb/|\s+))((?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9])(?:-\d+)?)",
        source,
        re.IGNORECASE,
    )
    if pmid_match:
        pmid = pmid_match.group(1)
        return {
            "key": f"pmid:{pmid}",
            "ref_id": f"PMID {pmid}",
            "pmid": pmid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "provider": "PubMed",
        }
    if pdb_match:
        pdb_id = pdb_match.group(1).upper()
        return {
            "key": f"pdb:{pdb_id}",
            "ref_id": f"PDB {pdb_id}",
            "url": f"https://www.rcsb.org/structure/{pdb_id}",
            "provider": "RCSB Protein Data Bank",
        }
    if uniprot_match:
        accession = uniprot_match.group(1).upper()
        return {
            "key": f"uniprot:{accession}",
            "ref_id": f"UniProt {accession}",
            "url": f"https://www.uniprot.org/uniprotkb/{accession}/entry",
            "provider": "UniProt Consortium",
        }
    if doi_match:
        doi = doi_match.group(1).rstrip(".,;)")
        return {
            "key": f"doi:{doi.lower()}",
            "ref_id": f"DOI {doi}",
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "provider": "Crossref",
        }
    if source.startswith(("https://", "http://")):
        host = urlparse(source).netloc.removeprefix("www.")
        return {
            "key": f"url:{source.rstrip('/')}",
            "ref_id": host or source,
            "url": source,
            "provider": host,
        }
    return None


def _finding_references(
    project_id: uuid.UUID,
    findings: list[ResearchFinding],
    existing: list[ResearchWorkspaceReference],
) -> list[ResearchWorkspaceReference]:
    result = list(existing)
    seen: set[str] = set()
    for reference in existing:
        for raw in (
            reference.url,
            reference.doi and f"DOI {reference.doi}",
            reference.pmid and f"PMID {reference.pmid}",
            reference.ref_id,
        ):
            parsed = _reference_source(raw)
            if parsed:
                seen.add(parsed["key"])

    ordered_findings = sorted(findings, key=lambda row: row.finding_type != "references_reading")
    for row in ordered_findings:
        evidence = row.evidence or {}
        raw_sources = [*_strings(evidence.get("sources")), *_strings(evidence.get("source_refs"))]
        source_metadata = evidence.get("source_metadata") if isinstance(evidence.get("source_metadata"), dict) else {}
        for raw_source in raw_sources:
            parsed = _reference_source(raw_source)
            if not parsed or parsed["key"] in seen:
                continue
            seen.add(parsed["key"])
            metadata = source_metadata.get(raw_source, {}) if isinstance(source_metadata, dict) else {}
            metadata = metadata if isinstance(metadata, dict) else {}
            provider = parsed.get("provider", "")
            title = metadata.get("localized_title") or metadata.get("title") or _finding_localized(row, "title")
            canonical_ref_id = parsed["ref_id"]
            if parsed["key"].startswith("url:"):
                if _text(metadata.get("pmid")):
                    canonical_ref_id = f"PMID {_text(metadata.get('pmid'))}"
                elif _text(metadata.get("doi")):
                    canonical_ref_id = f"DOI {_text(metadata.get('doi'))}"
            result.append(
                ResearchWorkspaceReference(
                    document_id=uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"https://bda.local/projects/{project_id}/references/{parsed['key']}",
                    ),
                    ref_id=canonical_ref_id,
                    title=title if isinstance(title, LocalizedResearchText) else _localized(title, row.title),
                    authors=_text(metadata.get("authors")) or (
                        provider if parsed["key"].startswith(("pdb:", "uniprot:")) else ""
                    ),
                    journal=_text(metadata.get("journal")) or (
                        "RCSB PDB" if parsed["key"].startswith("pdb:") else "UniProt" if parsed["key"].startswith("uniprot:") else ""
                    ),
                    year=_text(metadata.get("year")),
                    doi=_text(metadata.get("doi") or parsed.get("doi")),
                    pmid=_text(metadata.get("pmid") or parsed.get("pmid")),
                    pmcid=_text(metadata.get("pmcid")),
                    abstract=_text(metadata.get("abstract")),
                    url=_text(metadata.get("url") or parsed.get("url")),
                    verification_status=_text(evidence.get("review_status")) or "linked_from_review",
                    status="linked_from_review",
                    metadata={
                        **metadata,
                        "source": raw_source,
                        "provider": provider,
                        "derived_from_finding_id": str(row.id),
                    },
                )
            )
    return result


def _structures(rows: list[Artifact]) -> list[ResearchWorkspaceStructure]:
    storage = ObjectStorage()
    result: list[ResearchWorkspaceStructure] = []
    for row in rows:
        lineage = row.lineage or {}
        pdb_id = _text(lineage.get("pdb_id")).upper()
        localized = lineage.get("localized_content", {}) if isinstance(lineage.get("localized_content"), dict) else {}
        result.append(
            ResearchWorkspaceStructure(
                artifact_id=row.id,
                pdb_id=pdb_id or None,
                name=_localized(
                    localized.get("name") if isinstance(localized, dict) else None, lineage.get("name") or row.filename
                ),
                role=_localized(localized.get("role") if isinstance(localized, dict) else None, lineage.get("role")),
                method=_localized(
                    localized.get("method") if isinstance(localized, dict) else None, lineage.get("method")
                ),
                resolution=float(lineage["resolution"]) if isinstance(lineage.get("resolution"), int | float) else None,
                reference_id=_text(lineage.get("reference_id")) or (f"PDB {pdb_id}" if pdb_id else ""),
                rcsb_url=_text(lineage.get("rcsb_url")) or (
                    f"https://www.rcsb.org/structure/{pdb_id}" if pdb_id else ""
                ),
                download_url=storage.download_url(row.object_key) if row.status == "available" else None,
                status=row.status,
                lineage=lineage,
            )
        )
    return result


def _targets(rows: list[Candidate]) -> list[ResearchWorkspaceTarget]:
    result: list[ResearchWorkspaceTarget] = []
    for row in rows:
        props = row.properties or {}
        localized = props.get("localized_content", {}) if isinstance(props.get("localized_content"), dict) else {}
        result.append(
            ResearchWorkspaceTarget(
                id=row.id,
                candidate_key=row.candidate_key,
                name=_localized(localized.get("name"), row.name),
                pain_group=_localized(localized.get("pain_group"), props.get("pain_group")),
                gene=_text(props.get("gene")),
                protein_type=_localized(localized.get("protein_type"), props.get("protein_type")),
                localization=_localized(localized.get("localization"), props.get("localization")),
                axis=_localized(localized.get("axis"), props.get("axis")),
                score=row.score,
                rank=row.rank,
                scores=row.scores or {},
                properties=props,
                reference_ids=_strings(props.get("reference_ids")),
                review_status=_text(props.get("review_status")),
            )
        )
    return result


def _knowledge(rows: list[KnowledgeEntry]) -> tuple[list[ResearchWorkspaceKnowledge], list[ResearchWorkspaceKnowledge]]:
    methods: list[ResearchWorkspaceKnowledge] = []
    datasets: list[ResearchWorkspaceKnowledge] = []
    for row in rows:
        source = row.source or {}
        localized = source.get("localized_content", {})
        key = _text(source.get("entry_key") or row.entry_type)
        if isinstance(localized, dict) and ("title" in localized or "content" in localized):
            title_value = localized.get("title")
            content_value = localized.get("content")
        else:
            title_value = None
            content_value = localized
        if title_value is None:
            title_value = KNOWLEDGE_TITLES.get(key)
        item = ResearchWorkspaceKnowledge(
            id=row.id,
            key=key,
            title=_localized(title_value, row.title),
            content=_localized(content_value, row.content),
            data=source.get("data"),
            display_data=source.get("display_data"),
            source=source,
            version=row.version,
        )
        (datasets if key in DATASET_KEYS else methods).append(item)
    return methods, datasets


def build_research_workspace(session: Session, project: Project) -> ResearchWorkspaceResponse:
    brief = session.scalar(
        select(ResearchBrief).where(ResearchBrief.project_id == project.id).order_by(ResearchBrief.created_at.desc())
    )
    findings = list(
        session.scalars(
            select(ResearchFinding).where(ResearchFinding.project_id == project.id).order_by(ResearchFinding.created_at)
        )
    )
    documents = list(
        session.scalars(
            select(LiteratureDocument)
            .where(LiteratureDocument.project_id == project.id)
            .order_by(LiteratureDocument.created_at)
        )
    )
    artifacts = list(
        session.scalars(
            select(Artifact)
            .where(
                Artifact.project_id == project.id,
                Artifact.artifact_type == "target_structure",
                Artifact.deleted_at.is_(None),
            )
            .order_by(Artifact.created_at)
        )
    )
    candidates = list(
        session.scalars(
            select(Candidate)
            .where(Candidate.project_id == project.id, Candidate.candidate_kind == "research_target")
            .order_by(Candidate.rank, Candidate.created_at)
        )
    )
    knowledge = list(
        session.scalars(
            select(KnowledgeEntry).where(KnowledgeEntry.project_id == project.id).order_by(KnowledgeEntry.created_at)
        )
    )
    target = session.get(Target, project.primary_target_id) if project.primary_target_id else None
    localized_project = project.localized_content or {}
    graph_nodes, graph_edges = _evidence_relationships(findings, brief)
    methods, datasets = _knowledge(knowledge)
    references = _finding_references(project.id, findings, _references(documents))
    structures = _structures(artifacts)
    research_targets = _targets(candidates)
    primary_localized = localized_project.get("primary_target", {}) if isinstance(localized_project, dict) else {}
    primary_target = None
    if target:
        primary_target = {
            "id": str(target.id),
            "name": _localized(
                primary_localized.get("name") if isinstance(primary_localized, dict) else None, target.name
            ).model_dump(),
            "uniprot_accession": target.uniprot_accession,
            "organism": target.organism,
            "identity_status": target.identity_status,
            "structure_status": target.structure_status,
        }
    package = localized_project.get("package", {}) if isinstance(localized_project, dict) else {}
    return ResearchWorkspaceResponse(
        project=ResearchWorkspaceProject(
            id=project.id,
            name=_localized(
                localized_project.get("name") if isinstance(localized_project, dict) else None, project.name
            ),
            summary=_localized(
                localized_project.get("summary") if isinstance(localized_project, dict) else None, project.summary
            ),
            project_type=project.project_type,
            source_package_id=project.source_package_id,
            source_project_key=project.source_project_key,
            package=package if isinstance(package, dict) else {},
            primary_target=primary_target,
        ),
        review_document=_review_document(brief),
        review_sections=_review_sections(findings),
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        references=references,
        structures=structures,
        research_targets=research_targets,
        methods=methods,
        datasets=datasets,
        counts={
            "findings": len(findings),
            "review_findings": sum(len(section.items) for section in _review_sections(findings)),
            "graph_nodes": len(graph_nodes),
            "graph_edges": len(graph_edges),
            "references": len(references),
            "structures": len(structures),
            "research_targets": len(research_targets),
            "methods": len(methods),
            "datasets": len(datasets),
        },
    )
