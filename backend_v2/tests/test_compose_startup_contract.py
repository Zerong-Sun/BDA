from pathlib import Path

import yaml

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
    for service_name in ("worker-v2", "research-worker-v2", "copilot-worker-v2"):
        service = services[service_name]
        assert service["depends_on"]["api-v2"]["condition"] == "service_healthy"
        worker_queues.update(service["environment"]["BDA_V2_WORKER_QUEUES"].split(","))

    assert worker_queues == required_queues
