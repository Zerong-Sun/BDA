"""Offline synchronous-script adapters for the async provider HTTP boundary."""
from __future__ import annotations

from typing import Any

from backend_v2.app.copilot import provider


def mock_post(monkeypatch: Any, post: Any) -> None:
    async def send(_client: Any, url: str, **kwargs: Any) -> Any:
        return post(url, **kwargs)

    monkeypatch.setattr(provider.httpx.AsyncClient, "post", send)


def mock_sleep(monkeypatch: Any, callback: Any) -> None:
    async def sleep(delay: float) -> None:
        callback(delay)

    monkeypatch.setattr(provider.asyncio, "sleep", sleep)
