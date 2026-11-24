"""Exercise actual workspace persistence and HTTP transport without a paid service."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from geomemory.core.models import GenerationRequest, WorkspaceSettings
from geomemory.qa.backend_factory import build_llm_backend


def test_discover_apply_reopen_generate(client, open_ws, monkeypatch):
    requests = []

    class Endpoint(BaseHTTPRequestHandler):
        def reply(self, body):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_GET(self):
            requests.append((self.path, self.headers.get('Authorization'), None))
            self.reply({'data': [{'id': 'fixture-large'}, {'id': 'fixture-small'}]})

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, self.headers.get('Authorization'), payload['model']))
            self.reply({'choices': [{'message': {'content': 'fixture answer'}}]})

    with ThreadingHTTPServer(('127.0.0.1', 0), Endpoint) as endpoint:
        thread = Thread(target=endpoint.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{endpoint.server_port}/v1'
            monkeypatch.setenv('GEOMEMORY_LLM_API_BASE_URL', base)
            monkeypatch.setenv('GEOMEMORY_LLM_API_KEY', 'fixture-key')
            root = '/api/v1/workspace'
            assert client.put(root + '/settings', json={'offline': False}).is_success
            profile = next(p for p in client.get('/api/v1/providers').json() if p['base'] == base)
            models = client.get(f"/api/v1/providers/{profile['name']}/models").json()
            assert models == ['fixture-large', 'fixture-small']
            assert client.put(root + '/settings', json={'llm_provider':'api', 'llm_model_id':models[1], 'llm_api_base_url':base, 'llm_api_key_env':profile['keyEnv']}).is_success
            assert client.post(root + '/close').is_success
            assert client.post(root + '/open', json={'path':open_ws['path']}).is_success
            settings = WorkspaceSettings.model_validate(client.get(root).json()['settings'])
            backend, _ = build_llm_backend(settings)
            assert backend.generate(GenerationRequest(prompt='Synthetic question')).text == 'fixture answer'
            assert requests == [('/v1/models','Bearer fixture-key',None), ('/v1/chat/completions','Bearer fixture-key',models[1])]
        finally:
            endpoint.shutdown()
            thread.join()


def test_discover_uses_session_key_header_over_http(client, open_ws, monkeypatch):
    """The Studio 'Fetch models' button sends the session key as a header."""
    seen = {}

    class Endpoint(BaseHTTPRequestHandler):
        def do_GET(self):
            seen['auth'] = self.headers.get('Authorization')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'data': [{'id': 'kilo-model'}]}).encode())

    with ThreadingHTTPServer(('127.0.0.1', 0), Endpoint) as endpoint:
        thread = Thread(target=endpoint.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{endpoint.server_port}/v1'
            monkeypatch.setenv('GEOMEMORY_LLM_API_BASE_URL', base)
            monkeypatch.delenv('GEOMEMORY_LLM_API_KEY', raising=False)
            assert client.put('/api/v1/workspace/settings', json={'offline': False}).is_success
            profile = next(
                p for p in client.get('/api/v1/providers').json() if p['base'] == base
            )

            # No key anywhere → the documented 409 guard still fires.
            missing = client.get(f"/api/v1/providers/{profile['name']}/models")
            assert missing.status_code == 409
            assert missing.json()['error']['code'] == 'provider_key_missing'

            # Session key on the request authorizes discovery without being
            # written to the process environment.
            ok = client.get(
                f"/api/v1/providers/{profile['name']}/models",
                headers={'x-geomind-api-key': 'session-only-key'},
            )
            assert ok.json() == ['kilo-model']
            assert seen['auth'] == 'Bearer session-only-key'
            assert not os.getenv('GEOMEMORY_LLM_API_KEY')
        finally:
            endpoint.shutdown()
            thread.join()
