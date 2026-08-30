from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend_v2.app import all_models  # noqa: E402, F401
from backend_v2.app.core.models import Base  # noqa: E402
from backend_v2.app.main import app  # noqa: E402

PUBLIC_WRITE_PATHS = {"/api/v2/auth/token", "/api/v2/auth/refresh"}
WRITE_METHODS = {"post", "put", "patch", "delete"}


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "contracts/v2-flow-matrix.yaml")
    matrix = json.loads(path.read_text())
    resources = matrix.get("resources", [])
    configured_tables = [resource["table"] for resource in resources]
    model_tables = sorted(Base.metadata.tables)
    errors: list[str] = []
    if len(configured_tables) != len(set(configured_tables)):
        errors.append("flow matrix contains duplicate table entries")
    missing = sorted(set(model_tables) - set(configured_tables))
    extra = sorted(set(configured_tables) - set(model_tables))
    if missing:
        errors.append(f"tables missing from matrix: {', '.join(missing)}")
    if extra:
        errors.append(f"unknown matrix tables: {', '.join(extra)}")

    patterns = [pattern for resource in resources for pattern in resource.get("api_paths", [])]
    openapi = app.openapi()
    for route_path, methods in openapi["paths"].items():
        if not any(fnmatch.fnmatchcase(route_path, pattern) for pattern in patterns):
            errors.append(f"OpenAPI path is not mapped: {route_path}")
        for method, operation in methods.items():
            if method in WRITE_METHODS and route_path not in PUBLIC_WRITE_PATHS and not operation.get("x-permission"):
                errors.append(f"write operation lacks x-permission: {method.upper()} {route_path}")

    for resource in resources:
        if not resource.get("producers") or not resource.get("consumers"):
            errors.append(f"{resource['table']} must declare producers and consumers")
        if resource.get("visibility") == "business" and not resource.get("ui"):
            errors.append(f"business table has no UI consumer: {resource['table']}")

    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print(f"validated {len(model_tables)} tables and {len(openapi['paths'])} OpenAPI paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
