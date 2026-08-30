from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from starlette.exceptions import HTTPException as StarletteHTTPException

from .artifacts.api import router as artifacts_router
from .audit.api import router as audit_router
from .campaigns.api import router as campaigns_router
from .candidates.api import router as candidates_router
from .compute.api import router as compute_router
from .copilot.api import router as copilot_router
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
from .delivery.api import router as delivery_router
from .experiments.api import router as experiments_router
from .identity.api import router as identity_router
from .identity.organizations_api import router as organizations_router
from .intelligence.api import router as intelligence_router
from .knowledge.api import router as knowledge_router
from .ligands.api import router as ligands_router
from .literature.api import router as literature_router
from .platform.api import router as platform_router
from .projects.api import router as projects_router
from .registry.api import router as registry_router
from .research.api import router as research_router
from .targets.api import router as targets_router
from .timeline.api import router as timeline_router
from .wetlab.api import router as wetlab_router
from .workflows.api import router as workflows_router

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
            raise DomainError("writes_disabled", "BDA v2 writes are disabled for cutover validation", status_code=503)
    return await call_next(request)


app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_error_handler)

api = APIRouter(prefix="/api/v2")
for router in (
    identity_router,
    organizations_router,
    projects_router,
    targets_router,
    workflows_router,
    compute_router,
    candidates_router,
    campaigns_router,
    delivery_router,
    artifacts_router,
    audit_router,
    experiments_router,
    knowledge_router,
    literature_router,
    intelligence_router,
    registry_router,
    research_router,
    timeline_router,
    copilot_router,
    ligands_router,
    platform_router,
    wetlab_router,
):
    api.include_router(router)
app.include_router(api)
app.mount("/internal/metrics", make_asgi_app())
