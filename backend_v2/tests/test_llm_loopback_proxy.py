"""Only a deployment-owned local proxy can carry approved model requests."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from backend_v2.app.copilot import provider
from backend_v2.app.core.config import Settings


@pytest.mark.parametrize('url', ['http://127.0.0.1:1082', 'http://[::1]:1082', 'https://127.0.0.1:8443'])
def test_operator_can_select_a_literal_loopback_proxy(url):
    assert Settings(llm_loopback_proxy_url=url).llm_loopback_proxy_url == url


@pytest.mark.parametrize('url', [
    'http://proxy.example:1082', 'http://192.168.1.2:1082', 'http://localhost:1082',
    'http://127.0.0.1', 'http://127.0.0.1:0', 'http://127.0.0.1:65536',
    'http://user:password@127.0.0.1:1082', 'http://127.0.0.1:1082/path',
    'http://127.0.0.1:1082?target=example.com', 'http://127.0.0.1:1082#fragment',
    'socks5://127.0.0.1:1082', 'http://127.0.0.1:1082\n',
])
def test_nonlocal_or_ambiguous_proxy_is_rejected(url):
    with pytest.raises(ValueError, match='LLM proxy must'):
        Settings(llm_loopback_proxy_url=url)


@pytest.mark.parametrize('proxy_url', [None, 'http://127.0.0.1:1082'])
def test_transport_preserves_tls_redirect_and_environment_boundaries(monkeypatch, proxy_url):
    captured = {}
    original = httpx.AsyncClient
    monkeypatch.setenv('HTTPS_PROXY', 'http://untrusted.invalid:8080')
    monkeypatch.setattr(provider, 'get_settings', lambda: SimpleNamespace(llm_loopback_proxy_url=proxy_url))

    def client(**kwargs):
        captured.update(kwargs)
        kwargs.pop('proxy')  # No network: inspect configuration, then exercise redirect handling.
        return original(transport=httpx.MockTransport(lambda request: httpx.Response(
            307, headers={'location': 'https://unapproved.invalid/collect'}, request=request,
        )), **kwargs)

    monkeypatch.setattr(provider.httpx, 'AsyncClient', client)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(provider._completion_response('https://approved.invalid/chat/completions', 'test-only', {}))
    assert captured == {'proxy': proxy_url, 'trust_env': False, 'follow_redirects': False, 'verify': True}


def test_proxy_does_not_authorize_an_unapproved_model_origin(monkeypatch):
    from backend_v2.app.copilot import endpoint_policy
    from backend_v2.app.core.problem import DomainError

    settings = Settings(llm_loopback_proxy_url='http://127.0.0.1:1082',
                        llm_allowed_endpoint_origins='https://approved.invalid')
    monkeypatch.setattr(endpoint_policy, 'get_settings', lambda: settings)
    monkeypatch.setattr(provider, 'get_settings', lambda: settings)
    monkeypatch.setattr(provider, 'credential_value', lambda _: pytest.fail('Must reject before reading credentials'))
    monkeypatch.setattr(provider.httpx, 'AsyncClient', lambda **_: pytest.fail('Must reject before opening transport'))
    unapproved = SimpleNamespace(endpoint='https://unapproved.invalid', model='test', config={}, credential_ref='env:TEST')
    with pytest.raises(DomainError, match='origin must be approved'):
        provider.complete(unapproved, [{'role': 'user', 'content': 'synthetic check'}])
