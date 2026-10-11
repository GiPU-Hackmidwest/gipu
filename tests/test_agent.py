"""Real Strands SDK tool-loop tests with a scripted model; no live inference claims."""
import json

import pytest
from fastapi import HTTPException
from strands import tool
from strands.models.model import Model

from services.coordinator import agent
from tests.test_coordinator import png, request
from tests.test_routing import grid, submit


class ScriptedModel(Model):
    """Emit SDK streaming events deterministically so actual tool execution is exercised."""
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = 0
        self.config = {'model_id': 'scripted-test', 'context_window_limit': 32768}

    def update_config(self, **model_config):
        self.config.update(model_config)

    def get_config(self):
        return self.config

    async def structured_output(self, *args, **kwargs):
        raise NotImplementedError
        yield  # The Model interface requires an async generator.

    async def stream(self, messages, *args, **kwargs):
        step = self.steps[self.calls] if self.calls < len(self.steps) else []
        self.calls += 1
        if callable(step):
            step = step()
        if isinstance(step, Exception):
            raise step
        yield {'messageStart': {'role': 'assistant'}}
        for index, (name, arguments) in enumerate(step):
            yield {'contentBlockStart': {'contentBlockIndex': index,
                   'start': {'toolUse': {'toolUseId': f'tool-{self.calls}-{index}', 'name': name}}}}
            yield {'contentBlockDelta': {'contentBlockIndex': index,
                   'delta': {'toolUse': {'input': json.dumps(arguments)}}}}
            yield {'contentBlockStop': {'contentBlockIndex': index}}
        if not step:
            yield {'contentBlockStart': {'contentBlockIndex': 0, 'start': {}}}
            yield {'contentBlockDelta': {'contentBlockIndex': 0, 'delta': {'text': 'Checked.'}}}
            yield {'contentBlockStop': {'contentBlockIndex': 0}}
        yield {'messageStop': {'stopReason': 'tool_use' if step else 'end_turn'}}
        yield {'metadata': {'usage': {'inputTokens': 1, 'outputTokens': 1, 'totalTokens': 2},
                            'metrics': {'latencyMs': 0}}}


def response(name, **kwargs):
    return [(name, kwargs)]


def use_model(monkeypatch, steps):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    model = ScriptedModel(steps)
    modes = []
    def factory(mode):
        modes.append(mode)
        return model
    monkeypatch.setattr(agent, '_model', factory)
    return model, modes


def current(store, job_id):
    with store.tx() as db:
        return store.job(db, job_id)


def plan(store, user, req):
    """Accept the request, then run the background planner once."""
    accepted = agent.dispatch(store, user, req)
    assert accepted['status'] == 'planning' and not accepted['tasks']
    assert agent.plan_once(store)
    return current(store, accepted['id'])


def test_sdk_dispatch_routes_to_selected_device_and_is_idempotent(grid, monkeypatch):
    store, now, user, devices = grid
    model, modes = use_model(monkeypatch, [response('inspect_devices'), response('quote_job'),
        response('submit_job', explanation='Select B', generation_device_ids=[devices[1]],
                 finalize_device_ids=[devices[1]]), response('inspect_job')])
    req = dict(request(), use_agent=True)
    job = plan(store, user, req)
    assert modes == ['ollama'] and job['plan']['planning']['status'] == 'done'
    assert job['status'] == 'queued' and len(job['tasks']) == 1
    assert [t['tool'] for t in job['plan']['tools']] == ['inspect_devices', 'quote_job', 'submit_job', 'inspect_job']
    assert {d['id'] for d in job['plan']['tools'][0]['result']['devices']} == set(devices)
    assert store.claim(devices[0])['task'] is None
    assert store.claim(devices[1])['task']['job_id'] == job['id']
    assert agent.dispatch(store, user, req)['id'] == job['id']
    assert model.calls == 4
    assert store.snapshot(user)['balance'] == 90


def test_bad_model_selection_cannot_reserve_or_change_authorized_request(grid, monkeypatch):
    store, now, user, devices = grid
    use_model(monkeypatch, [response('inspect_devices'), response('quote_job'),
        response('submit_job', explanation='Invented target', generation_device_ids=['not-a-device'],
                 finalize_device_ids=[devices[1]])])
    job = plan(store, user, dict(request(), use_agent=True))
    assert job['status'] == 'failed' and not job['tasks']
    assert job['receipt'] == {'budget': 10, 'contributor_total': 0, 'platform_fee': 0, 'refund': 10, 'total_charged': 0}
    assert store.snapshot(user)['balance'] == 100


def test_provider_failure_after_submit_preserves_reservation_and_trace(grid, monkeypatch):
    store, now, user, devices = grid
    model, _ = use_model(monkeypatch, [response('inspect_devices'), response('quote_job'),
        response('submit_job', explanation='Select B', generation_device_ids=[devices[1]],
                 finalize_device_ids=[devices[1]]), RuntimeError('Secret provider body is not recorded')])
    job = plan(store, user, dict(request(), use_agent=True))
    assert job['status'] == 'queued'

    assert job['plan']['dispatch_error'] == 'RuntimeError'
    assert store.snapshot(user)['balance'] == 90
    assert 'Secret provider' not in json.dumps(job)
    assert model.calls == 4  # No automatic provider retries.


def test_sdk_failure_review_changes_real_routing_and_checks_it(grid, monkeypatch):
    store, now, user, devices = grid
    job = submit(store, user, devices)
    first = store.claim(devices[1])['task']
    store.task_failed(devices[1], first['id'], first['lease_id'], 'GPU unavailable')
    model, modes = use_model(monkeypatch, [response('inspect_job'), response('inspect_devices'),
        response('update_routing', generation_device_ids=[devices[0]], finalize_device_ids=[],
                 explanation='Move the failed image to A'), response('inspect_job')])
    assert agent.review_once(store)
    updated = store.snapshot(user)['jobs'][0]
    assert updated['plan']['review']['status'] == 'done'
    assert updated['plan']['task_routes'][first['id']]['device_ids'] == [devices[0]]
    trace = updated['plan']['reviews'][-1]['tools']
    assert trace[-1]['tool'] == 'inspect_job'
    assert trace[-1]['result']['task_routes'][first['id']]['device_ids'] == [devices[0]]
    assert modes == ['ollama'] and model.calls == 4
    assert not agent.review_once(store)
    retry = store.claim(devices[0])['task']
    assert retry['id'] == first['id'] and retry['lease_id'] != first['lease_id']
    with pytest.raises(HTTPException) as stale:
        store.complete(devices[1], first['id'], first['lease_id'], png(), {})
    assert stale.value.status_code == 409
    store.complete(devices[0], retry['id'], retry['lease_id'], png(), {})
    assert store.snapshot(user)['earned'] == 6


def test_sdk_terminal_review_checks_actual_receipt_without_rerouting(grid, monkeypatch):
    store, now, user, devices = grid
    submit(store, user, devices)
    generation = store.claim(devices[1])['task']
    store.complete(devices[1], generation['id'], generation['lease_id'], png(), {})
    export = store.claim(devices[1])['task']
    store.complete(devices[1], export['id'], export['lease_id'], png(True), {})
    previous_routes = store.snapshot(user)['jobs'][0]['plan'].get('task_routes', {})
    model, _ = use_model(monkeypatch, [response('inspect_job')])
    assert agent.review_once(store)
    job = store.snapshot(user)['jobs'][0]
    review = job['plan']['reviews'][-1]
    assert review['status'] == 'done'
    assert review['tools'][0]['result']['receipt']['total_charged'] == 8
    assert all(t['output_url'] for t in review['tools'][0]['result']['tasks'])
    assert job['plan'].get('task_routes', {}) == previous_routes
    assert not agent.review_once(store)
    assert model.calls == 1


def test_stale_sdk_review_cannot_change_running_work(grid, monkeypatch):
    store, now, user, devices = grid
    submit(store, user, devices)
    first = store.claim(devices[1])['task']
    store.task_failed(devices[1], first['id'], first['lease_id'], 'Disconnected')
    replacement = []
    def advance_before_tool():
        store.change_device(user, devices[1], False)
        replacement.append(store.claim(devices[0])['task'])
        return response('update_routing', generation_device_ids=[devices[1]], finalize_device_ids=[],
                        explanation='This observation is stale')
    use_model(monkeypatch, [response('inspect_job'), response('inspect_devices'),
                           advance_before_tool, response('inspect_job')])
    assert agent.review_once(store)
    job = store.snapshot(user)['jobs'][0]
    errors = [t for t in job['plan']['reviews'][-1]['tools'] if t['tool'] == 'update_routing']
    assert errors[0]['result']['status_code'] == 409
    assert job['tasks'][0]['device_id'] == devices[0] and job['tasks'][0]['attempts'] == 2
    assert replacement[0]['id'] == first['id']
    assert job['plan']['review']['status'] == 'done'  # Re-inspection honestly observed that it advanced.


def test_review_missing_inspection_is_visible_and_manual_mode_never_calls_model(grid, monkeypatch):
    store, now, user, devices = grid
    job = submit(store, user, devices)
    store.cancel(user, job['id'])
    model, _ = use_model(monkeypatch, [[]])
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    assert not agent.review_once(store)
    assert model.calls == 0
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'bedrock')
    assert not agent.review_once(store)  # Never substitute the provider of a historical job.
    assert model.calls == 0
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'ollama')
    assert agent.review_once(store)
    review = store.snapshot(user)['jobs'][0]['plan']['review']
    assert review['status'] == 'error' and 'without inspecting' in review['error']


def test_sdk_tool_budget_cancels_excess_calls_in_single_model_batch(monkeypatch):
    hits = []
    @tool
    def count_call() -> dict:
        """Count an actual tool execution in the test."""
        hits.append(True)
        return {'count': len(hits)}
    model, _ = use_model(monkeypatch, [[('count_call', {}) for _ in range(20)]])
    agent._run('ollama', [count_call], 'Test the execution bound.', 'Run the scripted calls.')
    assert len(hits) == agent.MAX_CALLS
    assert model.calls == 1


def test_sdk_provider_error_is_not_retried(monkeypatch):
    model, _ = use_model(monkeypatch, [RuntimeError('provider unavailable')])
    with pytest.raises(RuntimeError):
        agent._run('ollama', [], 'Test no retry.', 'Run.')
    assert model.calls == 1


def test_sdk_stops_a_model_that_keeps_requesting_tools(monkeypatch):
    hits = []
    @tool
    def keep_going() -> dict:
        """Exercise the runaway-model budget."""
        hits.append(True)
        return {'ok': True}
    model, _ = use_model(monkeypatch, [response('keep_going') for _ in range(40)])
    agent._run('ollama', [keep_going], 'Test bounded execution.', 'Run.')
    assert model.calls == agent.MAX_CALLS
    assert len(hits) == agent.MAX_CALLS


def test_corrective_continuations_finish_real_tools_after_early_model_end(grid, monkeypatch):
    store, now, user, devices = grid
    model, modes = use_model(monkeypatch, [response('inspect_devices'), [],
        response('quote_job'), [], response('submit_job', explanation='Selected B',
        generation_device_ids=[devices[1]], finalize_device_ids=[devices[1]]), [],
        response('inspect_job'), []])
    job = plan(store, user, dict(request(), use_agent=True))
    assert model.calls == 7 and modes == ['ollama']
    assert 'dispatch_error' not in job['plan']
    assert store.claim(devices[0])['task'] is None
    assert store.claim(devices[1])['task']['job_id'] == job['id']


def test_corrective_continuations_share_the_same_model_budget(grid, monkeypatch):
    store, now, user, devices = grid
    model, modes = use_model(monkeypatch, [[] for _ in range(40)])
    job = plan(store, user, dict(request(), use_agent=True))
    assert model.calls == agent.MAX_CALLS and modes == ['ollama']
    assert job['status'] == 'failed' and not job['tasks']
    assert store.snapshot(user)['balance'] == 100


@pytest.mark.parametrize('valid', [True, False])
def test_ollama_stringified_arrays_preserve_ids_and_still_use_store_validation(grid, monkeypatch, valid):
    store, now, user, devices = grid
    selected = [devices[1]] if valid else ['invented-device']
    model, _ = use_model(monkeypatch, [response('inspect_devices'), response('quote_job'),
        response('submit_job', explanation='Transport encoding test',
                 generation_device_ids=json.dumps(selected), finalize_device_ids=json.dumps([devices[1]])),
        response('inspect_job')])
    job = plan(store, user, dict(request(), use_agent=True))
    if valid:
        assert job['plan']['routes']['image_generate'] == selected
        assert job['plan']['tools'][2]['input']['image_generate'] == selected
        assert store.claim(devices[0])['task'] is None
        assert store.claim(devices[1])['task']['job_id'] == job['id']
    else:
        assert job['status'] == 'failed' and not job['tasks']
        assert store.snapshot(user)['balance'] == 100
