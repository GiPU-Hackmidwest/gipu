# PocketGrid local image worker

This worker runs **actual local diffusion inference**, then uploads a PNG to the coordinator. The model is `segmind/tiny-sd`, pinned to revision `cad0bd7495fa6c4bcca01b19a723dc91627fe84f` under the publisher's CreativeML Open RAIL-M license. Model weights are downloaded once; generation does not call a cloud inference API.

Use Python 3.11 or 3.12. From the repository root:

```sh
python3.11 -m venv workers/python/.venv
workers/python/.venv/bin/python -m pip install -r workers/python/requirements.txt
workers/python/.venv/bin/python workers/python/worker.py prepare
workers/python/.venv/bin/python workers/python/worker.py smoke --size 256 --steps 12
```

`prepare` downloads and loads the model **before any work is leased**. All model and download caches default to `workers/python/.cache`. The smoke PNG is written to `.cache/smoke-cat.png` and its generation time is printed. MPS is selected on supported Apple devices, CUDA on supported NVIDIA devices, and CPU otherwise. `--backend cpu` forces CPU execution.

To join a running coordinator and explicitly start a 30-minute sharing session:

```sh
workers/python/.venv/bin/python workers/python/worker.py run \
  --server http://127.0.0.1:8787 --name Alice --device-name "Alice's laptop" \
  --share --cpu-threads 2 --max-pixels 262144 --session-minutes 30
```

For an existing web-app owner, the desktop launcher supplies their session token through `POCKETGRID_SESSION_TOKEN`. Otherwise the CLI creates an owner session with the invite code from `POCKETGRID_JOIN_CODE` (local default `pocketgrid-demo`). An identity file stores owner and device credentials with owner-only file permissions. Do not share or commit it. To register another physical device/process, use a different `--identity PATH`.

Without `--share`, a new device registers paused. A restarted device may continue an existing, explicitly enabled session until it expires. The app can pause it or change its limits. Ctrl-C stops execution; the coordinator reassigns unfinished work after its lease expires.

Controls are concrete: one active job, an image pixel limit, a timed sharing session, and CPU thread count. The CPU thread limit does **not** promise a GPU percentage, RAM cap, or battery limit. Heartbeats run independently of inference. A pause/revocation cancels at the next denoising callback; the current kernel cannot be interrupted mid-step. Nine seconds without coordinator confirmation also requests cancellation. An abandoned image restarts on another worker rather than resuming a diffusion checkpoint.

Use `--finalize-only` to run the deterministic PNG export workload without downloading a model. It applies the protocol's exact four-pixel teal frame and preserves every interior pixel. Browser and iOS devices can perform this same small workload; this is not diffusion on a phone.

Use `--generate-only` on the laptop when demonstrating handoff to a phone/browser finalizer. Keep separate identity files when changing capabilities. A 512-pixel image with 24 steps is clearer than the fast 256-pixel default; the verified CPU smoke timings on this host were approximately 29 seconds and 3 seconds respectively, excluding model startup. These are measurements from one host, not performance promises.

The initial model is small and image quality varies. It does not include a safety checker; use public, suitable demo prompts. Inputs are visible to contributors and generated images are visible to grid members. There is no claim of private or cryptographically verified inference.

## Verification

```sh
workers/python/.venv/bin/python -m pip install pytest
workers/python/.venv/bin/python -m pytest tests/test_worker.py -q
```

Tests check pixel accuracy, cancellation boundaries, and source URL token isolation. The smoke command is the separate proof of real local inference.

## Experimental model comparison

The live grid still uses Tiny-SD. To test a different local model independently:

```sh
workers/python/.venv/bin/python workers/python/worker.py smoke --model sd-turbo --backend cpu --output .cache/sd-turbo.png
```

The first run downloads weights. Turbo defaults to 512px, four steps and zero guidance. Experimental models are blocked in `run` mode until the coordinator supports model-aware assignment. Use [the benchmark runner](../../benchmarks/README.md) for timed comparisons and image galleries.
