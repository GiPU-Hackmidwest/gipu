import base64
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from services.coordinator import cloud_images
from services.coordinator.app import create_app
from tests.test_coordinator import LIMITS, png, request


def cloud_png(size=512, color='purple'):
    out = io.BytesIO()
    Image.new('RGB', (size, size), color).save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv('AKAMAI_API_KEY', 'test-key')
    monkeypatch.setenv('AKAMAI_BASE_URL', 'https://images.test/v1')
    monkeypatch.delenv('POCKETGRID_IMAGE_GENERATOR', raising=False)


def test_hosted_image_is_requested_once_and_resized_to_the_task(key):
    seen = []
    def handler(req):
        seen.append(req)
        return httpx.Response(200, json={'data': [{'b64_json': cloud_png()}]})
    data = cloud_images.generate('a cat on a bicycle', 256, 256, 123, transport=httpx.MockTransport(handler))
    image = Image.open(io.BytesIO(data))
    assert image.format == 'PNG' and image.size == (256, 256)
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == 'https://images.test/v1/images/generations'
    assert seen[0].headers['authorization'] == 'Bearer test-key'
    assert body == {'model': 'hackathon-image', 'prompt': 'a cat on a bicycle', 'size': '512x512', 'n': 1,
                    'response_format': 'b64_json', 'seed': 123}


def test_rate_limit_waits_for_the_reset_then_succeeds(key):
    replies = iter([httpx.Response(429, headers={'x-ratelimit-reset': '7'}),
                    httpx.Response(200, json={'data': [{'b64_json': cloud_png()}]})])
    waits = []
    data = cloud_images.generate('x', 512, 512, 1, transport=httpx.MockTransport(lambda req: next(replies)), sleep=waits.append)
    assert waits == [7.0] and Image.open(io.BytesIO(data)).size == (512, 512)


def test_unconfigured_busy_and_failing_service_are_reported(key, monkeypatch):
    always_busy = httpx.MockTransport(lambda req: httpx.Response(429, headers={'x-ratelimit-reset': '30'}))
    with pytest.raises(cloud_images.CloudUnavailable, match='busy'):
        cloud_images.generate('x', 512, 512, 1, transport=always_busy, sleep=lambda s: None, budget_seconds=40)
    with pytest.raises(cloud_images.CloudUnavailable, match='500'):
        cloud_images.generate('x', 512, 512, 1, transport=httpx.MockTransport(lambda req: httpx.Response(500)))
    monkeypatch.delenv('AKAMAI_API_KEY')
    with pytest.raises(cloud_images.CloudUnavailable, match='not configured'):
        cloud_images.generate('x', 512, 512, 1)
    monkeypatch.setenv('POCKETGRID_IMAGE_GENERATOR', 'cloud')  # Forced on without a key.
    assert cloud_images.status() == {'mode': 'cloud', 'model': 'akamai/hackathon-image', 'available': False}


@pytest.fixture
def grid(tmp_path, monkeypatch, key):
    monkeypatch.setenv('POCKETGRID_AGENT_MODE', 'manual')
    calls = []
    def fake_generate(prompt, width, height, seed):
        calls.append((prompt, width, height, seed))
        return base64.b64decode(png())  # The same 256px PNG the coordinator tests use.
    monkeypatch.setattr(cloud_images, 'generate', fake_generate)
    with TestClient(create_app(tmp_path)) as client:
        def join(name):
            s = client.post('/api/sessions', json={'join_code': 'pocketgrid-demo', 'name': name}).json()
            return {'Authorization': f'Bearer {s["token"]}'}
        buyer, seller = join('Buyer'), join('Seller')
        laptop = client.post('/api/devices', json={'name': 'Laptop', 'kind': 'python', 'capabilities': ['image_generate', 'image_finalize'], 'limits': LIMITS}, headers=seller).json()
        client.patch(f'/api/devices/{laptop["device"]["id"]}', json={'enabled': True}, headers=seller)
        yield client, buyer, laptop['device']['id'], {'Authorization': f'Bearer {laptop["token"]}'}, calls


def test_worker_gets_cloud_pixels_and_images_are_labelled(grid):
    client, buyer, laptop, device_auth, calls = grid
    assert client.get('/api/health').json()['generation'] == {'mode': 'cloud', 'model': 'akamai/hackathon-image', 'available': True}
    client.post('/api/jobs', json=request(), headers=buyer)
    task = client.post(f'/api/devices/{laptop}/claim', headers=device_auth).json()['task']
    reply = client.post(f'/api/tasks/{task["id"]}/cloud-image', json={'lease_id': task['lease_id']}, headers=device_auth)
    assert reply.status_code == 200 and reply.json()['model'] == 'akamai/hackathon-image'
    assert calls == [(task['prompt'], 256, 256, task['seed'])]
    done = client.post(f'/api/tasks/{task["id"]}/complete', json={'lease_id': task['lease_id'], 'png_base64': reply.json()['png_base64'], 'metrics': {}}, headers=device_auth)
    assert done.json()['accepted']
    export = client.post(f'/api/devices/{laptop}/claim', headers=device_auth).json()['task']
    client.post(f'/api/tasks/{export["id"]}/complete', json={'lease_id': export['lease_id'], 'png_base64': png(), 'metrics': {}}, headers=device_auth)
    state = client.get('/api/state', headers=buyer).json()
    assert state['generation']['mode'] == 'cloud'
    images = state['jobs'][0]['images']
    assert {(i['stage'], i['generated_in'], i.get('model')) for i in images} == {
        ('image_generate', 'cloud', 'akamai/hackathon-image'), ('image_finalize', 'cloud', 'akamai/hackathon-image')}
    assert state['jobs'][0]['status'] == 'completed'


def test_cloud_images_need_a_live_generation_lease(grid):
    client, buyer, laptop, device_auth, calls = grid
    client.post('/api/jobs', json=request(), headers=buyer)
    task = client.post(f'/api/devices/{laptop}/claim', headers=device_auth).json()['task']
    assert client.post(f'/api/tasks/{task["id"]}/cloud-image', json={'lease_id': 'stale'}, headers=device_auth).status_code == 409
    client.post(f'/api/tasks/{task["id"]}/complete', json={'lease_id': task['lease_id'], 'png_base64': png(), 'metrics': {}}, headers=device_auth)
    export = client.post(f'/api/devices/{laptop}/claim', headers=device_auth).json()['task']
    assert client.post(f'/api/tasks/{export["id"]}/cloud-image', json={'lease_id': export['lease_id']}, headers=device_auth).status_code == 422
    assert calls == []
    images = client.get('/api/state', headers=buyer).json()['jobs'][0]['images']
    assert all(i['generated_in'] == 'device' for i in images)


def test_service_failures_and_local_mode(grid, monkeypatch):
    client, buyer, laptop, device_auth, calls = grid
    client.post('/api/jobs', json=request(), headers=buyer)
    task = client.post(f'/api/devices/{laptop}/claim', headers=device_auth).json()['task']
    def down(*args):
        raise cloud_images.CloudUnavailable('Cloud image service returned 500')
    monkeypatch.setattr(cloud_images, 'generate', down)
    reply = client.post(f'/api/tasks/{task["id"]}/cloud-image', json={'lease_id': task['lease_id']}, headers=device_auth)
    assert reply.status_code == 503 and '500' in reply.json()['detail']
    monkeypatch.setenv('POCKETGRID_IMAGE_GENERATOR', 'local')
    assert client.get('/api/health').json()['generation']['mode'] == 'local'
    assert client.post(f'/api/tasks/{task["id"]}/cloud-image', json={'lease_id': task['lease_id']}, headers=device_auth).status_code == 409


def test_cloud_is_the_default_only_when_a_key_is_configured(monkeypatch):
    monkeypatch.delenv('POCKETGRID_IMAGE_GENERATOR', raising=False)
    monkeypatch.delenv('AKAMAI_API_KEY', raising=False)
    assert cloud_images.mode() == 'local' and cloud_images.status()['model'] == 'segmind/tiny-sd'
    monkeypatch.setenv('AKAMAI_API_KEY', 'k')
    assert cloud_images.mode() == 'cloud'
    monkeypatch.setenv('POCKETGRID_IMAGE_GENERATOR', 'local')
    assert cloud_images.mode() == 'local'
