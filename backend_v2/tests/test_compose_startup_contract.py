import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory
from backend_v2.app.core.config import Settings
from backend_v2.scripts.run_scheduler_worker import WORKER_COMMAND

COMPOSE_PATH = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _services() -> dict:
    document = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    return document["services"]


def test_api_container_health_uses_liveness_to_avoid_worker_startup_cycle() -> None:
    services = _services()
    health_command = " ".join(services["api-v2"]["healthcheck"]["test"])

    assert "/api/v2/health/live" in health_command
    assert "/api/v2/health/ready" not in health_command

    # Readiness requires these queues, while each worker waits for API container
    # health. The API health dependency must therefore stay weaker than readiness.
    required_queues = set(
        services["api-v2"]["environment"]["BDA_V2_REQUIRED_WORKER_QUEUES"].split(",")
    )
    worker_queues: set[str] = set()
    for service_name in ("worker-v2", "research-worker-v2", "copilot-worker-v2", "scheduler-worker-v2"):
        service = services[service_name]
        assert service["depends_on"]["api-v2"]["condition"] == "service_healthy"
        worker_queues.update(service["environment"]["BDA_V2_WORKER_QUEUES"].split(","))

    assert worker_queues == required_queues


def test_scheduler_is_required_and_has_an_isolated_database_login() -> None:
    services = _services()
    scheduler = services["scheduler-worker-v2"]
    assert "scheduler" in services["api-v2"]["environment"]["BDA_V2_REQUIRED_WORKER_QUEUES"].split(",")
    assert scheduler["environment"]["BDA_V2_WORKER_QUEUES"] == "scheduler"
    assert scheduler["command"] == "python -m backend_v2.scripts.run_scheduler_worker"
    assert WORKER_COMMAND[WORKER_COMMAND.index("-Q") + 1] == "scheduler"
    assert "--concurrency=1" in WORKER_COMMAND
    assert "--prefetch-multiplier=1" in WORKER_COMMAND
    assert "BDA_V2_DATABASE_URL" not in scheduler["environment"]
    assert scheduler["env_file"] == [".env", "${BDA_V2_SCHEDULER_ENV_FILE:-./secrets/scheduler.env}"]
    for name in ("api-v2", "worker-v2", "research-worker-v2", "copilot-worker-v2", "beat-v2"):
        assert "SCHEDULER_DATABASE_URL" not in services[name]["environment"]["BDA_V2_DATABASE_URL"]
        assert services[name]["environment"]["BDA_V2_SCHEDULER_DATABASE_URL"] == ""


def test_rendered_compose_does_not_expose_scheduler_credentials_to_other_services(tmp_path):
    compose = shutil.which("docker-compose")
    if not compose:
        pytest.skip("Standalone Compose CLI is not installed")
    (tmp_path / "compose.yml").write_text(COMPOSE_PATH.read_text())
    (tmp_path / ".env").write_text(
        "BDA_V2_POSTGRES_PASSWORD=test\nBDA_V2_REDIS_PASSWORD=test\n"
        "BDA_V2_MINIO_ACCESS_KEY=test\nBDA_V2_MINIO_SECRET_KEY=test\n"
        "BDA_V2_SCHEDULER_DATABASE_URL=legacy-secret-must-be-masked\n"
    )
    (tmp_path / "secrets").mkdir()
    secret = "postgresql+psycopg://bda_scheduler:scheduler-only-secret@postgres-v2:5432/bda_v2"
    (tmp_path / "secrets/scheduler.env").write_text(f"BDA_V2_DATABASE_URL={secret}\n")
    result = subprocess.run([compose, "-f", str(tmp_path / "compose.yml"), "config", "--format", "json"],
                            check=True, capture_output=True, text=True, cwd=tmp_path)
    services = json.loads(result.stdout)["services"]
    assert services["scheduler-worker-v2"]["environment"]["BDA_V2_DATABASE_URL"] == secret
    for name, config in services.items():
        if name != "scheduler-worker-v2":
            assert "scheduler-only-secret" not in json.dumps(config)
            assert "legacy-secret-must-be-masked" not in json.dumps(config)


def test_runtime_schema_declarations_match_the_migration_head() -> None:
    root = COMPOSE_PATH.parent
    config = Config()
    config.set_main_option("script_location", str(root / "backend_v2/alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert Settings.model_fields["schema_revision"].default == head
    for name, service in _services().items():
        environment = service.get("environment", {})
        if "BDA_V2_SCHEMA_REVISION" in environment:
            assert environment["BDA_V2_SCHEMA_REVISION"] == head, name
    helm = (root / "backend_v2/helm/templates/configmap.yaml").read_text()
    revisions = re.findall(r'BDA_V2_SCHEMA_REVISION: "(\w+)"', helm)
    assert revisions == [head]
    for name in ("backend_v2/Dockerfile", ".github/workflows/ci.yml", ".github/workflows/staging.yml"):
        revisions = re.findall(r"BDA_SCHEMA_REVISION=(\w+)", (root / name).read_text())
        assert revisions and set(revisions) == {head}, name
