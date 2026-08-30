from __future__ import annotations

from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

HTTP_REQUESTS = Counter(
    "bda_v2_http_requests_total",
    "HTTP requests processed by the v2 API",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "bda_v2_http_request_duration_seconds",
    "HTTP request duration for the v2 API",
    ("method", "route"),
)
OUTBOX_BACKLOG = Gauge("bda_v2_outbox_backlog", "Unpublished transactional outbox events still being retried")
OUTBOX_DEAD_LETTERED = Gauge(
    "bda_v2_outbox_dead_lettered",
    "Outbox events that exhausted their delivery attempts and need an operator",
)
DATABASE_POOL_CHECKED_OUT = Gauge(
    "bda_v2_database_pool_checked_out",
    "Database connections currently checked out of the API pool",
)
DATABASE_POOL_SIZE = Gauge("bda_v2_database_pool_size", "Configured SQLAlchemy database pool size")
DATABASE_POOL_OVERFLOW = Gauge(
    "bda_v2_database_pool_overflow",
    "Current SQLAlchemy database pool overflow connections",
)
COPILOT_CITATION_COVERAGE = Histogram(
    "bda_v2_copilot_citation_coverage_ratio",
    "Share of a Copilot answer covered by structured workspace citations",
    buckets=(0, 0.25, 0.5, 0.75, 1.0),
)
COPILOT_UNSUPPORTED_CLAIMS = Counter(
    "bda_v2_copilot_unsupported_claims_total",
    "Copilot turns that could not be supported by retrieved evidence",
)
RESEARCH_TOOL_FAILURES = Counter(
    "bda_v2_research_tool_failures_total",
    "Controlled research evidence tool failures",
    ("tool",),
)
RESEARCH_DRAFT_VALIDATIONS = Counter(
    "bda_v2_research_draft_validations_total",
    "Research Draft v2 validation outcomes",
    ("result",),
)
RESEARCH_IMPORT_ACCEPTANCE = Counter(
    "bda_v2_research_import_acceptance_total",
    "Research Draft v2 import outcomes",
    ("result",),
)


def update_database_pool_capacity_metrics(pool: object) -> None:
    for metric, method_name in (
        (DATABASE_POOL_SIZE, "size"),
        (DATABASE_POOL_OVERFLOW, "overflow"),
    ):
        method = getattr(pool, method_name, None)
        if callable(method):
            # QueuePool reports negative overflow while its fixed-size pool is
            # still warming up.  For operations this metric means active
            # overflow connections, so expose the useful non-negative value.
            metric.set(max(0, method()))


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, route_path).observe(perf_counter() - started)
        return response
