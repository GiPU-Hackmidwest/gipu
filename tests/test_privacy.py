import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.coordinator.app import create_app
from tests.test_coordinator import LIMITS, png, request

JOIN = 'pocketgrid-demo'


@pytest.fixture
def grid(tmp_path, monkeypatch):
    """A requester and a contributor whose laptop runs the requester's job."""
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    with TestClient(create_app(tmp_path)) as client:
        store = client.app.state.store
        def join(name):
            session = client.post('/api/sessions', json={'join_code': JOIN, 'name': name}).json()
            return session['user']['id'], {'Authorization': f'Bearer {session["token"]}'}
        buyer, buyer_auth = join('Buyer')
        seller, seller_auth = join('Seller')
        stranger, stranger_auth = join('Stranger')
        laptop = client.post('/api/devices', json={'name': "Seller's MacBook", 'kind': 'python', 'capabilities': ['image_generate', 'image_finalize'], 'limits': LIMITS}, headers=seller_auth).json()
        client.patch(f'/api/devices/{laptop["device"]["id"]}', json={'enabled': True}, headers=seller_auth)
        yield {'client': client, 'store': store, 'buyer': (buyer, buyer_auth), 'seller': (seller, seller_auth),
               'stranger': (stranger, stranger_auth), 'laptop': laptop['device']['id'],
               'laptop_auth': {'Authorization': f'Bearer {laptop["token"]}'}}


def run_job(g, finished=True):
    client, store, laptop = g['client'], g['store'], g['laptop']
    job = client.post('/api/jobs', json=request(), headers=g['buyer'][1]).json()
    task = store.claim(laptop)['task']
    store.complete(laptop, task['id'], task['lease_id'], png(), {})
    if finished:
        export = store.claim(laptop)['task']
        store.complete(laptop, export['id'], export['lease_id'], png(), {})
    return job['id']


def test_each_member_sees_only_their_own_jobs_and_devices(grid):
    run_job(grid)
    client = grid['client']
    buyer = client.get('/api/state', headers=grid['buyer'][1]).json()
    seller = client.get('/api/state', headers=grid['seller'][1]).json()
    assert len(buyer['jobs']) == 1 and buyer['devices'] == []
    assert seller['jobs'] == [] and [d['id'] for d in seller['devices']] == [grid['laptop']]
    assert buyer['grid'] == seller['grid'] == {'connected': 1, 'ready_to_create': 1, 'ready_to_finish': 1}


def test_other_members_devices_stay_anonymous_in_jobs_and_activity(grid):
    run_job(grid)
    client = grid['client']
    state = client.get('/api/state', headers=grid['buyer'][1]).json()
    tasks = state['jobs'][0]['tasks']
    assert all(t['device_id'] is None and t['device_kind'] == 'python' for t in tasks)
    text = json.dumps(state)
    assert "Seller's MacBook" not in text and grid['laptop'] not in text
    assert not any(e['kind'] == 'credits_earned' for e in state['events'])
    assert any(e['message'] == 'A grid laptop started work on your images' for e in state['events'])
    # The contributor sees their own activity, without the requester's job ID.
    seller_events = client.get('/api/state', headers=grid['seller'][1]).json()['events']
    assert any(e['kind'] == 'credits_earned' for e in seller_events)
    assert all(e['job_id'] is None for e in seller_events if e['kind'] in ('task_started', 'credits_earned'))


def test_finished_images_are_marked_verified(grid):
    run_job(grid)
    images = grid['client'].get('/api/state', headers=grid['buyer'][1]).json()['jobs'][0]['images']
    assert sorted((i['stage'], i['verified']) for i in images) == [('image_finalize', True), ('image_generate', False)]


def test_images_and_jobs_are_limited_to_owner_and_assigned_devices(grid):
    job_id = run_job(grid, finished=False)
    client, store = grid['client'], grid['store']
    job = client.get(f'/api/jobs/{job_id}', headers=grid['buyer'][1]).json()
    url = job['images'][0]['url']
    assert client.get(url, headers=grid['buyer'][1]).status_code == 200
    assert client.get(url, headers=grid['seller'][1]).status_code == 404
    assert client.get(url, headers=grid['stranger'][1]).status_code == 404
    assert client.get(f'/api/jobs/{job_id}', headers=grid['stranger'][1]).status_code == 404
    # The finisher may read its source; the device that worked the job may read the job.
    store.claim(grid['laptop'])
    assert client.get(url, headers=grid['laptop_auth']).status_code == 200
    assert client.get(f'/api/jobs/{job_id}', headers=grid['laptop_auth']).status_code == 200


def test_planner_details_hide_other_members_devices(grid):
    store, buyer = grid['store'], grid['buyer'][0]
    plan = {'mode': 'strands-test', 'explanation': "Chose Seller's MacBook for speed",
            'routes': {'image_generate': [grid['laptop']], 'image_finalize': [grid['laptop']]}}
    job = store.create_job(buyer, dict(request(), request_id='planned-001'), plan)
    with store.tx() as db:
        raw = json.loads(db.execute('SELECT plan FROM jobs WHERE id=?', (job['id'],)).fetchone()[0])
        raw['tools'] = [{'tool': 'inspect_devices', 'result': {'devices': [{'name': "Seller's MacBook"}]}}]
        db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(raw), job['id']))
    view = store.view_job(store.existing_job(buyer, 'planned-001'), buyer)
    assert view['plan']['explanation'] == 'Compatible devices selected for your request.'
    assert view['plan']['routes'] == {'image_generate': [], 'image_finalize': []}
    assert 'tools' not in view['plan']


def test_finisher_returns_identical_pixels_and_legacy_frame_is_accepted_during_rollout(grid):
    store, laptop = grid['store'], grid['laptop']
    grid['client'].post('/api/jobs', json=request(), headers=grid['buyer'][1])
    task = store.claim(laptop)['task']
    store.complete(laptop, task['id'], task['lease_id'], png(), {})
    export = store.claim(laptop)['task']
    with pytest.raises(HTTPException) as altered:
        store.complete(laptop, export['id'], export['lease_id'], png(color='blue'), {})
    assert altered.value.status_code == 422
    assert store.complete(laptop, export['id'], export['lease_id'], png(framed=True), {})['accepted']


def test_legacy_frame_can_be_turned_off(grid, monkeypatch):
    store, laptop = grid['store'], grid['laptop']
    store.accept_legacy_frame = False
    grid['client'].post('/api/jobs', json=request(), headers=grid['buyer'][1])
    task = store.claim(laptop)['task']
    store.complete(laptop, task['id'], task['lease_id'], png(), {})
    export = store.claim(laptop)['task']
    with pytest.raises(HTTPException):
        store.complete(laptop, export['id'], export['lease_id'], png(framed=True), {})
    assert store.complete(laptop, export['id'], export['lease_id'], png(), {})['accepted']


@pytest.mark.parametrize('original_name, current_name', [('Pi', 'Pi'), ('Private old laptop', 'Renamed laptop')])
def test_public_projection_hides_short_historical_names_and_raw_ids(grid, original_name, current_name):
    store, buyer, foreign = grid['store'], grid['buyer'][0], grid['laptop']
    with store.tx() as db:
        db.execute('UPDATE devices SET name=? WHERE id=?', (original_name, foreign))
    secret = f'{original_name} ({foreign})'
    job = store.create_job(buyer, dict(request(), request_id='private-plan-001'), {
        'mode': 'strands-test', 'explanation': secret,
        'routes': {'image_generate': [foreign], 'image_finalize': [foreign]}})
    task_id = job['tasks'][0]['id']
    with store.tx() as db:
        plan = json.loads(db.execute('SELECT plan FROM jobs WHERE id=?', (job['id'],)).fetchone()[0])
        plan.update(dispatch_error=secret, extra=secret, review={'status': 'error', 'attempts': 1, 'error': secret, 'extra': secret},
                    planning={'status': 'done', 'attempts': 1, 'claim_id': foreign},
                    task_routes={task_id: {'device_ids': [foreign], 'until': 42, 'attempt': 0, 'explanation': secret, 'extra': secret},
                                 foreign: {'device_ids': [], 'explanation': secret}})
        db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(plan), job['id']))
        db.execute('UPDATE devices SET name=? WHERE id=?', (current_name, foreign))
        db.execute('UPDATE tasks SET device_id=?,metrics=? WHERE id=?',
                   (foreign, json.dumps({'backend': secret, foreign: secret, 'elapsed_seconds': 1.25}), task_id))
        for kind in ('routing_updated', 'task_reassigned', 'job_failed', 'unknown_future_event'):
            store.event(db, kind, secret, job_id=job['id'])  # No device ID to redact.
        store.ledger(db, buyer, job['id'], 'refund', 0, secret)
    state = grid['client'].get('/api/state', headers=grid['buyer'][1]).json()
    view = grid['client'].get(f'/api/jobs/{job["id"]}', headers=grid['buyer'][1]).json()
    for payload in (state, view):
        text = json.dumps(payload)
        assert foreign not in text and original_name not in text and current_name not in text
    assert view['plan']['planning'] == {'status': 'done', 'attempts': 1}
    assert view['plan']['task_routes'][task_id]['until'] == 42
    assert view['tasks'][0]['metrics'] == {'elapsed_seconds': 1.25}
    assert state['balance'] == 90 and state['reserved'] == 10
    # Internal planner diagnostics remain intact for recovery and operator review.
    assert store.existing_job(buyer, 'private-plan-001')['plan']['explanation'] == secret


def test_own_device_names_routes_metrics_and_earnings_are_preserved(grid):
    store, buyer = grid['store'], grid['buyer'][0]
    # Duplicate names cannot be used to infer which names are safe in raw prose.
    own = store.register(buyer, "Seller's MacBook", 'python', ['image_generate', 'image_finalize'], LIMITS)['device']['id']
    grid['client'].patch(f'/api/devices/{own}', json={'enabled': True}, headers=grid['buyer'][1])
    job = store.create_job(buyer, dict(request(), request_id='own-plan-001'), {
        'mode': 'strands-test', 'explanation': f'{grid["laptop"]} and {own}',
        'routes': {'image_generate': [own], 'image_finalize': [own]}})
    task = store.claim(own)['task']
    store.complete(own, task['id'], task['lease_id'], png(), {'backend': 'my-local-backend', 'elapsed_seconds': 2})
    view = store.snapshot(buyer)
    assert view['devices'][0]['name'] == "Seller's MacBook"
    public_job = view['jobs'][0]
    assert public_job['plan']['routes']['image_generate'] == [own]
    completed = next(t for t in public_job['tasks'] if t['id'] == task['id'])
    assert completed['device_id'] == own and completed['metrics']['backend'] == 'my-local-backend'
    assert any(e['device_id'] == own and "Seller's MacBook" in e['message'] for e in view['events'])
    assert any(e['message'] == '6 sandbox credits earned for accepted work' for e in view['events'])
    assert view['earned'] == 6 and grid['laptop'] not in json.dumps(view)


@pytest.mark.parametrize('end_assignment', ['cancel', 'expire'])
def test_source_image_access_ends_with_unfinished_assignment(grid, end_assignment):
    store, client = grid['store'], grid['client']
    finisher = store.register(grid['stranger'][0], 'Private finisher', 'browser', ['image_finalize'], LIMITS)
    device_id = finisher['device']['id']
    client.patch(f'/api/devices/{device_id}', json={'enabled': True}, headers=grid['stranger'][1])
    job_id = run_job(grid, finished=False)
    source = store.claim(device_id)['task']['source_url']
    auth = {'Authorization': f'Bearer {finisher["token"]}'}
    assert client.get(source, headers=auth).status_code == 200
    if end_assignment == 'cancel':
        store.cancel(grid['buyer'][0], job_id)
    else:
        expired = store.clock() + store.lease_seconds + 1
        store.clock = lambda: expired
    # GET itself expires stale leases, without depending on a background tick.
    assert client.get(source, headers=auth).status_code == 404
    assert client.get(source, headers=grid['buyer'][1]).status_code == 200
    assert client.get(source, headers=grid['laptop_auth']).status_code == 200  # Completed producer.
