"""One provider selection policy for briefs, research, chat and durable agents."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..registry.models import LLMProvider
from .models import CopilotConfig


def select_provider(
    session: Session, requested_id: str | uuid.UUID | None = None, *, project_id: uuid.UUID | None = None
) -> LLMProvider | None:
    config = session.scalar(select(CopilotConfig).where(CopilotConfig.project_id == project_id)) if project_id else None
    selected = requested_id or (config.llm_provider_id if config else None)
    if selected:
        provider = session.get(LLMProvider, uuid.UUID(str(selected)))
        if provider is None or not provider.enabled:
            return None  # An explicit selection must never silently switch providers.
        if provider.name.startswith("Project ") and provider.name.endswith(" BYOK"):
            if provider.name != f"Project {project_id} BYOK":
                return None
        return provider

    providers = [
        provider
        for provider in session.scalars(select(LLMProvider).where(LLMProvider.enabled.is_(True)))
        if not (provider.name.startswith("Project ") and provider.name.endswith(" BYOK"))
    ]
    reference = get_settings().llm_default_provider_ref
    if reference:
        providers = [provider for provider in providers if provider.credential_ref == reference]
    else:
        defaults = [provider for provider in providers if (provider.config or {}).get("platform_default") is True]
        if defaults:
            providers = defaults
    return providers[0] if len(providers) == 1 else None
