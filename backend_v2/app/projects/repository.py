from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..identity.models import OrganizationMember, User
from .models import Project, ProjectMember


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, project: Project) -> Project:
        self.session.add(project)
        self.session.flush()
        return project

    def get(self, project_id: uuid.UUID, *, include_deleted: bool = False) -> Project | None:
        query = select(Project).where(Project.id == project_id)
        if not include_deleted:
            query = query.where(Project.deleted_at.is_(None))
        return self.session.scalar(query)

    def by_research_source(
        self,
        organization_id: uuid.UUID,
        package_id: str,
        project_key: str,
    ) -> Project | None:
        return self.session.scalar(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.source_package_id == package_id,
                Project.source_project_key == project_key,
                Project.deleted_at.is_(None),
            )
        )

    def list_visible(
        self,
        user: User,
        *,
        after: uuid.UUID | None,
        limit: int,
    ) -> list[Project]:
        query = select(Project).where(Project.deleted_at.is_(None))
        if user.role != "admin":
            project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
            organization_ids = select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
            query = query.where(or_(Project.id.in_(project_ids), Project.organization_id.in_(organization_ids)))
        if after:
            query = query.where(Project.id > after)
        return list(self.session.scalars(query.order_by(Project.id).limit(limit + 1)))

    def user_can_access(self, project: Project, user: User) -> bool:
        if user.role == "admin" or project.owner_id == user.id:
            return True
        project_member = self.session.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user.id)
        )
        if project_member:
            return True
        organization_member = self.session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        return organization_member is not None

    def organization_role(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        member = self.session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return member.role if member else None
