"""Slow planning must not delay expiring work or responding to users."""
import threading

import pytest
from fastapi.testclient import TestClient

from services.coordinator import agent
from services.coordinator.app import create_app
from tests.test_coordinator import LIMITS, request


@pytest.mark.parametrize('loop',['review_once','plan_once'])
def test_slow_agent_call_does_not_block_lease_expiry(tmp_path,monkeypatch,loop):
    started=threading.Event()
    release=threading.Event()
    expired=threading.Event()
    now=[1000.0]
    app=create_app(tmp_path)
    store=app.state.store
    store.clock=lambda:now[0]
    owner=store.session('Owner')['user']['id']
    device=store.register(owner,'Worker','python',['image_generate'],LIMITS)['device']['id']
    store.change_device(owner,device,True)
    store.create_job(owner,request(),{'mode':'manual'})
    task=store.claim(device)['task']
    original_tick=store.tick

    def slow_review(_):
        started.set()
        assert release.wait(8),'test did not release the simulated model call'
        return False

    def observed_tick():
        original_tick()
        with store.tx() as db:
            status=db.execute('SELECT status FROM tasks WHERE id=?',(task['id'],)).fetchone()['status']
        if status=='queued':
            expired.set()

    monkeypatch.setattr(agent,loop,slow_review)
    monkeypatch.setattr(store,'tick',observed_tick)
    try:
        with TestClient(app) as client:
            assert started.wait(3)
            now[0]+=16
            # The review call is still blocked. The other lifespan task must
            # independently expire the lease without a worker/API sweep.
            assert expired.wait(3)
            assert not release.is_set()
            assert client.get('/api/health').status_code==200
            release.set()
    finally:
        release.set()


def test_background_planner_turns_accepted_request_into_queued_work(tmp_path,monkeypatch):
    from tests.test_agent import response,use_model
    app=create_app(tmp_path)
    store=app.state.store
    owner=store.session('Owner')['user']['id']
    device=store.register(owner,'Worker','python',['image_generate','image_finalize'],LIMITS)['device']['id']
    store.change_device(owner,device,True)
    use_model(monkeypatch,[response('inspect_devices'),response('quote_job'),
        response('submit_job',explanation='Only worker',generation_device_ids=[device],
                 finalize_device_ids=[device]),response('inspect_job')])
    accepted=agent.dispatch(store,owner,dict(request(),use_agent=True))
    planned=threading.Event()
    original=agent.plan_once
    def observed(target):
        result=original(target)
        if result:
            planned.set()
        return result
    monkeypatch.setattr(agent,'plan_once',observed)
    with TestClient(app):
        assert planned.wait(5)
    with store.tx() as db:
        job=store.job(db,accepted['id'])
    assert job['status']=='queued' and job['plan']['planning']['status']=='done'
    assert store.claim(device)['task']['job_id']==job['id']
