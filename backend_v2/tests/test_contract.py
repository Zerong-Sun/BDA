import ast
import re
from pathlib import Path

from backend_v2.app.main import app
from fastapi.testclient import TestClient

PUBLIC_WRITES = {
    ("/api/v2/auth/token", "post"),
    ("/api/v2/auth/refresh", "post"),
}


def test_api_modules_do_not_access_sqlalchemy_sessions_directly() -> None:
    forbidden_methods = {
        "add",
        "add_all",
        "delete",
        "execute",
        "flush",
        "get",
        "merge",
        "query",
        "scalar",
        "scalars",
    }
    forbidden_sql_names = {"delete", "insert", "select", "text", "update"}
    violations: list[str] = []
    app_root = Path(__file__).parents[1] / "app"
    for path in sorted(app_root.glob("*/api.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy":
                names = forbidden_sql_names & {alias.name for alias in node.names}
                if names:
                    violations.append(f"{path}:{node.lineno} imports {sorted(names)}")
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (
                isinstance(owner, ast.Name)
                and "session" in owner.id
                and node.func.attr in forbidden_methods
            ):
                violations.append(f"{path}:{node.lineno} calls {owner.id}.{node.func.attr}()")
    assert not violations, "API routes must use services/repositories:\n" + "\n".join(violations)


def test_sse_routes_release_the_request_database_session() -> None:
    app_root = Path(__file__).parents[1] / "app"
    for relative_path, route_name in (
        ("compute/api.py", "job_events"),
        ("copilot/api.py", "stream_messages"),
        ("platform/api.py", "operation_events"),
    ):
        tree = ast.parse((app_root / relative_path).read_text())
        route = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == route_name
        )
        defaults = [ast.unparse(default) for default in route.args.defaults]
        assert "Depends(streaming_user)" in defaults, (
            f"{relative_path}:{route_name} must authenticate with streaming_user so the "
            "request UoW closes before EventSourceResponse starts"
        )


def test_every_command_route_declares_permission_metadata() -> None:
    schema = app.openapi()
    for path, path_item in schema["paths"].items():
        for method in {"post", "put", "patch", "delete"} & path_item.keys():
            if (path, method) not in PUBLIC_WRITES:
                assert path_item[method].get("x-permission"), f"{method.upper()} {path} has no permission policy"


def test_operation_ids_are_unique_and_stable() -> None:
    schema = app.openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert all(operation_id and " " not in operation_id for operation_id in operation_ids)


def test_routes_declare_success_and_problem_schemas() -> None:
    schema = app.openapi()
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if path.endswith("/events"):
                continue
            success = [item for code, item in operation["responses"].items() if code.startswith("2")]
            assert success, f"{method.upper()} {path} has no success response"
            assert any("schema" in media for item in success for media in item.get("content", {}).values())
            problem = operation["responses"]["422"]["content"]
            assert "application/problem+json" in problem


def test_problem_details_and_w3c_trace_headers() -> None:
    client = TestClient(app)
    response = client.get("/api/v2/not-a-route")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == "http_error"
    assert re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-01", response.headers["traceparent"])
