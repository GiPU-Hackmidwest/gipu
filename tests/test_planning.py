"""Durable asynchronous planning: persisted acknowledgement, fencing, recovery and refunds."""
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.coordinator import agent
from services.coordinator.app import create_app
from services.coordinator.store import PLANNING_CLAIM_SECONDS, Store
from tests.test_agent import current, response, use_model
from tests.test_coordinator import request
from tests.test_routing import grid


def ledger(store, user):
    with store.tx() as db:
        rows = db.execute('SELECT kind,amount FROM ledger WHERE user_id=? ORDER BY rowid', (user,)).fetchall()
        balance = db.execute('SELECT balance FROM users WHERE id=?', (user,)).fetchone()[0]
    # The ledger must always reconcile with the stored balance.
    assert sum(r['amount'] for r in rows) == balance
    return [(r['kind'], r['amount']) for r in rows]


def routes(devices):
    return {'image_generate': [devices[1]], 'image_finalize': [devices[1]]}


def submitting_model(monkeypatch, devices):
    return use_model(monkeypatch, [response('inspect_devices'), response('quote_job'),
        response('submit_job', explanation='Select B', generation_device_ids=[devices[1]],
                 finalize_device_ids=[devices[1]]), response('inspect_job')])


def test_request_is_persisted_and_reserved_before_any_model_call(grid, monkeypatch):
    store, now, user, devices = grid
    model, _ = use_model(monkeypatch, [RuntimeError('model must not run during submission')])
    job = agent.dispatch(store, user, dict(request(), use_agent=True))
    assert model.calls == 0
    assert job['status'] == 'planning' and job['tasks'] == [] and job['reserved'] == 10
    assert job['plan']['planning'] == {'status': 'pending', 'attempts': 0}
    assert ledger(store, user) == [('demo_grant', 100), ('reserve', -10)]
    # No worker can claim unplanned work.
    assert store.claim(devices[0])['task'] is None


def test_retry_during_planning_returns_same_request_without_second_reservation(grid, monkeypatch):
    store, now, user, devices = grid
    submitting_model(monkeypatch, devices)
    req = dict(request(), use_agent=True)
    first = agent.dispatch(store, user, req)
    assert agent.dispatch(store, user, req)['id'] == first['id']
    store.claim_planning()
    assert agent.dispatch(store, user, req)['id'] == first['id']
    assert ledger(store, user).count(('reserve', -10)) == 1
    assert len(store.snapshot(user)['jobs']) == 1


def test_live_claim_prevents_a_second_planner(grid, monkeypatch):
    store, now, user, devices = grid
    use_model(monkeypatch, [])
    agent.dispatch(store, user, dict(request(), use_agent=True))
    assert store.claim_planning() is not None
    assert store.claim_planning() is None
    assert agent.plan_once(store) is False


def test_restart_recovers_planning_and_fences_the_stale_plan(grid, monkeypatch):
    store, now, user, devices = grid
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    job = agent.dispatch(store, user, dict(request(), use_agent=True))
    old = store.claim_planning()['plan']['planning']['claim_id']
    # The process stops mid-plan. A new process opens the same database.
    restarted = Store(store.root, clock=store.clock)
    assert restarted.claim_planning() is None
    now[0] += PLANNING_CLAIM_SECONDS
    claimed = restarted.claim_planning()
    assert claimed['id'] == job['id'] and claimed['plan']['planning']['attempts'] == 2
    new = claimed['plan']['planning']['claim_id']
    with pytest.raises(HTTPException) as stale:
        store.activate_job(job['id'], old, routes(devices), 'Late plan', [])
    assert stale.value.status_code == 409
    assert store.finish_planning(job['id'], old, [], error='late') is False
    restarted.heartbeat(devices[1], {})  # Still online after the simulated downtime.
    planned =restarted.activate_job(job['id'], new, routes(devices), 'Recovered plan', [])
    assert planned['status'] == 'queued' and len(planned['tasks']) == 1
    assert ledger(store, user).count(('reserve', -10)) == 1
    assert restarted.claim(devices[1])['task']['job_id'] == job['id']


def test_cancel_during_planning_refunds_and_rejects_later_submission(grid, monkeypatch):
    store, now, user, devices = grid
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    job = agent.dispatch(store, user, dict(request(), use_agent=True))
    claim_id = store.claim_planning()['plan']['planning']['claim_id']
    cancelled = store.cancel(user, job['id'])
    assert cancelled['status'] == 'cancelled'
    assert cancelled['receipt'] == {'budget': 10, 'contributor_total': 0, 'platform_fee': 0, 'refund': 10, 'total_charged': 0}
    with pytest.raises(HTTPException) as late:
        store.activate_job(job['id'], claim_id, routes(devices), 'Too late', [])
    assert late.value.status_code == 409
    assert store.finish_planning(job['id'], claim_id, [{'tool': 'submit_job'}])
    final = current(store, job['id'])
    assert final['status'] == 'cancelled' and final['tasks'] == []
    assert final['plan']['planning']['status'] == 'cancelled'
    assert ledger(store, user) == [('demo_grant', 100), ('reserve', -10), ('refund', 10)]
    assert store.claim_review() is None


def test_cancel_while_model_is_planning_wins_over_submission(grid, monkeypatch):
    store, now, user, devices = grid
    job_id = []
    def cancel_then_submit():
        store.cancel(user, job_id[0])
        return [('submit_job', {'explanation': 'Select B', 'generation_device_ids': [devices[1]],
                                'finalize_device_ids': [devices[1]]})]
    model, _ = use_model(monkeypatch, [response('inspect_devices'), response('quote_job'), cancel_then_submit])
    job_id.append(agent.dispatch(store, user, dict(request(), use_agent=True))['id'])
    assert agent.plan_once(store)
    final = current(store, job_id[0])
    assert final['status'] == 'cancelled' and final['tasks'] == []
    rejected = [t for t in final['plan']['tools'] if t['tool'] == 'submit_job']
    assert rejected and all(t['result'].get('status_code') == 409 for t in rejected)
    assert store.snapshot(user)['balance'] == 100


def test_repeated_planner_loss_fails_and_refunds_after_bounded_attempts(grid, monkeypatch):
    store, now, user, devices = grid
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    job = agent.dispatch(store, user, dict(request(), use_agent=True))
    for attempt in (1, 2, 3):
        assert store.claim_planning()['plan']['planning']['attempts'] == attempt
        now[0] += PLANNING_CLAIM_SECONDS
    assert store.claim_planning() is None
    final = current(store, job['id'])
    assert final['status'] == 'failed' and final['plan']['planning']['status'] == 'failed'
    assert ledger(store, user)[-1] == ('refund', 10)
    assert store.claim_review() is None


def test_provider_removed_after_acceptance_fails_without_model_call(grid, monkeypatch):
    store, now, user, devices = grid
    model, _ = use_model(monkeypatch, [response('inspect_devices')])
    job = agent.dispatch(store, user, dict(request(), use_agent=True))
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    assert agent.plan_once(store)
    final = current(store, job['id'])
    assert model.calls == 0 and final['status'] == 'failed'
    assert 'no longer configured' in final['plan']['dispatch_error']
    assert store.snapshot(user)['balance'] == 100


def test_planning_requests_count_toward_active_job_limit(grid, monkeypatch):
    store, now, user, devices = grid
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    for index in range(10):
        agent.dispatch(store, user, dict(request(f'plan-{index}', budget=8), use_agent=True))
    with pytest.raises(HTTPException) as limit:
        agent.dispatch(store, user, dict(request('plan-extra', budget=8), use_agent=True))
    assert limit.value.status_code == 409


def test_http_submission_acknowledges_planning_and_allows_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    monkeypatch.setenv('POCKETGRID_JOIN_CODE', 'test-code')
    # No lifespan context: the background planner is not running.
    client = TestClient(create_app(tmp_path))
    token = client.post('/api/sessions', json={'name': 'Requester', 'join_code': 'test-code'}).json()['token']
    auth = {'Authorization': f'Bearer {token}'}
    body = dict(request(), use_agent=True)
    first = client.post('/api/jobs', json=body, headers=auth)
    assert first.status_code == 200 and first.json()['status'] == 'planning'
    assert client.post('/api/jobs', json=body, headers=auth).json()['id'] == first.json()['id']
    state = client.get('/api/state', headers=auth).json()
    assert state['balance'] == 90 and state['reserved'] == 10
    cancelled = client.post(f'/api/jobs/{first.json()["id"]}/cancel', headers=auth).json()
    assert cancelled['status'] == 'cancelled'
    assert client.get('/api/state', headers=auth).json()['balance'] == 100
    assert 'test-code' not in json.dumps(cancelled)
