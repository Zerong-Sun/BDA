"""Design-prompt generation for new projects.

A ``ProjectPromptDraft`` is created and polled before the project it describes exists,
so it cannot be scoped to a project the way ``ResearchGeneration`` is — see
``require_project_prompt_draft`` in ``service.py`` for the resulting authorization model.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.celery_app import celery_app
from ..core.database import session_scope
from ..core.problem import DomainError

SYSTEM_PROMPT = (
    "You draft the kickoff brief for a computational protein-binder-design project. "
    "Write a concise design prompt (300-600 words) covering: the target rationale and "
    "biological context, the design goal and success criteria, key constraints "
    "(e.g. specificity, developability, known epitope or interface preferences), and "
    "the first two or three concrete steps a research team should take. Write in prose, "
    "addressed to the team that will run the project. Do not include a title or headers, "
    "just the brief itself."
)


def _select_llm_provider(session: Session, requested_id: str | None):
    from ..registry.models import LLMProvider

    if requested_id:
        provider = session.get(LLMProvider, uuid.UUID(requested_id))
        if provider is not None and provider.enabled:
            return provider
    return session.scalar(
        select(LLMProvider).where(LLMProvider.enabled.is_(True)).order_by(LLMProvider.name)
    )


@celery_app.task(name="bda_v2.project_prompt_generate")
def project_prompt_generate(draft_id: str) -> dict:
    from ..copilot.provider import complete
    from .models import ProjectPromptDraft

    parsed = uuid.UUID(draft_id)
    with session_scope() as session:
        row = session.get(ProjectPromptDraft, parsed)
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
            f"Project name: {request.get('name') or ''}\n"
            f"Project type: {request.get('project_type') or ''}\n"
            f"Objective / constraints: {request.get('summary') or '(none provided)'}"
        )
        try:
            text = complete(
                provider,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
        except (DomainError, ValueError, httpx.HTTPError) as exc:
            row.status = "failed"
            row.error = str(exc)[:4000]
            row.version += 1
            return {"draft_id": draft_id, "status": row.status}

        row.status = "ready"
        row.prompt = text
        row.version += 1
        return {"draft_id": draft_id, "status": row.status}
