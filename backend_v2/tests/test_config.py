import pytest
from backend_v2.app.core.config import Settings
from backend_v2.scripts.check_production_readiness import (
    REQUIRED_FILES,
    REQUIRED_SECRET_REFS,
    REQUIRED_VALUES,
    readiness_report,
)
from pydantic import ValidationError


def test_sqlite_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requires PostgreSQL"):
        Settings(database_url="sqlite:///unsafe.db", _env_file=None)


def test_insecure_production_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(environment="production", compute_backend="lsf", _env_file=None)


def test_demo_backend_is_allowed_only_outside_production() -> None:
    assert Settings(compute_backend="demo", _env_file=None).compute_backend == "demo"


def test_oidc_provider_requires_a_redirect_uri_allowlist() -> None:
    """redirect_uri arrives as a query parameter; without a declared list at startup
    there is nothing to validate it against at login time."""
    with pytest.raises(ValidationError, match="redirect_uris"):
        Settings(
            oidc_providers_json='{"campus": {"issuer": "https://idp.invalid", "client_id": "bda"}}',
            _env_file=None,
        )


def test_oidc_issuer_must_be_https() -> None:
    with pytest.raises(ValidationError, match="https"):
        Settings(
            oidc_providers_json=(
                '{"campus": {"issuer": "http://idp.invalid", "client_id": "bda",'
                ' "redirect_uris": "https://bda.invalid/callback"}}'
            ),
            _env_file=None,
        )


def test_fully_specified_oidc_provider_is_accepted() -> None:
    settings = Settings(
        oidc_providers_json=(
            '{"campus": {"issuer": "https://idp.invalid", "client_id": "bda",'
            ' "redirect_uris": "https://bda.invalid/callback"}}'
        ),
        _env_file=None,
    )
    assert settings.oidc_providers["campus"]["client_id"] == "bda"


def test_production_readiness_requires_readable_evidence(tmp_path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}")
    environment = {name: "configured" for name in REQUIRED_VALUES | REQUIRED_SECRET_REFS}
    environment.update({name: str(evidence) for name in REQUIRED_FILES})
    environment["BDA_V2_DOCKER_HOST"] = "tcp://docker.example:2376"
    environment["BDA_V2_WRITES_ENABLED"] = "false"
    assert readiness_report(environment)["ready"] is True

    environment["BDA_V2_LSF_SMOKE_REPORT"] = str(tmp_path / "missing.json")
    report = readiness_report(environment)
    assert report["ready"] is False
    assert any("LSF_SMOKE_REPORT" in item for item in report["invalid"])
