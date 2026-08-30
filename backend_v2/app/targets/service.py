from __future__ import annotations

from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..core.problem import DomainError
from ..identity.models import User
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from .identity import is_identified
from .models import Target, TargetStructureRevision
from .repository import TargetRepository
from .schemas import TargetStructurePrepare, TargetStructureReview, TargetUpdate, TargetUpsert


def upsert_target(session: Session, project: Project, payload: TargetUpsert, user: User) -> Target:
    repo = TargetRepository(session)
    target = repo.by_project(project.id)
    if target is None:
        target = repo.add(Target(project_id=project.id, name=payload.name))
        action = "target.create"
    else:
        target.version += 1
        action = "target.update"
    target.name = payload.name.strip()
    target.sequence = payload.sequence
    target.uniprot_accession = payload.uniprot_accession
    target.organism = payload.organism
    # These two decide what "identified" even means for this target (identity.py), so
    # dropping them here silently downgraded every small-molecule target to a protein
    # with no chemical identity - which then failed readiness on a missing structure
    # artifact that a ligand target is never supposed to have, and left the workflow
    # permanently read-only.
    target.target_kind = payload.target_kind
    target.chemical_identity = payload.chemical_identity
    target.identity_status = "confirmed" if is_identified(target) else "unconfirmed"
    record_audit(
        session,
        action=action,
        entity_type="target",
        entity_id=target.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return target


def create_target(session: Session, project: Project, payload: TargetUpsert, user: User) -> Target:
    target = Target(project_id=project.id, **payload.model_dump())
    target.identity_status = "confirmed" if is_identified(target) else "unconfirmed"
    TargetRepository(session).add(target)
    if project.primary_target_id is None:
        project.primary_target_id = target.id
        project.version += 1
    record_audit(
        session,
        action="target.create",
        entity_type="target",
        entity_id=target.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return target


def update_target(
    session: Session, project: Project, target: Target, payload: TargetUpdate, user: User, expected_version: int
) -> Target:
    if target.version != expected_version:
        raise DomainError("version_conflict", "Target was modified by another request", status_code=412)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    target.identity_status = "confirmed" if is_identified(target) else "unconfirmed"
    target.version += 1
    record_audit(
        session,
        action="target.update",
        entity_type="target",
        entity_id=target.id,
        project_id=project.id,
        organization_id=project.organization_id,
        actor_id=user.id,
    )
    return target


def select_primary_target(project: Project, target: Target) -> Target:
    project.primary_target_id = target.id
    project.version += 1
    return target


def attach_structure(target: Target, artifact: Artifact, expected_version: int) -> Target:
    if target.version != expected_version:
        raise DomainError("version_conflict", "Target was modified by another request", status_code=412)
    target.structure_artifact_id = artifact.id
    target.structure_status = "available"
    target.version += 1
    return target


def mark_structure_importing(target: Target) -> Target:
    target.structure_status = "importing"
    target.version += 1
    return target


def prepare_structure_revision(
    session: Session,
    target: Target,
    project: Project,
    artifact: Artifact,
    payload: TargetStructurePrepare,
    user: User,
) -> TargetStructureRevision:
    revision = TargetStructureRevision(
        target_id=target.id,
        source_artifact_id=artifact.id,
        options=payload.model_dump(exclude={"source_artifact_id"}),
        created_by=user.id,
    )
    session.add(revision)
    session.flush()
    enqueue_operation(
        session,
        topic="target.structure.prepare",
        resource_type="target_structure_revision",
        resource_id=revision.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"revision_id": str(revision.id)},
    )
    target.structure_status = "preparing"
    target.version += 1
    return revision


def review_structure_revision(
    revision: TargetStructureRevision, target: Target, payload: TargetStructureReview, expected_version: int
) -> TargetStructureRevision:
    if revision.version != expected_version:
        raise DomainError("version_conflict", "Structure revision was modified by another request", status_code=412)
    if payload.approve and revision.status != "available":
        raise DomainError("structure_revision_not_ready", "Structure revision is not available", status_code=409)
    revision.approved = payload.approve
    revision.version += 1
    if payload.approve:
        target.structure_artifact_id = revision.prepared_artifact_id or revision.source_artifact_id
        target.structure_status = "approved"
        target.version += 1
    return revision
