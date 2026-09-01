"""Research generation and gap resolution.

Moved out of ``compute.tasks``, which had grown to hold this domain's tasks alongside a
dozen others. Task names and queue routing are unchanged.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..artifacts.storage import ObjectStorage
from ..core.celery_app import celery_app
from ..core.config import get_settings
from ..core.database import SessionFactory, session_scope

# research_gaps_resolve runs a literature search inline rather than enqueuing one,
# because the caller needs the reference before it can decide what to do next.
from ..literature.tasks import literature_search
from ..projects.models import Project

settings = get_settings()


def _research_target_accession(session: Session, candidate) -> str:
    import httpx

    from ..knowledge.models import KnowledgeEntry

    properties = candidate.properties or {}
    direct = str(properties.get("uniprot_accession") or properties.get("uniprot") or "").strip().upper()
    if direct:
        return direct
    gene = str(properties.get("gene") or "").strip().upper()
    if any(separator in gene for separator in ("/", ",", ";", "|")):
        gene = ""
    if not gene:
        gene = {
            "PD-1": "PDCD1",
            "PD-L1": "CD274",
            "PD-L2": "PDCD1LG2",
            "SHP-2": "PTPN11",
            "CD80 IN CIS": "CD80",
        }.get(str(candidate.name or "").strip().upper(), "")
    aliases = {item.strip().upper() for item in re.split(r"[/,;|]", str(candidate.name or "")) if item.strip()}
    if gene:
        aliases.add(gene)
    entries = session.scalars(select(KnowledgeEntry).where(KnowledgeEntry.project_id == candidate.project_id))
    for entry in entries:
        source = entry.source or {}
        if str(source.get("entry_key") or entry.entry_type) != "identifiers":
            continue
        rows = source.get("data")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_gene = str(row.get("gene") or "").strip().upper()
            row_target = str(row.get("target") or row.get("name") or "").strip().upper()
            if aliases and row_gene not in aliases and row_target not in aliases:
                continue
            accession = str(row.get("uniprot_accession") or row.get("accession") or "").strip().upper()
            if accession:
                return accession
    if not gene:
        return ""
    response = httpx.get(
        "https://rest.uniprot.org/uniprotkb/search",
        params={
            "query": (f"(gene_exact:{gene}) AND (organism_id:9606) " "AND (reviewed:true)"),
            "format": "json",
            "size": 2,
            "fields": "accession,id,gene_names,protein_name,organism_name,length",
        },
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": "BDA-Research/2.0 (gap resolution)"},
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or len(results) != 1:
        return ""
    accession = str(results[0].get("primaryAccession") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6,10}", accession):
        return ""
    candidate.properties = {
        **properties,
        "gene": properties.get("gene") or gene,
        "uniprot_accession": accession,
        "identity_resolution": {
            "status": "verified_uniprot_rest",
            "gene": gene,
            "uniprot_accession": accession,
            "source_url": str(response.url),
            "resolved_at": datetime.now(UTC).isoformat(),
        },
    }
    candidate.version += 1
    session.flush()
    return accession


def _research_reference_document(session: Session, project_id: uuid.UUID, ref_id: str):
    from ..literature.models import LiteratureDocument

    for document in session.scalars(select(LiteratureDocument).where(LiteratureDocument.project_id == project_id)):
        metadata = document.metadata_json or {}
        if ref_id in {
            str(document.id),
            str(document.external_id or ""),
            str(metadata.get("ref_id") or ""),
            str(metadata.get("citation_id") or ""),
        }:
            return document
    return None


def _import_alphafold_research_structure(candidate_id: uuid.UUID) -> dict:
    from urllib.parse import urlparse

    import httpx

    from ..candidates.models import Candidate

    with session_scope() as session:
        # Outbox/Celery delivery is at-least-once. Serialize imports for the
        # same target through the complete fetch/store transaction so duplicate
        # deliveries cannot both create an artifact.
        candidate = session.scalar(select(Candidate).where(Candidate.id == candidate_id).with_for_update())
        if candidate is None:
            raise ValueError("research_target_not_found")
        if candidate.structure_artifact_id:
            artifact = session.get(Artifact, candidate.structure_artifact_id)
            if artifact is not None and artifact.status == "available":
                return {
                    "id": "predicted_structure",
                    "kind": "structure",
                    "status": "resolved",
                    "resolution": "existing_project_structure",
                    "artifact_id": str(artifact.id),
                }
        for artifact in session.scalars(
            select(Artifact).where(
                Artifact.project_id == candidate.project_id,
                Artifact.artifact_type == "target_structure",
                Artifact.deleted_at.is_(None),
            )
        ):
            lineage = artifact.lineage or {}
            if str(lineage.get("research_target_id") or "") == str(candidate.id) and artifact.status == "available":
                candidate.structure_artifact_id = artifact.id
                candidate.version += 1
                return {
                    "id": "predicted_structure",
                    "kind": "structure",
                    "status": "resolved",
                    "resolution": "existing_alphafold_model",
                    "artifact_id": str(artifact.id),
                }
        accession = _research_target_accession(session, candidate)
        if not accession or not re.fullmatch(r"[A-Z0-9]{6,10}", accession):
            raise ValueError("research_target_uniprot_accession_missing")
        project = session.get(Project, candidate.project_id)
        if project is None:
            raise ValueError("research_target_project_not_found")
        project_id = project.id
        created_by = project.owner_id
        candidate_name = candidate.name
        candidate_key = candidate.candidate_key

        api_url = f"https://alphafold.com/api/prediction/{accession}"
        metadata_response = httpx.get(
            api_url,
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "BDA-Research/2.0 (gap resolution)"},
        )
        metadata_response.raise_for_status()
        predictions = metadata_response.json()
        if not isinstance(predictions, list):
            raise ValueError("alphafold_prediction_response_invalid")
        prediction = next(
            (
                item
                for item in predictions
                if isinstance(item, dict)
                and str(item.get("uniprotAccession") or "").upper() == accession
                and not item.get("isComplex")
                and item.get("pdbUrl")
            ),
            None,
        )
        if prediction is None:
            raise ValueError("alphafold_prediction_not_found")
        pdb_url = str(prediction["pdbUrl"])
        parsed_url = urlparse(pdb_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "alphafold.ebi.ac.uk":
            raise ValueError("alphafold_download_url_invalid")
        structure_response = httpx.get(
            pdb_url,
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "BDA-Research/2.0 (gap resolution)"},
        )
        structure_response.raise_for_status()
        body = structure_response.content
        if not body or len(body) > settings.max_upload_bytes or b"ATOM" not in body[: min(len(body), 200_000)]:
            raise ValueError("alphafold_structure_invalid")
        checksum = hashlib.sha256(body).hexdigest()
        artifact_id = uuid.uuid4()
        entry_id = str(prediction.get("entryId") or f"AF-{accession}-F1")
        version = prediction.get("latestVersion")
        filename = f"{entry_id}-model_v{version}.pdb" if version else f"{entry_id}.pdb"
        object_key = f"projects/{project_id}/research-targets/{candidate_id}/" f"{artifact_id}.pdb"
        ObjectStorage().put_bytes(object_key, body, "chemical/x-pdb")
        artifact = Artifact(
            id=artifact_id,
            project_id=project_id,
            created_by=created_by,
            artifact_type="target_structure",
            filename=filename,
            content_type="chemical/x-pdb",
            object_key=object_key,
            size_bytes=len(body),
            checksum_sha256=checksum,
            lineage={
                "source": "alphafold_db",
                "predicted": True,
                "method": "AlphaFold predicted structure",
                "name": f"{candidate_name} predicted structure",
                "role": "research target predicted model",
                "research_target_id": str(candidate_id),
                "candidate_key": candidate_key,
                "uniprot_accession": accession,
                "model_entity_id": prediction.get("modelEntityId"),
                "entry_id": entry_id,
                "database_version": version,
                "global_metric_value": prediction.get("globalMetricValue"),
                "api_url": api_url,
                "source_url": pdb_url,
                "retrieved_at": datetime.now(UTC).isoformat(),
            },
        )
        session.add(artifact)
        candidate.structure_artifact_id = artifact.id
        candidate.version += 1
        return {
            "id": "predicted_structure",
            "kind": "structure",
            "status": "resolved_with_predicted_model",
            "resolution": "alphafold_db_import",
            "artifact_id": str(artifact_id),
            "uniprot_accession": accession,
            "database_version": version,
            "note": "Predicted model imported; this does not replace an experimental structure.",
        }


@celery_app.task(name="bda_v2.research_gaps_resolve")
def research_gaps_resolve(research_target_id: str, payload: dict) -> dict:
    import httpx

    from ..candidates.models import Candidate
    from ..literature.models import LiteratureChunk, LiteratureSearchRun

    parsed = uuid.UUID(research_target_id)
    with SessionFactory() as session:
        candidate = session.get(Candidate, parsed)
        if candidate is None or candidate.candidate_kind != "research_target":
            return {"research_target_id": research_target_id, "status": "missing"}
        project = session.get(Project, candidate.project_id)
        if project is None:
            return {"research_target_id": research_target_id, "status": "missing"}
        project_id = project.id
        created_by = project.owner_id
        reference_ids = [str(item) for item in (candidate.properties or {}).get("reference_ids", []) if str(item)]

    items: list[dict] = []
    if payload.get("resolve_structure", True):
        try:
            items.append(_import_alphafold_research_structure(parsed))
        except ValueError as exc:
            if str(exc) == "research_target_uniprot_accession_missing":
                items.append(
                    {
                        "id": "predicted_structure",
                        "kind": "structure",
                        "status": "requires_review",
                        "detail": (
                            "This Research target is not uniquely mapped to one "
                            "UniProt accession. Define a single molecular entity "
                            "before importing a predicted structure."
                        ),
                    }
                )
            else:
                items.append(
                    {
                        "id": "predicted_structure",
                        "kind": "structure",
                        "status": "failed",
                        "detail": str(exc)[:500],
                    }
                )
        except (RuntimeError, httpx.HTTPError) as exc:
            items.append(
                {
                    "id": "predicted_structure",
                    "kind": "structure",
                    "status": "failed",
                    "detail": str(exc)[:500],
                }
            )

    if payload.get("resolve_references", True):
        for ref_id in reference_ids:
            with SessionFactory() as session:
                document = _research_reference_document(session, project_id, ref_id)
                if document is None:
                    items.append(
                        {
                            "id": f"reference:{ref_id}",
                            "kind": "reference_content",
                            "status": "failed",
                            "detail": "reference_not_found",
                        }
                    )
                    continue
                has_content = session.scalar(
                    select(LiteratureChunk.id).where(LiteratureChunk.document_id == document.id).limit(1)
                )
                metadata = document.metadata_json or {}
                pmid = str(metadata.get("pmid") or "").strip()
                doi = str(metadata.get("doi") or "").strip()
                document_id = document.id
                provenance = metadata.get("content_provenance") or {}
            if has_content:
                items.append(
                    {
                        "id": f"reference:{ref_id}",
                        "kind": "reference_content",
                        "status": "resolved",
                        "resolution": "existing_saved_content",
                        "document_id": str(document_id),
                        "content_kind": provenance.get("content_kind"),
                    }
                )
                continue
            query = f"EXT_ID:{pmid} AND SRC:MED" if pmid else f'DOI:"{doi}"' if doi else ""
            if not query:
                items.append(
                    {
                        "id": f"reference:{ref_id}",
                        "kind": "reference_content",
                        "status": "failed",
                        "detail": "reference_has_no_searchable_identifier",
                    }
                )
                continue
            with session_scope() as session:
                run = LiteratureSearchRun(
                    project_id=project_id,
                    query=query,
                    sources=["europe_pmc"],
                    requested_limit=1,
                    fetch_full_text=True,
                    extract_claims=True,
                    created_by=created_by,
                )
                session.add(run)
                session.flush()
                run_id = str(run.id)
            search_result = literature_search.run(run_id)
            with SessionFactory() as session:
                document = _research_reference_document(session, project_id, ref_id)
                content_available = bool(
                    document
                    and session.scalar(
                        select(LiteratureChunk.id).where(LiteratureChunk.document_id == document.id).limit(1)
                    )
                )
                provenance = (document.metadata_json or {}).get("content_provenance") or {} if document else {}
            items.append(
                {
                    "id": f"reference:{ref_id}",
                    "kind": "reference_content",
                    "status": "resolved" if content_available else "failed",
                    "resolution": "europe_pmc_ingestion" if content_available else None,
                    "document_id": str(document.id) if document else None,
                    "content_kind": provenance.get("content_kind"),
                    "search_run_id": run_id,
                    "detail": None if content_available else search_result.get("status"),
                }
            )

    items.append(
        {
            "id": "scientific_validation",
            "kind": "non_automatable_scientific_gaps",
            "status": "requires_experiment",
            "detail": (
                "Wet-lab, clinical, patent-landscape, and experimental-structure gaps "
                "remain open until new reviewed evidence is produced or imported."
            ),
        }
    )
    failed = sum(1 for item in items if item.get("status") == "failed")
    resolved = sum(1 for item in items if str(item.get("status") or "").startswith("resolved"))
    status = "completed_with_failures" if failed else "completed_with_remaining_scientific_gaps"
    operation_id = str(payload.get("operation_id") or "")
    with session_scope() as session:
        candidate = session.scalar(
            select(Candidate).where(Candidate.id == parsed).with_for_update()
        )
        if candidate is None:
            return {"research_target_id": research_target_id, "status": "missing"}
        properties = dict(candidate.properties or {})
        pending = properties.get("gap_resolution")
        resolution = dict(pending) if isinstance(pending, dict) else {}
        current_operation_id = str(resolution.get("operation_id") or "")
        if not operation_id or not current_operation_id or operation_id == current_operation_id:
            resolution.update(
                {
                    "status": status,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "resolved_count": resolved,
                    "failed_count": failed,
                    "items": items,
                }
            )
            properties["gap_resolution"] = resolution
            candidate.properties = properties
            candidate.version += 1
    return {
        "research_target_id": research_target_id,
        "operation_id": operation_id or None,
        "status": status,
        "resolved_count": resolved,
        "failed_count": failed,
        "items": items,
    }


@celery_app.task(name="bda_v2.research_generate")
def research_generate(generation_id: str) -> dict:
    from ..research.generation import finalize_research_generation
    from ..research.models import ResearchGeneration

    parsed = uuid.UUID(generation_id)
    with session_scope() as session:
        row = session.get(ResearchGeneration, parsed)
        if row is None:
            return {"generation_id": generation_id, "status": "missing"}
        finalize_research_generation(session, row)
        return {
            "generation_id": generation_id,
            "status": row.status,
            "checksum": row.checksum,
            "counts": (row.draft or {}).get("counts", {}),
        }


DECISION_TREE_SYSTEM_PROMPT = (
    "You read a protein-design project's kickoff brief and propose the starting shape of "
    "its decision record: a small tree of research goals, and the open questions the "
    "project has not decided yet.\n\n"
    "Return ONLY a JSON object, no prose and no code fence, of the form:\n"
    '{"goals": [{"title": "...", "detail": "...", "children": [...]}], '
    '"branches": [{"title": "...", "summary": "...", "lane": "dry|wet|both", '
    '"goal_title": "<title of one goal above>", '
    '"alternatives": [{"option": "...", "rejected_because": "..."}]}]}\n\n'
    "Rules that matter more than coverage:\n"
    "- At most 12 goals in total, at most 3 levels deep, at most 12 branches. A reviewer "
    "who cannot read the whole proposal in one sitting stops reviewing and starts accepting.\n"
    "- Goal titles must be unique; every branch's goal_title must match one exactly.\n"
    "- A branch is a QUESTION, not a conclusion. Never state an answer, a ranking, or a "
    "recommendation. Do not claim any result.\n"
    "- `lane` is where the question will be ANSWERED: `dry` for computation, `wet` for "
    "bench work, `both` when the evidence comes from one half and the consequence lands "
    "in the other. Getting this right on day one is cheap; reconstructing it later is not.\n"
    "- `alternatives` is optional and only for approaches the brief itself already rules "
    "out, with the brief's own reason. Never invent a rejection.\n"
    "- Computational scores do not establish biological function; if the brief implies a "
    "functional claim, that belongs in a `wet` or `both` branch, not a `dry` one."
)


@celery_app.task(name="bda_v2.research_decision_tree_draft")
def research_decision_tree_draft(draft_id: str) -> dict:
    """Draft a starting tree, and store it only if it validates.

    Validation is not politeness. The draft is handed to a person to review item by item,
    and a malformed or over-large proposal makes that review worse, not merely uglier: an
    unmatched `goal_title` would silently reparent a branch, and forty items would not be
    read. Failing here with the parse error is more useful than storing something that
    looks reviewable and is not.
    """
    import json

    import httpx

    from ..core.problem import DomainError
    from ..projects.tasks import _select_llm_provider
    from .models import DecisionTreeDraft
    from .schemas import DecisionTreeProposal

    parsed = uuid.UUID(draft_id)
    with session_scope() as session:
        row = session.get(DecisionTreeDraft, parsed)
        if row is None:
            return {"draft_id": draft_id, "status": "missing"}

        request = row.request or {}
        provider = _select_llm_provider(session, request.get("llm_provider_id"))
        if provider is None:
            row.status = "failed"
            row.error = "no_llm_provider_configured"
            row.version += 1
            return {"draft_id": draft_id, "status": row.status}

        user_message = (
            f"Project type: {request.get('project_type') or ''}\n\n"
            f"Design brief:\n{request.get('prompt') or ''}"
        )
        try:
            from ..copilot.provider import complete

            text = complete(
                provider,
                [
                    {"role": "system", "content": DECISION_TREE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            proposal = DecisionTreeProposal.model_validate(json.loads(_strip_fence(text)))
        except (DomainError, ValueError, json.JSONDecodeError, httpx.HTTPError) as exc:
            row.status = "failed"
            row.error = str(exc)[:4000]
            row.version += 1
            return {"draft_id": draft_id, "status": row.status}

        row.status = "ready"
        row.draft = proposal.model_dump(mode="json")
        row.version += 1
        return {"draft_id": draft_id, "status": row.status}


def _strip_fence(text: str) -> str:
    """Models fence JSON even when told not to; that is not worth a failed draft."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped.split("\n", 1)[1] if "\n" in stripped else ""
    return body.rsplit("```", 1)[0].strip()
