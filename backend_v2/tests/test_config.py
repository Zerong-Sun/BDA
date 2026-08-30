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


def _production_database_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "database_url": "postgresql+psycopg://bda_api:secret@postgres/bda_v2",
        "maintenance_database_url": "postgresql+psycopg://bda_migrator:secret@postgres/bda_v2",
        "maintenance_database_role": "bda_migrator",
        "jwt_secret": "x" * 40,
        "rate_limit_fail_closed": True,
        "cors_origins": "https://bda.invalid",
        "compute_backend": "lsf",
        "lsf_ssh_host": "lsf.invalid",
        "lsf_remote_root": "/shared/bda",
        "lsf_ssh_key_path": "/var/run/secrets/lsf/key",
        "minio_secret_key": "x" * 20,
        "minio_public_endpoint": "artifacts.bda.invalid",
        "oidc_providers_json": (
            '{"campus":{"issuer":"https://idp.invalid","client_id":"bda",'
            '"redirect_uris":"https://bda.invalid/callback"}}'
        ),
        "llm_default_provider_ref": "file:/var/lib/bda/secrets/default.key",
        "external_research_sources_json": '{"europe_pmc":{"base_url":"https://example.invalid"}}',
        "otel_endpoint": "http://otel.invalid:4318",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_requires_distinct_application_and_migration_roles() -> None:
    with pytest.raises(ValidationError, match="must be distinct"):
        _production_database_settings(
            maintenance_database_url="postgresql+psycopg://bda_api:other@postgres/bda_v2"
        )

    assert _production_database_settings().maintenance_database_url is not None


def test_production_migration_job_requires_owner_role() -> None:
    with pytest.raises(ValidationError, match="maintenance_database_role"):
        _production_database_settings(
            require_maintenance_database_url=True,
            maintenance_database_role=None,
        )

    assert _production_database_settings(
        require_maintenance_database_url=True
    ).maintenance_database_role == "bda_migrator"


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
