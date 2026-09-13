"""Design-prompt generation for new projects.

A ``ProjectPromptDraft`` is created and polled before the project it describes exists,
so it cannot be scoped to a project the way ``ResearchGeneration`` is — see
``require_project_prompt_draft`` in ``service.py`` for the resulting authorization model.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.orm import Session

from ..core.celery_app import celery_app
from ..core.database import session_scope
from ..core.problem import DomainError

SYSTEM_PROMPT = (
    "You draft the kickoff brief for a protein research project of the specified project type. "
    "Write a concise design prompt (300-600 words) covering: the target rationale and "
    "biological context, the design goal and success criteria, key constraints "
    "(e.g. specificity, developability, known epitope or interface preferences), and "
    "the first two or three concrete steps a research team should take. Write in prose, "
    "addressed to the team that will run the project. Do not include a title or headers, "
    "just the brief itself. Use the requested language. Do not invent target identity, "
    "experimental results, citations, or numerical acceptance thresholds. Explicitly label "
    "missing information and proposed criteria for the user to confirm."
)


def _select_llm_provider(session: Session, requested_id: str | None):
    from ..copilot.provider_selection import select_provider

    return select_provider(session, requested_id)


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
        from ..copilot.provider_selection import select_provider

        provider = select_provider(
            session,
            request.get("llm_provider_id"),
            project_id=uuid.UUID(request["project_id"]) if request.get("project_id") else None,
        )
        if provider is None:
            row.status = "failed"
            row.error = "no_llm_provider_configured"
            row.version += 1
            return {"draft_id": draft_id, "status": row.status}

        user_message = (
            f"Language: {request.get('language', 'en')}\n"
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

        if not isinstance(text, str) or not text.strip():
            row.status = "failed"
            row.error = "Model returned an empty brief; retry with a configured model"
            row.version += 1
            return {"draft_id": draft_id, "status": row.status}
        row.status = "ready"
        row.prompt = text.strip()
        row.version += 1
        return {"draft_id": draft_id, "status": row.status}
