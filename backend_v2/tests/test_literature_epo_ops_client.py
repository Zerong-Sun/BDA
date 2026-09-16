"""The OPS client: what it records, and the answers it must not mistake for empty.

The credential is the new obligation. These tests check that it reaches the
token endpoint and nothing else - not an audit, not an error message - and
that every way OPS refuses (a rejected key, an exhausted quota, an oversized
answer) raises with a reason instead of passing as a search that found nothing.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

import httpx
import pytest
from backend_v2.app.literature.epo_ops import PublicationRef
from backend_v2.app.literature.epo_ops_client import (
    EpoOpsClient,
    EpoOpsUnavailable,
    credential_available,
    load_credential,
)

KEY, SECRET = "consumer-key-abc", "consumer-secret-xyz"
EP_GRANT = PublicationRef("EP", "1537878", "B1")


def _token(request: httpx.Request, *, token: str = "tok-1", lifetime: str = "1199") -> httpx.Response:
    return httpx.Response(200, json={"access_token": token, "expires_in": lifetime})


def _client(
    handler: Callable[[httpx.Request], httpx.Response], **kwargs
) -> tuple[EpoOpsClient, list[float]]:
    sleeps: list[float] = []
    client = EpoOpsClient(
        (KEY, SECRET),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
        **kwargs,
    )
    return client, sleeps


def test_a_search_authenticates_once_and_its_audit_holds_no_credential() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return httpx.Response(
            200,
            json={"ops:world-patent-data": {}},
            headers={"x-throttling-control": "idle (search=green:30)"},
        )

    client, _ = _client(handler)
    client.search('ta all "PD-1 antibody"', limit=10)
    result = client.search("ta=x", limit=500)

    token_requests = [request for request in seen if request.url.path.endswith("/auth/accesstoken")]
    assert len(token_requests) == 1, "a token is reused until it is about to expire"
    basic = token_requests[0].headers["Authorization"].removeprefix("Basic ")
    assert base64.b64decode(basic).decode() == f"{KEY}:{SECRET}"
    search_request = seen[-1]
    assert search_request.headers["Authorization"] == "Bearer tok-1"
    assert search_request.headers["Accept"] == "application/json"
    assert search_request.url.params["Range"] == "1-100", "OPS serves at most 100 records"

    audit = result.audit
    assert audit["tool"] == "epo_ops.search"
    assert audit["query"]["url"].endswith("/published-data/search/biblio")
    assert audit["query"]["params"] == {"q": "ta=x", "Range": "1-100"}
    assert audit["throttling"] == "idle (search=green:30)"
    assert len(audit["response_checksum_sha256"]) == 64
    recorded = json.dumps(client.audits)
    for secret in (KEY, SECRET, "tok-1", "Basic", "Bearer"):
        assert secret not in recorded


def test_no_hits_is_an_empty_answer_not_a_failure() -> None:
    """OPS answers a search that matched nothing with 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return httpx.Response(404, text="<fault><code>SERVER.EntityNotFound</code><message>No results found</message></fault>")

    client, _ = _client(handler)
    result = client.search('ta all "nothing"', limit=5)

    assert result.data == {}
    assert result.audit["status"] == "completed"
    assert result.audit["no_results"] is True
    assert result.audit["http_status"] == 404


def test_a_404_that_is_not_no_results_is_a_refusal_not_an_empty_search() -> None:
    """A broken query answered 404 must never be recorded as evidence of absence."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return httpx.Response(
            404,
            text=(
                '<fault xmlns="http://ops.epo.org"><code>CLIENT.InvalidIndex</code>'
                "<message>The query provided is invalid. Invalid index name zzz</message></fault>"
            ),
        )

    client, _ = _client(handler)
    with pytest.raises(RuntimeError) as raised:
        client.search('zzz all "pd1"', limit=5)

    assert "CLIENT.InvalidIndex" in str(raised.value)
    assert client.audits[-1]["status"] == "failed"


def test_no_results_is_recorded_as_what_ops_said() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return httpx.Response(
            404,
            text=(
                '<fault xmlns="http://ops.epo.org"><code>SERVER.EntityNotFound</code>'
                "<message>No results found</message></fault>"
            ),
        )

    client, _ = _client(handler)
    result = client.search('ta all "nothing at all"', limit=5)

    assert result.data == {}
    assert result.audit["no_results"] is True
    assert result.audit["fault"].startswith("SERVER.EntityNotFound")


def test_a_publication_ops_does_not_know_is_a_named_gap() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        paths.append(request.url.path)
        return httpx.Response(404)

    client, sleeps = _client(handler)
    with pytest.raises(RuntimeError, match="^epo_ops.family_legal_not_found$"):
        client.family_legal(EP_GRANT)

    assert paths == ["/3.2/rest-services/family/publication/docdb/EP.1537878.B1/legal"]
    assert sleeps == [], "a 404 is an answer, and asking again does not change it"
    assert client.audits[-1]["status"] == "failed"
    assert client.audits[-1]["http_status"] == 404


def test_a_revoked_token_is_renewed_once_without_spending_a_retry() -> None:
    tokens = 0
    gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tokens, gets
        if request.url.path.endswith("/auth/accesstoken"):
            tokens += 1
            return _token(request, token=f"tok-{tokens}")
        gets += 1
        if request.headers["Authorization"] == "Bearer tok-1":
            return httpx.Response(401)
        return httpx.Response(200, json={"ops:world-patent-data": {}})

    client, _ = _client(handler, max_retries=0)
    result = client.family_legal(EP_GRANT)

    assert tokens == 2 and gets == 2
    assert result.audit["attempts"] == 1


def test_a_token_is_renewed_before_it_expires() -> None:
    tokens = 0
    moments = iter([0.0, 10.0, 50.0])

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tokens
        if request.url.path.endswith("/auth/accesstoken"):
            tokens += 1
            return _token(request, lifetime="100")
        return httpx.Response(200, json={})

    client, _ = _client(handler, clock=lambda: next(moments))
    for _ in range(3):
        client.search("ta=x", limit=1)

    # 100 s less the one-minute margin is 40 s: the call at 50 s needs a new token.
    assert tokens == 2


def test_throttling_is_retried_after_a_pause() -> None:
    answers = iter([httpx.Response(429), httpx.Response(503), httpx.Response(200, json={})])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return next(answers)

    client, sleeps = _client(handler)
    result = client.search("ta=x", limit=1)

    assert result.audit["attempts"] == 3
    assert sleeps == [2.0, 4.0]


def test_a_quota_refusal_raises_with_its_reason_and_is_not_retried() -> None:
    gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal gets
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        gets += 1
        return httpx.Response(403, headers={"x-rejection-reason": "IndividualQuotaPerHour"})

    client, sleeps = _client(handler)
    with pytest.raises(RuntimeError, match="^epo_ops.search_refused: IndividualQuotaPerHour$"):
        client.search("ta=x", limit=1)

    assert gets == 1 and sleeps == []
    assert client.audits[-1]["rejection_reason"] == "IndividualQuotaPerHour"


@pytest.mark.parametrize(
    ("status", "error", "exception"),
    [
        (401, "epo_ops_credential_rejected", EpoOpsUnavailable),
        (500, "epo_ops_authentication_failed", RuntimeError),
    ],
)
def test_a_token_that_cannot_be_had_raises_and_is_audited(status: int, error: str, exception: type) -> None:
    gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal gets
        if request.url.path.endswith("/auth/accesstoken"):
            return httpx.Response(status, json={"error": "invalid_client"})
        gets += 1
        return httpx.Response(200, json={})

    client, _ = _client(handler)
    with pytest.raises(exception, match=f"^{error}$"):
        client.search("ta=x", limit=1)

    assert gets == 0
    assert client.audits[-1]["status"] == "failed" and client.audits[-1]["error"] == error


def test_an_unreachable_token_endpoint_raises_and_is_audited() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    client, _ = _client(handler)
    with pytest.raises(RuntimeError, match="^epo_ops_authentication_unreachable$"):
        client.family_legal(EP_GRANT)

    assert client.audits[-1]["error"] == "epo_ops_authentication_unreachable"


@pytest.mark.parametrize(
    "response",
    [httpx.Response(200, content=b"x" * 64), httpx.Response(200, json=["not", "an", "object"])],
)
def test_an_answer_that_cannot_be_evidence_is_refused_without_retrying(response: httpx.Response) -> None:
    gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal gets
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        gets += 1
        return response

    client, _ = _client(handler, max_bytes=32)
    with pytest.raises(RuntimeError, match="^epo_ops.search_failed$"):
        client.search("ta=x", limit=1)

    assert gets == 1


def test_the_call_budget_is_enforced() -> None:
    client, _ = _client(lambda request: _token(request) if "auth" in request.url.path else httpx.Response(200, json={}), max_calls=1)
    client.search("ta=x", limit=1)

    with pytest.raises(RuntimeError, match="evidence_tool_call_limit_reached"):
        client.search("ta=x", limit=1)


def test_only_a_client_it_created_is_closed(monkeypatch) -> None:
    closed: list[bool] = []
    borrowed = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    monkeypatch.setattr(borrowed, "close", lambda: closed.append(True))

    EpoOpsClient((KEY, SECRET), client=borrowed).close()
    assert closed == []

    monkeypatch.setattr("backend_v2.app.literature.epo_ops_client.httpx.Client", lambda **_kwargs: borrowed)
    owner = EpoOpsClient((KEY, SECRET))
    owner.close()
    owner.close()
    assert closed == [True]


def test_a_credential_file_holds_the_key_and_secret_in_either_layout(tmp_path, monkeypatch) -> None:
    one_line = tmp_path / "one"
    one_line.write_text(f"{KEY}:{SECRET}\n")
    two_lines = tmp_path / "two"
    two_lines.write_text(f"{KEY}\n{SECRET}\n")
    monkeypatch.setenv("BDA_TEST_OPS", f"{KEY}:{SECRET}")

    assert load_credential(f"file:{one_line}") == (KEY, SECRET)
    assert load_credential(f"file:{two_lines}") == (KEY, SECRET)
    assert load_credential("env:BDA_TEST_OPS") == (KEY, SECRET)
    assert credential_available(f"file:{one_line}") is True


@pytest.mark.parametrize(
    ("reference", "error"),
    [
        (None, "epo_ops_not_configured"),
        ("", "epo_ops_not_configured"),
        (f"{KEY}:{SECRET}", "epo_ops_credential_ref_invalid"),
        ("file:/nonexistent/bda-epo-ops", "epo_ops_credential_unreadable"),
        ("env:BDA_TEST_OPS_UNSET", "epo_ops_credential_malformed"),
        ("malformed", "epo_ops_credential_ref_invalid"),
    ],
)
def test_a_credential_that_cannot_be_used_is_named_and_never_echoed(reference: str | None, error: str) -> None:
    with pytest.raises(EpoOpsUnavailable) as raised:
        load_credential(reference)

    assert str(raised.value) == error
    assert SECRET not in str(raised.value)
    assert credential_available(reference) is False


def test_a_malformed_credential_file_is_refused_without_quoting_it(tmp_path) -> None:
    path = tmp_path / "bad"
    path.write_text(f"{SECRET}\n")

    with pytest.raises(EpoOpsUnavailable, match="^epo_ops_credential_malformed$"):
        load_credential(f"file:{path}")


# The body OPS actually returns for invalid CQL (fetched 2026-09-16).
CQL_FAULT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<fault xmlns="http://ops.epo.org">    <code>CLIENT.CQLSyntax</code>'
    "    <message>The query provided is invalid. CQL expression has invalid syntax. "
    "any/all/within values should be quoted. Position 0-0</message> </fault>"
)


def test_a_refusal_carries_the_reason_ops_gave_for_it() -> None:
    """Without the fault body a failed run says only that a request failed."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return httpx.Response(400, text=CQL_FAULT, headers={"content-type": "application/xml"})

    client, sleeps = _client(handler)
    with pytest.raises(RuntimeError) as raised:
        client.search("ta all antibody", limit=5)

    assert "CLIENT.CQLSyntax" in str(raised.value)
    assert "should be quoted" in str(raised.value)
    assert sleeps == [], "a rejected query is rejected again; retrying only spends the quota"
    assert client.audits[-1]["fault"].startswith("CLIENT.CQLSyntax:")


def test_a_body_without_a_fault_leaves_the_error_unadorned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return _token(request)
        return httpx.Response(400, text="<html>gateway</html>")

    client, _ = _client(handler)
    with pytest.raises(RuntimeError, match="^epo_ops.search_failed$"):
        client.search("ta=x", limit=1)

    assert client.audits[-1]["fault"] is None


def test_unexplained_search_404_is_not_evidence_of_no_results():
    def handler(request):
        if request.url.path.endswith('/auth/accesstoken'):
            return _token(request)
        return httpx.Response(404, text='<fault>Unknown</fault>')
    client, _ = _client(handler)
    with pytest.raises(RuntimeError, match='not_found'):
        client.search('ta all "example"', limit=5)
    assert client.audits[-1].get('no_results') is not True
