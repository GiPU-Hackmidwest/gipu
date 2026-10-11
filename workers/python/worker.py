#!/usr/bin/env python3
"""An opt-in PocketGrid device. Inference and pixels run on this machine."""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
from pathlib import Path
import signal
import socket
import threading
import time
from typing import Any, Callable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import httpx
from PIL import Image, ImageDraw
import psutil

MODEL = "segmind/tiny-sd"
MODEL_REVISION = "cad0bd7495fa6c4bcca01b19a723dc91627fe84f"
MODEL_PROFILES = {
    "tiny-sd": {"model": MODEL, "revision": MODEL_REVISION, "steps": 12,
                "size": 256, "guidance": 7.5, "safetensors": False},
    "sd-turbo": {"model": "stabilityai/sd-turbo", "revision": "b261bac6fd2cf515557d5d0707481eafa0485ec2",
                 "steps": 4, "size": 512, "guidance": 0.0, "safetensors": True},
    "sdxl-turbo": {"model": "stabilityai/sdxl-turbo", "revision": "71153311d3dbb46851df1931d3ca6e939de83304",
                   "steps": 4, "size": 512, "guidance": 0.0, "safetensors": True},
}
FRAME = (36, 203, 166)


class WorkCancelled(Exception):
    """The owner stopped sharing or the coordinator revoked this lease."""


def check_cancelled(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise WorkCancelled("Sharing stopped or lease revoked")


def finalize_image(source: bytes, cancel: threading.Event | None = None) -> bytes:
    cancel = cancel or threading.Event()
    check_cancelled(cancel)
    with Image.open(io.BytesIO(source)) as original:
        image = original.convert("RGB")
    if min(image.size) < 8:
        raise ValueError("Image must be at least 8 pixels across")
    ImageDraw.Draw(image).rectangle((0, 0, image.width - 1, image.height - 1), outline=FRAME, width=4)
    check_cancelled(cancel)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def denoising_callback(cancel: threading.Event, steps: int, progress: Callable[[float, str], None]):
    def on_step(_pipeline, step, _timestep, callback_kwargs):
        # Raise rather than decoding an unfinished image after interrupting the loop.
        check_cancelled(cancel)
        progress((step + 1) / steps * 0.94, "denoising")
        return callback_kwargs
    return on_step


class LocalRenderer:
    def __init__(self, backend: str = "auto", model: str = MODEL):
        self.backend = backend
        matches = [p for key, p in MODEL_PROFILES.items() if model in (key, p["model"])]
        if not matches:
            raise ValueError("Unknown model; select a pinned PocketGrid model profile")
        self.profile = matches[0]
        self.model = self.profile["model"]
        self.pipeline = None

    def load(self, cpu_threads: int = 2, local_only: bool = False) -> None:
        import torch
        from diffusers import AutoPipelineForText2Image
        torch.set_num_threads(cpu_threads)
        if self.backend == "auto":
            self.backend = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        if self.backend == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("Apple GPU (MPS) is unavailable in this process; use --backend cpu or run from a GPU-enabled terminal")
        if self.backend == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in this process")
        dtype = torch.float32 if self.backend == "cpu" else torch.float16
        print(f"Loading {self.model} on {self.backend}; no job lease is held during model setup", flush=True)
        load_options = {"variant": "fp16"} if self.profile["safetensors"] else {}
        self.pipeline = AutoPipelineForText2Image.from_pretrained(
            self.model, revision=self.profile["revision"], torch_dtype=dtype, local_files_only=local_only,
            use_safetensors=self.profile["safetensors"], **load_options,
        ).to(self.backend)
        self.pipeline.enable_attention_slicing()
        self.pipeline.set_progress_bar_config(disable=True)

    def generate(self, task: dict[str, Any], cancel: threading.Event,
                 progress: Callable[[float, str], None], cpu_threads: int) -> bytes:
        import torch
        if self.pipeline is None:
            raise RuntimeError("Run model setup before accepting work")
        check_cancelled(cancel)
        torch.set_num_threads(cpu_threads)
        progress(0.01, "encoding prompt")
        with torch.inference_mode():
            result = self.pipeline(
                prompt=task["prompt"], width=int(task["width"]), height=int(task["height"]),
                num_inference_steps=int(task["steps"]), guidance_scale=self.profile["guidance"],
                generator=torch.Generator(device="cpu").manual_seed(int(task["seed"])),
                callback_on_step_end=denoising_callback(cancel, int(task["steps"]), progress),
                callback_on_step_end_tensor_inputs=[],
            )
        check_cancelled(cancel)
        flagged = getattr(result, "nsfw_content_detected", None)
        if flagged and any(flagged):
            raise ValueError("The local model safety checker rejected this image")
        progress(0.98, "encoding PNG")
        output = io.BytesIO()
        result.images[0].convert("RGB").save(output, format="PNG")
        check_cancelled(cancel)
        return output.getvalue()


class DeviceWorker:
    def __init__(self, server: str, identity: dict, renderer: LocalRenderer | None):
        self.server = server.rstrip("/")
        self.identity = identity
        self.renderer = renderer
        self.client = httpx.Client(base_url=self.server, headers={"Authorization": f"Bearer {identity['token']}"}, timeout=3)
        self.stop = threading.Event()
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.task = None
        self.device = None
        self.progress = 0.0
        self.stage = "ready"
        self.process = psutil.Process()
        self.last_heartbeat = time.monotonic()
        self.task_threads = None

    def api(self, method: str, path: str, **kwargs):
        response = self.client.request(method, "/api" + path, **kwargs)
        response.raise_for_status()
        return response.json()

    def set_progress(self, value: float, stage: str) -> None:
        with self.lock:
            self.progress, self.stage = value, stage
        check_cancelled(self.cancel)

    def telemetry(self) -> dict:
        return {
            "backend": self.renderer.backend if self.renderer else "cpu",
            "model": self.renderer.model if self.renderer else "Pillow image finalizer",
            "rss_mb": round(self.process.memory_info().rss / 1024**2, 1),
            "cpu_percent": self.process.cpu_percent(), "progress": self.progress,
            "stage": self.stage,
        }

    def heartbeat(self) -> None:
        while not self.stop.is_set():
            with self.lock:
                task = self.task
                data = {"telemetry": self.telemetry()}
                if task:
                    data.update(task_id=task["id"], lease_id=task["lease_id"])
            try:
                result = self.api("POST", f"/devices/{self.identity['device_id']}/heartbeat", json=data)
                progress_payload = None
                with self.lock:
                    self.device = result["device"]
                    self.last_heartbeat = time.monotonic()
                    if task and self.task is task:
                        limits = self.device["limits"]
                        expired = (self.device.get("session_expires_at") or 0) <= time.time()
                        limits_changed = limits["cpu_threads"] != self.task_threads or task["width"] * task["height"] > limits["max_pixels"]
                        if not self.device["enabled"] or not result["lease_valid"] or expired or limits_changed:
                            self.cancel.set()
                        elif not self.cancel.is_set():
                            progress_payload = {
                                "lease_id": task["lease_id"], "progress": self.progress, "stage": self.stage,
                            }
                if progress_payload:
                    self.api("POST", f"/tasks/{task['id']}/progress", json=progress_payload)
            except httpx.HTTPStatusError as exc:
                if (exc.response.status_code in (401, 403, 404, 409)
                        or time.monotonic() - self.last_heartbeat >= 9):
                    self.cancel.set()
                print(f"Heartbeat: HTTP {exc.response.status_code}", flush=True)
            except httpx.HTTPError:
                if time.monotonic() - self.last_heartbeat >= 9:
                    self.cancel.set()
                print("Coordinator unavailable; local work stops after 9 seconds without lease confirmation", flush=True)
            self.stop.wait(3)

    def source_bytes(self, relative_url: str) -> bytes:
        # Never forward device credentials to task-supplied external URLs.
        parsed = urlsplit(relative_url)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/api/images/"):
            raise ValueError("Source must be a coordinator image URL")
        response = self.client.get(relative_url)
        response.raise_for_status()
        return response.content

    def perform(self, task: dict, device: dict) -> None:
        limits = device["limits"]
        if int(task["width"]) * int(task["height"]) > int(limits["max_pixels"]):
            raise ValueError("Task exceeds device pixel limit")
        if not device["enabled"] or (device.get("session_expires_at") or 0) <= time.time():
            raise WorkCancelled("Contribution session is not active")
        started = time.monotonic()
        if task["kind"] == "image_generate":
            if not self.renderer:
                raise ValueError("This device does not support image generation")
            png = self.renderer.generate(task, self.cancel, self.set_progress, limits["cpu_threads"])
        elif task["kind"] == "image_finalize":
            self.set_progress(0.1, "downloading image")
            png = finalize_image(self.source_bytes(task["source_url"]), self.cancel)
        else:
            raise ValueError("Unknown task kind")
        check_cancelled(self.cancel)
        self.set_progress(0.99, "submitting result")
        payload = {"lease_id": task["lease_id"], "png_base64": base64.b64encode(png).decode(), "metrics": {
            "backend": self.renderer.backend if task["kind"] == "image_generate" else "cpu",
            "model": self.renderer.model if task["kind"] == "image_generate" else "Pillow",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }}
        # The completion endpoint is idempotent. Retry an uncertain response without paying twice.
        for attempt in range(3):
            try:
                receipt = self.api("POST", f"/tasks/{task['id']}/complete", json=payload, timeout=20)
                print(f"Accepted {task['id']}: earned {receipt['earned']} sandbox credits in {payload['metrics']['elapsed_seconds']}s", flush=True)
                return
            except httpx.TransportError:
                if attempt == 2:
                    raise
                self.stop.wait(1)

    def run(self) -> None:
        thread = threading.Thread(target=self.heartbeat, daemon=True, name="pocketgrid-heartbeat")
        thread.start()
        print(f"Device {self.identity['device_id']} connected. Owner controls sharing in the app. Ctrl-C stops this worker.", flush=True)
        try:
            while not self.stop.is_set():
                task = None
                try:
                    response = self.api("POST", f"/devices/{self.identity['device_id']}/claim", json={})
                    task = response["task"]
                    if not task:
                        self.stop.wait(1)
                        continue
                    with self.lock:
                        self.cancel = threading.Event()
                        self.task = task
                        self.device = response["device"]
                        self.task_threads = self.device["limits"]["cpu_threads"]
                        self.progress, self.stage = 0.0, "starting"
                    print(f"Working on {task['kind']} {task['id']} (attempt {task.get('attempts', '?')})", flush=True)
                    self.perform(task, response["device"])
                except (httpx.HTTPError, WorkCancelled, ValueError, RuntimeError) as exc:
                    print(f"Worker: {type(exc).__name__}: {exc}", flush=True)
                    if task:
                        try:
                            self.api("POST", f"/tasks/{task['id']}/fail", json={"lease_id": task["lease_id"], "error": str(exc)[:250]})
                        except httpx.HTTPError:
                            pass  # A revoked/expired lease already belongs to another worker.
                    self.stop.wait(1)
                finally:
                    with self.lock:
                        self.task = None
                        self.progress, self.stage = 0.0, "ready"
        finally:
            self.cancel.set()
            self.stop.set()
            thread.join(timeout=5)
            self.client.close()


def save_identity(path: Path, identity: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(identity, handle)


def register(args, renderer) -> dict:
    path = Path(args.identity)
    server = args.server.rstrip("/")
    identity = json.loads(path.read_text()) if path.exists() else None
    if identity and identity["server"] != server:
        raise ValueError("Identity is for a different coordinator; use another --identity path")
    with httpx.Client(base_url=server, timeout=10) as client:
        owner_token = args.session_token or (identity or {}).get("owner_token")
        if not identity:
            if not owner_token:
                response = client.post("/api/sessions", json={"name": args.name, "join_code": args.join_code})
                response.raise_for_status()
                owner_token = response.json()["token"]
            response = client.post("/api/devices", headers={"Authorization": f"Bearer {owner_token}"}, json={
                "name": args.device_name, "kind": "python",
                "capabilities": (["image_generate"] if args.generate_only else ["image_generate", "image_finalize"]) if renderer else ["image_finalize"],
                "limits": {"cpu_threads": args.cpu_threads, "max_pixels": args.max_pixels, "session_minutes": args.session_minutes},
            })
            response.raise_for_status()
            result = response.json()
            identity = {"server": server, "device_id": result["device"]["id"], "token": result["token"], "owner_token": owner_token,
                        "generates": renderer is not None, "generate_only": args.generate_only}
            save_identity(path, identity)
        if identity.get("generates", True) != (renderer is not None):
            raise ValueError("Device capability changed; use a different --identity file")
        if identity.get("generate_only", False) != args.generate_only:
            raise ValueError("Device capability changed; use a different --identity file")
        if args.share:
            if not owner_token:
                raise ValueError("--share needs an owner session token")
            response = client.patch(f"/api/devices/{identity['device_id']}", headers={"Authorization": f"Bearer {owner_token}"}, json={
                "enabled": True, "limits": {"cpu_threads": args.cpu_threads, "max_pixels": args.max_pixels, "session_minutes": args.session_minutes},
            })
            response.raise_for_status()
    return identity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "smoke", "run"])
    parser.add_argument("--server", default=os.environ.get("POCKETGRID_SERVER", "http://127.0.0.1:8787"))
    parser.add_argument("--session-token", default=os.environ.get("POCKETGRID_SESSION_TOKEN"), help="Prefer POCKETGRID_SESSION_TOKEN to keep tokens out of process arguments")
    parser.add_argument("--join-code", default=os.environ.get("POCKETGRID_JOIN_CODE", "pocketgrid-demo"))
    parser.add_argument("--name", default="Demo contributor")
    parser.add_argument("--device-name", default=socket.gethostname())
    parser.add_argument("--identity", default=str(ROOT / ".device.json"))
    parser.add_argument("--share", action="store_true", help="Explicitly enable a timed contribution session")
    capabilities = parser.add_mutually_exclusive_group()
    capabilities.add_argument("--finalize-only", action="store_true", help="Only run deterministic image export; no model needed")
    capabilities.add_argument("--generate-only", action="store_true", help="Leave image export tasks to phones/browser workers")
    parser.add_argument("--model", choices=list(MODEL_PROFILES), default="tiny-sd",
                        help="Experimental models are available for prepare/smoke only until grid model routing is integrated")
    parser.add_argument("--backend", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--cpu-threads", type=int, choices=range(1, 9), default=2)
    parser.add_argument("--max-pixels", type=int, choices=[65536, 147456, 262144], default=262144)
    parser.add_argument("--session-minutes", type=int, choices=range(1, 121), default=30)
    parser.add_argument("--local-only", action="store_true", help="Fail instead of downloading uncached model files")
    parser.add_argument("--prompt", default="A cute orange cat riding a tiny blue bicycle, whimsical cartoon illustration, sunny park")
    parser.add_argument("--size", type=int, choices=[256, 384, 512], default=None)
    parser.add_argument("--steps", type=int, choices=range(1, 31), default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=str(ROOT / ".cache" / "smoke-cat.png"))
    args = parser.parse_args()
    if args.command == "run" and args.model != "tiny-sd":
        parser.error("Experimental models are benchmark-only; grid model routing is not integrated yet")
    profile = MODEL_PROFILES[args.model]
    args.size = args.size or profile["size"]
    args.steps = args.steps or profile["steps"]
    if args.model != "tiny-sd" and args.steps > 4:
        parser.error("Turbo profiles support 1–4 benchmark steps")
    renderer = None if args.finalize_only and args.command == "run" else LocalRenderer(args.backend, args.model)
    if renderer:
        renderer.load(args.cpu_threads, local_only=args.local_only)
    if args.command == "prepare":
        print("Local model ready. No contribution session started.")
        return
    if args.command == "smoke":
        started = time.monotonic()
        def progress(value, stage):
            print(f"{value:.0%} {stage}", flush=True)
        data = renderer.generate({"prompt": args.prompt, "width": args.size, "height": args.size, "steps": args.steps, "seed": args.seed}, threading.Event(), progress, args.cpu_threads)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        print(json.dumps({"output": str(output.resolve()), "backend": renderer.backend, "model": renderer.model, "elapsed_seconds": round(time.monotonic() - started, 3), "bytes": len(data)}))
        return
    identity = register(args, renderer)
    worker = DeviceWorker(args.server, identity, renderer)
    def stop(_signal, _frame):
        worker.cancel.set()
        worker.stop.set()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    worker.run()


if __name__ == "__main__":
    main()
