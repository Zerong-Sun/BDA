from __future__ import annotations

import uuid

import pytest
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.problem import DomainError
from backend_v2.app.core.rate_limit import (
    enforce_login_quota,
    enforce_project_quota,
)


class FakeRedis:
    def __init__(self, results: list[list[int]]) -> None:
        self.results = results
        self.keys: list[str] = []

    def eval(self, _script: str, _numkeys: int, key: str, _window: str) -> list[int]:
        self.keys.append(key)
        return self.results.pop(0)


def test_login_quota_is_scoped_by_ip_and_normalized_username(monkeypatch) -> None:
    fake = FakeRedis([[1, 60]])
    monkeypatch.setattr("backend_v2.app.core.rate_limit.Redis.from_url", lambda *_args, **_kwargs: fake)
    enforce_login_quota("192.0.2.1", " Researcher ")
    assert fake.keys[0].startswith("bda:rate:login:192.0.2.1:")
    assert "Researcher" not in fake.keys[0]


def test_project_quota_enforces_user_and_organization_with_retry_after(monkeypatch) -> None:
    settings = get_settings()
    fake = FakeRedis([[settings.rate_limit_expensive + 1, 17]])
    monkeypatch.setattr("backend_v2.app.core.rate_limit.Redis.from_url", lambda *_args, **_kwargs: fake)
    with pytest.raises(DomainError) as raised:
        enforce_project_quota(uuid.uuid4(), uuid.uuid4(), "compute")
    assert raised.value.status_code == 429
    assert raised.value.headers == {"Retry-After": "17"}
