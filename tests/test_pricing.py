import json

import pytest
from fastapi import HTTPException

from services.coordinator.store import LEGACY_PRICING, price_for, quote
from tests.test_coordinator import LIMITS, png, request, setup, submit


def test_more_ready_laptops_cost_slightly_less():
    assert [price_for(n)['generate'] for n in range(6)] == [7, 7, 6, 6, 5, 5]
    assert all(price_for(n)['finalize'] == 1 and price_for(n)['fee'] == 1 for n in range(6))
    assert [quote(1, price_for(n)) for n in (0, 2, 4)] == [9, 8, 7]
    assert quote(4, price_for(4)) == 25


def add_laptops(store, seller, count):
    ids = []
    for i in range(count):
        device = store.register(seller, f'Laptop {i}', 'python', ['image_generate', 'image_finalize'], LIMITS)['device']['id']
        store.change_device(seller, device, True)
        ids.append(device)
    return ids


def test_snapshot_shows_the_current_price_for_live_supply(setup):
    store, now, buyer, seller, device = setup
    assert store.snapshot(buyer)['pricing'] == {'generate': 7, 'finalize': 1, 'fee': 1}
    add_laptops(store, seller, 2)
    assert store.snapshot(buyer)['pricing']['generate'] == 6
    add_laptops(store, seller, 2)
    assert store.snapshot(buyer)['pricing']['generate'] == 5


def test_budget_must_cover_the_current_quote(setup):
    store, now, buyer, seller, device = setup
    with pytest.raises(HTTPException) as error:
        submit(store, buyer, budget=8)  # Nothing ready: one image quotes 9.
    assert error.value.status_code == 422 and '9' in error.value.detail
    assert store.snapshot(buyer)['balance'] == 100


def test_price_is_locked_when_the_request_is_created(setup):
    store, now, buyer, seller, device = setup
    laptops = add_laptops(store, seller, 4)
    job = submit(store, buyer, budget=10)
    assert job['plan']['pricing'] == {'generate': 5, 'finalize': 1, 'fee': 1}
    # Supply collapses after creation: the generation and later finishing prices stay locked.
    for laptop in laptops[1:]:
        store.change_device(seller, laptop, False)
    assert store.snapshot(buyer)['pricing']['generate'] == 7
    task = store.claim(laptops[0])['task']
    assert task['price'] == 5
    store.complete(laptops[0], task['id'], task['lease_id'], png(), {})
    export = store.claim(laptops[0])['task']
    assert export['price'] == 1
    store.complete(laptops[0], export['id'], export['lease_id'], png(), {})
    receipt = store.snapshot(buyer)['jobs'][0]['receipt']
    assert receipt == {'budget': 10, 'contributor_total': 6, 'platform_fee': 1, 'refund': 3, 'total_charged': 7}
    assert store.snapshot(buyer)['balance'] == 93


def test_jobs_created_before_dynamic_pricing_keep_fixed_prices(setup):
    store, now, buyer, seller, device = setup
    laptop = device()
    job = submit(store, buyer)
    with store.tx() as db:  # Recreate a pre-change job: no locked pricing in its plan.
        plan = json.loads(db.execute('SELECT plan FROM jobs WHERE id=?', (job['id'],)).fetchone()[0])
        plan.pop('pricing')
        db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(plan), job['id']))
        db.execute('UPDATE tasks SET price=? WHERE job_id=?', (LEGACY_PRICING['generate'], job['id']))
    task = store.claim(laptop)['task']
    store.complete(laptop, task['id'], task['lease_id'], png(), {})
    assert store.claim(laptop)['task']['price'] == LEGACY_PRICING['finalize']


def test_members_see_their_locked_prices(setup):
    store, now, buyer, seller, device = setup
    add_laptops(store, seller, 2)
    job = submit(store, buyer)
    view = store.view_job(store.existing_job(buyer, 'request-001'), buyer)
    assert view['plan']['pricing'] == {'generate': 6, 'finalize': 1, 'fee': 1}
