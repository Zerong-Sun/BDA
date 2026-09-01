from __future__ import annotations

from backend_v2.app import main
from fastapi.testclient import TestClient


def test_disabled_write_gate_returns_problem_response(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "writes_enabled", False)

    response = TestClient(main.app).post("/api/v2/projects", json={})

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == "writes_disabled"
