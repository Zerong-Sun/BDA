from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

import structlog
from opentelemetry import trace
from opentelemetry.propagate import extract
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_trace_id: ContextVar[str] = ContextVar("bda_v2_trace_id", default="")
_traceparent = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-(0[01])$")
logger = structlog.get_logger()
tracer = trace.get_tracer("bda-backend-v2.http")


def current_trace_id() -> str:
    value = _trace_id.get()
    return value or uuid.uuid4().hex


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get("traceparent", "")
        match = _traceparent.match(inbound)
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}", context=extract(dict(request.headers))
        ) as span:
            span_context = span.get_span_context()
            trace_id = (
                f"{span_context.trace_id:032x}"
                if span_context.is_valid
                else match.group(1)
                if match
                else request.headers.get("x-trace-id") or uuid.uuid4().hex
            )
            span_id = f"{span_context.span_id:016x}" if span_context.is_valid else uuid.uuid4().hex[:16]
            token = _trace_id.set(trace_id)
            request.state.trace_id = trace_id
            try:
                response = await call_next(request)
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("http.response.status_code", response.status_code)
                response.headers["X-Trace-Id"] = trace_id
                response.headers["traceparent"] = f"00-{trace_id}-{span_id}-01"
                logger.info(
                    "http_request",
                    method=request.method,
                    path=request.url.path,
                    status=response.status_code,
                    trace_id=trace_id,
                )
                return response
            finally:
                _trace_id.reset(token)
