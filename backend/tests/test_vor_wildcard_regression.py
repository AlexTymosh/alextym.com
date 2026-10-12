"""v1.3 manage and provider delivery regression tests. No external requests."""
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.vor import router
from app.services import vor_store


def client(monkeypatch, tmp_path):
    monkeypatch.setenv('VOR_DEMO_ENABLED', 'true')
    monkeypatch.setenv('VOR_DEMO_PASSWORD', 'Victoria')
    monkeypatch.setenv('VOR_DEMO_DB_PATH', str(tmp_path / 'fleet.sqlite3'))
    monkeypatch.delenv('VOR_DEMO_ALEX_EMAIL', raising=False)
    monkeypatch.delenv('VOR_DEMO_VICTORIA_EMAIL', raising=False)
    monkeypatch.setenv('VOR_DEMO_SEND_REAL_EMAIL', 'false')
    app = FastAPI()
    app.include_router(router, prefix='/api')
    c = TestClient(app)
    assert c.post('/api/vor/login', json={'password': 'Victoria'}).status_code == 200
    return c


def test_wildcard_allows_different_domains_without_bypassing_quota(monkeypatch, tmp_path):
    """'*' is an explicit opt-in to arbitrary domains, not arbitrary recipients."""
    with client(monkeypatch, tmp_path) as c:
        snap = c.get('/api/vor/bootstrap').json()
        vehicle_id = snap['vehicles'][0]['id']
        for subscribed in snap['subscriptions']:
            if subscribed['vehicle_id'] == vehicle_id:
                result = c.post('/api/vor/subscribers', json={
                    'vehicle_id': vehicle_id,
                    'contact_id': subscribed['contact_id'],
                    'subscribed': False,
                })
                assert result.status_code == 200, result.text
        addresses = ('test.one@alpha.example', 'test.two@beta.example')
        for address in addresses:
            added = c.post('/api/vor/contacts', json={
                'name': address.split('@')[0],
                'email': address,
                'role': 'external',
            })
            assert added.status_code == 200, added.text
            enabled = c.post('/api/vor/subscribers', json={
                'vehicle_id': vehicle_id,
                'contact_id': added.json()['id'],
                'subscribed': True,
            })
            assert enabled.status_code == 200, enabled.text

        monkeypatch.setenv('VOR_DEMO_SEND_REAL_EMAIL', 'true')
        monkeypatch.setenv('VOR_DEMO_ALLOWED_EMAIL_DOMAINS', '*')
        monkeypatch.setenv('VOR_DEMO_ALLOWED_RECIPIENTS', '')
        monkeypatch.setenv('VOR_DEMO_EMAIL_LIMIT', '2')
        monkeypatch.setenv('RESEND_API_KEY', 'fake-test-token')
        monkeypatch.setenv('VOR_DEMO_FROM_EMAIL', 'demo@verified.example')
        monkeypatch.setenv('VOR_DEMO_PUBLIC_URL', 'https://alextym.com/fleet-vor-hub')
        deliveries = []

        class FakeResponse:
            def raise_for_status(self):
                return None

        def fake_post(url, **kwargs):
            deliveries.append(kwargs['json'])
            return FakeResponse()

        monkeypatch.setattr('app.api.vor.httpx.post', fake_post)
        message = {'vehicle_id': vehicle_id, 'kind': 'email', 'text': 'Test update', 'subject': 'Update'}
        sent = c.post('/api/vor/messages', json=message)
        assert sent.status_code == 200, sent.text
        assert sent.json()['recipient_count'] == 2
        assert set(deliveries[0]['to'] + deliveries[0].get('bcc', [])) == set(addresses)
        assert c.post('/api/vor/messages', json=message).status_code == 429
        assert len(deliveries) == 1


def test_wildcard_is_exact_not_partial(monkeypatch, tmp_path):
    """'*.example' is not interpreted as an unrestricted wildcard."""
    with client(monkeypatch, tmp_path) as c:
        snap = c.get('/api/vor/bootstrap').json()
        vehicle_id = snap['vehicles'][0]['id']
        monkeypatch.setenv('VOR_DEMO_SEND_REAL_EMAIL', 'true')
        monkeypatch.setenv('VOR_DEMO_ALLOWED_EMAIL_DOMAINS', '*.example')
        monkeypatch.setenv('VOR_DEMO_ALLOWED_RECIPIENTS', '')
        response = c.post('/api/vor/messages', json={
            'vehicle_id': vehicle_id, 'kind': 'email', 'text': 'Not permitted',
        })
        assert response.status_code == 403, response.text
