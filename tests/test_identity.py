import sqlite3

import pytest
from fastapi.testclient import TestClient

from services.coordinator.app import create_app
from services.coordinator.store import Store, digest
from tests.test_coordinator import request

JOIN = 'pocketgrid-demo'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    with TestClient(create_app(tmp_path)) as client:
        yield client


def bearer(session):
    return {'Authorization': f'Bearer {session["token"]}'}


def test_anonymous_join_needs_no_name(client):
    session = client.post('/api/sessions', json={'join_code': JOIN}).json()
    assert session['user']['name'].startswith('Guest ') and session['balance'] == 100 and session['session_id']
    named = client.post('/api/sessions', json={'join_code': JOIN, 'name': '  Ada  '}).json()
    assert named['user']['name'] == 'Ada' and named['user']['id'] != session['user']['id']


def test_link_code_signs_a_second_device_into_the_same_balance(client):
    mac = client.post('/api/sessions', json={'join_code': JOIN}).json()
    assert client.post('/api/jobs', json=request(), headers=bearer(mac)).status_code == 200
    code = client.post('/api/sessions/link-codes', headers=bearer(mac)).json()
    assert len(code['code']) == 10 and code['expires_at'] > 0
    phone = client.post('/api/sessions/link', json={'code': code['code'].lower(), 'client_name': 'Pixel'}).json()
    assert phone['user'] == mac['user'] and phone['balance'] == 90 and phone['token'] != mac['token']
    assert client.get('/api/state', headers=bearer(phone)).json()['jobs'][0]['owner_id'] == mac['user']['id']
    # Single use.
    assert client.post('/api/sessions/link', json={'code': code['code']}).status_code == 400


def test_link_codes_expire_and_a_new_code_replaces_the_old_one(tmp_path):
    now = [1000.0]
    store = Store(tmp_path, clock=lambda: now[0])
    user = store.session('Ada')['user']['id']
    first = store.create_link_code(user)['code']
    second = store.create_link_code(user)['code']
    with pytest.raises(Exception) as replaced:
        store.redeem_link_code(first)
    assert replaced.value.status_code == 400
    now[0] += 121
    with pytest.raises(Exception) as expired:
        store.redeem_link_code(second)
    assert expired.value.status_code == 400


def test_repeated_bad_codes_are_rate_limited(client):
    mac = client.post('/api/sessions', json={'join_code': JOIN}).json()
    for _ in range(5):
        assert client.post('/api/sessions/link', json={'code': 'AAAAAAAAAA'}).status_code == 400
    code = client.post('/api/sessions/link-codes', headers=bearer(mac)).json()['code']
    assert client.post('/api/sessions/link', json={'code': code}).status_code == 429


def test_optional_login_recovers_the_same_account(client):
    guest = client.post('/api/sessions', json={'join_code': JOIN}).json()
    assert client.post('/api/account/credentials', json={'username': 'Ada.L', 'password': 'correct horse'}, headers=bearer(guest)).json() == {'username': 'ada.l'}
    assert client.get('/api/state', headers=bearer(guest)).json()['user']['username'] == 'ada.l'
    again = client.post('/api/sessions/login', json={'username': 'ADA.L', 'password': 'correct horse'}).json()
    assert again['user'] == guest['user']
    for body in ({'username': 'ada.l', 'password': 'wrong password'}, {'username': 'nobody', 'password': 'correct horse'}):
        response = client.post('/api/sessions/login', json=body)
        assert response.status_code == 401 and response.json()['detail'] == 'Incorrect username or password'


def test_login_names_are_unique_and_changes_need_the_current_password(client):
    first = client.post('/api/sessions', json={'join_code': JOIN}).json()
    second = client.post('/api/sessions', json={'join_code': JOIN}).json()
    client.post('/api/account/credentials', json={'username': 'ada', 'password': 'password-1'}, headers=bearer(first))
    assert client.post('/api/account/credentials', json={'username': 'ADA', 'password': 'password-2'}, headers=bearer(second)).status_code == 409
    assert client.post('/api/account/credentials', json={'username': 'ada2', 'password': 'password-2'}, headers=bearer(first)).status_code == 403
    changed = client.post('/api/account/credentials', json={'username': 'ada2', 'password': 'password-2', 'current_password': 'password-1'}, headers=bearer(first))
    assert changed.json() == {'username': 'ada2'}
    assert client.post('/api/account/credentials', json={'username': 'a b', 'password': 'password-3'}, headers=bearer(second)).status_code == 422


def test_sessions_can_be_listed_revoked_and_logged_out(client):
    mac = client.post('/api/sessions', json={'join_code': JOIN, 'client_name': 'Mac'}).json()
    code = client.post('/api/sessions/link-codes', headers=bearer(mac)).json()['code']
    phone = client.post('/api/sessions/link', json={'code': code, 'client_name': 'Pixel'}).json()
    listed = client.get('/api/sessions', headers=bearer(mac)).json()['sessions']
    assert [(s['client_name'], s['current']) for s in listed] == [('Mac', True), ('Pixel', False)]
    assert 'token' not in listed[0]
    assert client.delete(f'/api/sessions/{phone["session_id"]}', headers=bearer(mac)).json() == {'ok': True}
    assert client.get('/api/state', headers=bearer(phone)).status_code == 401
    assert client.delete(f'/api/sessions/{phone["session_id"]}', headers=bearer(mac)).status_code == 404
    assert client.post('/api/sessions/logout', headers=bearer(mac)).json() == {'ok': True}
    assert client.get('/api/state', headers=bearer(mac)).status_code == 401


def test_tokens_issued_before_multi_device_sign_in_keep_working(tmp_path):
    store = Store(tmp_path)
    user = store.session('Earlier')['user']['id']
    # Recreate the pre-V1 layout: the token lived on the user row.
    with sqlite3.connect(store.path) as db:
        db.execute('DELETE FROM user_sessions')
        db.execute('UPDATE users SET token=? WHERE id=?', (digest('old-token'), user))
    migrated = Store(tmp_path)
    assert migrated.auth('old-token')['id'] == user
    assert Store(tmp_path).auth('old-token')['id'] == user  # Migration is idempotent.


def test_legacy_migration_preserves_reservation_and_revocation_across_restart(tmp_path):
    store = Store(tmp_path)
    original = store.session('Earlier')
    user = original['user']['id']
    job = store.create_job(user, request(), {'mode': 'manual'})
    with sqlite3.connect(store.path) as db:
        db.execute('DELETE FROM user_sessions')
        db.execute('UPDATE users SET token=? WHERE id=?', (digest('old-token'), user))
    migrated = Store(tmp_path)
    session = migrated.auth('old-token')
    before = migrated.snapshot(user)
    assert before['balance'] == 90 and before['reserved'] == 10
    assert before['jobs'][0]['id'] == job['id'] and before['jobs'][0]['owner_id'] == user
    code = migrated.create_link_code(user)['code']
    linked = migrated.redeem_link_code(code, 'Phone')
    assert linked['user'] == original['user'] and linked['balance'] == 90
    migrated.revoke_session(user, session['session_id'])
    restarted = Store(tmp_path)
    with pytest.raises(Exception) as revoked:
        restarted.auth('old-token')
    assert revoked.value.status_code == 401
    assert restarted.auth(linked['token'])['id'] == user
    assert restarted.snapshot(user)['ledger'] == before['ledger']
    restarted.cancel(user, job['id'])
    after = restarted.snapshot(user)
    assert after['balance'] == 100 and after['reserved'] == 0
    assert sum(e['amount'] for e in after['ledger'] if e['kind'] == 'demo_grant') == 100
    assert after['jobs'][0]['receipt']['refund'] == 10


def test_session_revocation_is_scoped_to_the_owner(client):
    first = client.post('/api/sessions', json={'join_code': JOIN}).json()
    second = client.post('/api/sessions', json={'join_code': JOIN}).json()
    assert client.delete(f'/api/sessions/{second["session_id"]}', headers=bearer(first)).status_code == 404
    assert client.get('/api/state', headers=bearer(second)).status_code == 200
    assert [s['id'] for s in client.get('/api/sessions', headers=bearer(first)).json()['sessions']] == [first['session_id']]
