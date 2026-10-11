"""Private weekly progress and explicitly opted-in public rankings.

Accepted-work ledger rows are the source of truth for activity. Availability is
measured prospectively by the coordinator, once per account regardless of how
many devices it has. It never changes balances or awards credits.
"""
from __future__ import annotations

import math
import unicodedata

from .store import fail

WEEK_SECONDS = 7 * 86400
MONDAY_OFFSET = 4 * 86400
METRICS = ('overall', 'availability', 'credits', 'work')


def week_start(now):
    return math.floor((now - MONDAY_OFFSET) / WEEK_SECONDS) * WEEK_SECONDS + MONDAY_OFFSET


def nickname(value):
    value = unicodedata.normalize('NFC', value.strip())
    if not 1 <= len(value) <= 24 or not any(c.isalnum() for c in value):
        fail(422, 'Choose a public nickname of 1–24 characters')
    if any(not (c.isalnum() or c in ' ._-') for c in value):
        fail(422, 'Use letters, numbers, spaces, dots, underscores or hyphens')
    return value


def advance_availability(store, db):
    """Credit only bounded intervals observed by this running server process.

    Called before device-state mutations. Online grace is bounded by the same
    lease window as grid counts; pause and session expiry truncate it exactly.
    Restart and gaps longer than the lease window earn no inferred uptime.
    """
    now, previous = store.clock(), store.availability_checkpoint
    if now <= previous:
        return
    store.availability_checkpoint = now
    if now - previous > store.lease_seconds:
        return
    ends = {}
    for row in db.execute('SELECT owner_id,last_seen,session_expires_at FROM devices WHERE enabled=1'):
        if row['last_seen'] is None or row['session_expires_at'] is None:
            continue
        end = min(now, row['last_seen'] + store.lease_seconds, row['session_expires_at'])
        ends[row['owner_id']] = max(ends.get(row['owner_id'], previous), end)
    for owner_id, end in ends.items():
        start = previous
        while end > start:
            week = week_start(start)
            until = min(end, week + WEEK_SECONDS)
            db.execute('''INSERT INTO leaderboard_availability(user_id,week_start,seconds) VALUES(?,?,?)
                          ON CONFLICT(user_id,week_start) DO UPDATE SET seconds=seconds+excluded.seconds''',
                       (owner_id, week, until - start))
            start = until


def weekly_metrics(db, start, end):
    metrics = {}

    def member(user_id):
        return metrics.setdefault(user_id, {'availability_seconds': 0, 'credits_used': 0,
                                           'completed_tasks': 0, 'images_created': 0})

    for row in db.execute('SELECT user_id,seconds FROM leaderboard_availability WHERE week_start=?', (start,)):
        member(row['user_id'])['availability_seconds'] = max(0, int(row['seconds']))
    # Each accepted task emits exactly one earned row in its acceptance transaction.
    # Joining its canonical note to the task lets existing activity count too,
    # without trusting worker metrics or mutable client-supplied telemetry.
    for row in db.execute('''SELECT l.user_id,j.owner_id,t.kind,l.amount FROM ledger l
                            JOIN tasks t ON l.note='Accepted ' || t.kind || ' ' || t.id
                            JOIN jobs j ON j.id=t.job_id AND j.id=l.job_id
                            WHERE l.kind='earned' AND l.created_at>=? AND l.created_at<?''', (start, end)):
        # Own-device payments return to the requester and are not circulation.
        # Help another account to earn work points; self-recycling cannot farm it.
        if row['user_id'] != row['owner_id']:
            member(row['user_id'])['completed_tasks'] += 1
            member(row['owner_id'])['credits_used'] += row['amount']
        if row['kind'] == 'image_finalize':
            member(row['owner_id'])['images_created'] += 1
    # The one completion refund row records when the final fee was settled. Even
    # a zero refund has a row. Cancelled/failed jobs have fee=0; reservations and
    # grants never become spend. Crossing a week charges each accepted step then.
    for row in db.execute('''SELECT j.owner_id,j.fee FROM ledger l JOIN jobs j ON j.id=l.job_id
                            WHERE l.kind='refund' AND l.user_id=j.owner_id
                              AND l.created_at>=? AND l.created_at<?''', (start, end)):
        member(row['owner_id'])['credits_used'] += row['fee']
    for values in metrics.values():
        values['score'] = values['completed_tasks'] * 10 + values['credits_used'] + min(32, values['availability_seconds'] // 900)
    return metrics


def view(store, db, user_id, metric='overall'):
    if metric not in METRICS:
        fail(422, 'Unknown leaderboard metric')
    now = store.clock()
    start = week_start(now)
    values = weekly_metrics(db, start, start + WEEK_SECONDS)
    empty = {'score': 0, 'availability_seconds': 0, 'credits_used': 0, 'completed_tasks': 0, 'images_created': 0}
    own = db.execute('SELECT enabled,nickname FROM leaderboard_profiles WHERE user_id=?', (user_id,)).fetchone()
    profiles = db.execute('SELECT user_id,nickname FROM leaderboard_profiles WHERE enabled=1').fetchall()
    key = {'overall': 'score', 'availability': 'availability_seconds', 'credits': 'credits_used', 'work': 'completed_tasks'}[metric]
    entries = [{'nickname': row['nickname'], **values.get(row['user_id'], empty),
                'is_you': row['user_id'] == user_id, '_id': row['user_id']} for row in profiles]
    # Equal metrics share rank. Internal IDs provide stable top-50 selection only
    # and are removed before any response. No implicit identity/name disclosure.
    entries.sort(key=lambda entry: (-entry[key], entry['nickname'].casefold(), entry['_id']))
    last, rank, own_rank = None, 0, None
    for index, entry in enumerate(entries):
        if entry[key] != last:
            rank, last = index + 1, entry[key]
        entry['rank'] = rank
        if entry['is_you']:
            own_rank = rank
        del entry['_id']
    return {'week_start': start, 'week_end': start + WEEK_SECONDS, 'server_time': now, 'metric': metric,
            'enabled': bool(own and own['enabled']), 'nickname': own['nickname'] if own else '',
            'self': {'rank': own_rank, **values.get(user_id, empty)},
            'entries': entries[:50], 'member_count': len(entries)}
