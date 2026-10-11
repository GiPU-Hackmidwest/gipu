import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from services.coordinator import payments
from services.coordinator.app import create_app


@pytest.fixture
def stripe(monkeypatch):
    """A fake Stripe API: Checkout sessions the test can mark paid."""
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_fake')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
    sessions, created = {}, []
    def handler(request):
        if request.method == 'POST' and request.url.path == '/v1/checkout/sessions':
            form = dict(httpx.QueryParams(request.content.decode()))
            created.append((form, request.headers.get('idempotency-key')))
            sid = f'cs_test_{len(sessions) + 1}'
            sessions[sid] = {'id': sid, 'url': f'https://checkout.stripe.test/{sid}', 'payment_status': 'unpaid', 'status': 'open',
                             'livemode': False, 'client_reference_id': form['client_reference_id'],
                             'amount_total': int(form['line_items[0][price_data][unit_amount]']), 'currency': form['line_items[0][price_data][currency]']}
            return httpx.Response(200, json=sessions[sid])
        sid = request.url.path.rsplit('/', 1)[-1]
        return httpx.Response(200, json=sessions[sid]) if sid in sessions else httpx.Response(404)
    transport = httpx.MockTransport(handler)
    real_client = payments._client
    monkeypatch.setattr(payments, '_client', lambda transport_=None: real_client(transport))
    return sessions, created


@pytest.fixture
def client(tmp_path, monkeypatch, stripe):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    with TestClient(create_app(tmp_path)) as client:
        yield client


def join(client):
    s = client.post('/api/sessions', json={'join_code': 'pocketgrid-demo'}).json()
    return {'Authorization': f'Bearer {s["token"]}'}


def test_paid_checkout_adds_credits_exactly_once(client, stripe):
    sessions, created = stripe
    auth = join(client)
    started = client.post('/api/credits/checkout', json={'pack': 'standard'}, headers=auth).json()
    form, idempotency = created[0]
    assert started['url'].startswith('https://checkout.stripe.test/') and idempotency
    assert form['line_items[0][price_data][unit_amount]'] == '1000' and form['metadata[credits]'] == '120'
    assert form['success_url'].endswith('/api/credits/return?session_id={CHECKOUT_SESSION_ID}')
    # Unpaid: nothing changes.
    assert client.get(f"/api/credits/checkout/{started['session_id']}", headers=auth).json()['status'] == 'pending'
    assert client.get('/api/state', headers=auth).json()['balance'] == 100
    sessions[started['session_id']].update(payment_status='paid', status='complete')
    assert client.get(f"/api/credits/checkout/{started['session_id']}", headers=auth).json() == {'status': 'paid', 'credits': 120}
    page = client.get(f"/api/credits/return?session_id={started['session_id']}")
    assert '120 credits added' in page.text and 'cannot be cashed out' in page.text
    state = client.get('/api/state', headers=auth).json()
    assert state['balance'] == 220
    assert [e for e in state['ledger'] if e['kind'] == 'purchase'][0]['amount'] == 120
    assert any(e['kind'] == 'credits_purchased' for e in state['events'])


def test_mismatched_or_live_sessions_are_never_credited(client, stripe):
    sessions, _ = stripe
    auth = join(client)
    sid = client.post('/api/credits/checkout', json={'pack': 'starter'}, headers=auth).json()['session_id']
    genuine = dict(sessions[sid], payment_status='paid', status='complete')
    for tamper in ({'amount_total': 1}, {'currency': 'eur'}, {'client_reference_id': 'someone-else'}, {'livemode': True}, {'payment_status': 'unpaid'}):
        sessions[sid] = dict(genuine, **tamper)
        assert client.get(f'/api/credits/checkout/{sid}', headers=auth).json()['status'] == 'pending', tamper
    assert client.get('/api/state', headers=auth).json()['balance'] == 100


def test_other_accounts_cannot_see_a_purchase_and_packs_are_fixed(client, stripe):
    auth, other = join(client), join(client)
    sid = client.post('/api/credits/checkout', json={'pack': 'starter'}, headers=auth).json()['session_id']
    assert client.get(f'/api/credits/checkout/{sid}', headers=other).status_code == 404
    assert client.post('/api/credits/checkout', json={'pack': 'free'}, headers=auth).status_code == 422
    assert client.post('/api/credits/checkout', json={'pack': 'starter', 'amount': 1}, headers=auth).status_code == 422
    packs = client.get('/api/credits/packs').json()
    assert packs['available'] and packs['test_mode'] and [p['id'] for p in packs['packs']] == ['starter', 'standard', 'large']


def sign(payload: bytes, secret='whsec_test', at=None):
    at = int(at or time.time())
    return f't={at},v1=' + hmac.new(secret.encode(), f'{at}.'.encode() + payload, hashlib.sha256).hexdigest()


def test_signed_webhook_settles_and_bad_signatures_are_rejected(client, stripe):
    sessions, _ = stripe
    auth = join(client)
    sid = client.post('/api/credits/checkout', json={'pack': 'large'}, headers=auth).json()['session_id']
    paid = dict(sessions[sid], payment_status='paid', status='complete')
    body = json.dumps({'type': 'checkout.session.completed', 'data': {'object': paid}}).encode()
    assert client.post('/api/stripe/webhook', content=body, headers={'stripe-signature': sign(body, 'wrong')}).status_code == 400
    assert client.post('/api/stripe/webhook', content=body, headers={'stripe-signature': sign(body, at=time.time() - 3600)}).status_code == 400
    for _ in range(2):  # Stripe retries deliveries; credits are granted once.
        assert client.post('/api/stripe/webhook', content=body, headers={'stripe-signature': sign(body)}).json() == {'received': True}
    assert client.get('/api/state', headers=auth).json()['balance'] == 400


def test_live_keys_and_missing_keys_disable_buying(client, monkeypatch):
    auth = join(client)
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_live_real_money')
    assert client.get('/api/credits/packs').json()['available'] is False
    reply = client.post('/api/credits/checkout', json={'pack': 'starter'}, headers=auth)
    assert reply.status_code == 503
    monkeypatch.delenv('STRIPE_SECRET_KEY')
    assert client.get('/api/state', headers=auth).json()['payments']['available'] is False


def test_there_is_no_way_to_turn_credits_into_money(client):
    routes = {getattr(r, 'path', '') for r in client.app.routes}
    assert not any(word in path for path in routes for word in ('payout', 'withdraw', 'cash-out', 'cashout', 'redeem'))
