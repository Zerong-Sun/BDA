"""Generic helpers for binding workflow nodes to immutable registry plugins."""

from __future__ import annotations

from backend_v2.app.registry.models import ModelPlugin
from sqlalchemy import select
from sqlalchemy.orm import Session

# Only platform-level labels belong here. Project-specific manual stages must be
# declared by that project's private workflow/package manifest.
MANUAL_STAGE_PLUGINS: frozenset[str] = frozenset(
    {
        "Human review",
        "Imported project inputs",
        "BDA candidate table",
        "BDA developability filters",
        "BDA filters",
        "legacy-unknown",
    }
)
_RUNTIME_PREFERENCE = ("conda", "script", "module", "container")


def resolve_model_plugin(session: Session, model_plugin: str) -> ModelPlugin | None:
    """Resolve an enabled plugin deterministically without hiding missing tools."""
    candidates = list(
        session.scalars(
            select(ModelPlugin).where(
                ModelPlugin.plugin_key == model_plugin,
                ModelPlugin.enabled.is_(True),
            )
        )
    )
    if not candidates:
        return None

    def runtime_rank(plugin: ModelPlugin) -> int:
        mode = plugin.runtime_mode or "container"
        return _RUNTIME_PREFERENCE.index(mode) if mode in _RUNTIME_PREFERENCE else len(_RUNTIME_PREFERENCE)

    candidates.sort(key=lambda plugin: plugin.plugin_version, reverse=True)
    candidates.sort(key=runtime_rank)
    return candidates[0]
