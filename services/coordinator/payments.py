"""Buy credits with a card through Stripe Checkout, in test mode only.

Money only ever flows in: there is no payout, refund-to-card or withdrawal path,
and credits cannot be converted back to money. Packs and prices are fixed here,
and credits are granted only after Stripe confirms the payment (webhook, or the
coordinator retrieving the session itself), never on a client's say-so.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import httpx

API = 'https://api.stripe.com/v1'
# Server-side price list; clients choose a pack id, never an amount.
PACKS = {
    'starter': {'credits': 50, 'amount': 500},
    'standard': {'credits': 120, 'amount': 1000},
    'large': {'credits': 300, 'amount': 2000},
}
CURRENCY = 'usd'


class PaymentsUnavailable(Exception):
    pass


def _key() -> str:
    key = os.getenv('STRIPE_SECRET_KEY', '')
    # Refuse live keys outright: this prototype must never take real money.
    return key if key.startswith('sk_test_') else ''


def status() -> dict:
    return {'available': bool(_key()), 'test_mode': True, 'currency': CURRENCY,
            'packs': [{'id': name, **pack} for name, pack in PACKS.items()]}


def _client(transport=None) -> httpx.Client:
    key = _key()
    if not key:
        raise PaymentsUnavailable('Buying credits is not set up on this grid')
    return httpx.Client(base_url=API, timeout=20, transport=transport, headers={'Authorization': f'Bearer {key}'})


def create_checkout(user_id: str, pack: str, success_url: str, cancel_url: str, idempotency_key: str, transport=None) -> dict:
    if pack not in PACKS:
        raise ValueError('Unknown credit pack')
    item = PACKS[pack]
    form = {
        'mode': 'payment',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'client_reference_id': user_id,
        'metadata[user_id]': user_id,
        'metadata[pack]': pack,
        'metadata[credits]': str(item['credits']),
        'line_items[0][quantity]': '1',
        'line_items[0][price_data][currency]': CURRENCY,
        'line_items[0][price_data][unit_amount]': str(item['amount']),
        'line_items[0][price_data][product_data][name]': f"GiPU credits · {item['credits']}",
        'line_items[0][price_data][product_data][description]': 'Sandbox credits for GiPU image requests. Not redeemable for cash.',
    }
    with _client(transport) as client:
        response = client.post('/checkout/sessions', data=form, headers={'Idempotency-Key': idempotency_key})
    if response.status_code >= 400:
        raise PaymentsUnavailable(f'Stripe returned {response.status_code}')
    session = response.json()
    return {'id': session['id'], 'url': session['url']}


def retrieve_checkout(session_id: str, transport=None) -> dict:
    with _client(transport) as client:
        response = client.get(f'/checkout/sessions/{session_id}')
    if response.status_code >= 400:
        raise PaymentsUnavailable(f'Stripe returned {response.status_code}')
    return response.json()


def verify_webhook(payload: bytes, header: str, now: float | None = None, tolerance: int = 300) -> bool:
    """Stripe's signature scheme: HMAC-SHA256 of "<timestamp>.<raw body>" with the endpoint secret."""
    secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    if not secret or not header:
        return False
    parts = [item.split('=', 1) for item in header.split(',') if '=' in item]
    timestamps = [value for key, value in parts if key == 't']
    signatures = [value for key, value in parts if key == 'v1']
    if not timestamps or not signatures or not timestamps[0].isdigit():
        return False
    if abs((now or time.time()) - int(timestamps[0])) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f'{timestamps[0]}.'.encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)
