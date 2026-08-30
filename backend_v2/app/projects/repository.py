from __future__ import annotations

import uuid

from sqlalchemy import select
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
            organization_ids = select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
            query = query.where(Project.organization_id.in_(organization_ids))
        if after:
            query = query.where(Project.id > after)
        return list(self.session.scalars(query.order_by(Project.id).limit(limit + 1)))

    def user_can_access(self, project: Project, user: User) -> bool:
        if user.role == "admin":
            return True
        organization_member = self.session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        if organization_member is None:
            return False
        project_member = self.session.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user.id)
        )
        return project_member is not None or organization_member is not None

    def effective_project_role(self, project: Project, user: User) -> str | None:
        """Return the deny-first role after all three authorization caps."""
        if user.role == "admin":
            return "owner"
        organization_role = self.organization_role(project.organization_id, user.id)
        if organization_role is None:
            return None
        organization_role = "researcher" if organization_role == "member" else organization_role
        project_member = self.session.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user.id)
        )
        project_role = project_member.role if project_member is not None else organization_role
        if project.owner_id == user.id and project_member is None:
            project_role = "owner"
        ranks = {"viewer": 0, "researcher": 1, "admin": 2, "owner": 3}
        if organization_role not in ranks or project_role not in ranks:
            return None
        global_role = "researcher" if user.role == "member" else user.role
        if global_role not in ranks:
            return None
        effective_rank = min(ranks[global_role], ranks[organization_role], ranks[project_role])
        return next(role for role, rank in ranks.items() if rank == effective_rank)

    def organization_role(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        member = self.session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return member.role if member else None
