"""Real Ollama or Akamai + Strands routing/review with local diffusion output.

Uses an isolated in-process coordinator and heartbeating test clients to control
claim order, with the real Python image kernel in a subprocess. This is not a
physical multi-device or Akamai-hosted coordinator test. Requires the prepared
image model and either Ollama or the Akamai workshop key in the root .env.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from dotenv import load_dotenv

from services.coordinator import agent
from services.coordinator.store import Store

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'workers/python'
LIMITS={'cpu_threads':2,'max_pixels':65536,'session_minutes':15}


def main(provider='ollama'):
    load_dotenv(ROOT/'.env',override=False)
    os.environ['POCKETGRID_AGENT_MODE']=provider
    os.environ.setdefault('POCKETGRID_OLLAMA_MODEL','llama3.2:latest')
    cache=ROOT/'.cache/live-agent'
    cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        store=Store(temporary)
        user=store.session('Live agent test')['user']['id']
        clients=[]
        active={}
        stop=threading.Event()
        def add(name):
            device=store.register(user,name,'python',['image_generate','image_finalize'],LIMITS)['device']['id']
            store.change_device(user,device,True)
            clients.append(device)
            return device
        add('Routing client A')
        add('Routing client B')
        def heartbeat():
            while not stop.is_set():
                for device in list(clients):
                    task=active.get(device)
                    store.heartbeat(device,{'backend':'test client; actual kernel invoked separately'},
                                    task['id'] if task else None,task['lease_id'] if task else None)
                stop.wait(1)
        thread=threading.Thread(target=heartbeat,daemon=True)
        thread.start()
        try:
            job=agent.dispatch(store,user,{'prompt':'A cheerful orange cat riding a tiny blue bicycle, cartoon illustration',
                'count':1,'width':256,'height':256,'steps':12,'budget':10,'request_id':'live-agent-routing','use_agent':True})
            assert job['status']=='planning' and job['tasks']==[] and job['reserved']==10
            # This harness owns an in-process Store without the HTTP lifespan
            # loop. Explicitly advance the durable planner before reading routes.
            assert agent.plan_once(store),'Accepted request was not claimed for planning'
            with store.tx() as db:
                job=store.job(db,job['id'])
            assert job['status']=='queued' and job['plan']['planning']['status']=='done',job['plan']
            chosen=job['plan']['routes']['image_generate']
            assert chosen,job['plan']
            extra=add('Unselected newcomer C')
            assert store.claim(extra)['task'] is None,'Unselected client bypassed live model preference'
            first=store.claim(chosen[0])['task']
            assert first and first['job_id']==job['id']
            active[chosen[0]]=first
            print('Actual Strands selected generation IDs:',chosen,flush=True)
            # Explicit fault injection: the selected client reports an execution error.
            store.task_failed(chosen[0],first['id'],first['lease_id'],'Injected worker execution failure')
            active.pop(chosen[0],None)
            store.change_device(user,chosen[0],False)
            assert agent.review_once(store)
            with store.tx() as db:
                reviewed=store.job(db,job['id'])
            assert reviewed['plan']['review']['status']=='done',reviewed['plan']['review']
            route=reviewed['plan']['task_routes'][first['id']]['device_ids']
            assert chosen[0] not in route and route,reviewed['plan']
            second=store.claim(route[0])['task']
            assert second['id']==first['id'] and second['attempts']==2
            active[route[0]]=second
            print('Actual Strands rerouted failed task to:',route,flush=True)
            result=subprocess.run([str(WORKER/'.venv/bin/python'),str(WORKER/'worker.py'),'smoke',
                '--local-only','--backend','cpu','--size','256','--steps','12','--seed',str(second['seed']),
                '--prompt',second['prompt'],'--output',str(cache/'generated.png')],check=True,capture_output=True,text=True)
            (cache/'worker.log').write_text(result.stdout+result.stderr)
            metrics=json.loads(result.stdout.strip().splitlines()[-1])
            generated=(cache/'generated.png').read_bytes()
            store.complete(route[0],second['id'],second['lease_id'],base64.b64encode(generated).decode(),
                           {k:metrics[k] for k in ('backend','model','elapsed_seconds')})
            active.pop(route[0],None)
            export=None
            for device in clients:
                claim=store.claim(device)['task']
                if claim:
                    export=claim
                    exporter=device
                    break
            assert export and export['kind']=='image_finalize'
            active[exporter]=export
            exported=subprocess.run([str(WORKER/'.venv/bin/python'),'-c',
                'import sys; from worker import finalize_image; sys.stdout.buffer.write(finalize_image(sys.stdin.buffer.read()))'],
                cwd=WORKER,input=generated,capture_output=True,check=True).stdout
            store.complete(exporter,export['id'],export['lease_id'],base64.b64encode(exported).decode(),{'backend':'Pillow'})
            active.pop(exporter,None)
            assert agent.review_once(store)
            with store.tx() as db:
                finished=store.job(db,job['id'])
            assert finished['plan']['review']['status']=='done',finished['plan']['review']
            assert finished['receipt']['total_charged']==8 and finished['receipt']['refund']==2
            assert any(x['tool']=='inspect_job' and x['result'].get('receipt') for x in finished['plan']['reviews'][-1]['tools'])
            assert store.claim_review() is None
            evidence={'scope':f'One host; real Strands/{provider}, controlled test clients, actual local diffusion subprocess',
                      'passed':True,'initial_routes':job['plan']['routes'],'recovery_routes':route,
                      'attempts':second['attempts'],'receipt':finished['receipt'],'metrics':metrics,
                      'tools':finished['plan']['tools'],'reviews':finished['plan']['reviews']}
            evidence['metrics'].pop('output',None)
            filename='agent-routing.json' if provider=='ollama' else 'agent-routing-akamai.json'
            (ROOT/'docs/evidence'/filename).write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps({k:evidence[k] for k in ('passed','attempts','receipt','metrics')},indent=2))
        finally:
            stop.set()
            thread.join(timeout=5)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['ollama','akamai'],default='ollama')
    main(parser.parse_args().provider)
