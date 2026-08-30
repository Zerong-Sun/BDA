from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..identity.models import User
from ..projects.models import Project
from ..projects.service import require_project
from ..research.schemas import ResearchGapResolutionCreate
from ..research.service import request_gap_resolution


class ResearchActionService:
    """Project-scoped, permission-checked mutations available to Copilot."""

    def __init__(self, session: Session, project: Project, user: User):
        self.session = session
        self.project = project
        self.user = user

    def resolve_research_gaps(
        self,
        research_target_id: str,
        *,
        resolve_references: bool = True,
        resolve_structure: bool = True,
    ) -> dict[str, str]:
        if not self.user.enabled:
            raise ValueError("copilot_action_user_disabled")
        try:
            parsed_target_id = uuid.UUID(research_target_id)
        except ValueError as exc:
            raise ValueError("research_target_id_invalid") from exc
        project = require_project(self.session, self.project.id, self.user)
        accepted = request_gap_resolution(
            self.session,
            project,
            parsed_target_id,
            ResearchGapResolutionCreate(
                resolve_references=resolve_references,
                resolve_structure=resolve_structure,
            ),
            self.user,
        )
        return {
            "operation_id": str(accepted.operation_id),
            "research_target_id": str(accepted.research_target_id),
            "status": accepted.status,
        }
