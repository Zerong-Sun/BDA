from __future__ import annotations

from backend_v2.app.artifacts.models import Artifact
from backend_v2.app.artifacts.storage import ObjectStorage
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.core.database import session_scope
from backend_v2.app.projects.models import Project
from backend_v2.app.research.generation import (
    _ensure_research_targets,
    _ensure_review_sections,
    _evidence_source_project,
    _localized_text,
)
from backend_v2.app.research.models import ResearchBrief, ResearchFinding
from backend_v2.app.research.workspace import build_research_workspace
from sqlalchemy import select


def repair() -> tuple[int, int, int, int]:
    findings_created = 0
    targets_created = 0
    structures_repaired = 0
    summaries_repaired = 0
    storage: ObjectStorage | None = None
    with session_scope() as session:
        projects = list(
            session.scalars(
                select(Project).where(Project.source_package_id.like("copilot-research-v2:%"))
            )
        )
        for project in projects:
            evidence_project = _evidence_source_project(session, project)
            source_localized = evidence_project.localized_content or {}
            source_summary = source_localized.get("summary") or {"default": evidence_project.summary}
            localized = dict(project.localized_content or {})
            if project.summary != evidence_project.summary or localized.get("summary") != source_summary:
                project.summary = evidence_project.summary
                localized["summary"] = source_summary
                project.localized_content = localized
                project.version += 1
                summaries_repaired += 1
            current = build_research_workspace(session, project).model_dump(mode="json")
            brief = session.scalar(
                select(ResearchBrief)
                .where(ResearchBrief.project_id == project.id)
                .order_by(ResearchBrief.created_at.desc())
            )
            if brief is None:
                brief = ResearchBrief(
                    project_id=project.id,
                    title=f"{project.name} — Project Review",
                    content="",
                    status="draft",
                    scope={"source": "generated_research_repair", "review_status": "pending_review"},
                    created_by=project.owner_id,
                )
                session.add(brief)
                session.flush()

            if not current.get("review_sections"):
                for section in _ensure_review_sections(current):
                    for item in section.get("items", []):
                        session.add(
                            ResearchFinding(
                                project_id=project.id,
                                brief_id=brief.id,
                                finding_type=str(section.get("track") or "prior_art_landscape"),
                                title=_localized_text(item.get("title"))[:300],
                                content=_localized_text(item.get("content")),
                                evidence=item.get("evidence") or {},
                                created_by=project.owner_id,
                            )
                        )
                        findings_created += 1

            if not current.get("research_targets"):
                targets = _ensure_research_targets(current, limit=100, strata="")
                for target in targets:
                    session.add(
                        Candidate(
                            project_id=project.id,
                            candidate_key=str(target.get("candidate_key")),
                            name=_localized_text(target.get("name"))[:240],
                            candidate_kind="research_target",
                            status="proposed",
                            rank=target.get("rank"),
                            score=target.get("score"),
                            scores=target.get("scores") or {},
                            properties={
                                **(target.get("properties") or {}),
                                "localized_content": {
                                    key: target.get(key)
                                    for key in ("name", "pain_group", "protein_type", "localization", "axis")
                                },
                                "reference_ids": target.get("reference_ids", []),
                                "review_status": "pending_review",
                            },
                        )
                    )
                    targets_created += 1

            source_structures = {
                str((artifact.lineage or {}).get("pdb_id") or "").upper(): artifact
                for artifact in session.scalars(
                    select(Artifact).where(
                        Artifact.project_id == evidence_project.id,
                        Artifact.artifact_type == "target_structure",
                        Artifact.status == "available",
                        Artifact.deleted_at.is_(None),
                    )
                )
            }
            pending_structures = session.scalars(
                select(Artifact).where(
                    Artifact.project_id == project.id,
                    Artifact.artifact_type == "target_structure",
                    Artifact.status == "pending",
                    Artifact.deleted_at.is_(None),
                )
            )
            for artifact in pending_structures:
                pdb_id = str((artifact.lineage or {}).get("pdb_id") or "").upper()
                source = source_structures.get(pdb_id)
                if source is None:
                    continue
                target_key = f"projects/{project.id}/sha256/{source.checksum_sha256}"
                storage = storage or ObjectStorage()
                storage.copy(source.object_key, target_key)
                artifact.filename = source.filename
                artifact.content_type = source.content_type
                artifact.object_key = target_key
                artifact.status = "available"
                artifact.size_bytes = source.size_bytes
                artifact.checksum_sha256 = source.checksum_sha256
                artifact.lineage = {
                    **(artifact.lineage or {}),
                    "source_artifact_id": str(source.id),
                    "repair_status": "copied_from_evidence_source",
                }
                artifact.version += 1
                structures_repaired += 1
    return findings_created, targets_created, structures_repaired, summaries_repaired


if __name__ == "__main__":
    findings, targets, structures, summaries = repair()
    print(
        f"created {findings} review findings, created {targets} research targets, "
        f"repaired {structures} structures, repaired {summaries} project summaries"
    )
