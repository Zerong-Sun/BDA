from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sqlite3
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend_v2.app.artifacts.models import Artifact, ArtifactLineageEdge
from backend_v2.app.artifacts.storage import ObjectStorage
from backend_v2.app.audit.models import AuditLog
from backend_v2.app.campaigns.models import Campaign, CampaignDecision, CampaignEvaluation, CampaignRound
from backend_v2.app.candidates.models import Candidate
from backend_v2.app.compute.models import Job, JobAttempt, JobSubmission
from backend_v2.app.copilot.models import CopilotConfig
from backend_v2.app.core.database import session_scope
from backend_v2.app.delivery.models import DeliveryPackage
from backend_v2.app.experiments.models import ExperimentResult
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from backend_v2.app.intelligence.models import (
    DesignRoute,
    IntelligenceEvidence,
    IntelligenceHotspot,
    IntelligenceReport,
    IntelligenceRun,
)
from backend_v2.app.knowledge.models import KnowledgeEntry
from backend_v2.app.literature.models import (
    LiteratureChunk,
    LiteratureClaim,
    LiteratureDocument,
    LiteratureEvidence,
    LiteratureRelation,
    LiteratureSubscription,
)
from backend_v2.app.migration.core import file_sha256, local_artifact_path, parse_time, stable_id
from backend_v2.app.platform.models import MigrationRun
from backend_v2.app.projects.models import Project, ProjectMember
from backend_v2.app.registry.models import (
    ComputeNode,
    LLMProvider,
    MethodPlugin,
    ModelPlugin,
    ParameterCatalog,
    RegistryServer,
    ScriptAsset,
)
from backend_v2.app.research.models import ResearchBrief, ResearchFinding
from backend_v2.app.targets.models import Target
from backend_v2.app.workflows.models import WorkflowNode, WorkflowRun
from sqlalchemy import select

CORE_TABLES = {
    "users",
    "organizations",
    "organization_members",
    "projects",
    "project_members",
    "targets",
    "workflow_runs",
    "workflow_node_runs",
    "workflow_edges",
    "design_tasks",
    "jobs",
    "job_events",
    "artifacts",
    "experiment_results",
    "candidates",
    "server_connections",
    "compute_nodes",
    "model_plugins",
    "method_plugins",
    "model_parameter_catalog",
    "script_assets",
    "llm_providers",
    "research_campaigns",
    "campaign_rounds",
    "campaign_evaluations",
    "campaign_decisions",
    "research_briefs",
    "research_findings",
    "knowledge_entries",
    "research_sources",
    "literature_documents",
    "document_chunks",
    "scientific_claims",
    "claim_evidence",
    "claim_relations",
    "literature_subscriptions",
    "target_intelligence_runs",
    "target_agent_reports",
    "target_evidence_items",
    "target_hotspots",
    "target_design_routes",
    "delivery_packages",
    "audit_logs",
    "app_settings",
    "design_hypotheses",
    "evidence_links",
    "parameter_recommendations",
    "research_questions",
    "research_runs",
    "script_parameter_observations",
    "user_sessions",
    "workflow_plans",
}


def rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return list(connection.execute(f'SELECT * FROM "{table}"'))  # noqa: S608 - table comes from sqlite metadata


def json_value(raw: Any, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return fallback


def legacy_path_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.removeprefix("artifact://").replace("\\", "/").lstrip("/")
    return normalized or None


def mark(report: dict, table: str, kind: str, legacy_id: str | None = None, reason: str | None = None) -> None:
    report["tables"][table][kind] += 1
    if kind == "rejected":
        report["rejections"].append({"table": table, "legacy_id": legacy_id, "reason": reason})


def migrate(
    sqlite_path: Path,
    artifact_roots: list[Path],
    report_path: Path,
    *,
    skip_files: bool,
    rehearsal: int = 1,
) -> None:
    source = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    table_names = [item[0] for item in source.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    report: dict[str, Any] = {
        "source": str(sqlite_path.resolve()),
        "source_fingerprint": file_sha256(sqlite_path),
        "rehearsal": rehearsal,
        "started_at": datetime.now(UTC).isoformat(),
        "tables": defaultdict(lambda: {"source": 0, "migrated": 0, "deferred": 0, "rejected": 0}),
        "id_map": {},
        "files": {"verified": 0, "uploaded": 0, "missing": 0, "skipped": 0},
        "file_checksums": {},
        "rejections": [],
    }
    for table in table_names:
        count = source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # noqa: S608
        report["tables"][table]["source"] = count
        if table not in CORE_TABLES:
            report["tables"][table]["deferred"] = count

    with session_scope() as session:
        user_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "users"):
            legacy = row["user_id"]
            user_item = session.get(User, stable_id("users", legacy))
            if user_item is None:
                # A live v2 installation can already contain the bootstrap
                # administrator.  Preserve its UUID, password and refresh
                # sessions while mapping the v1 identity to it by the public
                # unique key.  This keeps the restore additive and avoids a
                # duplicate username without weakening deterministic project
                # and domain IDs.
                user_item = session.scalar(select(User).where(User.username == row["username"]))
            if user_item is None:
                user_item = User(
                    id=stable_id("users", legacy),
                    legacy_id=legacy,
                    username=row["username"],
                    password_hash=row["password_hash"],
                    display_name=row["display_name"] or row["username"],
                    role=row["role"] if row["role"] in {"admin", "researcher", "viewer"} else "researcher",
                    enabled=bool(row["enabled"]),
                )
                session.add(user_item)
            user_map[legacy] = user_item.id
            report["id_map"][f"users:{legacy}"] = str(user_item.id)
            mark(report, "users", "migrated")
        if not user_map:
            raise RuntimeError("v1 database has no user to own migrated records")
        default_user_id = next(iter(user_map.values()))
        session.flush()

        organization_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "organizations"):
            legacy = row["organization_id"]
            organization_item = session.get(Organization, stable_id("organizations", legacy))
            if organization_item is None:
                # Local bootstrap creates "Default Organization" before a
                # legacy restore.  Reuse it so existing memberships and the
                # current administrator remain valid.
                organization_item = session.scalar(select(Organization).where(Organization.name == row["name"]))
            if organization_item is None:
                organization_item = Organization(
                    id=stable_id("organizations", legacy), legacy_id=legacy, name=row["name"]
                )
                session.add(organization_item)
            organization_map[legacy] = organization_item.id
            report["id_map"][f"organizations:{legacy}"] = str(organization_item.id)
            mark(report, "organizations", "migrated")
        fallback_org = next(iter(organization_map.values()), None)
        if fallback_org is None:
            fallback = Organization(
                id=stable_id("organizations", "legacy-default"), legacy_id="legacy-default", name="Legacy"
            )
            session.add(fallback)
            fallback_org = fallback.id
        session.flush()

        for row in rows(source, "organization_members"):
            organization_id, user_id = organization_map.get(row["organization_id"]), user_map.get(row["user_id"])
            if not organization_id or not user_id:
                mark(report, "organization_members", "rejected", reason="missing organization or user")
                continue
            if session.get(OrganizationMember, (organization_id, user_id)) is None:
                session.add(OrganizationMember(organization_id=organization_id, user_id=user_id, role=row["role"]))
            mark(report, "organization_members", "migrated")

        project_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "projects"):
            legacy = row["project_id"]
            owner_id = user_map.get(row["owner_id"]) or default_user_id
            organization_id = organization_map.get(row["organization_id"]) or fallback_org
            project_item = session.get(Project, stable_id("projects", legacy))
            if project_item is None:
                project_item = Project(
                    id=stable_id("projects", legacy),
                    legacy_id=legacy,
                    organization_id=organization_id,
                    owner_id=owner_id,
                    name=row["project_name"],
                    project_type=row["project_type"],
                    summary=row["summary"],
                    status=row["status"],
                )
                session.add(project_item)
            project_created_at = parse_time(row["created_at"])
            project_updated_at = parse_time(row["updated_at"])
            if project_created_at is not None:
                project_item.created_at = project_created_at
            if project_updated_at is not None:
                project_item.updated_at = project_updated_at
            project_map[legacy] = project_item.id
            report["id_map"][f"projects:{legacy}"] = str(project_item.id)
            mark(report, "projects", "migrated")
        session.flush()

        for row in rows(source, "project_members"):
            project_id, user_id = project_map.get(row["project_id"]), user_map.get(row["user_id"])
            if not project_id or not user_id:
                mark(report, "project_members", "rejected", reason="missing project or user")
                continue
            if session.get(ProjectMember, (project_id, user_id)) is None:
                session.add(ProjectMember(project_id=project_id, user_id=user_id, role=row["role"]))
            mark(report, "project_members", "migrated")

        primary_targets: dict[uuid.UUID, uuid.UUID] = {}
        for row in rows(source, "targets"):
            project_id = project_map.get(row["project_id"])
            if not project_id:
                mark(report, "targets", "rejected", row["target_id"], "missing project")
                continue
            legacy = row["target_id"]
            target_item = session.get(Target, stable_id("targets", legacy))
            if target_item is None:
                target_item = Target(
                    id=stable_id("targets", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    name=row["target_name"],
                    sequence=row["sequence"],
                    structure_status="available" if row["structure_file_path"] else "missing",
                )
                session.add(target_item)
            # A legacy PDB accession is authoritative target identity evidence,
            # even when the old record did not duplicate the structure sequence.
            # Keep unverified name-only targets unconfirmed.
            if row["pdb_id"] or row["sequence"]:
                target_item.identity_status = "confirmed"
            report["id_map"][f"targets:{legacy}"] = str(stable_id("targets", legacy))
            primary_targets.setdefault(project_id, stable_id("targets", legacy))
            mark(report, "targets", "migrated")
        session.flush()
        for project_id, target_id in primary_targets.items():
            project = session.get(Project, project_id)
            if project and project.primary_target_id is None:
                project.primary_target_id = target_id

        task_rows = {row["task_id"]: row for row in rows(source, "design_tasks")}
        for legacy in task_rows:
            report["id_map"][f"design_tasks:{legacy}"] = str(stable_id("design_tasks", legacy))
            mark(report, "design_tasks", "migrated")
        run_rows = rows(source, "workflow_runs")
        node_rows = rows(source, "workflow_node_runs")
        edge_rows = rows(source, "workflow_edges")
        nodes_by_run: dict[str, list[sqlite3.Row]] = defaultdict(list)
        edges_by_run: dict[str, list[sqlite3.Row]] = defaultdict(list)
        node_map: dict[str, uuid.UUID] = {}
        for row in node_rows:
            nodes_by_run[row["workflow_run_id"]].append(row)
        for row in edge_rows:
            edges_by_run[row["workflow_run_id"]].append(row)
        run_map: dict[str, uuid.UUID] = {}
        for row in run_rows:
            legacy = row["workflow_run_id"]
            task = task_rows.get(row["task_id"])
            task_project_id = str(task["project_id"]) if task else ""
            project_id = project_map.get(task_project_id)
            if not project_id:
                mark(report, "workflow_runs", "rejected", legacy, "workflow task has no migrated project")
                continue
            graph_nodes = [
                {
                    "key": node["node_run_id"],
                    "node_type": node["node_type"],
                    "model_plugin": node["model_name"] or "legacy-unknown",
                    "parameters": json_value(node["parameters_json"], {}),
                }
                for node in nodes_by_run[legacy]
            ]
            graph_edges = [
                {"source": edge["source_node_run_id"], "target": edge["target_node_run_id"]}
                for edge in edges_by_run[legacy]
            ]
            workflow_item = session.get(WorkflowRun, stable_id("workflow_runs", legacy))
            if workflow_item is None:
                task_created_by = str(task["created_by"]) if task and task["created_by"] else ""
                workflow_item = WorkflowRun(
                    id=stable_id("workflow_runs", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    name=(task["objective"] if task else legacy)[:200],
                    status=row["status"],
                    graph={"nodes": graph_nodes, "edges": graph_edges},
                    created_by=user_map.get(task_created_by) or default_user_id,
                )
                session.add(workflow_item)
            run_map[legacy] = workflow_item.id
            report["id_map"][f"workflow_runs:{legacy}"] = str(workflow_item.id)
            mark(report, "workflow_runs", "migrated")
        session.flush()
        for row in node_rows:
            run_id = run_map.get(row["workflow_run_id"])
            if not run_id:
                mark(report, "workflow_node_runs", "rejected", row["node_run_id"], "missing workflow")
                continue
            legacy = row["node_run_id"]
            if session.get(WorkflowNode, stable_id("workflow_node_runs", legacy)) is None:
                session.add(
                    WorkflowNode(
                        id=stable_id("workflow_node_runs", legacy),
                        legacy_id=legacy,
                        workflow_run_id=run_id,
                        node_key=legacy,
                        node_type=row["node_type"],
                        model_plugin=row["model_name"] or "legacy-unknown",
                        status=row["status"],
                        parameters=json_value(row["parameters_json"], {}),
                        error_message=row["error_message"],
                    )
                )
            node_map[legacy] = stable_id("workflow_node_runs", legacy)
            report["id_map"][f"workflow_node_runs:{legacy}"] = str(stable_id("workflow_node_runs", legacy))
            mark(report, "workflow_node_runs", "migrated")
        for row in edge_rows:
            if row["workflow_run_id"] in run_map:
                mark(report, "workflow_edges", "migrated")
            else:
                mark(report, "workflow_edges", "rejected", row["edge_id"], "missing workflow")

        storage = ObjectStorage()
        artifact_by_path: dict[str, uuid.UUID] = {}
        artifact_metadata: dict[uuid.UUID, dict] = {}
        for row in rows(source, "artifacts"):
            legacy = row["artifact_id"]
            project_id = project_map.get(row["project_id"])
            if not project_id:
                mark(report, "artifacts", "rejected", legacy, "artifact has no migrated project")
                continue
            path = local_artifact_path(row["storage_uri"], artifact_roots)
            if path is None or not path.is_file():
                report["files"]["missing"] += 1
                mark(report, "artifacts", "rejected", legacy, "artifact file is missing or URI is unsupported")
                continue
            checksum = file_sha256(path)
            if row["checksum"] and row["checksum"].lower() != checksum:
                mark(report, "artifacts", "rejected", legacy, "source checksum mismatch")
                continue
            report["files"]["verified"] += 1
            report["file_checksums"][legacy] = checksum
            artifact_id = stable_id("artifacts", legacy)
            path_key = legacy_path_key(row["storage_uri"])
            if path_key:
                artifact_by_path[path_key] = artifact_id
            artifact_metadata[artifact_id] = json_value(row["metadata_json"], {})
            object_key = f"projects/{project_id}/sha256/{checksum}"
            if skip_files:
                report["files"]["skipped"] += 1
            else:
                storage.put_file(
                    object_key, str(path), mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                )
                report["files"]["uploaded"] += 1
            artifact_item = session.get(Artifact, artifact_id)
            if artifact_item is None:
                artifact_item = Artifact(
                    id=artifact_id,
                    legacy_id=legacy,
                    project_id=project_id,
                    created_by=user_map.get(row["created_by"]) or default_user_id,
                    artifact_type=row["artifact_type"],
                    filename=row["display_name"],
                    content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    object_key=object_key,
                    status="available" if not skip_files else "uploading",
                    size_bytes=path.stat().st_size,
                    checksum_sha256=checksum,
                    lineage={
                        "legacy_storage_uri": row["storage_uri"],
                        "legacy_workflow_run_id": row["workflow_run_id"],
                        "legacy_node_run_id": row["node_run_id"],
                        **json_value(row["metadata_json"], {}),
                    },
                )
                session.add(artifact_item)
            artifact_created_at = parse_time(row["created_at"])
            if artifact_created_at is not None:
                artifact_item.created_at = artifact_created_at
            report["id_map"][f"artifacts:{legacy}"] = str(stable_id("artifacts", legacy))
            mark(report, "artifacts", "migrated")

        # Targets were created before artifacts to break the project/target FK
        # cycle.  Resolve their legacy paths only after authoritative artifacts
        # have been validated and registered.
        target_artifact_by_route: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
        for row in rows(source, "targets"):
            target_id = stable_id("targets", row["target_id"])
            target = session.get(Target, target_id)
            path_key = legacy_path_key(row["structure_file_path"])
            target_artifact_id = artifact_by_path.get(path_key or "")
            if target is None or not path_key:
                continue
            if target_artifact_id is None:
                raise RuntimeError(f"target structure artifact is missing for {row['target_id']}: {path_key}")
            target.structure_artifact_id = target_artifact_id
            target.structure_status = "available"
            artifact = session.get(Artifact, target_artifact_id)
            metadata = dict(artifact_metadata.get(target_artifact_id, {}))
            chain_ids = [item.strip() for item in (row["chain_ids"] or "").split(",") if item.strip()]
            target_context = {
                "legacy_target_id": row["target_id"],
                "target_type": row["target_type"],
                "pdb_id": row["pdb_id"],
                "chains": chain_ids,
                "epitope_residues": json_value(row["epitope_residues"], row["epitope_residues"]),
                **json_value(row["metadata_json"], {}),
            }
            enriched_lineage = {
                **(artifact.lineage if artifact is not None else {}),
                **{key: value for key, value in target_context.items() if value not in (None, "", [])},
            }
            if artifact is not None and artifact.lineage != enriched_lineage:
                artifact.lineage = enriched_lineage
                artifact.version += 1
            route = metadata.get("route")
            if isinstance(route, str) and route:
                target_artifact_by_route[(target.project_id, route)] = target_artifact_id
        session.flush()

        def candidate_artifact(
            *, legacy_candidate: str, project_id: uuid.UUID, kind: str, legacy_path: str | None
        ) -> uuid.UUID | None:
            path_key = legacy_path_key(legacy_path)
            if path_key is None:
                return None
            existing_id = artifact_by_path.get(path_key)
            if existing_id is not None:
                return existing_id
            path = local_artifact_path(f"artifact://{path_key}", artifact_roots)
            if path is None:
                raise RuntimeError(f"candidate {kind} artifact is missing for {legacy_candidate}: {path_key}")
            checksum = file_sha256(path)
            artifact_id = stable_id("candidate_fixture_artifacts", f"{legacy_candidate}:{kind}")
            report_key = f"candidate_fixture:{legacy_candidate}:{kind}"
            report["file_checksums"][report_key] = checksum
            report["files"]["verified"] += 1
            object_key = f"projects/{project_id}/sha256/{checksum}"
            if skip_files:
                report["files"]["skipped"] += 1
            else:
                storage.put_file(
                    object_key,
                    str(path),
                    mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                )
                report["files"]["uploaded"] += 1
            if session.get(Artifact, artifact_id) is None:
                session.add(
                    Artifact(
                        id=artifact_id,
                        legacy_id=report_key,
                        project_id=project_id,
                        created_by=default_user_id,
                        artifact_type=f"candidate_{kind}",
                        filename=path.name,
                        content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        object_key=object_key,
                        status="available" if not skip_files else "uploading",
                        size_bytes=path.stat().st_size,
                        checksum_sha256=checksum,
                        lineage={"legacy_path": legacy_path, "candidate_id": legacy_candidate},
                    )
                )
            artifact_by_path[path_key] = artifact_id
            artifact_metadata[artifact_id] = {"candidate_id": legacy_candidate, "kind": kind}
            report["id_map"][report_key] = str(artifact_id)
            return artifact_id

        candidate_projects: dict[str, uuid.UUID | None] = {}
        candidate_structure_artifacts: dict[uuid.UUID, uuid.UUID] = {}
        for row in rows(source, "candidates"):
            legacy = row["candidate_id"]
            project_id = project_map.get(row["project_id"])
            candidate_projects[legacy] = project_id
            if not project_id:
                mark(report, "candidates", "rejected", legacy, "candidate has no migrated project")
                continue
            scores = {
                key: row[key]
                for key in (
                    "interface_score",
                    "plddt",
                    "interface_pae",
                    "rosetta_score",
                    "interface_energy",
                    "clash_count",
                    "buried_sasa",
                    "solubility_score",
                )
                if row[key] is not None
            }
            properties = {
                key: row[key]
                for key in ("sequence", "pred_kd", "aggregation_risk", "expression_risk", "decision", "next_action")
                if row[key] is not None
            }
            structure_artifact_id = candidate_artifact(
                legacy_candidate=legacy,
                project_id=project_id,
                kind="structure",
                legacy_path=row["structure_file_path"],
            )
            complex_artifact_id = candidate_artifact(
                legacy_candidate=legacy,
                project_id=project_id,
                kind="complex",
                legacy_path=row["complex_file_path"],
            )
            item: Any = session.get(Candidate, stable_id("candidates", legacy))
            if item is None:
                item = Candidate(
                    id=stable_id("candidates", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    candidate_key=legacy,
                    name=row["family"] or legacy,
                    status=row["status"],
                    score=row["interface_score"],
                    scores=scores,
                    properties=properties,
                    structure_artifact_id=structure_artifact_id,
                    complex_artifact_id=complex_artifact_id,
                )
                session.add(item)
            else:
                item.structure_artifact_id = structure_artifact_id
                item.complex_artifact_id = complex_artifact_id
            if structure_artifact_id:
                candidate_structure_artifacts[item.id] = structure_artifact_id
            if structure_artifact_id and complex_artifact_id:
                edge_id = stable_id("artifact_lineage_edges", f"{structure_artifact_id}:{complex_artifact_id}")
                if session.get(ArtifactLineageEdge, edge_id) is None:
                    session.add(
                        ArtifactLineageEdge(
                            id=edge_id,
                            project_id=project_id,
                            parent_artifact_id=structure_artifact_id,
                            child_artifact_id=complex_artifact_id,
                            relation="complex_from_structure",
                            details={"legacy_candidate_id": legacy},
                        )
                    )
            report["id_map"][f"candidates:{legacy}"] = str(item.id)
            mark(report, "candidates", "migrated")
        for row in rows(source, "experiment_results"):
            legacy = row["result_id"]
            project_id = candidate_projects.get(row["candidate_id"])
            if not project_id:
                mark(report, "experiment_results", "rejected", legacy, "candidate has no migrated project")
                continue
            try:
                numeric_value = float(row["value"]) if row["value"] not in (None, "") else None
            except (TypeError, ValueError):
                numeric_value = None
            if session.get(ExperimentResult, stable_id("experiment_results", legacy)) is None:
                session.add(
                    ExperimentResult(
                        id=stable_id("experiment_results", legacy),
                        legacy_id=legacy,
                        project_id=project_id,
                        candidate_id=stable_id("candidates", row["candidate_id"]),
                        candidate_ref=row["candidate_id"],
                        experiment_type=row["experiment_type"],
                        pass_status=row["pass_status"],
                        value=numeric_value,
                        unit=row["unit"],
                        conclusion=row["conclusion"] or row["failure_reason"],
                        created_by=default_user_id,
                    )
                )
            report["id_map"][f"experiment_results:{legacy}"] = str(stable_id("experiment_results", legacy))
            mark(report, "experiment_results", "migrated")

        default_project_id = next(iter(project_map.values()))
        server_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "server_connections"):
            legacy = row["server_id"]
            item = session.get(RegistryServer, stable_id("server_connections", legacy))
            if item is None:
                item = RegistryServer(
                    id=stable_id("server_connections", legacy),
                    legacy_id=legacy,
                    name=row["server_name"],
                    server_type=row["server_type"],
                    endpoint=row["base_url"] or "ssh://configured-by-secret",
                    credential_ref=row["credential_ref"],
                    enabled=bool(row["enabled"]),
                )
                session.add(item)
            server_map[legacy] = item.id
            report["id_map"][f"server_connections:{legacy}"] = str(item.id)
            mark(report, "server_connections", "migrated")
        # ComputeNode only stores a scalar server_id and does not expose an ORM
        # relationship, so SQLAlchemy cannot infer the insert dependency from
        # object references.  Persist registry servers before their FK users.
        session.flush()
        compute_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "compute_nodes"):
            legacy = row["compute_node_id"]
            item = session.get(ComputeNode, stable_id("compute_nodes", legacy))
            if item is None:
                item = ComputeNode(
                    id=stable_id("compute_nodes", legacy),
                    legacy_id=legacy,
                    server_id=server_map.get(row["server_id"]),
                    name=row["node_name"],
                    backend="lsf" if row["scheduler_type"] == "lsf" else "docker",
                    queue=row["queue_name"],
                    labels={
                        "node_type": row["node_type"],
                        "gpu_type": row["gpu_type"],
                        "gpu_count": row["gpu_count"],
                        "cpu_count": row["cpu_count"],
                        "memory_gb": row["memory_gb"],
                    },
                    enabled=row["status"] not in {"disabled", "offline"},
                )
                session.add(item)
            compute_map[legacy] = item.id
            report["id_map"][f"compute_nodes:{legacy}"] = str(item.id)
            mark(report, "compute_nodes", "migrated")
        plugin_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "model_plugins"):
            legacy = row["model_plugin_id"]
            item = session.get(ModelPlugin, stable_id("model_plugins", legacy))
            if item is None:
                item = ModelPlugin(
                    id=stable_id("model_plugins", legacy),
                    legacy_id=legacy,
                    plugin_key=row["model_name"],
                    plugin_version=row["version"],
                    name=row["model_name"],
                    container_image=row["container_image"] or "unconfigured",
                    command=row["command_template"] or "true",
                    parameter_schema=json_value(row["parameter_schema_json"], {}),
                    output_schema=json_value(row["output_schema_json"], {}),
                    enabled=row["status"] == "active",
                )
                session.add(item)
            plugin_map[legacy] = item.id
            report["id_map"][f"model_plugins:{legacy}"] = str(item.id)
            mark(report, "model_plugins", "migrated")
        for row in rows(source, "method_plugins"):
            legacy = row["method_plugin_id"]
            item = session.get(MethodPlugin, stable_id("method_plugins", legacy))
            if item is None:
                item = MethodPlugin(
                    id=stable_id("method_plugins", legacy),
                    legacy_id=legacy,
                    plugin_key=legacy,
                    name=row["method_name"],
                    specification={
                        "method_type": row["method_type"],
                        "version": row["version"],
                        "input_schema": json_value(row["input_schema_json"], {}),
                        "output_schema": json_value(row["output_schema_json"], {}),
                        "parameter_schema": json_value(row["parameter_schema_json"], {}),
                    },
                    enabled=row["status"] == "active",
                )
                session.add(item)
            report["id_map"][f"method_plugins:{legacy}"] = str(item.id)
            mark(report, "method_plugins", "migrated")
        session.flush()
        for row in rows(source, "model_parameter_catalog"):
            legacy = row["parameter_catalog_id"]
            plugin_id = plugin_map.get(row["model_plugin_id"])
            if not plugin_id:
                mark(report, "model_parameter_catalog", "rejected", legacy, "missing model plugin")
                continue
            item = session.get(ParameterCatalog, stable_id("model_parameter_catalog", legacy))
            if item is None:
                item = ParameterCatalog(
                    id=stable_id("model_parameter_catalog", legacy),
                    legacy_id=legacy,
                    plugin_id=plugin_id,
                    name=row["parameter_key"],
                    schema={"type": row["parameter_type"], **json_value(row["constraints_json"], {})},
                    defaults={"value": json_value(row["default_value_json"], None)},
                )
                session.add(item)
            report["id_map"][f"model_parameter_catalog:{legacy}"] = str(item.id)
            mark(report, "model_parameter_catalog", "migrated")
        for row in rows(source, "llm_providers"):
            legacy = row["llm_provider_id"]
            item = session.get(LLMProvider, stable_id("llm_providers", legacy))
            if item is None:
                item = LLMProvider(
                    id=stable_id("llm_providers", legacy),
                    legacy_id=legacy,
                    name=row["provider_name"],
                    provider_type=row["provider_type"],
                    endpoint=row["base_url"],
                    model=(json_value(row["model_names"], ["unconfigured"]) or ["unconfigured"])[0],
                    credential_ref=row["credential_ref"] or f"unconfigured/{legacy}",
                    config={
                        "allowed_scopes": json_value(row["allowed_scopes"], []),
                        "data_policy": json_value(row["data_policy"], {}),
                    },
                    enabled=row["status"] == "active",
                )
                session.add(item)
            report["id_map"][f"llm_providers:{legacy}"] = str(item.id)
            mark(report, "llm_providers", "migrated")

        submission_map: dict[str, uuid.UUID] = {}
        job_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "jobs"):
            legacy = row["job_id"]
            workflow_id = run_map.get(row["workflow_run_id"])
            node_id = node_map.get(row["node_run_id"])
            workflow = session.get(WorkflowRun, workflow_id) if workflow_id else None
            if workflow is None or node_id is None:
                mark(report, "jobs", "rejected", legacy, "missing migrated workflow or node")
                continue
            submission_id = submission_map.get(row["workflow_run_id"])
            if submission_id is None:
                submission_id = stable_id("job_submissions", row["workflow_run_id"])
                submission = session.get(JobSubmission, submission_id)
                if submission is None:
                    submission = JobSubmission(
                        id=submission_id,
                        workflow_run_id=workflow.id,
                        project_id=workflow.project_id,
                        created_by=workflow.created_by,
                        status="succeeded" if row["status"] == "completed" else row["status"],
                        compute_backend="lsf",
                    )
                    session.add(submission)
                submission_map[row["workflow_run_id"]] = submission_id
                session.flush()
            status = {"completed": "succeeded", "error": "failed"}.get(row["status"], row["status"])
            job_id = stable_id("jobs", legacy)
            if session.get(Job, job_id) is None:
                session.add(
                    Job(
                        id=job_id,
                        submission_id=submission_id,
                        workflow_run_id=workflow.id,
                        workflow_node_id=node_id,
                        project_id=workflow.project_id,
                        status=status,
                        compute_backend="lsf",
                        model_plugin=row["plugin_id"] or "legacy-unknown",
                        external_id=row["external_id"],
                        error_code="legacy_compute_failed" if status == "failed" else None,
                        error_message=row["error_message"],
                        runtime_spec={
                            "legacy_input_artifacts": json_value(row["input_artifacts"], {}),
                            "legacy_output_artifacts": json_value(row["output_artifacts"], {}),
                            "legacy_logs": row["logs"],
                            "historical_terminal": status in {"succeeded", "failed", "cancelled"},
                        },
                        created_at=parse_time(row["created_at"]) or datetime.now(UTC),
                    )
                )
                session.flush()
                session.add(
                    JobAttempt(
                        id=stable_id("job_attempts", legacy),
                        job_id=job_id,
                        attempt_number=1,
                        status=status,
                        external_id=row["external_id"],
                        error=row["error_message"],
                        started_at=parse_time(row["started_at"]) or parse_time(row["created_at"]) or datetime.now(UTC),
                        finished_at=parse_time(row["finished_at"]),
                    )
                )
            report["id_map"][f"jobs:{legacy}"] = str(job_id)
            job_map[legacy] = job_id
            mark(report, "jobs", "migrated")

        session.flush()
        for candidate_id, artifact_id in candidate_structure_artifacts.items():
            candidate = session.get(Candidate, candidate_id)
            if candidate is None:
                continue
            metadata = artifact_metadata.get(artifact_id, {})
            legacy_job_id = metadata.get("source_job_id")
            if isinstance(legacy_job_id, str) and legacy_job_id in job_map:
                candidate.source_job_id = job_map[legacy_job_id]
            route = metadata.get("route")
            if not isinstance(route, str) or not route:
                continue
            parent_id = target_artifact_by_route.get((candidate.project_id, route))
            if parent_id is None or parent_id == artifact_id:
                continue
            edge_id = stable_id("artifact_lineage_edges", f"{parent_id}:{artifact_id}:generated_from")
            if session.get(ArtifactLineageEdge, edge_id) is None:
                session.add(
                    ArtifactLineageEdge(
                        id=edge_id,
                        project_id=candidate.project_id,
                        parent_artifact_id=parent_id,
                        child_artifact_id=artifact_id,
                        relation="generated_from",
                        details={
                            "legacy_candidate_id": candidate.legacy_id,
                            "legacy_job_id": legacy_job_id,
                        },
                    )
                )
            report["id_map"][f"artifact_lineage_edges:{parent_id}:{artifact_id}"] = str(edge_id)

        source_rows = {row["source_id"]: row for row in rows(source, "research_sources")}
        for legacy, _row in source_rows.items():
            mark(report, "research_sources", "migrated")
            report["id_map"][f"research_sources:{legacy}"] = str(stable_id("research_sources", legacy))
        for row in rows(source, "script_assets"):
            legacy = row["script_asset_id"]
            source_row = source_rows.get(row["source_id"])
            uri = str(source_row["uri"]) if source_row else row["relative_path"]
            path = local_artifact_path(f"artifact://{uri}", artifact_roots)
            if path is None or not path.is_file():
                mark(
                    report, "script_assets", "rejected", legacy, "script source is outside allowlisted roots or missing"
                )
                continue
            checksum = file_sha256(path)
            source_meta = json_value(source_row["metadata_json"], {}) if source_row else {}
            source_project_id = source_meta.get("project_id")
            project_id = project_map.get(str(source_project_id)) if source_project_id else None
            project_id = project_id or default_project_id
            artifact_id = stable_id("script_asset_artifacts", legacy)
            object_key = f"projects/{project_id}/scripts/{checksum}"
            if not skip_files:
                storage.put_file(object_key, str(path), "text/plain")
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                artifact = Artifact(
                    id=artifact_id,
                    legacy_id=f"script:{legacy}",
                    project_id=project_id,
                    created_by=default_user_id,
                    artifact_type="script_asset",
                    filename=path.name,
                    content_type="text/plain",
                    object_key=object_key,
                    status="available" if not skip_files else "uploading",
                    size_bytes=path.stat().st_size,
                    checksum_sha256=checksum,
                    lineage={"legacy_path": uri},
                )
                session.add(artifact)
            script = session.get(ScriptAsset, stable_id("script_assets", legacy))
            if script is None:
                script = ScriptAsset(
                    id=stable_id("script_assets", legacy),
                    legacy_id=legacy,
                    name=path.name,
                    artifact_id=artifact_id,
                    checksum_sha256=checksum,
                    runtime=row["language"],
                    created_by=default_user_id,
                )
                session.add(script)
            report["id_map"][f"script_assets:{legacy}"] = str(script.id)
            mark(report, "script_assets", "migrated")

        campaign_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "research_campaigns"):
            legacy = row["campaign_id"]
            project_id = project_map.get(row["project_id"])
            if not project_id:
                mark(report, "research_campaigns", "rejected", legacy, "missing project")
                continue
            item = session.get(Campaign, stable_id("research_campaigns", legacy))
            if item is None:
                item = Campaign(
                    id=stable_id("research_campaigns", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    name=row["name"],
                    objective=row["objective"],
                    status=row["status"],
                    config={
                        "max_rounds": row["max_rounds"],
                        "budget": json_value(row["budget_json"], {}),
                        "stop_conditions": json_value(row["stop_conditions_json"], []),
                        "strategy": json_value(row["strategy_json"], {}),
                    },
                    created_by=user_map.get(row["created_by"]) or default_user_id,
                )
                session.add(item)
            campaign_map[legacy] = item.id
            report["id_map"][f"research_campaigns:{legacy}"] = str(item.id)
            mark(report, "research_campaigns", "migrated")
        session.flush()
        round_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "campaign_rounds"):
            legacy = row["campaign_round_id"]
            campaign_id = campaign_map.get(row["campaign_id"])
            if not campaign_id:
                mark(report, "campaign_rounds", "rejected", legacy, "missing campaign")
                continue
            item = session.get(CampaignRound, stable_id("campaign_rounds", legacy))
            if item is None:
                item = CampaignRound(
                    id=stable_id("campaign_rounds", legacy),
                    legacy_id=legacy,
                    campaign_id=campaign_id,
                    round_number=row["round_number"],
                    status=row["status"],
                    workflow_run_id=run_map.get(row["workflow_run_id"]),
                    hypothesis=json.dumps(json_value(row["parameter_patch_json"], {})),
                )
                session.add(item)
            round_map[legacy] = item.id
            report["id_map"][f"campaign_rounds:{legacy}"] = str(item.id)
            mark(report, "campaign_rounds", "migrated")
        session.flush()
        for row in rows(source, "campaign_evaluations"):
            legacy = row["evaluation_id"]
            round_id = round_map.get(row["campaign_round_id"])
            if not round_id:
                mark(report, "campaign_evaluations", "rejected", legacy, "missing round")
                continue
            if session.get(CampaignEvaluation, stable_id("campaign_evaluations", legacy)) is None:
                session.add(
                    CampaignEvaluation(
                        id=stable_id("campaign_evaluations", legacy),
                        legacy_id=legacy,
                        round_id=round_id,
                        metrics={
                            **json_value(row["metrics_json"], {}),
                            "criteria": json_value(row["criteria_results_json"], []),
                        },
                        outcome=row["recommendation"],
                        notes=row["rationale"],
                    )
                )
            report["id_map"][f"campaign_evaluations:{legacy}"] = str(stable_id("campaign_evaluations", legacy))
            mark(report, "campaign_evaluations", "migrated")
        for row in rows(source, "campaign_decisions"):
            legacy = row["decision_id"]
            round_id = round_map.get(row["campaign_round_id"])
            if not round_id:
                mark(report, "campaign_decisions", "rejected", legacy, "missing round")
                continue
            if session.get(CampaignDecision, stable_id("campaign_decisions", legacy)) is None:
                session.add(
                    CampaignDecision(
                        id=stable_id("campaign_decisions", legacy),
                        legacy_id=legacy,
                        round_id=round_id,
                        decision=row["decision_type"],
                        rationale=row["rationale"] or json.dumps(json_value(row["parameter_patch_json"], {})),
                        decided_by=user_map.get(row["reviewed_by"]) or default_user_id,
                        parameter_patch=json_value(row["parameter_patch_json"], {}),
                        review_status=row["status"] or "pending",
                        reviewed_by=user_map.get(row["reviewed_by"]),
                        reviewed_at=parse_time(row["reviewed_at"]),
                    )
                )
            report["id_map"][f"campaign_decisions:{legacy}"] = str(stable_id("campaign_decisions", legacy))
            mark(report, "campaign_decisions", "migrated")

        brief_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "research_briefs"):
            legacy = row["research_brief_id"]
            project_id = project_map.get(row["project_id"])
            if not project_id:
                mark(report, "research_briefs", "rejected", legacy, "missing project")
                continue
            item = session.get(ResearchBrief, stable_id("research_briefs", legacy))
            if item is None:
                item = ResearchBrief(
                    id=stable_id("research_briefs", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    title=row["title"],
                    status=row["status"],
                    content=row["objective"],
                    scope={
                        "product_context": row["product_context"],
                        "constraints": json_value(row["constraints_json"], {}),
                        "source_material": json_value(row["source_material_json"], []),
                        "assumptions": json_value(row["assumptions_json"], []),
                    },
                    created_by=user_map.get(row["created_by"]) or default_user_id,
                )
                session.add(item)
            brief_created_at = parse_time(row["created_at"])
            brief_updated_at = parse_time(row["updated_at"])
            if brief_created_at is not None:
                item.created_at = brief_created_at
            if brief_updated_at is not None:
                item.updated_at = brief_updated_at
            brief_map[legacy] = item.id
            report["id_map"][f"research_briefs:{legacy}"] = str(item.id)
            mark(report, "research_briefs", "migrated")
        session.flush()
        for row in rows(source, "research_findings"):
            legacy = row["research_finding_id"]
            brief_id = brief_map.get(row["research_brief_id"])
            brief = session.get(ResearchBrief, brief_id) if brief_id else None
            if not brief:
                mark(report, "research_findings", "rejected", legacy, "missing research brief")
                continue
            finding = session.get(ResearchFinding, stable_id("research_findings", legacy))
            if finding is None:
                finding = ResearchFinding(
                    id=stable_id("research_findings", legacy),
                    legacy_id=legacy,
                    project_id=brief.project_id,
                    brief_id=brief.id,
                    finding_type=row["track"],
                    title=row["title"],
                    content=row["statement"],
                    evidence={
                        "level": row["evidence_level"],
                        "sources": json_value(row["source_refs_json"], []),
                        "uncertainty": row["uncertainty"],
                        "review_status": row["review_status"],
                    },
                    created_by=default_user_id,
                )
                session.add(finding)
            finding_created_at = parse_time(row["created_at"])
            finding_updated_at = parse_time(row["updated_at"])
            if finding_created_at is not None:
                finding.created_at = finding_created_at
            if finding_updated_at is not None:
                finding.updated_at = finding_updated_at
            report["id_map"][f"research_findings:{legacy}"] = str(stable_id("research_findings", legacy))
            mark(report, "research_findings", "migrated")
        for row in rows(source, "knowledge_entries"):
            legacy = row["knowledge_entry_id"]
            if session.get(KnowledgeEntry, stable_id("knowledge_entries", legacy)) is None:
                session.add(
                    KnowledgeEntry(
                        id=stable_id("knowledge_entries", legacy),
                        legacy_id=legacy,
                        project_id=default_project_id,
                        title=row["title"],
                        content=row["content"],
                        entry_type=row["category"],
                        source={
                            "type": row["source_type"],
                            "citation": row["citation"],
                            "confidence": row["confidence"],
                        },
                        tags=json_value(row["tags_json"], []),
                        created_by=default_user_id,
                    )
                )
            report["id_map"][f"knowledge_entries:{legacy}"] = str(stable_id("knowledge_entries", legacy))
            mark(report, "knowledge_entries", "migrated")

        document_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "literature_documents"):
            legacy = row["document_id"]
            source_row = source_rows.get(row["source_id"])
            source_meta = json_value(source_row["metadata_json"], {}) if source_row else {}
            source_project_id = source_meta.get("project_id")
            project_id = project_map.get(str(source_project_id)) if source_project_id else None
            project_id = project_id or default_project_id
            item = session.get(LiteratureDocument, stable_id("literature_documents", legacy))
            if item is None:
                item = LiteratureDocument(
                    id=stable_id("literature_documents", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    title=row["title"],
                    source=row["external_source"],
                    external_id=row["external_id"],
                    abstract=row["abstract_text"],
                    metadata_json={
                        **json_value(row["metadata_json"], {}),
                        "authors": row["authors"],
                        "journal": row["journal"],
                        "year": row["publication_year"],
                        "doi": row["doi"],
                        "pmid": row["pmid"],
                        "pmcid": row["pmcid"],
                    },
                    status="available" if row["status"] == "active" else row["status"],
                )
                session.add(item)
            document_map[legacy] = item.id
            report["id_map"][f"literature_documents:{legacy}"] = str(item.id)
            mark(report, "literature_documents", "migrated")
        session.flush()
        chunk_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "document_chunks"):
            legacy = row["chunk_id"]
            document_id = document_map.get(row["document_id"])
            if not document_id:
                mark(report, "document_chunks", "rejected", legacy, "missing literature document")
                continue
            item = session.get(LiteratureChunk, stable_id("document_chunks", legacy))
            if item is None:
                item = LiteratureChunk(
                    id=stable_id("document_chunks", legacy),
                    legacy_id=legacy,
                    document_id=document_id,
                    position=row["chunk_index"],
                    content=row["content"],
                    embedding_ref=None,
                )
                session.add(item)
            chunk_map[legacy] = item.id
            report["id_map"][f"document_chunks:{legacy}"] = str(item.id)
            mark(report, "document_chunks", "migrated")
        session.flush()
        claim_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "scientific_claims"):
            legacy = row["claim_id"]
            document_id = document_map.get(row["document_id"])
            if not document_id:
                mark(report, "scientific_claims", "rejected", legacy, "missing literature document")
                continue
            item = session.get(LiteratureClaim, stable_id("scientific_claims", legacy))
            if item is None:
                item = LiteratureClaim(
                    id=stable_id("scientific_claims", legacy),
                    legacy_id=legacy,
                    document_id=document_id,
                    claim=row["statement"],
                    confidence=str(row["confidence"] or "unknown"),
                    attributes={
                        "claim_type": row["claim_type"],
                        "context": json_value(row["context_json"], {}),
                        "extraction_method": row["extraction_method"],
                    },
                    review_status=row["review_status"] or "pending",
                    reviewed_by=user_map.get(row["reviewed_by"]),
                    reviewed_at=parse_time(row["reviewed_at"]),
                )
                session.add(item)
            claim_map[legacy] = item.id
            report["id_map"][f"scientific_claims:{legacy}"] = str(item.id)
            mark(report, "scientific_claims", "migrated")
        session.flush()
        for row in rows(source, "claim_evidence"):
            legacy = row["evidence_id"]
            claim_id = claim_map.get(row["claim_id"])
            if not claim_id:
                mark(report, "claim_evidence", "rejected", legacy, "missing claim")
                continue
            if session.get(LiteratureEvidence, stable_id("claim_evidence", legacy)) is None:
                session.add(
                    LiteratureEvidence(
                        id=stable_id("claim_evidence", legacy),
                        legacy_id=legacy,
                        claim_id=claim_id,
                        evidence_type=row["evidence_role"],
                        content=row["evidence_excerpt"],
                        source_ref={
                            "chunk_id": str(chunk_map.get(row["chunk_id"]) or ""),
                            "start_offset": row["start_offset"],
                            "end_offset": row["end_offset"],
                        },
                    )
                )
            report["id_map"][f"claim_evidence:{legacy}"] = str(stable_id("claim_evidence", legacy))
            mark(report, "claim_evidence", "migrated")
        for row in rows(source, "claim_relations"):
            legacy = row["relation_id"]
            source_claim_id, target_claim_id = (
                claim_map.get(row["source_claim_id"]),
                claim_map.get(row["target_claim_id"]),
            )
            if not source_claim_id or not target_claim_id:
                mark(report, "claim_relations", "rejected", legacy, "missing related claim")
                continue
            source_claim = session.get(LiteratureClaim, source_claim_id)
            document = session.get(LiteratureDocument, source_claim.document_id) if source_claim else None
            if session.get(LiteratureRelation, stable_id("claim_relations", legacy)) is None:
                session.add(
                    LiteratureRelation(
                        id=stable_id("claim_relations", legacy),
                        legacy_id=legacy,
                        project_id=document.project_id if document else default_project_id,
                        source_claim_id=source_claim_id,
                        target_claim_id=target_claim_id,
                        relation_type=row["relation_type"],
                        rationale=row["rationale"],
                        review_status=row["review_status"] or "pending",
                        reviewed_by=user_map.get(row["reviewed_by"]),
                        reviewed_at=parse_time(row["reviewed_at"]),
                    )
                )
            report["id_map"][f"claim_relations:{legacy}"] = str(stable_id("claim_relations", legacy))
            mark(report, "claim_relations", "migrated")
        for row in rows(source, "literature_subscriptions"):
            legacy = row["subscription_id"]
            if session.get(LiteratureSubscription, stable_id("literature_subscriptions", legacy)) is None:
                hours = int(row["interval_hours"])
                cadence = "daily" if hours == 24 else f"every_{hours}_hours"
                session.add(
                    LiteratureSubscription(
                        id=stable_id("literature_subscriptions", legacy),
                        legacy_id=legacy,
                        project_id=default_project_id,
                        query=row["query"],
                        cadence=cadence,
                        enabled=bool(row["enabled"]),
                        created_by=user_map.get(row["created_by"]) or default_user_id,
                    )
                )
            report["id_map"][f"literature_subscriptions:{legacy}"] = str(stable_id("literature_subscriptions", legacy))
            mark(report, "literature_subscriptions", "migrated")

        intelligence_map: dict[str, uuid.UUID] = {}
        for row in rows(source, "target_intelligence_runs"):
            legacy = row["run_id"]
            project_id = project_map.get(row["project_id"]) or default_project_id
            project = session.get(Project, project_id)
            intelligence_target_id = project.primary_target_id if project else None
            if intelligence_target_id is None:
                target_payload = json_value(row["target_json"], {})
                intelligence_target_id = stable_id("intelligence_targets", legacy)
                if session.get(Target, intelligence_target_id) is None:
                    session.add(
                        Target(
                            id=intelligence_target_id,
                            legacy_id=f"intelligence:{legacy}",
                            project_id=project_id,
                            name=str(target_payload.get("name") or row["target_query"] or "Migrated target")[:240],
                            sequence=target_payload.get("sequence"),
                            structure_status="missing",
                        )
                    )
                    # Project.primary_target_id creates a deliberate cycle
                    # with Target.project_id.  Insert the target side first,
                    # then update the project in a second statement.
                    session.flush()
                if project:
                    project.primary_target_id = intelligence_target_id
                session.flush()
            item = session.get(IntelligenceRun, stable_id("target_intelligence_runs", legacy))
            if item is None:
                item = IntelligenceRun(
                    id=stable_id("target_intelligence_runs", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    target_id=intelligence_target_id,
                    status="succeeded" if row["status"] == "completed" else row["status"],
                    query={
                        "target_query": row["target_query"],
                        "objective": row["objective"],
                        "modality": row["modality"],
                        "organism": row["organism"],
                        "constraints": json_value(row["constraints_json"], {}),
                    },
                    created_by=user_map.get(row["created_by"]) or default_user_id,
                )
                session.add(item)
            intelligence_map[legacy] = item.id
            report["id_map"][f"target_intelligence_runs:{legacy}"] = str(item.id)
            mark(report, "target_intelligence_runs", "migrated")
        session.flush()
        for row in rows(source, "target_agent_reports"):
            legacy = row["report_id"]
            run_id = intelligence_map.get(row["run_id"])
            if not run_id:
                mark(report, "target_agent_reports", "rejected", legacy, "missing intelligence run")
                continue
            if session.get(IntelligenceReport, stable_id("target_agent_reports", legacy)) is None:
                session.add(
                    IntelligenceReport(
                        id=stable_id("target_agent_reports", legacy),
                        legacy_id=legacy,
                        run_id=run_id,
                        title=row["title"],
                        summary=row["summary"],
                        review_status="draft",
                        content=json_value(row["dossier_json"], {}),
                    )
                )
            report["id_map"][f"target_agent_reports:{legacy}"] = str(stable_id("target_agent_reports", legacy))
            mark(report, "target_agent_reports", "migrated")
        for row in rows(source, "target_evidence_items"):
            legacy = row["evidence_item_id"]
            run_id = intelligence_map.get(row["run_id"])
            if not run_id:
                mark(report, "target_evidence_items", "rejected", legacy, "missing intelligence run")
                continue
            if session.get(IntelligenceEvidence, stable_id("target_evidence_items", legacy)) is None:
                confidence_raw = str(row["confidence"] or "0")
                confidence = {"low": 0.25, "medium": 0.5, "high": 0.85}.get(confidence_raw)
                session.add(
                    IntelligenceEvidence(
                        id=stable_id("target_evidence_items", legacy),
                        legacy_id=legacy,
                        run_id=run_id,
                        evidence_type=row["source_type"],
                        citation={"identifier": row["identifier"], "title": row["title"], "url": row["url"]},
                        content=row["claim"],
                        confidence=confidence,
                        review_status=row["review_status"] or "pending",
                    )
                )
            report["id_map"][f"target_evidence_items:{legacy}"] = str(stable_id("target_evidence_items", legacy))
            mark(report, "target_evidence_items", "migrated")
        for row in rows(source, "target_hotspots"):
            legacy = row["hotspot_id"]
            run_id = intelligence_map.get(row["run_id"])
            if not run_id:
                mark(report, "target_hotspots", "rejected", legacy, "missing intelligence run")
                continue
            if session.get(IntelligenceHotspot, stable_id("target_hotspots", legacy)) is None:
                session.add(
                    IntelligenceHotspot(
                        id=stable_id("target_hotspots", legacy),
                        legacy_id=legacy,
                        run_id=run_id,
                        label=row["residue"],
                        residues=[{"residue": row["residue"], "index": row["residue_index"], "chain": row["chain_id"]}],
                        rationale=row["rationale"],
                        review_status=row["status"] or "pending",
                    )
                )
            report["id_map"][f"target_hotspots:{legacy}"] = str(stable_id("target_hotspots", legacy))
            mark(report, "target_hotspots", "migrated")
        for row in rows(source, "target_design_routes"):
            legacy = row["design_route_id"]
            run_id = intelligence_map.get(row["run_id"])
            if not run_id:
                mark(report, "target_design_routes", "rejected", legacy, "missing intelligence run")
                continue
            if session.get(DesignRoute, stable_id("target_design_routes", legacy)) is None:
                session.add(
                    DesignRoute(
                        id=stable_id("target_design_routes", legacy),
                        legacy_id=legacy,
                        run_id=run_id,
                        name=row["label"],
                        status=row["status"],
                        workflow_spec={
                            "nodes": [],
                            "edges": [],
                            "methods": json_value(row["methods_json"], []),
                            "module_ids": json_value(row["module_ids_json"], []),
                            "rationale": row["rationale"],
                            "risks": json_value(row["risks_json"], []),
                        },
                        applied_workflow_id=run_map.get(row["workflow_run_id"]),
                    )
                )
            report["id_map"][f"target_design_routes:{legacy}"] = str(stable_id("target_design_routes", legacy))
            mark(report, "target_design_routes", "migrated")
        for row in rows(source, "delivery_packages"):
            legacy = row["package_id"]
            project_id = project_map.get(row["project_id"])
            if not project_id:
                mark(report, "delivery_packages", "rejected", legacy, "missing project")
                continue
            delivery = session.get(DeliveryPackage, stable_id("delivery_packages", legacy))
            if delivery is None:
                delivery = DeliveryPackage(
                    id=stable_id("delivery_packages", legacy),
                    legacy_id=legacy,
                    project_id=project_id,
                    created_by=default_user_id,
                    status="pending",
                    name=f"Legacy delivery {legacy}",
                    selection={
                        "candidate_ids": json_value(row["candidate_ids"], []),
                        "experiment_summary": row["experiment_summary"],
                        "redesign_constraints": json_value(row["redesign_constraints"], {}),
                    },
                )
                session.add(delivery)
            delivery_created_at = parse_time(row["created_at"])
            if delivery_created_at is not None:
                delivery.created_at = delivery_created_at
            report["id_map"][f"delivery_packages:{legacy}"] = str(stable_id("delivery_packages", legacy))
            mark(report, "delivery_packages", "migrated")

        for row in rows(source, "audit_logs"):
            legacy = row["audit_id"]
            project_id = project_map.get(row["project_id"])
            project = session.get(Project, project_id) if project_id else None
            audit_id = stable_id("audit_logs", legacy)
            if session.get(AuditLog, audit_id) is None:
                session.add(
                    AuditLog(
                        id=audit_id,
                        actor_id=user_map.get(row["actor_id"]),
                        organization_id=project.organization_id if project else None,
                        project_id=project_id,
                        action=row["action"],
                        entity_type=row["entity_type"],
                        entity_id=stable_id(row["entity_type"], row["entity_id"]) if row["entity_id"] else None,
                        trace_id=f"legacy:{legacy}",
                        result="success",
                        payload={"legacy_id": legacy, **json_value(row["payload_json"], {})},
                        created_at=parse_time(row["created_at"]) or datetime.now(UTC),
                    )
                )
            report["id_map"][f"audit_logs:{legacy}"] = str(audit_id)
            mark(report, "audit_logs", "migrated")

        app_settings = rows(source, "app_settings")
        copilot_settings = {
            row["key"]: json_value(row["value"], row["value"]) for row in app_settings if row["namespace"] == "copilot"
        }
        provider_rows = rows(source, "llm_providers")
        provider_id = stable_id("llm_providers", provider_rows[0]["llm_provider_id"]) if provider_rows else None
        if copilot_settings:
            for legacy_project, project_id in project_map.items():
                config_id = stable_id("copilot_configs", legacy_project)
                if session.get(CopilotConfig, config_id) is None:
                    session.add(
                        CopilotConfig(
                            id=config_id,
                            legacy_id=legacy_project,
                            project_id=project_id,
                            llm_provider_id=provider_id,
                            settings=copilot_settings,
                            enabled_skills=["knowledge", "literature", "intelligence", "interpretation"],
                        )
                    )
                report["id_map"][f"copilot_configs:{legacy_project}"] = str(config_id)
        for row in app_settings:
            legacy = f"{row['namespace']}:{row['key']}"
            report["id_map"][f"app_settings:{legacy}"] = str(stable_id("app_settings", legacy))
            mark(report, "app_settings", "migrated")

    source.close()
    report["finished_at"] = datetime.now(UTC).isoformat()
    report["tables"] = dict(report["tables"])
    unexplained = {
        table: values
        for table, values in report["tables"].items()
        if values["source"] != values["migrated"] + values["deferred"] + values["rejected"]
    }
    if unexplained:
        raise RuntimeError(f"migration report has unexplained source rows: {unexplained}")
    canonical_id_map = json.dumps(report["id_map"], sort_keys=True, separators=(",", ":")).encode()
    canonical_checksums = json.dumps(report["file_checksums"], sort_keys=True, separators=(",", ":")).encode()
    report["id_map_digest"] = hashlib.sha256(canonical_id_map).hexdigest()
    report["file_checksums_digest"] = hashlib.sha256(canonical_checksums).hexdigest()
    rejection_summary: dict[str, int] = defaultdict(int)
    for rejection in report["rejections"]:
        rejection_summary[f"{rejection['table']}:{rejection['reason']}"] += 1
    report["rejection_summary"] = dict(sorted(rejection_summary.items()))
    migration_run_id = stable_id("migration_runs", f"{report['source_fingerprint']}:{rehearsal}")
    with session_scope() as session:
        migration_run = session.get(MigrationRun, migration_run_id)
        if migration_run is None:
            migration_run = MigrationRun(
                id=migration_run_id,
                legacy_id=f"rehearsal:{report['source_fingerprint']}:{rehearsal}",
                source_fingerprint=report["source_fingerprint"],
                rehearsal=rehearsal,
                status="succeeded" if not report["rejections"] else "completed_with_rejections",
                counts=report["tables"],
                checksums={
                    "files": report["file_checksums_digest"],
                    "verified": report["files"]["verified"],
                },
                id_map_digest=report["id_map_digest"],
                rejection_summary=report["rejection_summary"],
            )
            session.add(migration_run)
        else:
            migration_run.status = "succeeded" if not report["rejections"] else "completed_with_rejections"
            migration_run.counts = report["tables"]
            migration_run.checksums = {
                "files": report["file_checksums_digest"],
                "verified": report["files"]["verified"],
            }
            migration_run.id_map_digest = report["id_map_digest"]
            migration_run.rejection_summary = report["rejection_summary"]
            migration_run.version += 1
    report["migration_run_id"] = str(migration_run_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotently migrate a read-only BDA v1 snapshot into v2")
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument(
        "--artifact-root",
        dest="artifact_roots",
        type=Path,
        action="append",
        help="Allowed artifact root; repeat for backend/artifacts and repository deliverables",
    )
    parser.add_argument("--artifacts-root", dest="legacy_artifacts_root", type=Path, help="Deprecated single-root form")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--rehearsal", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--skip-files", action="store_true", help="Inventory files without uploading them to MinIO")
    args = parser.parse_args()
    artifact_roots = args.artifact_roots or ([args.legacy_artifacts_root] if args.legacy_artifacts_root else [])
    if not artifact_roots:
        parser.error("at least one --artifact-root is required")
    migrate(
        args.sqlite,
        artifact_roots,
        args.report,
        skip_files=args.skip_files,
        rehearsal=args.rehearsal,
    )


if __name__ == "__main__":
    main()
