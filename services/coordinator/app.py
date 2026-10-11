from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import agent
from .store import Store


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Session(Strict):
    name: str = Field(min_length=1, max_length=60)
    join_code: str = Field(min_length=1, max_length=200)


class Limits(Strict):
    cpu_threads: int = Field(default=2, ge=1, le=8)
    max_pixels: Literal[65536, 147456, 262144] = 262144
    session_minutes: int = Field(default=30, ge=1, le=120)


class DeviceRegistration(Strict):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['browser','python','ios']
    capabilities: list[Literal['image_generate','image_finalize']] = Field(min_length=1,max_length=2)
    limits: Limits = Field(default_factory=Limits)


class DeviceUpdate(Strict):
    enabled: bool | None = None
    limits: Limits | None = None


class Heartbeat(Strict):
    telemetry: dict = Field(default_factory=dict)
    task_id: str | None = None
    lease_id: str | None = None


class JobRequest(Strict):
    prompt: str = Field(min_length=3, max_length=1000)
    count: int = Field(default=1, ge=1, le=4)
    width: Literal[256,384,512] = 256
    height: Literal[256,384,512] = 256
    steps: int = Field(default=12, ge=4, le=30)
    budget: int = Field(default=10, ge=1, le=100)
    request_id: str = Field(min_length=8,max_length=80)
    use_agent: bool = False


class Progress(Strict):
    lease_id: str
    progress: float = Field(ge=0,le=1)
    stage: str = Field(default='',max_length=200)


class Completion(Strict):
    lease_id: str
    png_base64: str = Field(max_length=4_000_000)
    metrics: dict = Field(default_factory=dict)


class Failure(Strict):
    lease_id: str
    error: str = Field(max_length=1000)


def create_app(data_dir=None):
    store = Store(data_dir or os.getenv('POCKETGRID_DATA', './data'))

    @asynccontextmanager
    async def lifespan(app):
        async def expire():
            while True:
                await asyncio.to_thread(store.tick)
                await asyncio.sleep(1)
        async def background(name, step, pause):
            while True:
                try:
                    # A slow provider call blocks only this loop, never lease expiry.
                    await asyncio.to_thread(step,store)
                except Exception:
                    # Claims are durable and expire; an unexpected agent failure
                    # must never stop lease expiry or accepted-work settlement.
                    import logging
                    logging.getLogger('pocketgrid').exception('Background agent %s failed', name)
                await asyncio.sleep(pause)
        tasks = [asyncio.create_task(expire()),
                 asyncio.create_task(background('planning', agent.plan_once, 1)),
                 asyncio.create_task(background('review', agent.review_once, 2))]
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)

    app = FastAPI(title='PocketGrid', version='0.1.0', lifespan=lifespan)
    app.state.store = store
    origins = os.getenv('POCKETGRID_ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173,tauri://localhost,http://tauri.localhost').split(',')
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET','POST','PATCH'], allow_headers=['Authorization','Content-Type'])

    @app.middleware('http')
    async def size_limit(request: Request, call_next):
        if int(request.headers.get('content-length','0')) > 4_200_000:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Request exceeds prototype upload limit'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def token(authorization: str = Header(default='')):
        if not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Bearer credential required')
        return authorization[7:]

    def owner(credential=Depends(token)):
        return store.auth(credential)

    def worker(credential=Depends(token)):
        return store.auth(credential,'device')

    def member(credential=Depends(token)):
        return store.auth_any(credential)

    def own_worker(device_id, device):
        if device['id'] != device_id:
            raise HTTPException(403,'Device token does not match')

    @app.get('/api/health')
    def health():
        return {'ok':True,'service':'pocketgrid','agent':agent.status(),'inference':'participating devices only'}

    @app.post('/api/sessions')
    def session(body: Session):
        expected = os.getenv('POCKETGRID_JOIN_CODE','pocketgrid-demo')
        if not secrets.compare_digest(body.join_code, expected):
            raise HTTPException(403,'Incorrect grid join code')
        return store.session(body.name.strip())

    @app.get('/api/state')
    def state(user=Depends(owner)):
        result = store.snapshot(user['id'])
        result['agent'] = agent.status()
        return result

    @app.post('/api/devices')
    def register(body: DeviceRegistration,user=Depends(owner)):
        if body.kind != 'python' and 'image_generate' in body.capabilities:
            raise HTTPException(422,'This prototype runs diffusion only on Python laptop workers')
        return store.register(user['id'],body.name,body.kind,body.capabilities,body.limits.model_dump())

    @app.patch('/api/devices/{device_id}')
    def update(device_id: str,body: DeviceUpdate,user=Depends(owner)):
        return store.change_device(user['id'],device_id,body.enabled,body.limits.model_dump(exclude_unset=True) if body.limits else None)

    @app.post('/api/devices/{device_id}/heartbeat')
    def heartbeat(device_id: str,body: Heartbeat,device=Depends(worker)):
        own_worker(device_id,device)
        if len(str(body.telemetry))>4000:
            raise HTTPException(422,'Telemetry too large')
        return store.heartbeat(device_id,body.telemetry,body.task_id,body.lease_id)

    @app.post('/api/devices/{device_id}/claim')
    def claim(device_id: str,device=Depends(worker)):
        own_worker(device_id,device)
        return store.claim(device_id)

    @app.post('/api/tasks/{task_id}/progress')
    def progress(task_id: str,body: Progress,device=Depends(worker)):
        return store.progress(device['id'],task_id,body.lease_id,body.progress,body.stage)

    @app.post('/api/tasks/{task_id}/complete')
    def complete(task_id: str,body: Completion,device=Depends(worker)):
        if len(str(body.metrics))>4000:
            raise HTTPException(422,'Metrics too large')
        return store.complete(device['id'],task_id,body.lease_id,body.png_base64,body.metrics)

    @app.post('/api/tasks/{task_id}/fail')
    def task_failed(task_id: str,body: Failure,device=Depends(worker)):
        return store.task_failed(device['id'],task_id,body.lease_id,body.error)

    @app.post('/api/jobs')
    def create_job(body: JobRequest,user=Depends(owner)):
        return agent.dispatch(store,user['id'],body.model_dump())

    @app.get('/api/jobs/{job_id}')
    def job(job_id: str,_=Depends(member)):
        with store.tx() as db:
            store.sweep(db)
            return store.job(db,job_id)

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id: str,user=Depends(owner)):
        return store.cancel(user['id'],job_id)

    @app.get('/api/images/{artifact_id}')
    def image(artifact_id: str,_=Depends(member)):
        with store.tx() as db:
            if not db.execute('SELECT id FROM artifacts WHERE id=?',(artifact_id,)).fetchone():
                raise HTTPException(404,'Image not found')
        return FileResponse(store.root / 'images' / f'{artifact_id}.png',media_type='image/png')

    web_dir = Path(os.getenv('POCKETGRID_WEB_DIR','apps/web/dist'))
    if web_dir.exists():
        app.mount('/',StaticFiles(directory=web_dir,html=True),name='web')
    return app


app = create_app()
