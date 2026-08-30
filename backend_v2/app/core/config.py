from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BDA_V2_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://bda:bda@localhost:5433/bda_v2"
    database_pool_size: int = Field(default=20, ge=5, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    redis_url: str = "redis://localhost:6380/0"
    celery_broker_url: str = "redis://localhost:6380/1"
    jwt_secret: str = "development-only-change-this-bda-v2-secret"
    jwt_issuer: str = "bda-v2"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    minio_endpoint: str = "localhost:9002"
    minio_public_endpoint: str | None = None
    minio_region: str = "us-east-1"
    minio_access_key: str = "bda-v2"
    minio_secret_key: str = "development-minio-secret"
    minio_bucket: str = "bda-v2-artifacts"
    minio_secure: bool = False
    upload_url_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1024)
    compute_backend: str = "docker"
    docker_host: str = "tcp://localhost:2376"
    docker_tls_ca: str | None = None
    docker_tls_cert: str | None = None
    docker_tls_key: str | None = None
    docker_tls_verify: bool = True
    # No default host or remote root: both are site-specific. They used to name one
    # institution's cluster and one user's scratch directory, so an unconfigured
    # deployment silently aimed at somebody else's filesystem instead of failing.
    lsf_ssh_host: str = ""
    lsf_ssh_port: int = Field(default=22, ge=1, le=65535)
    lsf_ssh_user: str | None = None
    lsf_remote_root: str = ""
    lsf_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    lsf_queue: str = "normal"
    lsf_upload_wrapper: str = "/usr/local/bin/bda-minio-upload"
    # ssh: the API stages inputs and retrieves outputs over SFTP, and the job only ever
    # touches the shared filesystem. presigned: the job talks to the object store itself.
    # ssh is the default because compute nodes commonly have no route to the object store.
    lsf_staging_mode: str = Field(default="ssh", pattern="^(ssh|presigned)$")
    lsf_ssh_key_path: str | None = None
    # Some clusters disable publickey entirely and only accept passwords. Reference a
    # file (``file:/run/secrets/lsf-password``); never an inline value.
    lsf_ssh_password_ref: str | None = None
    llm_default_provider_ref: str | None = None
    # Absolute, and outside the source tree. The previous relative default pointed into
    # `backend/`, a directory removed with v1, so BYOK either wrote into whatever the
    # working directory happened to be or failed outright on a read-only root filesystem.
    llm_local_secret_dir: str = "/var/lib/bda/secrets"
    external_research_sources_json: str = "{}"
    writes_enabled: bool = True
    oidc_providers_json: str = "{}"
    otel_endpoint: str | None = None
    expose_docs: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def oidc_providers(self) -> dict[str, dict[str, str]]:
        try:
            value = json.loads(self.oidc_providers_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    @property
    def external_research_sources(self) -> dict[str, dict[str, str]]:
        try:
            value = json.loads(self.external_research_sources_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    @model_validator(mode="after")
    def validate_runtime(self) -> Settings:
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("BDA v2 requires PostgreSQL; SQLite is not supported")
        if self.compute_backend not in {"docker", "lsf", "demo"}:
            raise ValueError("compute_backend must be docker, lsf, or demo")
        try:
            providers = json.loads(self.oidc_providers_json)
        except json.JSONDecodeError as exc:
            raise ValueError("oidc_providers_json must be valid JSON") from exc
        if not isinstance(providers, dict):
            raise ValueError("oidc_providers_json must be a JSON object")
        for name, value in providers.items():
            if not isinstance(value, dict) or not value.get("issuer") or not value.get("client_id"):
                raise ValueError("each OIDC provider requires issuer and client_id")
            # The callback verifies the ID token against this issuer and fetches JWKS from
            # its discovery document, so plaintext here undoes every later check.
            if not str(value["issuer"]).startswith("https://"):
                raise ValueError(f"OIDC provider {name} issuer must be an https URL")
            # Checked at startup rather than at first login: redirect_uri arrives as a
            # query parameter, and without a declared allowlist there is nothing to
            # check it against.
            if not str(value.get("redirect_uris", "")).strip():
                raise ValueError(f"OIDC provider {name} requires a comma-separated redirect_uris allowlist")
        try:
            research_sources = json.loads(self.external_research_sources_json)
        except json.JSONDecodeError as exc:
            raise ValueError("external_research_sources_json must be valid JSON") from exc
        if not isinstance(research_sources, dict):
            raise ValueError("external_research_sources_json must be a JSON object")
        if self.is_production:
            if len(self.jwt_secret) < 32 or "development" in self.jwt_secret:
                raise ValueError("production jwt_secret must be a strong secret")
            if not self.cors_origins_list or "*" in self.cors_origins_list:
                raise ValueError("production cors_origins must be an explicit allowlist")
            if self.compute_backend == "demo":
                raise ValueError("demo compute is forbidden in production")
            if self.compute_backend == "docker" and not self.docker_host.startswith(("tcp://", "https://")):
                raise ValueError("production Docker must use a dedicated remote mTLS daemon")
            if self.compute_backend == "docker" and not all(
                (self.docker_tls_ca, self.docker_tls_cert, self.docker_tls_key)
            ):
                raise ValueError("production Docker requires CA, client certificate and client key")
            if self.compute_backend == "lsf" and not (self.lsf_ssh_key_path or self.lsf_ssh_password_ref):
                raise ValueError("production LSF requires an SSH key path or a password reference")
            if self.compute_backend == "lsf" and not (self.lsf_ssh_host.strip() and self.lsf_remote_root.strip()):
                raise ValueError("production LSF requires an explicit ssh host and remote root")
            if self.lsf_ssh_password_ref and not self.lsf_ssh_password_ref.startswith("file:"):
                raise ValueError("lsf_ssh_password_ref must be a file: reference, not an inline secret")
            if len(self.minio_secret_key) < 16 or "development" in self.minio_secret_key:
                raise ValueError("production MinIO credentials are insecure")
            if not self.minio_public_endpoint:
                raise ValueError("production requires an explicit public MinIO presign endpoint")
            if not self.oidc_providers:
                raise ValueError("production requires at least one OIDC provider")
            if not self.llm_default_provider_ref:
                raise ValueError("production requires an LLM provider credential reference")
            if not self.external_research_sources:
                raise ValueError("production requires configured external research sources")
            if not self.otel_endpoint:
                raise ValueError("production requires an OTLP endpoint")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
