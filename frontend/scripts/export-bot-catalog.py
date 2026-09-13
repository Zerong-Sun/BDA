"""Export the actual FastAPI Bot/service responses for browser acceptance.

Run with the backend development dependencies installed. Authentication is
overridden only in this isolated app; no database, model or live service runs.
"""
import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend_v2.app.copilot.api import router  # noqa: E402
from backend_v2.app.identity.deps import current_user  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(role="researcher")
    with TestClient(app) as client:
        responses = {key: client.get(f"/api/v2/copilot/{path}") for key, path in
                     (("bots", "bots"), ("services", "task-services"))}
        for response in responses.values():
            response.raise_for_status()
        catalog = {key: response.json() for key, response in responses.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    print(f"FastAPI catalog verified: {len(catalog['bots'])} Bots, {len(catalog['services'])} services")


if __name__ == "__main__":
    main()
