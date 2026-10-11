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

For an existing web-app owner, the desktop launcher supplies their session token through `POCKETGRID_SESSION_TOKEN`. Otherwise the CLI creates an owner session with the invite code from `POCKETGRID_JOIN_CODE` (local default `pocketgrid-demo`). An identity file stores owner and device credentials with owner-only file permissions. Do not share or commit it. To register another physical device/process, use a different `--identity PATH`. A supplied session token must match an existing identity's owner token; pairing a different account requires a new identity path. This check happens before model loading or coordinator requests.

Without `--share`, a new device registers paused. A restarted device may continue an existing, explicitly enabled session until it expires. The app can pause it or change its limits. Ctrl-C stops execution; the coordinator reassigns unfinished work after its lease expires.

To connect with sharing paused even when reusing a previously enabled identity:

```sh
workers/python/.venv/bin/python workers/python/worker.py run \
  --server http://127.0.0.1:8787 --generate-only --connect-paused --local-only \
  --identity workers/python/.cache/desktop-paired-device.json
```

`--connect-paused` confirms an owner-authenticated pause with the coordinator before the worker can claim work. It cannot be combined with `--share`. After the model loads and registration succeeds, stdout includes one `POCKETGRID_READY ` line followed by JSON containing only `device_id`, `backend`, and `model`. A failed registration or pause emits no readiness line and does not enter the work loop.

The native desktop **Connect** action uses this paused, generation-only, cache-only path and a separate identity for each coordinator/account pairing. It requires an already prepared Python environment and cached Tiny-SD weights; it does not install dependencies or download models. Run the setup and `prepare` commands above first. Once connected, explicitly choose **Start sharing** in the app to enable generation. Connecting alone does not start sharing. A paused worker keeps the model loaded in memory until it exits.

Controls are concrete: one active job, an image pixel limit, a timed sharing session, and CPU thread count. The CPU thread limit does **not** promise a GPU percentage, RAM cap, or battery limit. Heartbeats run independently of inference. A pause/revocation cancels at the next denoising callback; the current kernel cannot be interrupted mid-step. Nine seconds without coordinator confirmation also requests cancellation. An abandoned image restarts on another worker rather than resuming a diffusion checkpoint.

Use `--finalize-only` to run the deterministic PNG export workload without downloading a model. It returns a lossless PNG whose pixels are identical to the generated image; nothing is drawn on it, and the coordinator checks every pixel. Browser, Android and iOS devices perform this same small workload; this is not diffusion on a phone.

Use `--generate-only` on the laptop when demonstrating handoff to a phone/browser finalizer. Keep separate identity files when changing capabilities. A 512-pixel image with 24 steps is clearer than the fast 256-pixel default; the verified CPU smoke timings on this host were approximately 29 seconds and 3 seconds respectively, excluding model startup. These are measurements from one host, not performance promises.

The initial model is small and image quality varies. It does not include a safety checker; use public, suitable demo prompts. Inputs are visible to contributors and generated images are visible to grid members. There is no claim of private or cryptographically verified inference.

## Verification

```sh
workers/python/.venv/bin/python -m pip install pytest
workers/python/.venv/bin/python -m pytest tests/test_worker.py -q
```

Tests check pixel accuracy, cancellation boundaries, source URL token isolation, paused registration, account-pairing isolation, and readiness ordering. Registration tests use mocked HTTP and model loading; they perform no live work or model downloads. The smoke command is the separate proof of real local inference.

## Experimental model comparison

The live grid still uses Tiny-SD. To test a different local model independently:

```sh
workers/python/.venv/bin/python workers/python/worker.py smoke --model sd-turbo --backend cpu --output .cache/sd-turbo.png
```

The first run downloads weights. Turbo defaults to 512px, four steps and zero guidance. Experimental models are blocked in `run` mode until the coordinator supports model-aware assignment. Use [the benchmark runner](../../benchmarks/README.md) for timed comparisons and image galleries.
