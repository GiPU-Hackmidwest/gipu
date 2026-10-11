"""Exercise the real Strands OpenAI adapter over a simulated workshop HTTP API."""
import json

import httpx
import openai
import pytest
from fastapi import HTTPException

from services.coordinator import agent
from tests.test_agent import current, plan
from tests.test_coordinator import request
from tests.test_routing import grid


def configure(monkeypatch):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE','akamai')
    monkeypatch.setenv('AKAMAI_API_KEY','test-only-key')
    monkeypatch.setenv('AKAMAI_BASE_URL','https://workshop.example/v1')
    monkeypatch.setenv('AKAMAI_CHAT_MODEL','hackathon-chat')


def test_akamai_http_tool_calls_create_real_selected_route(grid,monkeypatch):
    store,now,user,devices=grid
    configure(monkeypatch)
    calls=[]
    def endpoint(req):
        assert str(req.url)=='https://workshop.example/v1/chat/completions'
        assert req.headers['authorization']=='Bearer test-only-key'
        body=json.loads(req.content)
        assert body['model']=='hackathon-chat' and body['stream'] is False
        name=body['tools'][0]['function']['name']
        calls.append(name)
        args=({'explanation':'Use B','generation_device_ids':[devices[1]],
               'finalize_device_ids':[devices[1]]} if name=='submit_job' else {})
        return httpx.Response(200,json={'id':'test-chat','object':'chat.completion','created':0,
            'model':'hackathon-chat','choices':[{'index':0,'finish_reason':'tool_calls',
            'message':{'role':'assistant','content':None,'tool_calls':[{'id':f'call-{len(calls)}',
            'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}],
            'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
    original_client=openai.AsyncOpenAI
    def client(**kwargs):
        return original_client(**kwargs,http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)))
    monkeypatch.setattr(openai,'AsyncOpenAI',client)
    job=plan(store,user,dict(request(),use_agent=True))
    assert job['plan']['mode']=='strands-akamai'
    assert calls==['inspect_devices','quote_job','submit_job','inspect_job']
    assert store.claim(devices[0])['task'] is None
    assert store.claim(devices[1])['task']['job_id']==job['id']
    assert 'test-only-key' not in json.dumps(job)
    store.cancel(user,job['id'])
    assert agent.review_once(store)
    assert store.snapshot(user)['jobs'][0]['plan']['review']['status']=='done'


def test_missing_akamai_key_never_reserves_budget(grid,monkeypatch):
    store,now,user,devices=grid
    configure(monkeypatch)
    monkeypatch.delenv('AKAMAI_API_KEY')
    with pytest.raises(HTTPException) as exc:
        agent.dispatch(store,user,dict(request(),use_agent=True))
    assert exc.value.status_code==503
    assert store.snapshot(user)['balance']==100
    assert not store.snapshot(user)['jobs']


def test_akamai_auth_failure_is_not_retried_or_exposed(grid,monkeypatch):
    store,now,user,devices=grid
    configure(monkeypatch)
    calls=[]
    def endpoint(req):
        calls.append(req)
        return httpx.Response(401,json={'error':{'message':'private provider details test-only-key'}})
    original_client=openai.AsyncOpenAI
    def client(**kwargs):
        return original_client(**kwargs,http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)))
    monkeypatch.setattr(openai,'AsyncOpenAI',client)
    job=plan(store,user,dict(request(),use_agent=True))
    assert len(calls)==1
    assert job['status']=='failed' and job['plan']['dispatch_error']=='AuthenticationError'
    assert 'test-only-key' not in json.dumps(store.snapshot(user))
    assert store.snapshot(user)['balance']==100
