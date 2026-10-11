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
    assert view['plan']['explanation'] == 'Chose a grid device for speed'
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
