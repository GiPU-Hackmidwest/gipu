import base64
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from services.coordinator.app import create_app
from services.coordinator.store import Store

LIMITS = {'cpu_threads':2,'max_pixels':262144,'session_minutes':30}


def png(framed=False, color='orange'):
    image = Image.new('RGB',(256,256),color)
    if framed:
        ImageDraw.Draw(image).rectangle((0,0,255,255),outline=(36,203,166),width=4)
    output = io.BytesIO()
    image.save(output,format='PNG')
    return base64.b64encode(output.getvalue()).decode()


@pytest.fixture
def setup(tmp_path):
    now = [1000.0]
    store = Store(tmp_path,clock=lambda:now[0])
    buyer = store.session('Buyer')['user']['id']
    seller = store.session('Contributor')['user']['id']
    def device(name='Laptop',capabilities=None):
        result = store.register(seller,name,'python',capabilities or ['image_generate','image_finalize'],LIMITS)
        store.change_device(seller,result['device']['id'],True)
        return result['device']['id']
    return store,now,buyer,seller,device


def request(key='request-001',count=1,budget=10):
    return {'prompt':'A cat riding a tiny bicycle','count':count,'width':256,'height':256,'steps':12,'budget':budget,'request_id':key}


def submit(store,buyer,**kwargs):
    return store.create_job(buyer,request(**kwargs),{'mode':'test','explanation':'Explicit deterministic test fixture'})


def accepted(store,device,task,framed=False):
    return store.complete(device,task['id'],task['lease_id'],png(framed),{'backend':'test-fixture'})


def test_conserved_credits_and_duplicate_completion(setup):
    store,now,buyer,seller,device = setup
    laptop = device()
    job = submit(store,buyer)
    assert store.snapshot(buyer)['balance'] == 90
    task = store.claim(laptop)['task']
    assert accepted(store,laptop,task)['earned'] == 6
    assert accepted(store,laptop,task)['duplicate'] is True
    export = store.claim(laptop)['task']
    assert export['kind'] == 'image_finalize'
    accepted(store,laptop,export,True)
    snapshot = store.snapshot(buyer)
    receipt = snapshot['jobs'][0]['receipt']
    assert receipt == {'budget':10,'contributor_total':7,'platform_fee':1,'refund':2,'total_charged':8}
    assert snapshot['balance'] == 92 and snapshot['reserved'] == 0
    assert store.snapshot(seller)['balance'] == 107
    assert snapshot['balance'] + store.snapshot(seller)['balance'] + receipt['platform_fee'] == 200
    assert len(snapshot['jobs'][0]['images']) == 2
    assert 'lease_id' not in snapshot['jobs'][0]['tasks'][0]


def test_disconnect_reassigns_and_rejects_late_result(setup):
    store,now,buyer,seller,device = setup
    first,second = device('First'),device('Second')
    submit(store,buyer)
    original = store.claim(first)['task']
    now[0] += 16
    store.tick()
    replacement = store.claim(second)['task']
    assert replacement['id'] == original['id']
    assert replacement['lease_id'] != original['lease_id']
    with pytest.raises(HTTPException) as error:
        accepted(store,first,original)
    assert error.value.status_code == 409
    accepted(store,second,replacement)
    assert store.snapshot(seller)['earned'] == 6


def test_pause_time_limit_and_pixel_limit_enforced(setup):
    store,now,buyer,seller,device = setup
    worker = device()
    submit(store,buyer)
    task = store.claim(worker)['task']
    store.change_device(seller,worker,False)
    assert store.claim(worker)['task'] is None
    assert store.heartbeat(worker,{},task['id'],task['lease_id'])['lease_valid'] is False
    store.change_device(seller,worker,True,dict(LIMITS,session_minutes=1))
    now[0] += 61
    store.tick()
    assert store.claim(worker)['device']['enabled'] is False


def test_idempotent_reservation_and_cancel(setup):
    store,now,buyer,seller,device = setup
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _:submit(store,buyer),range(5)))
    assert len({j['id'] for j in results}) == 1
    assert store.snapshot(buyer)['balance'] == 90
    job_id = results[0]['id']
    store.cancel(buyer,job_id)
    store.cancel(buyer,job_id)
    assert store.snapshot(buyer)['balance'] == 100


def test_shorter_active_session_limit_expires_from_original_start(setup):
    store,now,buyer,seller,device = setup
    worker = device()
    now[0] += 10
    changed = store.change_device(seller,worker,limits={'session_minutes':1})
    assert changed['session_expires_at'] == 1060
    now[0] = 1061
    store.tick()
    assert store.claim(worker)['device']['enabled'] is False


def test_partial_limit_patch_preserves_other_resource_caps(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        session = client.post('/api/sessions',json={'name':'a','join_code':'pocketgrid-demo'}).json()
        headers = {'Authorization':'Bearer '+session['token']}
        registration = {'name':'a','kind':'python','capabilities':['image_generate'],
                        'limits':{'cpu_threads':2,'max_pixels':65536,'session_minutes':5}}
        device = client.post('/api/devices',json=registration,headers=headers).json()['device']
        result = client.patch('/api/devices/'+device['id'],json={'limits':{'cpu_threads':1}},headers=headers).json()
        assert result['limits'] == {'cpu_threads':1,'max_pixels':65536,'session_minutes':5}


def test_rejects_forged_export_without_paying(setup):
    store,now,buyer,seller,device = setup
    worker = device()
    submit(store,buyer)
    accepted(store,worker,store.claim(worker)['task'])
    export = store.claim(worker)['task']
    with pytest.raises(HTTPException) as error:
        store.complete(worker,export['id'],export['lease_id'],png(True,'blue'),{})
    assert error.value.status_code == 422
    assert store.snapshot(seller)['earned'] == 6
    accepted(store,worker,export,True)


def test_cancel_after_partial_work_keeps_payment_and_refunds_rest(setup):
    store,now,buyer,seller,device = setup
    worker = device()
    job = submit(store,buyer)
    accepted(store,worker,store.claim(worker)['task'])
    cancelled = store.cancel(buyer,job['id'])
    assert cancelled['receipt']['refund'] == 4
    assert cancelled['receipt']['platform_fee'] == 0
    assert store.snapshot(buyer)['balance'] == 94
    assert store.snapshot(seller)['balance'] == 106


def test_bounded_retries_refund_and_survive_restart(setup):
    store,now,buyer,seller,device = setup
    worker = device()
    submit(store,buyer)
    for _ in range(4):
        task = store.claim(worker)['task']
        store.task_failed(worker,task['id'],task['lease_id'],'Model failed')
        now[0] += 6
    restarted = Store(store.root,clock=lambda:now[0])
    snapshot = restarted.snapshot(buyer)
    assert snapshot['jobs'][0]['status'] == 'failed'
    assert snapshot['balance'] == 100


def test_independent_devices_claim_different_variants(setup):
    store,now,buyer,seller,device = setup
    devices = [device(str(i)) for i in range(3)]
    submit(store,buyer,count=3,budget=25)
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = list(executor.map(lambda d:store.claim(d)['task'],devices))
    assert len({t['id'] for t in tasks}) == 3
    assert {t['variant'] for t in tasks} == {0,1,2}


def test_auth_limits_and_disabled_agent(tmp_path,monkeypatch):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE','manual')
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/api/state').status_code == 401
        assert client.post('/api/sessions',json={'name':'a','join_code':'wrong'}).status_code == 403
        session = client.post('/api/sessions',json={'name':'a','join_code':'pocketgrid-demo'}).json()
        headers = {'Authorization':f'Bearer {session["token"]}'}
        req = request()
        req['use_agent'] = True
        assert client.post('/api/jobs',json=req,headers=headers).status_code == 503
        assert client.get('/api/state',headers=headers).json()['balance'] == 100
        req['use_agent'] = False
        req['budget'] = 1
        assert client.post('/api/jobs',json=req,headers=headers).status_code == 422
        registration = {'name':'browser','kind':'browser','capabilities':['image_generate'],'limits':LIMITS}
        assert client.post('/api/devices',json=registration,headers=headers).status_code == 422
