"""Durable single-coordinator queue and integer sandbox-credit ledger.

All transitions use BEGIN IMMEDIATE. Lease IDs fence late workers, and settlement
occurs in the same transaction as result acceptance. SQLite is intentionally a
single-node prototype; do not run replicas against different volumes.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from PIL import Image
from fastapi import HTTPException


def uid() -> str:
    return uuid.uuid4().hex


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def fail(status: int, detail: str):
    raise HTTPException(status_code=status, detail=detail)


# A planning claim outlives the agent's 90-second invocation deadline. An expired
# claim means its process stopped; another planner may then take the request.
PLANNING_CLAIM_SECONDS = 150
PLANNING_ATTEMPTS = 3
ACTIVE = ('planning', 'queued', 'running')
# Link codes avoid characters that are easy to misread when typed.
LINK_ALPHABET = '23456789ABCDEFGHJKMNPQRSTVWXYZ'
LEGACY_PRICING = {'generate': 6, 'finalize': 1, 'fee': 1}


def price_for(ready_to_create):
    """Generation credits per image from live supply: more ready laptops cost slightly less.

    0-1 ready: 7, 2-3: 6 (the original fixed price), 4 or more: 5. Finishing and the
    fee stay at 1. The coordinator locks the result into each job when it reserves
    the budget, so later supply changes never alter what an accepted request pays."""
    generate = 5 if ready_to_create >= 4 else 6 if ready_to_create >= 2 else 7
    return {'generate': generate, 'finalize': 1, 'fee': 1}


def quote(count, pricing):
    return count * (pricing['generate'] + pricing['finalize']) + pricing['fee']
LINK_SECONDS = 120
DEVICE_WORDS = {'python': 'laptop', 'ios': 'phone', 'browser': 'device'}


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


class Store:
    def __init__(self, root: str | Path, lease_seconds=15, clock=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'images').mkdir(exist_ok=True)
        self.path = self.root / 'pocketgrid.sqlite'
        self.clock, self.lease_seconds = clock, lease_seconds
        self.lock = threading.RLock()
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT,token TEXT UNIQUE,balance INTEGER CHECK(balance>=0),created REAL);
            CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,owner_id TEXT,name TEXT,kind TEXT,token TEXT UNIQUE,capabilities TEXT,limits TEXT,enabled INTEGER DEFAULT 0,last_seen REAL,session_expires_at REAL,telemetry TEXT DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner_id TEXT,request_id TEXT,prompt TEXT,status TEXT,count INTEGER,width INTEGER,height INTEGER,steps INTEGER,budget INTEGER,spent INTEGER DEFAULT 0,refunded INTEGER DEFAULT 0,fee INTEGER DEFAULT 0,created_at REAL,plan TEXT,UNIQUE(owner_id,request_id));
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,job_id TEXT,kind TEXT,status TEXT,variant INTEGER,prompt TEXT,width INTEGER,height INTEGER,steps INTEGER,seed INTEGER,price INTEGER,attempts INTEGER DEFAULT 0,device_id TEXT,lease_id TEXT,lease_expires_at REAL,progress REAL DEFAULT 0,source_task_id TEXT,artifact_id TEXT,last_device_id TEXT,retry_after REAL DEFAULT 0,metrics TEXT DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY,user_id TEXT,job_id TEXT,kind TEXT,amount INTEGER,created_at REAL,note TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,device_id TEXT,job_id TEXT,kind TEXT,message TEXT,created_at REAL);
            CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,job_id TEXT,task_id TEXT,sha256 TEXT);
            CREATE TABLE IF NOT EXISTS user_sessions(id TEXT PRIMARY KEY,user_id TEXT,token TEXT UNIQUE,client_name TEXT,created_at REAL,last_used_at REAL,revoked_at REAL);
            CREATE TABLE IF NOT EXISTS link_codes(code TEXT PRIMARY KEY,user_id TEXT,expires_at REAL,used_at REAL);
            CREATE TABLE IF NOT EXISTS credentials(user_id TEXT PRIMARY KEY,username TEXT UNIQUE,salt TEXT,hash TEXT,updated_at REAL);
            CREATE TABLE IF NOT EXISTS cloud_outputs(task_id TEXT PRIMARY KEY,model TEXT,created_at REAL);
            CREATE TABLE IF NOT EXISTS leaderboard_profiles(user_id TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0,nickname TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS leaderboard_availability(user_id TEXT,week_start REAL,seconds REAL NOT NULL DEFAULT 0,PRIMARY KEY(user_id,week_start));

            CREATE TABLE IF NOT EXISTS purchases(session_id TEXT PRIMARY KEY,user_id TEXT,pack TEXT,credits INTEGER,amount INTEGER,currency TEXT,status TEXT,created_at REAL,settled_at REAL);
            CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status,kind);
            CREATE INDEX IF NOT EXISTS tasks_job ON tasks(job_id);
            CREATE INDEX IF NOT EXISTS sessions_user ON user_sessions(user_id);
            ''')
            # Tokens issued before multi-device sign-in keep working as sessions.
            for row in db.execute('SELECT id,token,created FROM users WHERE token IS NOT NULL').fetchall():
                db.execute("INSERT OR IGNORE INTO user_sessions(id,user_id,token,client_name,created_at) VALUES(?,?,?,'Earlier sign-in',?)",
                           (uid(), row['id'], row['token'], row['created']))
            db.execute('UPDATE users SET token=NULL WHERE token IS NOT NULL')
        # Older iOS/Android finishers draw the teal frame; accept it until they all ship.
        self.accept_legacy_frame = os.getenv('POCKETGRID_ACCEPT_LEGACY_FRAME', '1') != '0'
        # Prospective uptime only: a restart never backfills an unobserved gap.
        self.availability_checkpoint = self.clock()

    @contextmanager
    def tx(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=20)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def event(self, db, kind, message, user_id=None, device_id=None, job_id=None):
        db.execute('INSERT INTO events(user_id,device_id,job_id,kind,message,created_at) VALUES(?,?,?,?,?,?)',
                   (user_id, device_id, job_id, kind, message, self.clock()))

    def ledger(self, db, user_id, job_id, kind, amount, note):
        db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?)', (uid(), user_id, job_id, kind, amount, self.clock(), note))

    def new_session(self, db, user_id, client_name=None):
        token, session_id = secrets.token_urlsafe(32), uid()
        db.execute('INSERT INTO user_sessions(id,user_id,token,client_name,created_at,last_used_at) VALUES(?,?,?,?,?,?)',
                   (session_id, user_id, digest(token), client_name or '', self.clock(), self.clock()))
        user = db.execute('SELECT id,name,balance FROM users WHERE id=?', (user_id,)).fetchone()
        return {'token': token, 'session_id': session_id, 'user': {'id': user['id'], 'name': user['name']}, 'balance': user['balance']}

    def session(self, name=None, client_name=None):
        user_id = uid()
        name = name or 'Guest ' + ''.join(secrets.choice(LINK_ALPHABET) for _ in range(4))
        with self.tx() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (user_id, name, None, 100, self.clock()))
            self.ledger(db, user_id, None, 'demo_grant', 100, 'Sandbox grant; no cash value')
            return self.new_session(db, user_id, client_name)

    def auth(self, token, kind='session'):
        with self.tx() as db:
            if kind == 'session':
                row = db.execute('SELECT u.*,s.id AS session_id,s.last_used_at FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.revoked_at IS NULL',
                                 (digest(token),)).fetchone()
                if row and (row['last_used_at'] or 0) < self.clock() - 60:
                    db.execute('UPDATE user_sessions SET last_used_at=? WHERE id=?', (self.clock(), row['session_id']))
            else:
                row = db.execute('SELECT * FROM devices WHERE token=?', (digest(token),)).fetchone()
            if not row:
                fail(401, 'Invalid or missing credential')
            return dict(row)

    def create_link_code(self, user_id):
        code = ''.join(secrets.choice(LINK_ALPHABET) for _ in range(10))
        expires = self.clock() + LINK_SECONDS
        with self.tx() as db:
            db.execute('DELETE FROM link_codes WHERE user_id=? AND used_at IS NULL', (user_id,))
            db.execute('INSERT INTO link_codes VALUES(?,?,?,NULL)', (digest(code), user_id, expires))
        return {'code': code, 'expires_at': expires}

    def redeem_link_code(self, code, client_name=None):
        code = code.upper().replace('-', '').replace(' ', '')
        with self.tx() as db:
            row = db.execute('SELECT * FROM link_codes WHERE code=? AND used_at IS NULL AND expires_at>?', (digest(code), self.clock())).fetchone()
            if not row:
                fail(400, 'Link code invalid or expired')
            db.execute('UPDATE link_codes SET used_at=? WHERE code=?', (self.clock(), row['code']))
            return self.new_session(db, row['user_id'], client_name)

    def set_credentials(self, user_id, username, password, current_password=None):
        username = username.strip().lower()
        with self.tx() as db:
            existing = db.execute('SELECT * FROM credentials WHERE user_id=?', (user_id,)).fetchone()
            if existing and not (current_password and secrets.compare_digest(
                    password_hash(current_password, bytes.fromhex(existing['salt'])), existing['hash'])):
                fail(403, 'Current password required to change this login')
            taken = db.execute('SELECT user_id FROM credentials WHERE username=?', (username,)).fetchone()
            if taken and taken['user_id'] != user_id:
                fail(409, 'Username taken')
            salt = secrets.token_bytes(16)
            db.execute('INSERT OR REPLACE INTO credentials VALUES(?,?,?,?,?)', (user_id, username, salt.hex(), password_hash(password, salt), self.clock()))
        return {'username': username}

    def login(self, username, password, client_name=None):
        with self.tx() as db:
            row = db.execute('SELECT * FROM credentials WHERE username=?', (username.strip().lower(),)).fetchone()
            # Hash even for unknown names so timing does not reveal which part was wrong.
            candidate = password_hash(password, bytes.fromhex(row['salt']) if row else b'pocketgrid-none!')
            if not row or not secrets.compare_digest(candidate, row['hash']):
                fail(401, 'Incorrect username or password')
            return self.new_session(db, row['user_id'], client_name)

    def sessions(self, user_id, current_id):
        with self.tx() as db:
            rows = db.execute('SELECT * FROM user_sessions WHERE user_id=? AND revoked_at IS NULL ORDER BY created_at', (user_id,)).fetchall()
            return {'sessions': [{'id': r['id'], 'client_name': r['client_name'] or '', 'created_at': r['created_at'],
                                  'last_used_at': r['last_used_at'], 'current': r['id'] == current_id} for r in rows]}

    def revoke_session(self, user_id, session_id):
        with self.tx() as db:
            if db.execute('UPDATE user_sessions SET revoked_at=? WHERE id=? AND user_id=? AND revoked_at IS NULL',
                          (self.clock(), session_id, user_id)).rowcount != 1:
                fail(404, 'Session not found')
        return {'ok': True}

    def auth_any(self, token):
        """Returns (user, None) for a member session or (None, device) for a device token."""
        try:
            return self.auth(token), None
        except HTTPException:
            return None, self.auth(token, 'device')

    def register(self, user_id, name, kind, capabilities, limits):
        token, device_id = secrets.token_urlsafe(32), uid()
        with self.tx() as db:
            count = db.execute('SELECT COUNT(*) FROM devices WHERE owner_id=?', (user_id,)).fetchone()[0]
            if count >= 20:
                fail(409, 'Prototype limit: 20 devices per member')
            db.execute('INSERT INTO devices(id,owner_id,name,kind,token,capabilities,limits,last_seen) VALUES(?,?,?,?,?,?,?,?)',
                       (device_id, user_id, name, kind, digest(token), json.dumps(capabilities), json.dumps(limits), self.clock()))
            return {'device': self.device(db, device_id), 'token': token}

    def device(self, db, device_id):
        row = dict(db.execute('SELECT * FROM devices WHERE id=?', (device_id,)).fetchone())
        row.pop('token')
        for key in ('capabilities', 'limits', 'telemetry'):
            row[key] = json.loads(row[key])
        row['enabled'] = bool(row['enabled'])
        row['online'] = bool(row['last_seen'] and row['last_seen'] > self.clock() - self.lease_seconds)
        task = db.execute("SELECT id FROM tasks WHERE device_id=? AND status='running'", (device_id,)).fetchone()
        row['active_task_id'] = task['id'] if task else None
        row['earned'] = db.execute("SELECT COALESCE(SUM(price),0) FROM tasks WHERE device_id=? AND status='completed'", (device_id,)).fetchone()[0]
        return row

    def change_device(self, user_id, device_id, enabled=None, limits=None):
        with self.tx() as db:
            self.sweep(db)
            row = db.execute('SELECT * FROM devices WHERE id=? AND owner_id=?', (device_id, user_id)).fetchone()
            if not row:
                fail(404, 'Device not found')
            settings = json.loads(row['limits'])
            if limits is not None:
                previous_minutes = settings['session_minutes']
                settings.update(limits)
                db.execute('UPDATE devices SET limits=? WHERE id=?', (json.dumps(settings), device_id))
                if row['enabled'] and 'session_minutes' in limits and row['session_expires_at']:
                    started_at = row['session_expires_at'] - previous_minutes * 60
                    expiry = started_at + settings['session_minutes'] * 60
                    db.execute('UPDATE devices SET session_expires_at=? WHERE id=?', (expiry,device_id))
                    if expiry <= self.clock() and enabled is not True:
                        db.execute('UPDATE devices SET enabled=0 WHERE id=?', (device_id,))
                # Changing limits revokes work so a worker cannot keep old settings.
                self.revoke(db, device_id, 'Workload limits changed')
            if enabled is not None:
                expires = self.clock() + settings['session_minutes'] * 60 if enabled else None
                db.execute('UPDATE devices SET enabled=?,session_expires_at=? WHERE id=?', (enabled, expires, device_id))
                if not enabled:
                    self.revoke(db, device_id, 'Contributor paused')
                    self.event(db, 'device_paused', f"{row['name']} paused sharing", user_id, device_id)
            return self.device(db, device_id)

    def revoke(self, db, device_id, reason):
        rows = db.execute("SELECT * FROM tasks WHERE device_id=? AND status='running'", (device_id,)).fetchall()
        for task in rows:
            self.retry(db, task, reason)

    def retry(self, db, task, reason):
        current = db.execute('SELECT status FROM tasks WHERE id=?', (task['id'],)).fetchone()
        if current['status'] != 'running':
            return
        if task['attempts'] >= 4:
            self.finish_unsuccessful(db, task['job_id'], 'failed', f'Four attempts exhausted: {reason}')
            return
        db.execute("UPDATE tasks SET status='queued',last_device_id=device_id,retry_after=?,device_id=NULL,lease_id=NULL,lease_expires_at=NULL,progress=0 WHERE id=?", (self.clock()+5, task['id']))
        self.event(db, 'task_reassigned', f'{task["kind"]} queued again: {reason}', job_id=task['job_id'], device_id=task['device_id'])

    def sweep(self, db):
        from .leaderboard import advance_availability
        advance_availability(self, db)
        for row in db.execute('SELECT id,owner_id FROM devices WHERE enabled=1 AND session_expires_at<=?', (self.clock(),)).fetchall():
            db.execute('UPDATE devices SET enabled=0 WHERE id=?', (row['id'],))
            self.revoke(db, row['id'], 'Contribution session expired')
            self.event(db, 'device_paused', 'Contribution time limit reached', row['owner_id'], row['id'])
        for task in db.execute("SELECT * FROM tasks WHERE status='running' AND lease_expires_at<=?", (self.clock(),)).fetchall():
            self.retry(db, task, 'Worker disconnected or lease expired')

    def heartbeat(self, device_id, telemetry, task_id=None, lease_id=None):
        with self.tx() as db:
            self.sweep(db)
            db.execute('UPDATE devices SET last_seen=?,telemetry=? WHERE id=?', (self.clock(), json.dumps(telemetry), device_id))
            valid = False
            if task_id and lease_id:
                cursor = db.execute("UPDATE tasks SET lease_expires_at=? WHERE id=? AND device_id=? AND lease_id=? AND status='running'", (self.clock()+self.lease_seconds, task_id, device_id, lease_id))
                valid = cursor.rowcount == 1
            return {'device': self.device(db, device_id), 'lease_valid': valid}

    def new_task(self, db, job, variant, kind='image_generate', source=None):
        task_id = uid()
        db.execute('''INSERT INTO tasks(id,job_id,kind,status,variant,prompt,width,height,steps,seed,price,source_task_id)
                      VALUES(?,?,?,'queued',?,?,?,?,?,?,?,?)''',
                   (task_id, job['id'], kind, variant, job['prompt'], job['width'], job['height'], job['steps'],
                    int(hashlib.sha256(f'{job["id"]}:{variant}'.encode()).hexdigest()[:7], 16),
                    self.job_pricing(db, job['id'])['generate' if kind == 'image_generate' else 'finalize'], source))
        if kind == 'image_finalize':
            # This stage may become ready long after dispatch's generation window.
            # Give its original selection a fresh bounded window when work exists.
            plan = json.loads(db.execute('SELECT plan FROM jobs WHERE id=?', (job['id'],)).fetchone()[0])
            if plan.get('mode', '').startswith('strands-'):
                plan.setdefault('task_routes', {})[task_id] = {
                    'device_ids': plan.get('routes', {}).get(kind, []),
                    'until': self.clock() + 45, 'attempt': 0,
                    'explanation': 'Initial finalizer selection; stage is now ready',
                }
                db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(plan), job['id']))

    def existing_job(self, user_id, request_id):
        with self.tx() as db:
            row = db.execute('SELECT id FROM jobs WHERE owner_id=? AND request_id=?', (user_id, request_id)).fetchone()
            return self.job(db, row['id']) if row else None

    def validate_routes(self, db, request, routes, stages=None):
        """An agent can choose capable volunteers, never widen their consent/limits."""
        stages = stages or ('image_generate','image_finalize')
        if not isinstance(routes,dict) or set(routes)-{'image_generate','image_finalize'}:
            fail(422,'Routes must contain only supported image stages')
        checked = {}
        for stage in stages:
            selected = routes.get(stage,[])
            if not isinstance(selected,list) or len(selected)>20 or any(not isinstance(i,str) for i in selected):
                fail(422,'Routing choices must be a bounded list of device IDs')
            selected = list(dict.fromkeys(selected))
            eligible = []
            for row in db.execute('SELECT id FROM devices'):
                device = self.device(db,row['id'])
                if self.is_eligible(device,stage,request['width']*request['height']):
                    eligible.append(device['id'])
            if any(device_id not in eligible for device_id in selected):
                fail(422,'Selected device is offline, paused, incompatible or over its image limit')
            if eligible and not selected:
                fail(422,f'Choose at least one eligible device for {stage}')
            checked[stage] = selected
        return checked

    @staticmethod
    def is_eligible(device,kind,pixels):
        return device['enabled'] and device['online'] and kind in device['capabilities'] and pixels<=device['limits']['max_pixels']

    def preferred_ready(self,db,task,plan):
        override = plan.get('task_routes',{}).get(task['id'])
        if override:
            if override['attempt'] != task['attempts']:
                return []
            ids,until = override['device_ids'],override['until']
        else:
            # The initial preference authorizes only the first attempt. A failed
            # selected worker must not hold every retry until its window expires.
            if task['attempts']:
                return []
            ids,until = plan.get('routes',{}).get(task['kind'],[]),plan.get('routing_until',0)
        if until<=self.clock():
            return []
        ready = []
        for device_id in ids:
            if task['last_device_id'] == device_id and task['retry_after'] > self.clock():
                continue
            device = self.device(db,device_id)
            if self.is_eligible(device,task['kind'],task['width']*task['height']) and not device['active_task_id']:
                ready.append(device_id)
        return ready

    def update_routing(self,user_id,job_id,routes,expected_attempts,explanation,*,review_claim_id=None):
        with self.tx() as db:
            self.sweep(db)
            row = db.execute('SELECT * FROM jobs WHERE id=? AND owner_id=?',(job_id,user_id)).fetchone()
            if not row:
                fail(404,'Job not found')
            if row['status'] not in ('queued','running'):
                fail(409,'Job is terminal; routing cannot change')
            plan = json.loads(row['plan'])
            if review_claim_id is not None:
                review = plan.get('review', {})
                if (review.get('claim_id') != review_claim_id or review.get('status') != 'running'
                        or review.get('started_at', 0) + 150 <= self.clock()):
                    fail(409, 'Review claim expired or replaced; routing cannot change')
            queued = db.execute("SELECT * FROM tasks WHERE job_id=? AND status='queued'",(job_id,)).fetchall()
            actual = {t['id']:t['attempts'] for t in queued}
            if not actual or actual != expected_attempts:
                fail(409,'Queued work changed; inspect the job again before routing')
            stages = sorted({t['kind'] for t in queued})
            checked = self.validate_routes(db,row,routes,stages)
            overrides = plan.setdefault('task_routes',{})
            for task in queued:
                overrides[task['id']] = {'device_ids':checked[task['kind']],'until':self.clock()+45,
                                         'attempt':task['attempts'],'explanation':str(explanation)[:1200]}
            db.execute('UPDATE jobs SET plan=? WHERE id=?',(json.dumps(plan),job_id))
            self.event(db,'routing_updated',f'Strands updated routing for {len(queued)} queued task(s): {str(explanation)[:300]}',job_id=job_id)
            return self.job(db,job_id)

    def claim_review(self,mode=None):
        """Persist the review lease before calling a provider; no LLM in queue expiry."""
        with self.tx() as db:
            self.sweep(db)
            for row in db.execute('SELECT * FROM jobs ORDER BY created_at').fetchall():
                plan = json.loads(row['plan'])
                if not plan.get('mode','').startswith('strands-'):
                    continue
                if mode and plan.get('mode')!=f'strands-{mode}':
                    continue
                # A request that never left planning has no execution to review.
                if plan.get('planning',{}).get('status','done')!='done':
                    continue
                event = db.execute("SELECT * FROM events WHERE job_id=? AND kind IN ('task_reassigned','job_completed','job_failed','job_cancelled') ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone()
                if not event:
                    continue
                review = plan.get('review',{})
                if review.get('status')=='running' and review.get('started_at',0)+150>self.clock():
                    continue
                same = review.get('event_id')==event['id']
                if same and (review.get('status')=='done' or review.get('attempts',0)>=3 or review.get('next_retry_at',0)>self.clock()):
                    continue
                plan['review'] = {'claim_id':uid(),'event_id':event['id'],'status':'running','started_at':self.clock(),
                                  'attempts':review.get('attempts',0)+1 if same else 1}
                db.execute('UPDATE jobs SET plan=? WHERE id=?',(json.dumps(plan),row['id']))
                result = self.job(db,row['id'])
                result['review_event'] = dict(event)
                return result
            return None

    def finish_review(self,job_id,event_id,trace,error=None,claim_id=None):
        with self.tx() as db:
            row = db.execute('SELECT plan FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not row:
                return False
            plan = json.loads(row['plan'])
            review = plan.get('review',{})
            if (review.get('event_id')!=event_id or review.get('status')!='running'
                    or review.get('started_at',0)+150<=self.clock()
                    or (claim_id and review.get('claim_id')!=claim_id)):
                return False
            review.update(status='error' if error else 'done',finished_at=self.clock(),next_retry_at=self.clock()+30)
            if error:
                review['error'] = str(error)[:500]
            history = plan.setdefault('reviews',[])
            history.append({'event_id':event_id,'at':self.clock(),'status':review['status'],'tools':trace,'error':str(error)[:500] if error else None})
            plan['reviews'] = history[-10:]
            db.execute('UPDATE jobs SET plan=? WHERE id=?',(json.dumps(plan),job_id))
            self.event(db,'agent_review_failed' if error else 'agent_reviewed',
                       'Strands review unavailable; deterministic recovery remains active' if error else 'Strands checked execution results and routing',job_id=job_id)
            return True

    def current_pricing(self, db):
        grid = self.grid_counts(db)
        return price_for(grid['ready_to_create'])

    def job_pricing(self, db, job_id):
        """The prices locked when the job reserved its budget; older jobs used fixed prices."""
        plan = json.loads(db.execute('SELECT plan FROM jobs WHERE id=?', (job_id,)).fetchone()[0])
        return plan.get('pricing') or LEGACY_PRICING

    def reserve_job(self, db, user_id, request, status, plan):
        """Insert a job and reserve its full budget; caller has checked idempotency."""
        pricing = self.current_pricing(db)
        minimum = quote(request['count'], pricing)
        if request['budget'] < minimum:
            fail(422, f'Budget must cover the current quote of {minimum} sandbox credits')
        plan = dict(plan, pricing=pricing)
        active = db.execute(f"SELECT COUNT(*) FROM jobs WHERE owner_id=? AND status IN {ACTIVE}", (user_id,)).fetchone()[0]
        if active >= 10:
            fail(409, 'Finish or cancel an existing job first')
        if db.execute('UPDATE users SET balance=balance-? WHERE id=? AND balance>=?', (request['budget'], user_id, request['budget'])).rowcount != 1:
            fail(402, 'Insufficient sandbox balance')
        job_id = uid()
        db.execute('''INSERT INTO jobs(id,owner_id,request_id,prompt,status,count,width,height,steps,budget,created_at,plan)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (job_id, user_id, request['request_id'], request['prompt'], status, request['count'], request['width'], request['height'], request['steps'], request['budget'], self.clock(), json.dumps(plan)))
        self.ledger(db, user_id, job_id, 'reserve', -request['budget'], 'Reserved for device computation')
        return job_id

    def create_job(self, user_id, request, plan):
        with self.tx() as db:
            self.sweep(db)
            previous = db.execute('SELECT id FROM jobs WHERE owner_id=? AND request_id=?', (user_id, request['request_id'])).fetchone()
            if previous:
                return self.job(db, previous['id'])
            plan = dict(plan)
            if plan.get('mode','').startswith('strands-'):
                plan['routes'] = self.validate_routes(db,request,plan.get('routes',{}))
                plan['routing_until'] = self.clock()+45
            job_id = self.reserve_job(db, user_id, request, 'queued', plan)
            job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
            for variant in range(request['count']):
                self.new_task(db, job, variant)
            self.event(db, 'job_created', f'{request["count"]} image(s) queued; {request["budget"]} credits reserved', job_id=job_id)
            return self.job(db, job_id)

    def create_planning_job(self, user_id, request, mode):
        """Persist and reserve before any model call so retries and restarts find it."""
        with self.tx() as db:
            self.sweep(db)
            previous = db.execute('SELECT id FROM jobs WHERE owner_id=? AND request_id=?', (user_id, request['request_id'])).fetchone()
            if previous:
                return self.job(db, previous['id'])
            plan = {'mode': f'strands-{mode}', 'explanation': 'Strands is planning device selection.',
                    'planning': {'status': 'pending', 'attempts': 0}}
            job_id = self.reserve_job(db, user_id, request, 'planning', plan)
            self.event(db, 'job_planning', f'{request["count"]} image(s) accepted for planning; {request["budget"]} credits reserved', job_id=job_id)
            return self.job(db, job_id)

    @staticmethod
    def planning_claim_live(planning, claim_id, now):
        return (planning.get('claim_id') == claim_id and planning.get('status') == 'running'
                and planning.get('started_at', 0) + PLANNING_CLAIM_SECONDS > now)

    def claim_planning(self):
        """Durably lease the oldest unplanned request before calling a provider."""
        with self.tx() as db:
            self.sweep(db)
            for row in db.execute("SELECT * FROM jobs WHERE status='planning' ORDER BY created_at").fetchall():
                plan = json.loads(row['plan'])
                planning = plan.setdefault('planning', {'status': 'pending', 'attempts': 0})
                if planning.get('status') == 'running' and planning.get('started_at', 0) + PLANNING_CLAIM_SECONDS > self.clock():
                    continue
                if planning.get('attempts', 0) >= PLANNING_ATTEMPTS:
                    planning.update(status='failed', finished_at=self.clock())
                    db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(plan), row['id']))
                    self.finish_unsuccessful(db, row['id'], 'failed', 'Planning did not finish; reserved credits returned')
                    continue
                planning.update(claim_id=uid(), status='running', started_at=self.clock(),
                                attempts=planning.get('attempts', 0) + 1)
                db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(plan), row['id']))
                return self.job(db, row['id'])
            return None

    def activate_job(self, job_id, claim_id, routes, explanation, tools):
        """Turn a planned request into queued work, only under its live planning claim."""
        with self.tx() as db:
            self.sweep(db)
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                fail(404, 'Job not found')
            if row['status'] != 'planning':
                fail(409, f'Request is {row["status"]}; it can no longer be submitted')
            plan = json.loads(row['plan'])
            if not self.planning_claim_live(plan.get('planning', {}), claim_id, self.clock()):
                fail(409, 'Planning claim expired or replaced; this plan is stale')
            plan.update(explanation=str(explanation)[:1200], tools=tools,
                        routes=self.validate_routes(db, row, routes), routing_until=self.clock()+45)
            plan['planning'].update(status='done', finished_at=self.clock())
            db.execute("UPDATE jobs SET status='queued',plan=? WHERE id=?", (json.dumps(plan), job_id))
            job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
            for variant in range(job['count']):
                self.new_task(db, job, variant)
            self.event(db, 'job_created', f'Strands planned {job["count"]} image(s); work queued', job_id=job_id)
            return self.job(db, job_id)

    def finish_planning(self, job_id, claim_id, tools, error=None):
        """Record the planner trace; fail and refund a request the planner never submitted."""
        with self.tx() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                return False
            plan = json.loads(row['plan'])
            planning = plan.get('planning', {})
            if planning.get('claim_id') != claim_id:
                return False
            if row['status'] == 'planning' and not self.planning_claim_live(planning, claim_id, self.clock()):
                return False  # Another planner may now own this request.
            plan['tools'] = tools
            if error:
                plan['dispatch_error'] = str(error)[:200]
            if row['status'] == 'planning':
                planning.update(status='failed', finished_at=self.clock())
            elif planning.get('status') == 'running':
                planning.update(status=row['status'], finished_at=self.clock())  # Cancelled meanwhile.
            db.execute('UPDATE jobs SET plan=? WHERE id=?', (json.dumps(plan), job_id))
            if row['status'] == 'planning':
                self.finish_unsuccessful(db, job_id, 'failed',
                                         f'Strands could not schedule ({str(error or "no submission")[:120]}); reserved credits returned')
            return True

    def task(self, db, row):
        task = dict(row)
        task.pop('last_device_id', None)
        task.pop('retry_after', None)
        task['metrics'] = json.loads(task['metrics'])
        if task['source_task_id']:
            source = db.execute('SELECT artifact_id FROM tasks WHERE id=?', (task['source_task_id'],)).fetchone()
            task['source_url'] = f'/api/images/{source["artifact_id"]}'
        else:
            task['source_url'] = None
        task['output_url'] = f'/api/images/{task["artifact_id"]}' if task['artifact_id'] else None
        device = db.execute('SELECT kind FROM devices WHERE id=?', (task['device_id'],)).fetchone() if task['device_id'] else None
        task['device_kind'] = device['kind'] if device else None
        return task

    def claim(self, device_id):
        with self.tx() as db:
            self.sweep(db)
            device = self.device(db, device_id)
            if not device['enabled']:
                return {'task': None, 'device': device}
            db.execute('UPDATE devices SET last_seen=? WHERE id=?', (self.clock(), device_id))
            active = db.execute("SELECT * FROM tasks WHERE device_id=? AND status='running'", (device_id,)).fetchone()
            if active:
                return {'task': self.task(db, active), 'device': self.device(db, device_id)}
            rows = db.execute("SELECT t.* FROM tasks t JOIN jobs j ON j.id=t.job_id WHERE t.status='queued' AND j.status IN ('queued','running') ORDER BY CASE t.kind WHEN 'image_generate' THEN 0 ELSE 1 END,j.created_at,t.variant").fetchall()
            for task in rows:
                if task['kind'] not in device['capabilities'] or task['width']*task['height'] > device['limits']['max_pixels']:
                    continue
                if task['last_device_id'] == device_id and task['retry_after'] > self.clock():
                    continue
                plan = json.loads(db.execute('SELECT plan FROM jobs WHERE id=?',(task['job_id'],)).fetchone()[0])
                preferred = self.preferred_ready(db,task,plan)
                if preferred and device_id not in preferred:
                    continue
                lease = uid()
                db.execute("UPDATE tasks SET status='running',device_id=?,lease_id=?,lease_expires_at=?,attempts=attempts+1 WHERE id=?", (device_id, lease, self.clock()+self.lease_seconds, task['id']))
                db.execute("UPDATE jobs SET status='running' WHERE id=?", (task['job_id'],))
                self.event(db, 'task_started', f"{device['name']} started {task['kind']}", device['owner_id'], device_id, task['job_id'])
                if preferred:
                    self.event(db,'routing_applied',f"Strands-selected device {device['name']} claimed {task['kind']}",job_id=task['job_id'],device_id=device_id)
                return {'task': self.task(db, db.execute('SELECT * FROM tasks WHERE id=?', (task['id'],)).fetchone()), 'device': self.device(db, device_id)}
            return {'task': None, 'device': self.device(db, device_id)}

    def cloud_task(self, device_id, task_id, lease_id):
        """What the hosted model needs for a generation task this device currently holds."""
        with self.tx() as db:
            task = self.live_task(db, task_id, device_id, lease_id)
            if task['status'] != 'running':
                fail(409, 'Task is no longer running')
            if task['kind'] != 'image_generate':
                fail(422, 'Only image generation runs in the cloud')
            return {key: task[key] for key in ('prompt', 'width', 'height', 'seed')}

    def record_cloud_output(self, task_id, model):
        # Coordinator-side record: the label cannot be set or hidden by a worker.
        with self.tx() as db:
            db.execute('INSERT OR REPLACE INTO cloud_outputs VALUES(?,?,?)', (task_id, model, self.clock()))

    def record_checkout(self, user_id, session_id, pack, credits, amount, currency):
        with self.tx() as db:
            db.execute("INSERT INTO purchases VALUES(?,?,?,?,?,?,'pending',?,NULL)",
                       (session_id, user_id, pack, credits, amount, currency, self.clock()))

    def purchase(self, session_id, user_id=None):
        with self.tx() as db:
            row = db.execute('SELECT * FROM purchases WHERE session_id=?', (session_id,)).fetchone()
        if not row or (user_id and row['user_id'] != user_id):
            fail(404, 'Purchase not found')
        return dict(row)

    def settle_purchase(self, session):
        """Grant credits once for a paid Stripe Checkout session this coordinator created.

        Money only flows in: credits are added to the balance and ledger, and nothing
        in the system converts them back to money."""
        with self.tx() as db:
            row = db.execute('SELECT * FROM purchases WHERE session_id=?', (session.get('id'),)).fetchone()
            if not row:
                fail(404, 'Purchase not found')
            if row['status'] == 'paid':
                return {'status': 'paid', 'credits': row['credits'], 'duplicate': True}
            matches = (session.get('payment_status') == 'paid' and session.get('livemode') is False
                       and session.get('client_reference_id') == row['user_id']
                       and session.get('amount_total') == row['amount'] and session.get('currency') == row['currency'])
            if not matches:
                return {'status': row['status'], 'credits': row['credits'], 'duplicate': False}
            if db.execute("UPDATE purchases SET status='paid',settled_at=? WHERE session_id=? AND status='pending'",
                          (self.clock(), row['session_id'])).rowcount != 1:
                return {'status': 'paid', 'credits': row['credits'], 'duplicate': True}
            db.execute('UPDATE users SET balance=balance+? WHERE id=?', (row['credits'], row['user_id']))
            self.ledger(db, row['user_id'], None, 'purchase', row['credits'],
                        f"Bought {row['credits']} credits (test-mode card payment); credits cannot be cashed out")
            self.event(db, 'credits_purchased', 'Credits added from a test-mode card payment', row['user_id'])
            return {'status': 'paid', 'credits': row['credits'], 'duplicate': False}

    def live_task(self, db, task_id, device_id, lease_id):
        self.sweep(db)
        row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            fail(404, 'Task not found')
        if row['device_id'] != device_id or row['lease_id'] != lease_id:
            fail(409, 'Lease revoked; discard this result')
        return row

    def progress(self, device_id, task_id, lease_id, progress, stage):
        with self.tx() as db:
            task = self.live_task(db, task_id, device_id, lease_id)
            if task['status'] != 'running':
                fail(409, 'Task is no longer running')
            db.execute('UPDATE tasks SET progress=? WHERE id=?', (progress, task_id))
            return {'ok': True}

    def task_failed(self, device_id, task_id, lease_id, error):
        with self.tx() as db:
            task = self.live_task(db, task_id, device_id, lease_id)
            if task['status'] != 'running':
                fail(409, 'Task is no longer running')
            self.retry(db, task, error[:200])
            return {'ok': True}

    def complete(self, device_id, task_id, lease_id, png_base64, metrics):
        # Decode bounded input first; settlement remains entirely transactional.
        try:
            payload = base64.b64decode(png_base64, validate=True)
            with Image.open(io.BytesIO(payload)) as opened:
                if opened.format != 'PNG' or opened.width > 512 or opened.height > 512:
                    fail(422, 'Expected PNG no larger than 512x512')
                opened.load()
                image = opened.convert('RGB')
        except HTTPException:
            raise
        except Exception:
            fail(422, 'Invalid PNG data')
        with self.tx() as db:
            task = self.live_task(db, task_id, device_id, lease_id)
            if task['status'] == 'completed':
                return {'accepted': True, 'duplicate': True, 'earned': task['price']}
            if task['status'] != 'running':
                fail(409, 'Task is no longer running')
            if image.size != (task['width'], task['height']):
                fail(422, 'Image dimensions differ from assigned task')
            if task['kind'] == 'image_finalize':
                source = db.execute('SELECT artifact_id FROM tasks WHERE id=?', (task['source_task_id'],)).fetchone()
                with Image.open(self.root / 'images' / f'{source["artifact_id"]}.png') as original:
                    expected = original.convert('RGB')
                if image.tobytes() != expected.tobytes():
                    from PIL import ImageDraw
                    ImageDraw.Draw(expected).rectangle((0, 0, expected.width-1, expected.height-1), outline=(36,203,166), width=4)
                    if not self.accept_legacy_frame or image.tobytes() != expected.tobytes():
                        fail(422, 'Export pixel verification failed')
            artifact_id = uid()
            path = self.root / 'images' / f'{artifact_id}.png'
            # Re-encode to remove arbitrary metadata from contributed files.
            image.save(path, format='PNG')
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?)', (artifact_id, task['job_id'], task_id, hashlib.sha256(path.read_bytes()).hexdigest()))
            db.execute("UPDATE tasks SET status='completed',progress=1,artifact_id=?,metrics=? WHERE id=?", (artifact_id, json.dumps(metrics), task_id))
            owner_id = db.execute('SELECT owner_id FROM devices WHERE id=?', (device_id,)).fetchone()[0]
            db.execute('UPDATE users SET balance=balance+? WHERE id=?', (task['price'], owner_id))
            db.execute('UPDATE jobs SET spent=spent+? WHERE id=?', (task['price'], task['job_id']))
            self.ledger(db, owner_id, task['job_id'], 'earned', task['price'], f'Accepted {task["kind"]} {task_id}')
            self.event(db, 'credits_earned', f'{task["price"]} sandbox credits earned for accepted work', owner_id, device_id, task['job_id'])
            job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (task['job_id'],)).fetchone())
            if task['kind'] == 'image_generate':
                self.new_task(db, job, task['variant'], 'image_finalize', task_id)
            if db.execute("SELECT COUNT(*) FROM tasks WHERE job_id=? AND status!='completed'", (job['id'],)).fetchone()[0] == 0:
                fee = self.job_pricing(db, job['id'])['fee']
                refund = job['budget'] - job['spent'] - fee
                db.execute("UPDATE jobs SET status='completed',fee=?,spent=spent+?,refunded=? WHERE id=?", (fee, fee, refund, job['id']))
                db.execute('UPDATE users SET balance=balance+? WHERE id=?', (refund, job['owner_id']))
                self.ledger(db, job['owner_id'], job['id'], 'refund', refund, 'Unused reservation returned')
                self.event(db, 'job_completed', 'Images ready. Contributors paid; unused credits returned.', job_id=job['id'])
            return {'accepted': True, 'duplicate': False, 'earned': task['price']}

    def finish_unsuccessful(self, db, job_id, status, reason):
        job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if job['status'] in ('completed','cancelled','failed'):
            return
        refund = job['budget'] - job['spent']
        db.execute('UPDATE jobs SET status=?,refunded=? WHERE id=?', (status, refund, job_id))
        db.execute("UPDATE tasks SET status='cancelled',lease_id=NULL,lease_expires_at=NULL WHERE job_id=? AND status!='completed'", (job_id,))
        db.execute('UPDATE users SET balance=balance+? WHERE id=?', (refund, job['owner_id']))
        self.ledger(db, job['owner_id'], job_id, 'refund', refund, reason)
        self.event(db, f'job_{status}', reason, job_id=job_id)

    def cancel(self, user_id, job_id):
        with self.tx() as db:
            if not db.execute('SELECT id FROM jobs WHERE id=? AND owner_id=?', (job_id, user_id)).fetchone():
                fail(404, 'Job not found')
            self.finish_unsuccessful(db, job_id, 'cancelled', 'Cancelled; unfinished work refunded')
            return self.job(db, job_id)

    def job(self, db, job_id):
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            fail(404, 'Job not found')
        job = dict(row)
        job['plan'] = json.loads(job['plan'])
        job['reserved'] = job['budget'] - job['spent'] - job['refunded']
        job['tasks'] = [self.task(db, t) for t in db.execute('SELECT * FROM tasks WHERE job_id=? ORDER BY variant,kind', (job_id,))]
        # Only expose public job fields. A live lease is a worker credential.
        for task in job['tasks']:
            task.pop('lease_id', None)
        cloud = {r['task_id']: r['model'] for r in db.execute(
            'SELECT task_id,model FROM cloud_outputs WHERE task_id IN (SELECT id FROM tasks WHERE job_id=?)', (job_id,))}
        def made_by(task):
            # A finished image carries the label of the generation it copies.
            model = cloud.get(task['id'] if task['kind'] == 'image_generate' else task['source_task_id'])
            return {'generated_in': 'cloud', 'model': model} if model else {'generated_in': 'device'}
        job['images'] = [{'task_id': t['id'], 'url': t['output_url'], 'variant': t['variant'], 'stage': t['kind'],
                          'verified': t['kind'] == 'image_finalize', **made_by(t)} for t in job['tasks'] if t['output_url']]
        job['receipt'] = {'budget': job['budget'], 'contributor_total': job['spent']-job['fee'], 'platform_fee': job['fee'], 'refund': job['refunded'], 'total_charged': job['spent']} if job['status'] in ('completed','cancelled','failed') else None
        return job

    def grid_devices(self, db=None):
        """Every device, for the planner and grid counts; never returned to a member."""
        if db is None:
            with self.tx() as db:
                self.sweep(db)
                return self.grid_devices(db)
        return [self.device(db, row['id']) for row in db.execute('SELECT id FROM devices ORDER BY rowid')]

    def grid_counts(self, db):
        devices = [d for d in self.grid_devices(db) if d['online']]
        ready = lambda kind: sum(1 for d in devices if d['enabled'] and kind in d['capabilities'])
        return {'connected': len(devices), 'ready_to_create': ready('image_generate'), 'ready_to_finish': ready('image_finalize')}

    def own_devices(self, db, viewer_id):
        return {r['id']: dict(r) for r in db.execute(
            'SELECT id,name,kind FROM devices WHERE owner_id=?', (viewer_id,))}

    @staticmethod
    def public_plan(plan, own, task_ids):
        """Project trusted fields, never redact free text using today's device names.

        Planner explanations/errors/traces can contain old names, short names and
        raw IDs. Keep those internally; member summaries come from fixed strings.
        """
        mode = plan.get('mode', '')
        if mode not in ('manual', 'strands-ollama', 'strands-akamai', 'strands-bedrock'):
            mode = 'strands' if mode.startswith('strands-') else 'manual'
        result = {'mode': mode,
                  'explanation': 'Compatible devices selected for your request.',
                  'routes': {stage: [d for d in ids if d in own]
                             for stage, ids in plan.get('routes', {}).items()
                             if stage in ('image_generate', 'image_finalize')}}
        if isinstance(plan.get('routing_until'), (int, float)):
            result['routing_until'] = plan['routing_until']
        pricing = plan.get('pricing')
        if isinstance(pricing, dict) and all(isinstance(pricing.get(k), int) for k in ('generate', 'finalize', 'fee')):
            result['pricing'] = {k: pricing[k] for k in ('generate', 'finalize', 'fee')}
        for key in ('planning', 'review'):
            if key not in plan:
                continue
            source = plan[key]
            state = {k: source[k] for k in ('attempts', 'started_at', 'finished_at', 'next_retry_at')
                     if isinstance(source.get(k), (int, float))}
            if source.get('status') in ('pending', 'running', 'done', 'failed', 'cancelled', 'error'):
                state['status'] = source['status']
            if source.get('error'):
                state['error'] = 'Device selection is temporarily unavailable.'
            result[key] = state
        if plan.get('dispatch_error'):
            result['dispatch_error'] = 'Device selection could not finish.'
        if 'task_routes' in plan:
            result['task_routes'] = {}
            for task_id, route in plan['task_routes'].items():
                if task_id not in task_ids:
                    continue
                result['task_routes'][task_id] = {
                    'device_ids': [d for d in route.get('device_ids', []) if d in own],
                    'explanation': 'Device selection updated for this work.',
                    **{k: route[k] for k in ('until', 'attempt') if isinstance(route.get(k), (int, float))}}
        return result

    def public_job(self, db, job, viewer_id):
        """A member's view: own routes remain useful; foreign devices are anonymous."""
        own = self.own_devices(db, viewer_id)
        job = copy.deepcopy(job)
        for task in job['tasks']:
            if task.get('device_id') not in own:
                task['device_id'] = None
                # Worker-supplied metrics are free-form, including keys. Retain
                # useful numeric timing without exposing arbitrary worker text.
                task['metrics'] = {k: v for k, v in task.get('metrics', {}).items()
                                   if k == 'elapsed_seconds' and isinstance(v, (int, float))}
        job['plan'] = self.public_plan(job['plan'], own, {t['id'] for t in job['tasks']})
        return job

    def view_job(self, job, viewer_id):
        with self.tx() as db:
            return self.public_job(db, job, viewer_id)

    def member_job(self, job_id, user=None, device=None):
        """GET /jobs/{id}: the owning member, or a device assigned to one of its tasks."""
        with self.tx() as db:
            self.sweep(db)
            row = db.execute('SELECT owner_id FROM jobs WHERE id=?', (job_id,)).fetchone()
            if user and row and row['owner_id'] == user['id']:
                return self.public_job(db, self.job(db, job_id), user['id'])
            if device and row and db.execute('SELECT 1 FROM tasks WHERE job_id=? AND (device_id=? OR last_device_id=?)', (job_id, device['id'], device['id'])).fetchone():
                return self.public_job(db, self.job(db, job_id), device['owner_id'])
            fail(404, 'Job not found')

    def image_path(self, artifact_id, user=None, device=None):
        with self.tx() as db:
            self.sweep(db)
            artifact = db.execute('SELECT a.*,j.owner_id FROM artifacts a JOIN jobs j ON j.id=a.job_id WHERE a.id=?', (artifact_id,)).fetchone()
            allowed = artifact and (
                (user and artifact['owner_id'] == user['id'])
                or (device and db.execute("SELECT 1 FROM tasks WHERE device_id=? AND status IN ('running','completed') AND (id=? OR source_task_id=?)",
                                          (device['id'], artifact['task_id'], artifact['task_id'])).fetchone()))
            if not allowed:
                fail(404, 'Image not found')
        return self.root / 'images' / f'{artifact_id}.png'

    def public_events(self, db, user_id):
        own = self.own_devices(db, user_id)
        jobs = {r['id']: dict(r) for r in db.execute('SELECT id,count,budget FROM jobs WHERE owner_id=?', (user_id,))}
        kinds = {r['id']: r['kind'] for r in db.execute('SELECT id,kind FROM devices')}
        summaries = {
            'routing_updated': 'Device selection updated for your request',
            'task_reassigned': 'Image work queued again for another device',
            'agent_review_failed': 'Device selection is unavailable; automatic recovery remains active',
            'agent_reviewed': 'Execution results and device selection checked',
            'job_completed': 'Images ready. Contributors paid; unused credits returned.',
            'job_failed': 'Request could not finish; unused credits returned',
            'job_cancelled': 'Cancelled; unfinished work refunded',
            'credits_purchased': 'Credits added from a test-mode card payment',
        }
        events = []
        for row in db.execute('SELECT * FROM events WHERE user_id=? OR job_id IN (SELECT id FROM jobs WHERE owner_id=?) ORDER BY id DESC LIMIT 60', (user_id, user_id)):
            event = dict(row)
            mine = event['user_id'] == user_id
            if not mine and event['kind'] == 'credits_earned':
                continue
            device = own.get(event['device_id'])
            word = DEVICE_WORDS.get(kinds.get(event['device_id']), 'device')
            subject = device['name'] if device else f'A grid {word}'
            # Do not forward stored messages: provider errors and routing events
            # can leak names/IDs even when there is no associated device_id.
            message = summaries.get(event['kind'], 'Grid activity updated')
            if event['kind'] == 'task_started':
                message = f'{subject} started work on your images' if not device else f'{subject} started image work'
            elif event['kind'] == 'routing_applied':
                message = f'{subject} took selected image work'
            elif event['kind'] == 'device_paused' and device:
                message = f'{subject} reached its contribution time limit' if event['message'] == 'Contribution time limit reached' else f'{subject} paused sharing'
            elif event['kind'] == 'credits_earned' and mine:
                # This exact coordinator-generated format has no arbitrary text.
                earned_messages = {f'{price} sandbox credits earned for accepted work' for price in range(1, 10)}
                message = event['message'] if event['message'] in earned_messages else 'Sandbox credits earned for accepted work'
            elif event['kind'] in ('job_created', 'job_planning') and event['job_id'] in jobs:
                job = jobs[event['job_id']]
                action = 'accepted for planning' if event['kind'] == 'job_planning' else 'queued'
                message = f'{job["count"]} image(s) {action}; {job["budget"]} credits reserved'
            event['message'] = message
            if not device:
                event['device_id'] = None
            if not mine:
                event['user_id'] = None
            if event['job_id'] not in jobs:
                event['job_id'] = None
            events.append(event)
        return events

    def public_ledger(self, db, user_id):
        entries = [dict(row) for row in db.execute('SELECT * FROM ledger WHERE user_id=? ORDER BY created_at DESC LIMIT 60', (user_id,))]
        for entry in entries:
            # Refund reasons may embed planner errors. Amounts and job links are
            # unchanged; the original reason remains in the coordinator ledger.
            if entry['kind'] == 'refund':
                entry['note'] = 'Unused reservation returned'
        return entries

    def snapshot(self, user_id):
        with self.tx() as db:
            self.sweep(db)
            user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            login = db.execute('SELECT username FROM credentials WHERE user_id=?', (user_id,)).fetchone()
            return {
                'user': {'id': user['id'], 'name': user['name'], 'username': login['username'] if login else None}, 'balance': user['balance'],
                'reserved': db.execute("SELECT COALESCE(SUM(budget-spent-refunded),0) FROM jobs WHERE owner_id=?", (user_id,)).fetchone()[0],
                'earned': db.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE user_id=? AND kind='earned'", (user_id,)).fetchone()[0],
                'grid': self.grid_counts(db),
                'devices': [self.device(db, row['id']) for row in db.execute('SELECT id FROM devices WHERE owner_id=? ORDER BY rowid', (user_id,))],
                'jobs': [self.public_job(db, self.job(db, row['id']), user_id) for row in db.execute('SELECT id FROM jobs WHERE owner_id=? ORDER BY created_at DESC LIMIT 30', (user_id,))],
                'events': self.public_events(db, user_id),
                'ledger': self.public_ledger(db, user_id),
                'pricing': self.current_pricing(db), 'server_time': self.clock(),
            }

    def tick(self):
        with self.tx() as db:
            self.sweep(db)

    def leaderboard(self, user_id, metric='overall'):
        from .leaderboard import view
        with self.tx() as db:
            self.sweep(db)
            return view(self, db, user_id, metric)

    def leaderboard_profile(self, user_id, enabled, public_nickname):
        from .leaderboard import nickname, view
        public_nickname = nickname(public_nickname)
        with self.tx() as db:
            self.sweep(db)
            db.execute('''INSERT INTO leaderboard_profiles(user_id,enabled,nickname) VALUES(?,?,?)
                          ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,nickname=excluded.nickname''',
                       (user_id, bool(enabled), public_nickname))
            return view(self, db, user_id)
