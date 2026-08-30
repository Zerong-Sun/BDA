from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..candidates.models import Candidate
from ..compute.models import ComputeDraft, Job
from ..experiments.models import ExperimentResult
from ..knowledge.models import KnowledgeEntry
from ..projects.models import Project
from ..targets.models import Target
from ..workflows.models import WorkflowNode, WorkflowRun

MAX_CONTEXT_TEXT = 8_000
MAX_CONTEXT_ITEMS = 100
MAX_CONTEXT_DEPTH = 8


def _sensitive_key(key: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", key.lower())
    markers = (
        "apikey",
        "token",
        "credential",
        "password",
        "secret",
        "authorization",
        "cookie",
        "privatekey",
        "signingkey",
        "objectkey",
        "downloadurl",
        "signedurl",
        "presignedurl",
    )
    return any(
        compact == marker
        or compact.endswith(marker)
        or (marker != "token" and compact.startswith(marker))
        for marker in markers
    )


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth >= MAX_CONTEXT_DEPTH:
        return "[truncated: maximum nesting depth]"
    if isinstance(value, dict):
        return {
            str(key): _sanitize(item, depth=depth + 1)
            for key, item in list(value.items())[:MAX_CONTEXT_ITEMS]
            if not _sensitive_key(str(key)) and not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [
            _sanitize(item, depth=depth + 1)
            for item in value[:MAX_CONTEXT_ITEMS]
        ]
    if isinstance(value, str) and len(value) > MAX_CONTEXT_TEXT:
        return value[:MAX_CONTEXT_TEXT] + "\n[truncated]"
    return value


def _uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("invalid_entity_id") from exc


class ProjectContextService:
    """Bounded, read-only access to operational project data."""

    def __init__(self, session: Session, project: Project):
        self.session = session
        self.project = project
        self.project_id = project.id

    def list_targets(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(Target)
            .where(Target.project_id == self.project_id)
            .order_by(Target.created_at)
            .limit(max(1, min(limit, 50)))
        )
        return [
            self._item(
                "target",
                row.id,
                row.name,
                {
                    "name": row.name,
                    "uniprot_accession": row.uniprot_accession,
                    "organism": row.organism,
                    "identity_status": row.identity_status,
                    "structure_status": row.structure_status,
                    "structure_artifact_id": (
                        str(row.structure_artifact_id)
                        if row.structure_artifact_id
                        else None
                    ),
                },
            )
            for row in rows
        ]

    def list_candidates(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = select(Candidate).where(
            Candidate.project_id == self.project_id,
            Candidate.candidate_kind == "design_candidate",
        )
        if status:
            query = query.where(Candidate.status == status)
        rows = self.session.scalars(
            query.order_by(
                Candidate.rank.asc().nullslast(),
                Candidate.score.desc().nullslast(),
                Candidate.created_at,
            ).limit(max(1, min(limit, 50)))
        )
        return [
            self._item(
                "candidate",
                row.id,
                row.name,
                {
                    "candidate_key": row.candidate_key,
                    "name": row.name,
                    "status": row.status,
                    "rank": row.rank,
                    "score": row.score,
                    "scores": _sanitize(row.scores or {}),
                    "properties": _sanitize(row.properties or {}),
                    "structure_artifact_id": (
                        str(row.structure_artifact_id)
                        if row.structure_artifact_id
                        else None
                    ),
                    "complex_artifact_id": (
                        str(row.complex_artifact_id)
                        if row.complex_artifact_id
                        else None
                    ),
                },
            )
            for row in rows
        ]

    def list_experiment_results(
        self,
        *,
        candidate_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        parsed_candidate_id = _uuid(candidate_id)
        query = select(ExperimentResult).where(
            ExperimentResult.project_id == self.project_id
        )
        if parsed_candidate_id:
            query = query.where(ExperimentResult.candidate_id == parsed_candidate_id)
        rows = self.session.scalars(
            query.order_by(ExperimentResult.created_at.desc()).limit(
                max(1, min(limit, 50))
            )
        )
        return [
            self._item(
                "experiment_result",
                row.id,
                f"{row.experiment_type}: {row.candidate_ref or row.candidate_id or 'project'}",
                {
                    "candidate_id": str(row.candidate_id) if row.candidate_id else None,
                    "candidate_ref": row.candidate_ref,
                    "experiment_type": row.experiment_type,
                    "pass_status": row.pass_status,
                    "value": row.value,
                    "unit": row.unit,
                    "conclusion": row.conclusion,
                    "failure_reason": row.failure_reason,
                    "metadata": _sanitize(row.result_metadata or {}),
                    "source_artifact_id": (
                        str(row.source_artifact_id)
                        if row.source_artifact_id
                        else None
                    ),
                },
            )
            for row in rows
        ]

    def workflow_status(
        self,
        *,
        workflow_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        parsed_workflow_id = _uuid(workflow_id)
        query = select(WorkflowRun).where(
            WorkflowRun.project_id == self.project_id
        )
        if parsed_workflow_id:
            query = query.where(WorkflowRun.id == parsed_workflow_id)
        workflows = list(
            self.session.scalars(
                query.order_by(WorkflowRun.created_at.desc()).limit(
                    max(1, min(limit, 20))
                )
            )
        )
        if not workflows:
            return []
        nodes = list(
            self.session.scalars(
                select(WorkflowNode)
                .where(
                    WorkflowNode.workflow_run_id.in_(
                        [workflow.id for workflow in workflows]
                    )
                )
                .order_by(WorkflowNode.workflow_run_id, WorkflowNode.node_key)
            )
        )
        by_workflow: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for node in nodes:
            by_workflow.setdefault(node.workflow_run_id, []).append(
                {
                    "id": str(node.id),
                    "node_key": node.node_key,
                    "node_type": node.node_type,
                    "model_plugin": node.model_plugin,
                    "status": node.status,
                    "error_message": node.error_message,
                }
            )
        return [
            self._item(
                "workflow",
                workflow.id,
                workflow.name,
                {
                    "name": workflow.name,
                    "status": workflow.status,
                    "nodes": by_workflow.get(workflow.id, [])[:100],
                    "graph_summary": {
                        "node_count": len((workflow.graph or {}).get("nodes", [])),
                        "edge_count": len((workflow.graph or {}).get("edges", [])),
                    },
                },
            )
            for workflow in workflows
        ]

    def compute_status(self, *, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        bounded = max(1, min(limit, 50))
        drafts = list(
            self.session.scalars(
                select(ComputeDraft)
                .where(ComputeDraft.project_id == self.project_id)
                .order_by(ComputeDraft.created_at.desc())
                .limit(bounded)
            )
        )
        jobs = list(
            self.session.scalars(
                select(Job)
                .where(Job.project_id == self.project_id)
                .order_by(Job.created_at.desc())
                .limit(bounded)
            )
        )
        return {
            "drafts": [
                self._item(
                    "compute_draft",
                    row.id,
                    row.name,
                    {
                        "name": row.name,
                        "backend": row.backend,
                        "status": row.status,
                        "confirmed_job_id": (
                            str(row.confirmed_job_id)
                            if row.confirmed_job_id
                            else None
                        ),
                        "specification": _sanitize(row.specification or {}),
                    },
                )
                for row in drafts
            ],
            "jobs": [
                self._item(
                    "compute_job",
                    row.id,
                    row.model_plugin,
                    {
                        "workflow_run_id": str(row.workflow_run_id),
                        "workflow_node_id": str(row.workflow_node_id),
                        "status": row.status,
                        "compute_backend": row.compute_backend,
                        "model_plugin": row.model_plugin,
                        "attempt_number": row.attempt_number,
                        "error_code": row.error_code,
                        "error_message": row.error_message,
                    },
                )
                for row in jobs
            ],
        }

    def search_knowledge(
        self,
        query: str,
        *,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        normalized = query.strip().lower()
        rows = list(
            self.session.scalars(
                select(KnowledgeEntry)
                .where(KnowledgeEntry.project_id == self.project_id)
                .order_by(KnowledgeEntry.updated_at.desc())
                .limit(500)
            )
        )
        matches = [
            row
            for row in rows
            if not normalized
            or normalized in f"{row.title}\n{row.content}\n{' '.join(row.tags or [])}".lower()
        ][: max(1, min(limit, 50))]
        return [
            self._item(
                "knowledge_entry",
                row.id,
                row.title,
                {
                    "title": row.title,
                    "content": row.content,
                    "entry_type": row.entry_type,
                    "source": _sanitize(row.source or {}),
                    "tags": row.tags or [],
                    "version": row.version,
                },
            )
            for row in matches
        ]

    @staticmethod
    def citation_for_item(item: dict[str, Any]) -> dict[str, Any]:
        data = item.get("data") or {}
        return {
            "source_type": "project_database",
            "workspace_type": item["kind"],
            "entity_id": item["id"],
            "label": item["label"],
            "artifact_id": (
                data.get("source_artifact_id")
                or data.get("structure_artifact_id")
                or data.get("complex_artifact_id")
            ),
        }

    @staticmethod
    def _item(
        kind: str,
        identifier: uuid.UUID,
        label: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "kind": kind,
            "id": str(identifier),
            "label": label,
            "data": _sanitize(data),
        }

    def overview_packet(self) -> str:
        return json.dumps(
            {
                "project_id": str(self.project_id),
                "available_operational_tools": [
                    "targets",
                    "candidates",
                    "experiment_results",
                    "workflows",
                    "compute",
                    "knowledge",
                ],
            },
            ensure_ascii=False,
        )
