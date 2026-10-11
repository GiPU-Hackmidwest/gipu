import base64
import io
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from services.coordinator.app import create_app
from services.coordinator.leaderboard import WEEK_SECONDS, week_start
from services.coordinator.store import Store


LIMITS = {'cpu_threads': 2, 'max_pixels': 262144, 'session_minutes': 30}
MONDAY = 1791763200  # Monday 2026-10-12 00:00 UTC.


@pytest.fixture
def grid(tmp_path):
    now = [MONDAY + 100.0]
    store = Store(tmp_path, clock=lambda: now[0])
    buyer = store.session('Private Buyer')['user']['id']
    helper = store.session('Private Helper')['user']['id']
    return store, now, buyer, helper


def device(store, owner, enabled=True, minutes=30):
    item = store.register(owner, 'Private Mac', 'python', ['image_generate', 'image_finalize'],
                          dict(LIMITS, session_minutes=minutes))
    if enabled:
        store.change_device(owner, item['device']['id'], True)
    return item['device']['id']


def job(store, owner, key='leaderboard-test-1', count=1):
    return store.create_job(owner, {'prompt': 'Private prompt for an orange cat', 'count': count,
                                  'width': 256, 'height': 256, 'steps': 12,
                                  'budget': 20, 'request_id': key}, {'mode': 'manual'})


def complete(store, worker):
    task = store.claim(worker)['task']
    assert task is not None
    image = Image.new('RGB', (256, 256), 'orange')
    output = io.BytesIO()
    image.save(output, format='PNG')
    payload = base64.b64encode(output.getvalue()).decode()
    result = store.complete(worker, task['id'], task['lease_id'], payload, {})
    return task, payload, result


def test_default_private_and_explicit_alias_without_identity_leaks(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper)
    request = job(store, buyer)
    complete(store, worker)
    board = store.leaderboard(helper)
    assert board['enabled'] is False and board['nickname'] == ''
    assert board['entries'] == [] and board['self']['rank'] is None
    assert board['self']['completed_tasks'] == 1
    store.leaderboard_profile(helper, True, '  Orange Helper  ')
    public = store.leaderboard(buyer)
    assert public['entries'][0]['nickname'] == 'Orange Helper'
    serialized = json.dumps(public)
    for private in (buyer, helper, worker, request['id'], 'Private Buyer', 'Private Helper', 'Private Mac', 'Private prompt'):
        assert private not in serialized
    assert public['self']['credits_used'] == 7
    removed = store.leaderboard_profile(helper, False, 'Orange Helper')
    assert removed['entries'] == [] and removed['self']['rank'] is None
    assert removed['self']['completed_tasks'] == 1
    assert store.leaderboard(buyer)['entries'] == []


def test_actual_circulation_partial_cancel_refund_and_duplicate(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper)
    request = job(store, buyer)
    assert store.leaderboard(buyer)['self']['credits_used'] == 0  # Grant and reserve excluded.
    task, payload, _ = complete(store, worker)
    before = store.leaderboard(helper)['self']
    assert before['completed_tasks'] == 1 and before['score'] == 10
    assert store.complete(worker, task['id'], task['lease_id'], payload, {})['duplicate'] is True
    assert store.leaderboard(helper)['self'] == before
    store.cancel(buyer, request['id'])
    store.cancel(buyer, request['id'])
    assert store.leaderboard(buyer)['self']['credits_used'] == 7
    assert store.leaderboard(buyer)['self']['images_created'] == 0
    assert store.snapshot(buyer)['balance'] == 93


def test_revoked_and_rejected_work_cannot_award_progress(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper)
    request = job(store, buyer)
    claimed = store.claim(worker)['task']
    image = Image.new('RGB', (256, 256), 'orange')
    output = io.BytesIO()
    image.save(output, format='PNG')
    payload = base64.b64encode(output.getvalue()).decode()
    store.change_device(helper, worker, False)
    with pytest.raises(HTTPException) as stale:
        store.complete(worker, claimed['id'], claimed['lease_id'], payload,
                       {'completed_tasks': 9999, 'credits_used': 9999})
    assert stale.value.status_code == 409
    store.cancel(buyer, request['id'])
    assert store.leaderboard(helper)['self']['completed_tasks'] == 0
    assert store.leaderboard(buyer)['self']['credits_used'] == 0
    assert store.snapshot(buyer)['balance'] == 100


def test_existing_ledger_activity_survives_restart_without_profile_retroactive_optin(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper)
    job(store, buyer)
    complete(store, worker)
    complete(store, worker)
    restarted = Store(store.root, clock=lambda: now[0])
    assert restarted.leaderboard(helper)['self']['completed_tasks'] == 2
    assert restarted.leaderboard(buyer)['self']['credits_used'] == 9
    assert restarted.leaderboard(helper)['entries'] == []
    restarted.leaderboard_profile(helper, True, 'Helpful')
    assert restarted.leaderboard(buyer)['entries'][0]['completed_tasks'] == 2


def test_completed_images_and_exact_fee_count_once(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper)
    request = job(store, buyer, count=2)
    for _ in range(4):
        complete(store, worker)
    buyer_metrics = store.leaderboard(buyer)['self']
    assert buyer_metrics['credits_used'] == 17
    assert buyer_metrics['images_created'] == 2
    assert buyer_metrics['completed_tasks'] == 0
    assert store.leaderboard(helper)['self']['completed_tasks'] == 4
    assert store.leaderboard(helper)['self']['score'] == 40
    receipt = store.snapshot(buyer)['jobs'][0]['receipt']
    assert buyer_metrics['credits_used'] == receipt['total_charged']
    store.cancel(buyer, request['id'])
    assert store.leaderboard(buyer)['self'] == buyer_metrics


def test_self_recycling_never_farms_work_or_used_credits(grid):
    store, now, buyer, helper = grid
    worker = device(store, buyer)
    job(store, buyer)
    complete(store, worker)
    assert store.leaderboard(buyer)['self']['credits_used'] == 0
    complete(store, worker)
    own = store.leaderboard(buyer)['self']
    assert own['completed_tasks'] == 0 and own['credits_used'] == 1
    assert own['images_created'] == 1 and own['score'] == 1
    assert store.snapshot(buyer)['balance'] == 99


def test_mixed_own_and_other_contributors_only_net_out_own_payments(grid):
    store, now, buyer, helper = grid
    own_worker = device(store, buyer)
    other_worker = device(store, helper)
    job(store, buyer)
    complete(store, own_worker)
    complete(store, other_worker)
    assert store.leaderboard(buyer)['self']['credits_used'] == 2  # Other finisher + fee.
    assert store.leaderboard(buyer)['self']['completed_tasks'] == 0
    assert store.leaderboard(helper)['self']['completed_tasks'] == 1


def test_measured_availability_union_pause_offline_and_disabled(grid):
    store, now, buyer, helper = grid
    first = device(store, helper)
    second = device(store, helper)
    device(store, buyer, enabled=False)
    now[0] += 10
    assert store.leaderboard(helper)['self']['availability_seconds'] == 10
    store.change_device(helper, first, False)
    now[0] += 4
    store.heartbeat(second, {})
    now[0] += 10
    store.tick()
    store.change_device(helper, second, False)
    now[0] += 10
    assert store.leaderboard(helper)['self']['availability_seconds'] == 24
    assert store.leaderboard(buyer)['self']['availability_seconds'] == 0
    store.change_device(helper, first, True)  # Last heartbeat stale: no time until observed online.
    now[0] += 5
    assert store.leaderboard(helper)['self']['availability_seconds'] == 24
    store.heartbeat(first, {})
    now[0] += 10
    store.tick()
    now[0] += 10
    assert store.leaderboard(helper)['self']['availability_seconds'] == 39  # Bounded 15s grace.


def test_expiry_truncates_availability_and_server_gaps_do_not_backfill(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper, minutes=1)
    for _ in range(11):
        now[0] += 5
        store.heartbeat(worker, {})
    now[0] += 10
    assert store.leaderboard(helper)['self']['availability_seconds'] == 60
    assert store.snapshot(helper)['devices'][0]['enabled'] is False
    store.change_device(helper, worker, True)
    store.heartbeat(worker, {})
    now[0] += 100
    assert store.leaderboard(helper)['self']['availability_seconds'] == 60


def test_restart_and_clock_rollback_cannot_replay_intervals(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper)
    now[0] += 10
    assert store.leaderboard(helper)['self']['availability_seconds'] == 10
    now[0] -= 5
    store.tick()
    now[0] += 5
    assert store.leaderboard(helper)['self']['availability_seconds'] == 10
    now[0] += 100
    restarted = Store(store.root, clock=lambda: now[0])
    assert restarted.leaderboard(helper)['self']['availability_seconds'] == 10
    restarted.heartbeat(worker, {})
    now[0] += 5
    assert restarted.leaderboard(helper)['self']['availability_seconds'] == 15


def test_week_boundary_splits_uptime_and_uses_acceptance_not_request_time(grid):
    store, now, buyer, helper = grid
    now[0] = MONDAY + WEEK_SECONDS - 5
    store.tick()
    worker = device(store, helper)
    job(store, buyer)
    complete(store, worker)
    now[0] += 10
    complete(store, worker)
    board = store.leaderboard(helper)
    assert board['week_start'] == MONDAY + WEEK_SECONDS
    assert board['week_end'] == MONDAY + 2 * WEEK_SECONDS
    assert board['self']['availability_seconds'] == 5
    assert board['self']['completed_tasks'] == 1
    assert store.leaderboard(buyer)['self']['credits_used'] == 2  # Finishing + fee this week.
    assert store.leaderboard(buyer)['self']['images_created'] == 1
    with store.tx() as db:
        previous = db.execute('SELECT seconds FROM leaderboard_availability WHERE user_id=? AND week_start=?', (helper, MONDAY)).fetchone()
        assert previous['seconds'] == 5
    assert week_start(MONDAY - 1) == MONDAY - WEEK_SECONDS


def test_idle_score_cap_preserves_actual_seconds(grid):
    store, now, buyer, helper = grid
    worker = device(store, helper, minutes=120)
    for _ in range(4):
        store.change_device(helper, worker, True)
        for _ in range(480):
            now[0] += 15
            store.heartbeat(worker, {})
    assert store.leaderboard(helper)['self']['score'] == 32
    assert store.leaderboard(helper)['self']['availability_seconds'] == 28800
    store.change_device(helper, worker, True)
    now[0] += 10
    store.tick()
    assert store.leaderboard(helper)['self']['availability_seconds'] == 28810
    assert store.leaderboard(helper)['self']['score'] == 32


def test_ranked_top50_private_self_rank_ties_and_metric_switching(grid):
    store, now, buyer, helper = grid
    for index in range(51):
        owner = store.session('Private ' + str(index))['user']['id']
        store.leaderboard_profile(owner, True, f'Player {index:02}')
        with store.tx() as db:
            db.execute('INSERT INTO leaderboard_availability VALUES(?,?,?)', (owner, MONDAY, (51 - index) * 900))
        last = owner
    board = store.leaderboard(last, 'availability')
    assert board['member_count'] == 51 and len(board['entries']) == 50
    assert board['self']['rank'] == 51
    assert all(not entry['is_you'] for entry in board['entries'])
    credits = store.leaderboard(last, 'credits')
    assert all(entry['rank'] == 1 for entry in credits['entries'])
    store.leaderboard_profile(last, False, 'Player 50')
    assert store.leaderboard(last)['self']['rank'] is None


@pytest.mark.parametrize('value', ['', ' ', 'x' * 25, '<script>', 'Alias\nName', 'Name\u202ename', '💰', '---'])
def test_nickname_validation(grid, value):
    store, now, buyer, helper = grid
    with pytest.raises(HTTPException) as error:
        store.leaderboard_profile(buyer, True, value)
    assert error.value.status_code == 422
    assert store.leaderboard(buyer)['enabled'] is False


def test_api_requires_owner_and_valid_profile_and_metric(tmp_path, monkeypatch):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/leaderboard').status_code == 401
        session = client.post('/api/sessions', json={'join_code': 'pocketgrid-demo', 'name': 'Secret'}).json()
        headers = {'Authorization': 'Bearer ' + session['token']}
        worker = client.post('/api/devices', headers=headers, json={'name': 'Private', 'kind': 'python', 'capabilities': ['image_generate']}).json()
        worker_headers = {'Authorization': 'Bearer ' + worker['token']}
        assert client.get('/api/leaderboard', headers=worker_headers).status_code == 401
        assert client.patch('/api/leaderboard/profile', headers=worker_headers, json={'enabled': True, 'nickname': 'Alias'}).status_code == 401
        assert client.get('/api/leaderboard?metric=bad', headers=headers).status_code == 422
        assert client.patch('/api/leaderboard/profile', headers=headers, json={'enabled': True, 'nickname': 'Alias', 'user_id': 'other'}).status_code == 422
        response = client.patch('/api/leaderboard/profile', headers=headers, json={'enabled': True, 'nickname': 'Éclair 7'})
        assert response.status_code == 200
        assert response.json()['entries'][0]['is_you'] is True
        assert response.json()['entries'][0]['nickname'] == 'Éclair 7'
        assert client.post('/api/sessions/logout', headers=headers).status_code == 200
        assert client.get('/api/leaderboard', headers=headers).status_code == 401
