#!/usr/bin/env python3
"""Run one pinned image model per process, without registering a grid worker."""
import argparse
import html
import json
from pathlib import Path
import platform
import statistics
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workers.python.worker import LocalRenderer, MODEL_PROFILES
import psutil
import torch


def synchronize(backend):
    if backend == 'mps':
        torch.mps.synchronize()
    elif backend == 'cuda':
        torch.cuda.synchronize()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=list(MODEL_PROFILES), default='tiny-sd')
    p.add_argument('--backend', choices=['cpu', 'mps', 'cuda', 'auto'], default='cpu')
    p.add_argument('--size', type=int, choices=[256, 384, 512], default=512)
    p.add_argument('--steps', type=int)
    p.add_argument('--repeats', type=int, choices=range(1, 11), default=2)
    p.add_argument('--limit', type=int, choices=range(1, 6), default=5)
    p.add_argument('--cpu-threads', type=int, choices=range(1, 9), default=2)
    p.add_argument('--local-only', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    steps = args.steps or MODEL_PROFILES[args.model]['steps']
    if not 1 <= steps <= (30 if args.model == 'tiny-sd' else 4):
        p.error('Use 1–4 steps for Turbo, or 1–30 for Tiny-SD')
    args.output.mkdir(parents=True, exist_ok=False)
    prompts = json.loads((ROOT / 'benchmarks/prompts.json').read_text())[:args.limit]
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()
    def sample():
        while not stop.wait(.05):
            peak[0] = max(peak[0], process.memory_info().rss)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    report = {'model': args.model, 'profile': MODEL_PROFILES[args.model], 'size': args.size,
              'steps': steps, 'cpu_threads': args.cpu_threads, 'platform': platform.platform(),
              'machine': platform.machine(), 'torch': torch.__version__, 'runs': [],
              'scope': 'Local generation only; excludes agent planning, queue, transfers and phone finalization',
              'memory_note': 'Sampled process RSS, not total GPU memory or a hard memory cap',
              'quality_note': 'Images require human review; no automated quality score is claimed'}
    renderer = LocalRenderer(args.backend, args.model)
    try:
        started = time.perf_counter()
        renderer.load(args.cpu_threads, local_only=args.local_only)
        synchronize(renderer.backend)
        report.update(backend=renderer.backend, load_seconds=round(time.perf_counter()-started, 3),
                      safety_checker_present=getattr(renderer.pipeline, 'safety_checker', None) is not None)
        # Keep first inference separate from warm measured requests.
        started = time.perf_counter()
        renderer.generate({'prompt': prompts[0]['prompt'], 'width': args.size, 'height': args.size,
                           'steps': steps, 'seed': 42}, threading.Event(), lambda *_: None, args.cpu_threads)
        synchronize(renderer.backend)
        report['first_inference_seconds'] = round(time.perf_counter()-started, 3)
        for prompt in prompts:
            for repeat in range(args.repeats):
                seed = 42 + repeat
                started = time.perf_counter()
                image = renderer.generate({'prompt': prompt['prompt'], 'width': args.size, 'height': args.size,
                                           'steps': steps, 'seed': seed}, threading.Event(), lambda *_: None, args.cpu_threads)
                synchronize(renderer.backend)
                elapsed = time.perf_counter()-started
                filename = f"{prompt['id']}-{seed}.png"
                (args.output / filename).write_bytes(image)
                row = {**prompt, 'seed': seed, 'seconds': round(elapsed, 3), 'image': filename}
                report['runs'].append(row)
                print(json.dumps(row), flush=True)
                (args.output / 'results.json').write_text(json.dumps(report, indent=2))
        values = [r['seconds'] for r in report['runs']]
        report['summary'] = {'samples': len(values), 'median_seconds': statistics.median(values),
                             'min_seconds': min(values), 'max_seconds': max(values)}
    except Exception as exc:
        report['failure'] = type(exc).__name__ + ': ' + str(exc)[:400]
        raise
    finally:
        stop.set(); sampler.join(timeout=1)
        report['peak_process_rss_mb'] = round(max(peak[0], process.memory_info().rss)/1024**2, 1)
        (args.output / 'results.json').write_text(json.dumps(report, indent=2))
        cards = ''.join(f'<article><img src="{html.escape(r["image"])}" alt="{html.escape(r["prompt"])}"><h2>{html.escape(r["id"])}</h2><p>{html.escape(r["prompt"])}</p><p>Seed {r["seed"]} · {r["seconds"]} seconds</p></article>' for r in report['runs'])
        (args.output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>PocketGrid model benchmark</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:16px;background:#fafafa;color:#182020}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}img{width:100%}pre{white-space:pre-wrap}article{padding:16px;background:white}</style><h1>'+html.escape(args.model)+' local benchmark</h1><p>Quality needs human review. Timings exclude planning, network and finalization.</p><pre>'+html.escape(json.dumps({k:v for k,v in report.items() if k not in ('runs',)},indent=2))+'</pre><main>'+cards+'</main>')
    print(json.dumps(report.get('summary', {})), flush=True)

if __name__ == '__main__':
    main()
