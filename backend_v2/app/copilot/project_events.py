"""Project invalidations derived from committed rows; no transcript in the stream.

A bounded stream checks aggregate revisions, never retains a transaction between
checks, and reauthorizes each read. It catches updates to older room entries too.
Polling clients remain supported when a proxy buffers or closes SSE.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..compute.models import ComputeDraft
from ..core.database import SessionFactory, set_request_rls_context
from ..core.problem import DomainError
from ..identity.models import User
from ..literature.models import LiteratureClaim, LiteratureDocument
from ..projects.service import require_project_permission
from .models import CopilotAgentRun, CopilotConversation, CopilotDecisionRequest, CopilotHandoff, CopilotMessage


def revision(session: Session, project_id: uuid.UUID) -> str:
    revisions: list[Any] = []
    for model in (CopilotAgentRun, CopilotDecisionRequest, CopilotHandoff, ComputeDraft):
        revisions.append(tuple(session.execute(select(
            func.count(model.id), func.max(model.updated_at), func.sum(model.version),
        ).where(model.project_id == project_id)).one()))
    revisions.append(tuple(session.execute(select(
        func.count(CopilotMessage.id), func.max(CopilotMessage.updated_at), func.sum(CopilotMessage.version),
    ).join(CopilotConversation, CopilotMessage.conversation_id == CopilotConversation.id).where(
        CopilotConversation.project_id == project_id,
        CopilotMessage.role.in_(['user', 'assistant']),
    )).one()))
    revisions.append(tuple(session.execute(select(
        func.count(LiteratureClaim.id), func.max(LiteratureClaim.updated_at), func.sum(LiteratureClaim.version),
    ).join(LiteratureDocument, LiteratureClaim.document_id == LiteratureDocument.id).where(
        LiteratureDocument.project_id == project_id,
    )).one()))
    return hashlib.sha256(json.dumps(revisions, default=str).encode()).hexdigest()


def authorized_revision(project_id: uuid.UUID, user_id: uuid.UUID) -> str:
    with SessionFactory() as session:
        # Start with a non-admin context; the user row is reloaded on every tick.
        set_request_rls_context(session, user_id=user_id, is_global_admin=False)
        user = session.get(User, user_id)
        if user is None or not user.enabled:
            raise DomainError('forbidden', 'Account is no longer active', status_code=403)
        set_request_rls_context(session, user_id=user.id, is_global_admin=user.role == 'admin')
        require_project_permission(session, project_id, user, 'read')
        return revision(session, project_id)


async def stream(project_id: uuid.UUID, user_id: uuid.UUID) -> AsyncIterator[dict[str, str]]:
    previous: str | None = None
    for _ in range(12):
        try:
            current = await asyncio.to_thread(authorized_revision, project_id, user_id)
        except DomainError:
            return
        if current != previous:
            yield {'event': 'project-change', 'id': current, 'data': json.dumps({'project_id': str(project_id)})}
            previous = current
        else:
            yield {'event': 'heartbeat', 'data': '{}'}
        await asyncio.sleep(5)
