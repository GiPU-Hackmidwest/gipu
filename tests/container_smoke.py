"""Real host-worker inference through the deployment container, isolated from the demo.

Build `pocketgrid-prototype:local` first. Run with the coordinator virtualenv.
Only the exact container and worker created here are stopped at the end.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port = sock.getsockname()[1]
    name = 'pocketgrid-smoke-'+uuid.uuid4().hex[:10]
    logs = ROOT / '.cache/container-smoke'
    logs.mkdir(parents=True,exist_ok=True)
    process = None
    subprocess.run(['docker','run','--rm','-d','--name',name,'-p',f'127.0.0.1:{port}:8787',
                    '-e','POCKETGRID_JOIN_CODE=container-test-only','pocketgrid-prototype:local'],check=True,capture_output=True)
    try:
        client = httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15)
        for _ in range(40):
            try:
                if client.get('/api/health').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise TimeoutError('Container did not become healthy')
        assert client.get('/').status_code == 200
        session = client.post('/api/sessions',json={'name':'Container buyer','join_code':'container-test-only'}).json()
        client.headers['Authorization'] = 'Bearer '+session['token']
        with tempfile.TemporaryDirectory(prefix='identity-',dir=logs) as temporary, (logs/'worker.log').open('w') as log:
            environment = dict(os.environ)
            environment.pop('POCKETGRID_SESSION_TOKEN',None)
            environment['POCKETGRID_JOIN_CODE'] = 'container-test-only'
            process = subprocess.Popen([str(ROOT/'workers/python/.venv/bin/python'),str(ROOT/'workers/python/worker.py'),
                                        'run','--server',str(client.base_url).rstrip('/'),'--join-code','container-test-only',
                                        '--local-only','--share','--device-name','Host CPU worker for container test',
                                        '--identity',str(Path(temporary)/'identity.json')],env=environment,stdout=log,stderr=subprocess.STDOUT)
            response = client.post('/api/jobs',json={'prompt':'A tiny orange cat riding a blue bicycle, cartoon illustration',
                                                   'count':1,'width':256,'height':256,'steps':12,'budget':10,
                                                   'request_id':uuid.uuid4().hex,'use_agent':False})
            response.raise_for_status()
            job_id = response.json()['id']
            deadline = time.monotonic()+150
            while time.monotonic()<deadline:
                job = client.get('/api/jobs/'+job_id).json()
                if job['status'] == 'completed':
                    break
                if process.poll() is not None:
                    raise RuntimeError('Worker exited; inspect .cache/container-smoke/worker.log')
                if job['status'] == 'failed':
                    raise RuntimeError('Container job failed')
                time.sleep(1)
            else:
                raise TimeoutError('Container job did not complete')
            assert job['receipt'] == {'budget':10,'contributor_total':7,'platform_fee':1,'refund':2,'total_charged':8}
            assert client.get('/api/state').json()['balance'] == 92
            runtime = subprocess.check_output(['docker','exec',name,'python','-c',
                                               'import importlib.util,json,os; print(json.dumps({"uid":os.getuid(),"torch_installed":importlib.util.find_spec("torch") is not None}))'],text=True)
            runtime = json.loads(runtime)
            assert runtime['uid'] != 0 and runtime['torch_installed'] is False
            evidence = {'passed':True,'deployment_container':'pocketgrid-prototype:local','physical_hosts':1,
                        'runtime':runtime,'job_id':job_id,'receipt':job['receipt'],
                        'tasks':[{'kind':t['kind'],'metrics':t['metrics']} for t in job['tasks']]}
            (ROOT/'docs/evidence/container.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps(evidence,indent=2))
            process.terminate()
            process.wait(timeout=15)
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        subprocess.run(['docker','stop',name],check=False,capture_output=True)


if __name__ == '__main__':
    main()
