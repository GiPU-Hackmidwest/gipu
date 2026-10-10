"""Durable single-coordinator queue and integer sandbox-credit ledger.

All transitions use BEGIN IMMEDIATE. Lease IDs fence late workers, and settlement
occurs in the same transaction as result acceptance. SQLite is intentionally a
single-node prototype; do not run replicas against different volumes.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
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
            CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status,kind);
            CREATE INDEX IF NOT EXISTS tasks_job ON tasks(job_id);
            ''')

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

    def session(self, name):
        token, user_id = secrets.token_urlsafe(32), uid()
        with self.tx() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (user_id, name, digest(token), 100, self.clock()))
            self.ledger(db, user_id, None, 'demo_grant', 100, 'Sandbox grant; no cash value')
        return {'token': token, 'user': {'id': user_id, 'name': name}, 'balance': 100}

    def auth(self, token, kind='session'):
        table = 'users' if kind == 'session' else 'devices'
        with self.tx() as db:
            row = db.execute(f'SELECT * FROM {table} WHERE token=?', (digest(token),)).fetchone()
            if not row:
                fail(401, 'Invalid or missing credential')
            return dict(row)

    def auth_any(self, token):
        try:
            return self.auth(token)
        except HTTPException:
            return self.auth(token, 'device')

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
                    6 if kind == 'image_generate' else 1, source))
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
            minimum = request['count'] * 7 + 1
            if request['budget'] < minimum:
                fail(422, f'Budget must cover the fixed quote of {minimum} sandbox credits')
            active = db.execute("SELECT COUNT(*) FROM jobs WHERE owner_id=? AND status IN ('queued','running')", (user_id,)).fetchone()[0]
            if active >= 10:
                fail(409, 'Finish or cancel an existing job first')
            if db.execute('UPDATE users SET balance=balance-? WHERE id=? AND balance>=?', (request['budget'], user_id, request['budget'])).rowcount != 1:
                fail(402, 'Insufficient sandbox balance')
            job_id = uid()
            db.execute('''INSERT INTO jobs(id,owner_id,request_id,prompt,status,count,width,height,steps,budget,created_at,plan)
                          VALUES(?,?,?,?,'queued',?,?,?,?,?,?,?)''',
                       (job_id, user_id, request['request_id'], request['prompt'], request['count'], request['width'], request['height'], request['steps'], request['budget'], self.clock(), json.dumps(plan)))
            job = dict(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
            for variant in range(request['count']):
                self.new_task(db, job, variant)
            self.ledger(db, user_id, job_id, 'reserve', -request['budget'], 'Reserved for device computation')
            self.event(db, 'job_created', f'{request["count"]} image(s) queued; {request["budget"]} credits reserved', job_id=job_id)
            return self.job(db, job_id)

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
                from PIL import ImageDraw
                draw = ImageDraw.Draw(expected)
                draw.rectangle((0, 0, expected.width-1, expected.height-1), outline=(36,203,166), width=4)
                if image.tobytes() != expected.tobytes():
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
                refund = job['budget'] - job['spent'] - 1
                db.execute("UPDATE jobs SET status='completed',fee=1,spent=spent+1,refunded=? WHERE id=?", (refund, job['id']))
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
        job['images'] = [{'task_id': t['id'], 'url': t['output_url'], 'variant': t['variant'], 'stage': t['kind']} for t in job['tasks'] if t['output_url']]
        job['receipt'] = {'budget': job['budget'], 'contributor_total': job['spent']-job['fee'], 'platform_fee': job['fee'], 'refund': job['refunded'], 'total_charged': job['spent']} if job['status'] in ('completed','cancelled','failed') else None
        return job

    def snapshot(self, user_id):
        with self.tx() as db:
            self.sweep(db)
            user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            return {
                'user': {'id': user['id'], 'name': user['name']}, 'balance': user['balance'],
                'reserved': db.execute("SELECT COALESCE(SUM(budget-spent-refunded),0) FROM jobs WHERE owner_id=?", (user_id,)).fetchone()[0],
                'earned': db.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE user_id=? AND kind='earned'", (user_id,)).fetchone()[0],
                'devices': [self.device(db, row['id']) for row in db.execute('SELECT id FROM devices ORDER BY rowid')],
                'jobs': [self.job(db, row['id']) for row in db.execute('SELECT id FROM jobs ORDER BY created_at DESC LIMIT 30')],
                'events': [dict(row) for row in db.execute('SELECT * FROM events WHERE user_id=? OR user_id IS NULL OR job_id IN (SELECT id FROM jobs WHERE owner_id=?) ORDER BY id DESC LIMIT 60', (user_id,user_id))],
                'ledger': [dict(row) for row in db.execute('SELECT * FROM ledger WHERE user_id=? ORDER BY created_at DESC LIMIT 60', (user_id,))],
                'pricing': {'generate': 6, 'finalize': 1, 'fee': 1}, 'server_time': self.clock(),
            }

    def tick(self):
        with self.tx() as db:
            self.sweep(db)
