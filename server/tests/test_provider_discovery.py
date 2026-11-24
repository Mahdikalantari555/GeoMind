"""Discovery contract with synthetic upstream responses; no API credentials required."""
import asyncio
import os
from types import SimpleNamespace

import httpx
import pytest

from geofront_api.errors import GeoFrontError
from geofront_api.routers import providers


def setup_workspace(monkeypatch, offline=False):
    ws = SimpleNamespace(settings=SimpleNamespace(offline=offline))
    monkeypatch.setattr(providers, 'get_state', lambda: SimpleNamespace(require_workspace=lambda: ws))


@pytest.mark.parametrize('status,payload,expected', [
    (200, {'data': [{'id': 'b'}, {'id': 'a'}, {'id': 'a'}]}, ['a', 'b']),
    (200, {'data': []}, []), (401, {}, 'provider_status'),
    (429, {}, 'provider_status'), (200, {'models': []}, 'provider_unavailable'),
])
def test_discovery(monkeypatch, status, payload, expected):
    setup_workspace(monkeypatch)
    monkeypatch.setenv('GEOMEMORY_OPENAI_API_KEY', 'synthetic-only')
    def upstream(request):
        assert str(request.url) == 'https://api.openai.com/v1/models'
        assert request.headers['Authorization'] == 'Bearer synthetic-only'
        return httpx.Response(status, json=payload)
    client = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(upstream), **kw))
    if isinstance(expected, list):
        assert asyncio.run(providers.discover('OpenAI')) == expected
    else:
        with pytest.raises(GeoFrontError) as exc:
            asyncio.run(providers.discover('OpenAI'))
        assert exc.value.code == expected
        assert 'synthetic-only' not in exc.value.message


def test_discovery_accepts_session_key_without_persisting_it(monkeypatch):
    """A key typed in the UI is used for this call only (Studio 'Fetch models')."""
    setup_workspace(monkeypatch)
    monkeypatch.delenv('GEOMEMORY_OPENAI_API_KEY', raising=False)
    seen = {}

    def upstream(request):
        seen['auth'] = request.headers.get('Authorization')
        return httpx.Response(200, json={'data': [{'id': 'session-model'}]})

    client = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, 'AsyncClient',
                        lambda **kw: client(transport=httpx.MockTransport(upstream), **kw))

    # Without a key the guard fires (existing behavior preserved).
    with pytest.raises(GeoFrontError) as exc:
        asyncio.run(providers.discover('OpenAI'))
    assert exc.value.code == 'provider_key_missing'

    # The session key authorizes the very next call and is never written to env.
    assert asyncio.run(providers.discover('OpenAI', 'session-only-key')) == ['session-model']
    assert seen['auth'] == 'Bearer session-only-key'
    assert os.getenv('GEOMEMORY_OPENAI_API_KEY') is None


@pytest.mark.parametrize('name,offline,code', [('OpenAI', True, 'offline'), ('arbitrary', False, 'unknown_provider')])
def test_discovery_guard(monkeypatch, name, offline, code):
    setup_workspace(monkeypatch, offline)
    with pytest.raises(GeoFrontError) as exc:
        asyncio.run(providers.discover(name))
    assert exc.value.code == code


def test_custom_connections_bind_keys_to_exact_base(monkeypatch):
    bases = ['https://example.test/one', 'https://example.test/two']
    monkeypatch.setenv('GEOMIND_APPROVED_PROVIDER_BASES', ','.join(bases))
    def connect(base):
        return asyncio.run(providers.connect(providers.ConnectionRequest(base=base)))

    assert connect(bases[0])['keyEnv'] != connect(bases[1])['keyEnv']
    with pytest.raises(GeoFrontError):
        connect('https://elsewhere.test/v1')
