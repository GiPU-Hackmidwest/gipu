"""Checks real pixel transformations and immediate cancellation boundaries."""
import importlib.util
import io
from pathlib import Path
import threading

import httpx
from PIL import Image
import pytest

spec = importlib.util.spec_from_file_location("pocketgrid_worker", Path(__file__).parents[1] / "workers/python/worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def source_png():
    original = Image.new("RGB", (32, 24))
    original.putdata([(x * 3 % 256, x * 7 % 256, x * 11 % 256) for x in range(32 * 24)])
    output = io.BytesIO()
    original.save(output, format="PNG")
    return original, output.getvalue()


def test_finalize_preserves_every_interior_pixel_and_frames_edges():
    original, source = source_png()
    result = Image.open(io.BytesIO(worker.finalize_image(source)))
    assert result.size == original.size
    for y in range(result.height):
        for x in range(result.width):
            expected = worker.FRAME if x < 4 or y < 4 or x >= result.width - 4 or y >= result.height - 4 else original.getpixel((x, y))
            assert result.getpixel((x, y)) == expected


def test_paused_work_cannot_produce_a_result():
    _, source = source_png()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(worker.WorkCancelled):
        worker.finalize_image(source, cancel)


def test_denoising_cancellation_never_emits_partial_completion():
    cancel = threading.Event()
    progress = []
    callback = worker.denoising_callback(cancel, 12, lambda *event: progress.append(event))
    state = {"latents": "sample"}
    assert callback(None, 0, None, state) is state
    cancel.set()
    with pytest.raises(worker.WorkCancelled):
        callback(None, 1, None, state)
    assert len(progress) == 1


def test_does_not_forward_device_token_to_external_artifact_server():
    device = worker.DeviceWorker("http://localhost:8787", {"token": "device-secret", "device_id": "a"}, None)
    try:
        with pytest.raises(ValueError, match="coordinator image"):
            device.source_bytes("https://example.org/api/images/1")
    finally:
        device.client.close()


def test_experimental_model_cannot_join_existing_untyped_grid(monkeypatch):
    import sys
    monkeypatch.setattr(sys, 'argv', ['worker.py', 'run', '--model', 'sd-turbo'])
    monkeypatch.setattr(worker.LocalRenderer, 'load', lambda *a, **k: pytest.fail('Must reject before downloading or joining'))
    with pytest.raises(SystemExit) as error:
        worker.main()
    assert error.value.code == 2


def test_renderer_cancels_before_calling_experimental_pipeline():
    renderer = worker.LocalRenderer('cpu', 'sd-turbo')
    renderer.pipeline = lambda **kwargs: pytest.fail('Cancelled work must not run inference')
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(worker.WorkCancelled):
        renderer.generate({'prompt': 'cat', 'width': 512, 'height': 512, 'steps': 4, 'seed': 42},
                          cancel, lambda *_: None, 2)


def test_unknown_model_is_rejected_without_downloading():
    with pytest.raises(ValueError, match='pinned'):
        worker.LocalRenderer('cpu', 'untrusted/arbitrary-model')


@pytest.fixture
def run_heartbeats(monkeypatch):
    """Exercise active leases with scripted HTTP replies and no wall-clock waits."""
    clients = []

    def run(outcomes):
        clock = [0.0]
        monkeypatch.setattr(worker.time, "monotonic", lambda: clock[0])
        device = worker.DeviceWorker("http://worker.test", {"token": "test-token", "device_id": "a"}, None)
        device.task = {"id": "task-a", "lease_id": "lease-a", "width": 256, "height": 256}
        device.task_threads = 2
        active_device = {
            "enabled": True, "session_expires_at": worker.time.time() + 60,
            "limits": {"cpu_threads": 2, "max_pixels": 65536},
        }
        replies = iter(outcomes)
        cancellations = []

        def respond(request):
            if request.url.path == "/api/devices/a/heartbeat":
                clock[0], outcome = next(replies)
                if isinstance(outcome, Exception):
                    raise outcome
                return httpx.Response(outcome, json={"device": active_device, "lease_valid": True})
            assert request.url.path == "/api/tasks/task-a/progress"
            return httpx.Response(200, json={"ok": True})

        def advance_loop(_seconds):
            cancellations.append(device.cancel.is_set())
            if len(cancellations) == len(outcomes):
                device.stop.set()

        device.client.close()
        device.client = httpx.Client(base_url=device.server, transport=httpx.MockTransport(respond))
        clients.append(device.client)
        monkeypatch.setattr(device.stop, "wait", advance_loop)
        device.heartbeat()
        return device, cancellations

    yield run
    for client in clients:
        client.close()


@pytest.mark.parametrize("status", [500, 503, 429])
def test_heartbeat_http_errors_cancel_at_confirmation_deadline(run_heartbeats, status):
    _, cancellations = run_heartbeats([(3, status), (6, status), (8.9, status), (9, status)])
    assert cancellations == [False, False, False, True]


def test_successful_heartbeat_resets_confirmation_deadline(run_heartbeats):
    device, cancellations = run_heartbeats([(6, 503), (8, 200), (9, 503), (16.9, 503), (17, 503)])
    assert device.last_heartbeat == 8
    assert cancellations == [False, False, False, False, True]


@pytest.mark.parametrize("status", [401, 403, 404, 409])
def test_heartbeat_rejection_cancels_without_waiting_for_deadline(run_heartbeats, status):
    _, cancellations = run_heartbeats([(1, status)])
    assert cancellations == [True]


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
def test_heartbeat_transport_errors_keep_confirmation_deadline(run_heartbeats, error_type):
    _, cancellations = run_heartbeats([
        (3, error_type("Coordinator unavailable")),
        (8.9, error_type("Coordinator unavailable")),
        (9, error_type("Coordinator unavailable")),
    ])
    assert cancellations == [False, False, True]


def test_lost_heartbeat_cancels_at_next_denoising_callback(run_heartbeats):
    device, _ = run_heartbeats([(9, 503)])
    progress = []
    callback = worker.denoising_callback(device.cancel, 12, lambda *event: progress.append(event))
    with pytest.raises(worker.WorkCancelled):
        callback(None, 0, None, {})
    assert progress == []
