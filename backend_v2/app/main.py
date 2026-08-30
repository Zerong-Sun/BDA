from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core.config import get_settings
from .core.metrics import MetricsMiddleware
from .core.problem import (
    DomainError,
    Problem,
    domain_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from .core.telemetry import configure_telemetry
from .core.trace import TraceMiddleware
from .module_registry import routers

settings = get_settings()
configure_telemetry(settings.otel_endpoint)
problem_response = {
    "description": "RFC 9457 Problem Details",
    "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
}
app = FastAPI(
    title="BDA API v2",
    version="2.0.0",
    docs_url="/api/v2/docs" if settings.expose_docs and not settings.is_production else None,
    openapi_url="/api/v2/openapi.json" if settings.expose_docs and not settings.is_production else None,
    responses={code: problem_response for code in (400, 401, 403, 404, 409, 422, 500)},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-Match", "Traceparent", "X-Trace-Id"],
)
app.add_middleware(TraceMiddleware)
app.add_middleware(MetricsMiddleware)


@app.middleware("http")
async def production_write_gate(request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/v2"):
        if not settings.writes_enabled and request.url.path not in {"/api/v2/auth/token", "/api/v2/auth/refresh"}:
            return await domain_error_handler(
                request,
                DomainError(
                    "writes_disabled",
                    "BDA v2 writes are disabled for cutover validation",
                    status_code=503,
                ),
            )
    return await call_next(request)


app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_error_handler)

api = APIRouter(prefix="/api/v2")
for router in routers():
    api.include_router(router)
app.include_router(api)
app.mount("/internal/metrics", make_asgi_app())
