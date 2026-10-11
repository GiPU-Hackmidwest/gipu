"""Checks real pixel transformations and immediate cancellation boundaries."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

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


def test_finalize_returns_every_pixel_unchanged_with_no_border():
    original, source = source_png()
    result = Image.open(io.BytesIO(worker.finalize_image(source)))
    assert result.format == "PNG" and result.size == original.size
    assert result.convert("RGB").tobytes() == original.tobytes()


def test_finalize_refuses_a_non_png_source():
    original, _ = source_png()
    jpeg = io.BytesIO()
    original.save(jpeg, format="JPEG")
    with pytest.raises(ValueError):
        worker.finalize_image(jpeg.getvalue())


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


@pytest.fixture
def registration_args(tmp_path):
    return SimpleNamespace(
        identity=str(tmp_path / "desktop-device.json"), server="http://worker.test",
        session_token="owner-secret", name="Test owner", join_code="test-join-code",
        device_name="Test laptop", generate_only=True, share=False, connect_paused=False,
        cpu_threads=2, max_pixels=262144, session_minutes=30,
    )


def saved_identity(args):
    identity = {
        "server": args.server, "device_id": "device-a", "token": "device-secret",
        "owner_token": "owner-secret", "generates": True, "generate_only": True,
    }
    worker.save_identity(Path(args.identity), identity)
    return identity


@pytest.fixture
def mock_registration_http(monkeypatch):
    client_class = httpx.Client

    def install(handler):
        requests = []

        def respond(request):
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(worker.httpx, "Client", lambda **kwargs: client_class(
            **kwargs, transport=httpx.MockTransport(respond)))
        return requests

    return install


def test_connect_paused_registers_and_explicitly_disables_new_device(registration_args, mock_registration_http):
    args = registration_args
    args.connect_paused = True

    def respond(request):
        assert request.headers["Authorization"] == "Bearer owner-secret"
        if request.method == "POST":
            assert request.url.path == "/api/devices"
            assert json.loads(request.content)["capabilities"] == ["image_generate"]
            return httpx.Response(200, json={"device": {"id": "device-a", "enabled": False}, "token": "device-secret"})
        assert (request.method, request.url.path) == ("PATCH", "/api/devices/device-a")
        assert json.loads(request.content) == {"enabled": False}
        return httpx.Response(200, json={"device": {"id": "device-a", "enabled": False}})

    requests = mock_registration_http(respond)
    identity = worker.register(args, worker.LocalRenderer("cpu"))
    assert [request.method for request in requests] == ["POST", "PATCH"]
    assert json.loads(Path(args.identity).read_text()) == identity
    assert Path(args.identity).stat().st_mode & 0o777 == 0o600


def test_connect_paused_disables_previously_enabled_identity_before_return(registration_args, mock_registration_http):
    args = registration_args
    expected = saved_identity(args)
    args.session_token = None  # Reuse the persisted owner credential.
    args.connect_paused = True
    state = {"enabled": True}

    def respond(request):
        assert (request.method, request.url.path) == ("PATCH", "/api/devices/device-a")
        assert request.headers["Authorization"] == "Bearer owner-secret"
        assert json.loads(request.content) == {"enabled": False}
        state.update(json.loads(request.content))
        return httpx.Response(200, json={"device": state})

    requests = mock_registration_http(respond)
    assert worker.register(args, worker.LocalRenderer("cpu")) == expected
    assert not state["enabled"]
    assert len(requests) == 1
    assert json.loads(Path(args.identity).read_text()) == expected


def test_share_and_connect_paused_conflict_before_loading_or_network(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["worker.py", "run", "--share", "--connect-paused", "--identity", str(tmp_path / "new.json")])
    monkeypatch.setattr(worker.LocalRenderer, "load", lambda *a, **k: pytest.fail("Conflicting options must not load a model"))
    monkeypatch.setattr(worker.httpx, "Client", lambda *a, **k: pytest.fail("Conflicting options must not contact the coordinator"))
    with pytest.raises(SystemExit) as error:
        worker.main()
    assert error.value.code == 2
    assert not (tmp_path / "new.json").exists()


@pytest.mark.parametrize("sharing_option", [[], ["--share"], ["--connect-paused"]])
def test_owner_mismatch_rejected_before_model_load_network_or_mutation(monkeypatch, registration_args, sharing_option):
    args = registration_args
    saved_identity(args)
    before = Path(args.identity).read_bytes()
    monkeypatch.setattr(sys, "argv", [
        "worker.py", "run", "--server", args.server, "--identity", args.identity,
        "--session-token", "other-owner-secret", "--generate-only", *sharing_option,
    ])
    monkeypatch.setattr(worker.LocalRenderer, "load", lambda *a, **k: pytest.fail("Owner mismatch must not download a model"))
    monkeypatch.setattr(worker.httpx, "Client", lambda *a, **k: pytest.fail("Owner mismatch must not contact the coordinator"))
    monkeypatch.setattr(worker, "save_identity", lambda *a, **k: pytest.fail("Owner mismatch must not change the identity"))
    with pytest.raises(ValueError, match="different owner session.*new --identity") as error:
        worker.main()
    assert "owner-secret" not in str(error.value)
    assert Path(args.identity).read_bytes() == before


def test_register_also_rejects_owner_mismatch_before_network(monkeypatch, registration_args):
    args = registration_args
    saved_identity(args)
    args.session_token = "other-owner-secret"
    monkeypatch.setattr(worker.httpx, "Client", lambda *a, **k: pytest.fail("Owner mismatch must not contact the coordinator"))
    with pytest.raises(ValueError, match="different owner session.*new --identity"):
        worker.register(args, worker.LocalRenderer("cpu"))


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("share", [False, True])
def test_ordinary_registration_preserves_explicit_sharing_and_restart_behavior(
        registration_args, mock_registration_http, existing, share):
    args = registration_args
    args.share = share
    if existing:
        saved_identity(args)
    state = {"id": "device-a", "enabled": existing}

    def respond(request):
        assert request.headers["Authorization"] == "Bearer owner-secret"
        if request.method == "POST":
            assert not existing
            assert request.url.path == "/api/devices"
            return httpx.Response(200, json={"device": state, "token": "device-secret"})
        assert share
        assert (request.method, request.url.path) == ("PATCH", "/api/devices/device-a")
        assert json.loads(request.content) == {
            "enabled": True,
            "limits": {"cpu_threads": 2, "max_pixels": 262144, "session_minutes": 30},
        }
        state.update(json.loads(request.content))
        return httpx.Response(200, json={"device": state})

    requests = mock_registration_http(respond)
    worker.register(args, worker.LocalRenderer("cpu"))
    assert state["enabled"] is (existing or share)
    assert [request.method for request in requests] == ([] if existing else ["POST"]) + (["PATCH"] if share else [])


@pytest.mark.parametrize("pause_status", [200, 403, 503])
def test_native_readiness_requires_loaded_model_and_confirmed_pause(
        monkeypatch, registration_args, mock_registration_http, capsys, pause_status):
    args = registration_args
    events = []

    def load(renderer, cpu_threads, local_only):
        assert cpu_threads == 2
        assert local_only is True
        renderer.backend = "cpu"
        events.append("model loaded")

    def respond(request):
        assert events[0] == "model loaded"
        if request.method == "POST":
            assert request.url.path == "/api/devices"
            events.append("registered")
            return httpx.Response(200, json={"device": {"id": "device-a"}, "token": "device-secret"})
        assert (request.method, request.url.path) == ("PATCH", "/api/devices/device-a")
        assert request.headers["Authorization"] == "Bearer owner-secret"
        assert json.loads(request.content) == {"enabled": False}
        events.append("pause confirmed" if pause_status == 200 else "pause failed")
        return httpx.Response(pause_status, json={"device": {"id": "device-a", "enabled": False}})

    class ReadyWorker:
        def __init__(self, server, identity, renderer):
            assert pause_status == 200
            self.stop = threading.Event()
            self.cancel = threading.Event()

        def run(self):
            output = capsys.readouterr().out
            lines = output.splitlines()
            assert len(lines) == 1
            assert lines[0].startswith("POCKETGRID_READY ")
            assert json.loads(lines[0].removeprefix("POCKETGRID_READY ")) == {
                "device_id": "device-a", "backend": "cpu", "model": "segmind/tiny-sd",
            }
            assert all(secret not in output for secret in ["owner-secret", "device-secret", "owner_token", "token"])
            assert events == ["model loaded", "registered", "pause confirmed"]
            events.append("work loop")

    mock_registration_http(respond)
    monkeypatch.setattr(worker.LocalRenderer, "load", load)
    monkeypatch.setattr(worker, "DeviceWorker", ReadyWorker)
    monkeypatch.setattr(worker.signal, "signal", lambda *a: None)
    monkeypatch.setattr(sys, "argv", [
        "worker.py", "run", "--generate-only", "--connect-paused", "--local-only",
        "--server", args.server, "--identity", args.identity, "--session-token", args.session_token,
    ])
    if pause_status == 200:
        worker.main()
        assert events[-1] == "work loop"
    else:
        with pytest.raises(httpx.HTTPStatusError):
            worker.main()
        assert "POCKETGRID_READY" not in capsys.readouterr().out
        assert events[-1] == "pause failed"


def test_model_load_failure_never_registers_or_reports_ready(monkeypatch, registration_args, capsys):
    args = registration_args

    def unavailable(*a, **k):
        raise RuntimeError("Cached model is unavailable")

    monkeypatch.setattr(worker.LocalRenderer, "load", unavailable)
    monkeypatch.setattr(worker.httpx, "Client", lambda *a, **k: pytest.fail("Model must load before registration"))
    monkeypatch.setattr(sys, "argv", [
        "worker.py", "run", "--generate-only", "--connect-paused", "--local-only",
        "--server", args.server, "--identity", args.identity, "--session-token", args.session_token,
    ])
    with pytest.raises(RuntimeError, match="Cached model"):
        worker.main()
    assert "POCKETGRID_READY" not in capsys.readouterr().out
    assert not Path(args.identity).exists()


def test_cloud_renderer_asks_the_coordinator_under_the_lease():
    sent = []
    def handler(req):
        sent.append(req)
        return httpx.Response(200, json={"png_base64": base64.b64encode(b"PNGDATA").decode(), "model": "akamai/hackathon-image"})
    renderer = worker.CloudRenderer()
    renderer.client = httpx.Client(base_url="http://grid.test", transport=httpx.MockTransport(handler))
    stages = []
    data = renderer.generate({"id": "task-1", "lease_id": "lease-1"}, threading.Event(), lambda v, s: stages.append(s), 2)
    assert data == b"PNGDATA" and stages == ["generating in the cloud", "received cloud image"]
    assert str(sent[0].url) == "http://grid.test/api/tasks/task-1/cloud-image" and json.loads(sent[0].content) == {"lease_id": "lease-1"}


def test_grid_generation_falls_back_to_local_for_older_coordinators(monkeypatch):
    monkeypatch.setattr(worker.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert worker.grid_generation("http://grid.test") == {"mode": "local"}
