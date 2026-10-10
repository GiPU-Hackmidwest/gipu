"""Checks real pixel transformations and immediate cancellation boundaries."""
import importlib.util
import io
from pathlib import Path
import threading

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
