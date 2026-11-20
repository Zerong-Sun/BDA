from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..artifacts.models import Artifact
from ..audit.service import record_audit
from ..core.models import update_versioned
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


def sync_package_target(
    session: Session,
    project: Project,
    *,
    name: str,
    uniprot_accession: str | None,
    organism: str | None,
) -> Target:
    """Make a research package's primary target the project's primary target.

    A package carries only name, accession and organism. Sequence, target kind and
    chemical identity are left alone so a re-import never erases what a user entered,
    and the version moves only when one of the package fields actually changed.
    """
    repo = TargetRepository(session)
    target = repo.by_project(project.id)
    if target is None:
        target = repo.add(Target(project_id=project.id, name=name))
    update_versioned(
        target,
        name=name,
        uniprot_accession=uniprot_accession,
        organism=organism,
        identity_status="confirmed" if uniprot_accession else "unconfirmed",
    )
    if project.primary_target_id != target.id:
        project.primary_target_id = target.id
        project.version += 1
    return target


def add_unconfirmed_primary_target(
    session: Session, project: Project, *, name: str, uniprot_accession: str | None, organism: str | None
) -> Target:
    """Give a new project the primary target an unreviewed import proposed; a person confirms it later."""
    target = TargetRepository(session).add(
        Target(
            project_id=project.id,
            name=name,
            uniprot_accession=uniprot_accession,
            organism=organism,
            identity_status="unconfirmed",
        )
    )
    project.primary_target_id = target.id
    project.version += 1
    return target


def get_target(session: Session, target_id: uuid.UUID) -> Target | None:
    return TargetRepository(session).get(target_id)


def project_primary_target(session: Session, project: Project) -> Target | None:
    return session.get(Target, project.primary_target_id) if project.primary_target_id else None


def release_structure(target: Target, artifact_id: uuid.UUID) -> None:
    """Detach a structure that is being retired, if it is this target's current one."""
    if target.structure_artifact_id == artifact_id:
        target.structure_artifact_id = None
        target.structure_status = "missing"
        target.version += 1


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
    if target.project_id != project.id:
        raise DomainError("target_not_found", "Target does not belong to this project", status_code=404)
    project.primary_target_id = target.id
    project.version += 1
    return target


def attach_structure(target: Target, artifact: Artifact, expected_version: int) -> Target:
    if artifact.project_id != target.project_id or artifact.status != "available" or artifact.deleted_at is not None:
        raise DomainError("artifact_not_found", "Available project artifact was not found", status_code=404)
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
    if target.project_id != project.id:
        raise DomainError("target_not_found", "Target does not belong to this project", status_code=404)
    if artifact.project_id != project.id or artifact.status != "available" or artifact.deleted_at is not None:
        raise DomainError("artifact_not_found", "Available project artifact was not found", status_code=404)
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
    if revision.target_id != target.id:
        raise DomainError("structure_revision_not_found", "Structure revision was not found for this target", status_code=404)
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
