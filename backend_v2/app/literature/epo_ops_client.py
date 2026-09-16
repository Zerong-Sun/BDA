"""The one place BDA talks to EPO Open Patent Services, and what it records when it does.

OPS is the first evidence source here that needs a credential, which adds two
obligations the keyless sources never had:

* **The credential never reaches a record.** It is read from a ``file:``
  reference at the moment a token is needed. An audit keeps the URL and the
  query parameters - what was asked - and never a header, so a retrieval trace
  can be shown to anyone who can see the project.
* **A refused credential is not an empty answer.** OPS answers an unauthorised
  or over-quota request with 4xx; read as "no results" that would become a
  search that found nothing, which is exactly the misreading the policy on
  absence exists to prevent. Refusal raises, and the run records why.

The audits have the shape `research.evidence_tools` produces, so the literature
task writes OPS traces through the code it already uses for Europe PMC.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from ..research.evidence_tools import EvidenceToolResult
from .epo_ops import BASE_URL, MAX_SEARCH_RANGE, PublicationRef

#: A 65-member family with legal events is about 0.9 MB. Anything past this is
#: not a response a lookup should hold in memory and archive.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class EpoOpsUnavailable(RuntimeError):
    """OPS cannot be used: no credential, an unreadable one, or one it refused.

    A `RuntimeError`, so every caller that already records a failed evidence
    call records this one too - with a reason that names the credential and
    never contains it.
    """


def load_credential(reference: str | None) -> tuple[str, str]:
    """The consumer key and secret behind a ``file:`` (or, in development, ``env:``) reference."""
    if not reference:
        raise EpoOpsUnavailable("epo_ops_not_configured")
    if reference.startswith("file:"):
        try:
            value = Path(reference.removeprefix("file:")).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise EpoOpsUnavailable("epo_ops_credential_unreadable") from exc
    elif reference.startswith("env:"):
        value = os.getenv(reference.removeprefix("env:")) or ""
    else:
        raise EpoOpsUnavailable("epo_ops_credential_ref_invalid")
    # `key:secret` on one line, or the key and the secret on two.
    parts = [part.strip() for part in value.replace("\n", ":").split(":") if part.strip()]
    if len(parts) != 2:
        raise EpoOpsUnavailable("epo_ops_credential_malformed")
    return parts[0], parts[1]


def credential_available(reference: str | None) -> bool:
    try:
        load_credential(reference)
    except EpoOpsUnavailable:
        return False
    return True


class EpoOpsClient:
    """Bounded, audited, read-only calls to the OPS endpoints BDA uses."""

    def __init__(
        self,
        credential: tuple[str, str],
        *,
        client: httpx.Client | None = None,
        max_calls: int = 60,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        max_bytes: int = MAX_RESPONSE_BYTES,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._key, self._secret = credential
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": "BDA-Research/2.0 (controlled evidence verification)"},
        )
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.max_bytes = max_bytes
        self._sleep = sleep
        self._clock = clock
        self._token: str | None = None
        self._token_expires_at = 0.0
        self.calls = 0
        self.audits: list[dict[str, Any]] = []

    def close(self) -> None:
        if self._owns_client:
            self.client.close()
            self._owns_client = False

    def search(self, cql: str, *, limit: int) -> EvidenceToolResult:
        """Bibliographic search. No hits is an answer, not a failure: OPS says it with a 404."""
        size = max(1, min(limit, MAX_SEARCH_RANGE))
        return self._get(
            "epo_ops.search",
            f"{BASE_URL}/rest-services/published-data/search/biblio",
            params={"q": cql, "Range": f"1-{size}"},
            not_found_is_empty=True,
        )

    def family_legal(self, publication: PublicationRef) -> EvidenceToolResult:
        """The DOCDB family of a publication, with INPADOC legal events on each member."""
        return self._get(
            "epo_ops.family_legal",
            f"{BASE_URL}/rest-services/family/publication/docdb/{quote(publication.docdb, safe='.')}/legal",
            params={},
        )

    def claims(self, publication: PublicationRef) -> EvidenceToolResult:
        """Retrieve the publication's literal claims, never a legal interpretation."""
        return self._get(
            "epo_ops.claims",
            f"{BASE_URL}/rest-services/published-data/publication/docdb/{quote(publication.docdb, safe='.')}/claims",
            params={},
            xml=True,
        )

    def _access_token(self) -> str:
        now = self._clock()
        if self._token and now < self._token_expires_at:
            return self._token
        basic = base64.b64encode(f"{self._key}:{self._secret}".encode()).decode()
        try:
            response = self.client.post(
                f"{BASE_URL}/auth/accesstoken",
                headers={"Authorization": f"Basic {basic}"},
                data={"grant_type": "client_credentials"},
            )
        except httpx.HTTPError as exc:
            raise RuntimeError("epo_ops_authentication_unreachable") from exc
        if response.status_code in {400, 401, 403}:
            raise EpoOpsUnavailable("epo_ops_credential_rejected")
        try:
            response.raise_for_status()
            payload = response.json()
            token = str(payload["access_token"])
            lifetime = int(payload.get("expires_in") or 0)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("epo_ops_authentication_failed") from exc
        self._token = token
        # Renew a minute early, so a token never expires between check and use.
        self._token_expires_at = now + max(lifetime - 60, 30)
        return token

    def _get(
        self,
        tool: str,
        url: str,
        *,
        params: dict[str, Any],
        not_found_is_empty: bool = False,
        xml: bool = False,
    ) -> EvidenceToolResult:
        if self.calls >= self.max_calls:
            raise RuntimeError("evidence_tool_call_limit_reached")
        self.calls += 1
        started_at = datetime.now(UTC)
        query = {"url": url, "params": params}
        last_error: Exception | None = None
        last_status: int | None = None
        throttling: str | None = None
        rejection: str | None = None
        reauthenticated = False
        attempts = 0
        while attempts <= self.max_retries:
            attempts += 1
            try:
                token = self._access_token()
                response = self.client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/fulltext+xml" if xml else "application/json"},
                )
                throttling = response.headers.get("x-throttling-control") or throttling
                last_status = response.status_code
                if response.status_code == 401 and not reauthenticated:
                    # A token revoked early. One fresh token, not counted as a retry.
                    reauthenticated = True
                    self._token = None
                    attempts -= 1
                    continue
                if response.status_code == 404 and not_found_is_empty:
                    audit = self._audit(tool, query, started_at, attempts, response, throttling)
                    audit["no_results"] = True
                    return EvidenceToolResult(data={}, audit=audit)
                response.raise_for_status()
                if len(response.content) > self.max_bytes:
                    raise ValueError("evidence_tool_response_too_large")
                payload = {"xml": response.text} if xml else response.json()
                if not isinstance(payload, dict):
                    raise ValueError("evidence_tool_response_not_object")
                return EvidenceToolResult(
                    data=payload,
                    audit=self._audit(tool, query, started_at, attempts, response, throttling),
                )
            except RuntimeError as exc:
                # No token: a refused or unreachable credential endpoint. Recorded, then raised.
                self.audits.append(self._failure(tool, query, started_at, attempts, str(exc), None, None, None))
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if isinstance(exc, httpx.HTTPStatusError):
                    # OPS names why it refused (quota, blocked) in this header.
                    rejection = exc.response.headers.get("x-rejection-reason") or rejection
                if status is not None and status not in {429, 503} and status < 500:
                    break
                if isinstance(exc, ValueError):
                    break
                if attempts <= self.max_retries:
                    # OPS throttles per minute; retrying at once only spends the quota.
                    self._sleep(min(2.0 * 2 ** (attempts - 1), 20.0))
        error = str(last_error)[:500] if last_error else "epo_ops_unauthorized"
        self.audits.append(self._failure(tool, query, started_at, attempts, error, last_status, throttling, rejection))
        if last_status == 404:
            raise RuntimeError(f"{tool}_not_found") from last_error
        if last_status in {401, 403}:
            raise RuntimeError(f"{tool}_refused{': ' + rejection if rejection else ''}") from last_error
        raise RuntimeError(f"{tool}_failed") from last_error

    def _audit(
        self,
        tool: str,
        query: dict[str, Any],
        started_at: datetime,
        attempts: int,
        response: httpx.Response,
        throttling: str | None,
    ) -> dict[str, Any]:
        audit = {
            "tool": tool,
            "query": query,
            "queried_at": started_at.isoformat(),
            "response_checksum_sha256": hashlib.sha256(response.content).hexdigest(),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "byte_count": len(response.content),
            "attempts": attempts,
            "status": "completed",
            "throttling": throttling,
        }
        self.audits.append(audit)
        return audit

    @staticmethod
    def _failure(
        tool: str,
        query: dict[str, Any],
        started_at: datetime,
        attempts: int,
        error: str,
        http_status: int | None,
        throttling: str | None,
        rejection: str | None,
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "query": query,
            "queried_at": started_at.isoformat(),
            "attempts": attempts,
            "status": "failed",
            "error": error,
            "http_status": http_status,
            "throttling": throttling,
            "rejection_reason": rejection,
        }
