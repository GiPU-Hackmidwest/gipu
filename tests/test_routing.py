import pytest
from fastapi import HTTPException

from tests.test_coordinator import LIMITS,png,request
from services.coordinator.store import Store


@pytest.fixture
def grid(tmp_path):
    now = [1000.0]
    store = Store(tmp_path,clock=lambda:now[0])
    user = store.session('Test owner')['user']['id']
    devices=[]
    for name in ('A','B'):
        d=store.register(user,name,'python',['image_generate','image_finalize'],LIMITS)['device']['id']
        store.change_device(user,d,True)
        devices.append(d)
    return store,now,user,devices


def submit(store,user,devices):
    return store.create_job(user,request(),{'mode':'strands-ollama','explanation':'Selected B',
                                           'routes':{'image_generate':[devices[1]],'image_finalize':[devices[1]]}})


def test_selected_device_wins_even_when_other_worker_polls_first(grid):
    store,now,user,devices=grid
    job=submit(store,user,devices)
    assert store.claim(devices[0])['task'] is None
    task=store.claim(devices[1])['task']
    assert task['job_id']==job['id']
    assert any(e['kind']=='routing_applied' and e['device_id']==devices[1] for e in store.snapshot(user)['events'])


def test_invalid_preference_never_reserves_funds(grid):
    store,now,user,devices=grid
    store.change_device(user,devices[1],False)
    with pytest.raises(HTTPException) as exc:
        submit(store,user,devices)
    assert exc.value.status_code==422
    assert store.snapshot(user)['balance']==100
    assert not store.snapshot(user)['jobs']


def test_offline_or_expired_preference_does_not_block_fallback(grid):
    store,now,user,devices=grid
    submit(store,user,devices)
    now[0]+=16
    assert store.claim(devices[0])['task'] is not None


def test_preference_deadline_expires_even_when_selected_worker_heartbeats(grid):
    store,now,user,devices=grid
    submit(store,user,devices)
    now[0]+=46
    store.heartbeat(devices[1],{})
    assert store.claim(devices[0])['task'] is not None


@pytest.mark.parametrize('reroute_failed_device', [False, True])
def test_failed_preferred_worker_does_not_block_available_fallback(grid, reroute_failed_device):
    store,now,user,devices=grid
    job=submit(store,user,devices)
    task=store.claim(devices[1])['task']
    store.task_failed(devices[1],task['id'],task['lease_id'],'Model unavailable')
    if reroute_failed_device:
        # Even a new agent preference cannot reserve work for a cooling worker.
        store.update_routing(user,job['id'],{'image_generate':[devices[1]]},
                             {task['id']:1},'Retry selected worker')
    assert store.claim(devices[1])['task'] is None
    fallback=store.claim(devices[0])['task']
    assert fallback['id']==task['id']
    assert fallback['lease_id']!=task['lease_id']
    assert fallback['attempts']==2


def test_initial_selection_is_not_reused_after_failure_cooldown(grid):
    store,now,user,devices=grid
    submit(store,user,devices)
    task=store.claim(devices[1])['task']
    store.task_failed(devices[1],task['id'],task['lease_id'],'Model unavailable')
    now[0]+=6
    store.heartbeat(devices[1],{})
    assert store.claim(devices[0])['task']['id']==task['id']


@pytest.mark.parametrize('wait_for_finalizer_deadline', [False, True])
def test_finalizer_preference_window_starts_when_generation_finishes(grid, wait_for_finalizer_deadline):
    store,now,user,devices=grid
    submit(store,user,devices)
    generation=store.claim(devices[1])['task']
    # A realistic generation outlives the initial routing window but stays leased.
    for _ in range(5):
        now[0]+=10
        store.heartbeat(devices[1],{},generation['id'],generation['lease_id'])
    store.complete(devices[1],generation['id'],generation['lease_id'],png(),{})
    if wait_for_finalizer_deadline:
        now[0]+=46
        store.heartbeat(devices[1],{})
        assert store.claim(devices[0])['task']['kind']=='image_finalize'
    else:
        assert store.claim(devices[0])['task'] is None
        assert store.claim(devices[1])['task']['kind']=='image_finalize'


def test_review_changes_only_current_queued_work_and_fences_old_result(grid):
    store,now,user,devices=grid
    job=submit(store,user,devices)
    first=store.claim(devices[1])['task']
    store.task_failed(devices[1],first['id'],first['lease_id'],'Worker error')
    scope={first['id']:1}
    updated=store.update_routing(user,job['id'],{'image_generate':[devices[0]],'image_finalize':[]},scope,'Move work from B to A')
    assert updated['plan']['task_routes'][first['id']]['device_ids']==[devices[0]]
    next_task=store.claim(devices[0])['task']
    assert next_task['id']==first['id'] and next_task['lease_id']!=first['lease_id']
    with pytest.raises(HTTPException) as stale:
        store.update_routing(user,job['id'],{'image_generate':[devices[1]]},scope,'Stale')
    assert stale.value.status_code==409
    with pytest.raises(HTTPException):
        store.complete(devices[1],first['id'],first['lease_id'],png(),{})
    store.complete(devices[0],next_task['id'],next_task['lease_id'],png(),{})
    assert store.snapshot(user)['earned']==6


def test_manual_jobs_never_get_model_review(grid):
    store,now,user,devices=grid
    job=store.create_job(user,request(),{'mode':'manual'})
    store.cancel(user,job['id'])
    assert store.claim_review() is None


def test_durable_bounded_review_claims_and_fencing(grid):
    store,now,user,devices=grid
    job=submit(store,user,devices)
    store.cancel(user,job['id'])
    first=store.claim_review()
    assert first['review_event']['kind']=='job_cancelled'
    assert store.claim_review() is None
    # A fresh Store instance sees the same live review lease.
    restarted=Store(store.root,clock=lambda:now[0])
    assert restarted.claim_review() is None
    event_id=first['review_event']['id']
    claim_id=first['plan']['review']['claim_id']
    assert not store.finish_review(job['id'],event_id,[],claim_id='wrong')
    store.finish_review(job['id'],event_id,[],error='Provider unavailable',claim_id=claim_id)
    assert store.claim_review() is None
    for attempt in (2,3):
        now[0]+=31
        claimed=store.claim_review()
        assert claimed['plan']['review']['attempts']==attempt
        store.finish_review(job['id'],event_id,[],error='Provider unavailable',claim_id=claimed['plan']['review']['claim_id'])
    now[0]+=1000
    assert restarted.claim_review() is None


def test_expired_and_replaced_review_claims_cannot_change_routing(grid):
    store,now,user,devices=grid
    job=submit(store,user,devices)
    task=store.claim(devices[1])['task']
    store.task_failed(devices[1],task['id'],task['lease_id'],'Model unavailable')
    first=store.claim_review()
    claim_id=first['plan']['review']['claim_id']
    scope={task['id']:1}
    now[0]+=151
    for device_id in devices:
        store.heartbeat(device_id,{})
    with pytest.raises(HTTPException) as expired:
        store.update_routing(user,job['id'],{'image_generate':[devices[1]]},scope,
                             'Expired decision',review_claim_id=claim_id)
    assert expired.value.status_code==409
    assert not store.finish_review(job['id'],first['review_event']['id'],[],claim_id=claim_id)
    second=store.claim_review()
    new_claim=second['plan']['review']['claim_id']
    assert new_claim!=claim_id
    store.update_routing(user,job['id'],{'image_generate':[devices[0]]},scope,
                         'Current decision',review_claim_id=new_claim)
    with pytest.raises(HTTPException) as replaced:
        store.update_routing(user,job['id'],{'image_generate':[devices[1]]},scope,
                             'Superseded decision',review_claim_id=claim_id)
    assert replaced.value.status_code==409
    current=store.existing_job(user,'request-001')
    assert current['plan']['task_routes'][task['id']]['device_ids']==[devices[0]]
    store.finish_review(job['id'],second['review_event']['id'],[],claim_id=new_claim)
    with pytest.raises(HTTPException) as finished:
        store.update_routing(user,job['id'],{'image_generate':[devices[1]]},scope,
                             'Already finished',review_claim_id=new_claim)
    assert finished.value.status_code==409


def test_terminal_result_review_is_claimed_once_and_contains_receipt(grid):
    store,now,user,devices=grid
    job=submit(store,user,devices)
    generation=store.claim(devices[1])['task']
    store.complete(devices[1],generation['id'],generation['lease_id'],png(),{})
    export=store.claim(devices[1])['task']
    store.complete(devices[1],export['id'],export['lease_id'],png(True),{})
    review=store.claim_review()
    assert review['review_event']['kind']=='job_completed'
    assert review['receipt']['total_charged']==8
    assert all(t['output_url'] for t in review['tasks'])
    store.finish_review(job['id'],review['review_event']['id'],[{'tool':'inspect_job'}],claim_id=review['plan']['review']['claim_id'])
    assert store.claim_review() is None
