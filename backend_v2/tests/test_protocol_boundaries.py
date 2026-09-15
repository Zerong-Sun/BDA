from __future__ import annotations

import math

import pytest
from backend_v2.app.core.etag import parse_if_match
from backend_v2.app.core.problem import DomainError, problem_response
from starlette.requests import Request


@pytest.mark.parametrize('value', ['W/1', 'WW//"1"', '"1', '1"', 'W/"-1"', 'W/"+1"', 'W/"١"'])
def test_if_match_rejects_malformed_resource_versions(value: str) -> None:
    with pytest.raises(DomainError) as caught:
        parse_if_match(value)
    assert caught.value.status_code == 422


@pytest.mark.parametrize('value', ['W/"1"', '"1"', ' \tW/"1"\t '])
def test_if_match_accepts_a_single_quoted_version(value: str) -> None:
    assert parse_if_match(value) == 1


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
def test_validation_problem_handles_nonfinite_input(value: float) -> None:
    response = problem_response(
        Request({'type': 'http', 'path': '/api/v2/test', 'headers': []}),
        status=422, code='validation_error', detail='Invalid input',
        errors=[{'input': value, 'ctx': {'value': value}}],
    )
    assert response.status_code == 422
    assert b'"input":"' in response.body
