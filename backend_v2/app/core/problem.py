from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .trace import current_trace_id


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    error_code: str
    trace_id: str
    errors: list[dict[str, Any]] | None = None


class DomainError(Exception):
    def __init__(
        self,
        error_code: str,
        detail: str,
        *,
        status_code: int = 400,
        errors: Sequence[Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        self.errors = list(errors) if errors else None


def _json_safe(value: Any) -> Any:
    """Coerce anything that cannot survive JSON encoding into a readable string.

    Pydantic puts the original exception object into an error's ``ctx`` whenever a
    validator raises (``ValueError("entry_type must be one of ...")``). Handing that
    straight to the encoder raises PydanticSerializationError, so a request that should
    have produced a tidy 422 blew up mid-response instead - for every endpoint whose
    schema validates with a plain ``raise ValueError``, which is most of them.

    Sanitising here rather than at each call site keeps the guarantee in one place: a
    problem+json body is always encodable, whatever a validator chose to raise.
    """
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def problem_response(
    request: Request, *, status: int, code: str, detail: str, errors: Sequence[Any] | None = None
) -> JSONResponse:
    body = Problem(
        type=f"https://bda.invalid/problems/{code}",
        title=code.replace("_", " ").title(),
        status=status,
        detail=detail,
        instance=request.url.path,
        error_code=code,
        trace_id=current_trace_id(),
        errors=[_json_safe(item) for item in errors] if errors else None,
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"), media_type="application/problem+json")


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return problem_response(
        request,
        status=exc.status_code,
        code=exc.error_code,
        detail=exc.detail,
        errors=exc.errors,
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return problem_response(request, status=exc.status_code, code="http_error", detail=str(exc.detail))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return problem_response(
        request,
        status=422,
        code="validation_error",
        detail="Request validation failed",
        errors=exc.errors(),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(request, status=500, code="internal_error", detail="Unexpected backend error")
