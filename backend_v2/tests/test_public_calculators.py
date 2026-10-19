from __future__ import annotations

import pytest
from backend_v2.app.core.config import get_settings
from backend_v2.app.core.database import get_session
from backend_v2.app.core.problem import DomainError
from backend_v2.app.main import app
from backend_v2.app.wetlab import access
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "deployment_kind", "public")
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)
    # Public calculators must never touch identity, organization or project data.
    def no_database():
        yield None
    app.dependency_overrides[get_session] = no_database
    with TestClient(app) as opened:
        yield opened
    app.dependency_overrides.clear()


def test_public_calculators_are_anonymous_and_non_persistent(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "writes_enabled", False)
    response = client.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "MWK"})
    assert response.status_code == 200, response.text
    assert any(value["key"] == "molecular_weight_g_mol" for value in response.json()["values"])
    assert client.get("/api/v2/wetlab/unit-conversion?value=1&from_unit=M&to_unit=uM").status_code == 200
    assert client.get("/api/v2/wetlab/dilution-series?stock_conc_uM=100&start_conc_uM=50&dilution_factor=2&n_steps=3&vol_per_well_uL=100").status_code == 200


def test_private_calculators_still_require_login(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "deployment_kind", "private")
    assert client.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "MWK"}).status_code == 401
    assert client.get("/api/v2/wetlab/unit-conversion?value=1&from_unit=mM&to_unit=uM").status_code == 401


def test_public_access_does_not_open_projects_or_bot(client):
    assert client.get("/api/v2/projects").status_code == 401
    assert client.get("/api/v2/organizations").status_code == 401
    response = client.post("/api/v2/copilot/chat", json={"project_id": "00000000-0000-4000-8000-000000000001", "message": "test"})
    assert response.status_code == 401


def test_anonymous_calculations_use_quota_and_validate_inputs(client, monkeypatch):
    assert client.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "INVALID123"}).status_code == 422
    def exceeded(_ip):
        raise DomainError("rate_limit_exceeded", "Request quota exceeded", status_code=429)
    monkeypatch.setattr(access, "enforce_public_calculator_quota", exceeded)
    assert client.post("/api/v2/wetlab/calculations", json={"kind": "protein-properties", "sequence": "MWK"}).status_code == 429
