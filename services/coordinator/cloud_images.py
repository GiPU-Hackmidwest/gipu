"""Cloud image generation for demos, through the Akamai workshop's hosted image model.

The grid pipeline is unchanged: a contributor's worker still claims the task, holds
the lease and uploads the result, and it still earns the task's credits. Only the
pixels come from the hosted model. The coordinator makes the provider call so the
team key never leaves the server, and every such image is labelled cloud-generated.

Without AKAMAI_API_KEY, or with POCKETGRID_IMAGE_GENERATOR=local, devices generate locally (Tiny-SD).
"""
from __future__ import annotations

import base64
import io
import os
import threading
import time

import httpx
from PIL import Image

SIZES = (512, 768, 1024)  # Square sizes the hosted model accepts.
# The team quota is 6 images per minute; one request at a time keeps retries orderly.
_lock = threading.Lock()


class CloudUnavailable(Exception):
    """The hosted model cannot produce this image now; the worker reports a retryable failure."""


def mode() -> str:
    """An explicit setting wins; otherwise use the hosted model whenever a key is configured."""
    setting = os.getenv('POCKETGRID_IMAGE_GENERATOR', '').strip().lower()
    if setting in ('cloud', 'local'):
        return setting
    return 'cloud' if os.getenv('AKAMAI_API_KEY') else 'local'


def model_name() -> str:
    return os.getenv('AKAMAI_IMAGE_MODEL', 'hackathon-image')


def status() -> dict:
    if mode() == 'local':
        return {'mode': 'local', 'model': 'segmind/tiny-sd', 'available': True}
    return {'mode': 'cloud', 'model': f'akamai/{model_name()}', 'available': bool(os.getenv('AKAMAI_API_KEY'))}


def generate(prompt: str, width: int, height: int, seed: int, *,
             transport: httpx.BaseTransport | None = None, sleep=time.sleep, budget_seconds: float = 100) -> bytes:
    """Return a PNG of exactly width x height from the hosted model."""
    key = os.getenv('AKAMAI_API_KEY', '')
    if not key:
        raise CloudUnavailable('Cloud image generation is not configured on this grid')
    base = os.getenv('AKAMAI_BASE_URL', 'https://ws.akamai-workshops.com/v1').rstrip('/')
    size = next(s for s in SIZES if s >= max(width, height))
    body = {'model': model_name(), 'prompt': prompt[:2000], 'size': f'{size}x{size}',
            'n': 1, 'response_format': 'b64_json', 'seed': int(seed) % 2**31}
    started = time.monotonic()
    with _lock, httpx.Client(timeout=90, transport=transport) as client:
        for attempt in range(4):
            try:
                response = client.post(f'{base}/images/generations', json=body,
                                       headers={'Authorization': f'Bearer {key}'})
            except httpx.HTTPError:
                raise CloudUnavailable('Cloud image service is unreachable') from None
            if response.status_code == 429:
                # This service reports the wait in seconds in x-ratelimit-reset.
                try:
                    wait = float(response.headers.get('x-ratelimit-reset') or response.headers.get('retry-after') or 10)
                except ValueError:
                    wait = 10
                wait = min(max(wait, 1), 30)
                if attempt == 3 or time.monotonic() - started + wait > budget_seconds:
                    break
                sleep(wait)
                continue
            if response.status_code >= 400:
                raise CloudUnavailable(f'Cloud image service returned {response.status_code}')
            try:
                data = base64.b64decode(response.json()['data'][0]['b64_json'])
                with Image.open(io.BytesIO(data)) as opened:
                    image = opened.convert('RGB')
            except Exception:
                raise CloudUnavailable('Cloud image service returned an unreadable image') from None
            if image.size != (width, height):
                image = image.resize((width, height), Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format='PNG')
            return output.getvalue()
    raise CloudUnavailable('Cloud image service is busy; the task will be retried')
