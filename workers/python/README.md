# GiPU image worker

This worker claims generation or finishing tasks, keeps their leases alive and uploads PNGs. Generation follows the coordinator's mode: **local Tiny-SD inference** or **Akamai cloud inference through the coordinator**. The default `--generator auto` reads grid health; use `--generator local` or `--generator cloud` to select explicitly.

## Local mode

The local model is `segmind/tiny-sd`, pinned to revision `cad0bd7495fa6c4bcca01b19a723dc91627fe84f` under the publisher's CreativeML Open RAIL-M license. Weights are downloaded once; this path does not call a cloud image API.

Use Python 3.11 or 3.12. From the repository root:

```sh
python3.11 -m venv workers/python/.venv
workers/python/.venv/bin/python -m pip install -r workers/python/requirements.txt
workers/python/.venv/bin/python workers/python/worker.py prepare
workers/python/.venv/bin/python workers/python/worker.py smoke --size 256 --steps 12
```

`prepare` downloads and loads the model **before any work is leased**. All model and download caches default to `workers/python/.cache`. The smoke PNG is written to `.cache/smoke-cat.png` and its generation time is printed. MPS is selected on supported Apple devices, CUDA on supported NVIDIA devices, and CPU otherwise. `--backend cpu` forces CPU execution.

## Cloud mode

Configure `AKAMAI_API_KEY` on the coordinator, not the laptop. Create the same Python environment and install `requirements.txt` as above, but skip `prepare` and `smoke`: no model download is needed. The requirements still install the local inference libraries; this is not a smaller dependency package. `./scripts/setup-worker.sh` always prepares Tiny-SD, so skip that helper when setting up only for cloud generation.

```sh
workers/python/.venv/bin/python workers/python/worker.py run \
  --server https://YOUR-GRID --join-code YOUR-CODE --device-name "My laptop" \
  --generator cloud --share
```

The worker requests pixels through the coordinator's authenticated cloud endpoint, then uploads the output through the normal completion API. The model alias is `hackathon-image`; the provider key never goes to devices. The coordinator verifies and settles the leased task as usual. See [generation modes](../../README.md#generation-modes) for grid configuration and provider limits.

## Join and contribute

To join a local coordinator and explicitly start a 30-minute sharing session:

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

`--connect-paused` confirms an owner-authenticated pause with the coordinator before the worker can claim work. It cannot be combined with `--share`. After generation setup and registration succeed, stdout includes one `POCKETGRID_READY ` line followed by JSON containing only `device_id`, `backend`, and `model`. A failed registration or pause emits no readiness line and does not enter the work loop.

The native Mac app's **Create images** toggle connects a generation-only worker paused, then explicitly starts it as the owner's action. In a standalone app the worker is bundled; local mode asks before downloading its model, while cloud mode skips that download. Development builds use a prepared checkout selected in **Developer options**. Model loading in the native local path uses only the existing cache; prepare it first. Developer options also exposes manual connection details. A manual connection alone starts paused; a paused local worker retains its loaded model until it exits.

Controls are concrete: one active job, an image pixel limit, a timed sharing session, and CPU thread count. The CPU thread limit does **not** promise a GPU percentage, RAM cap, or battery limit. Heartbeats run independently of inference. A pause/revocation cancels at the next denoising callback; the current kernel cannot be interrupted mid-step. Nine seconds without coordinator confirmation also requests cancellation. An abandoned image restarts on another worker rather than resuming a diffusion checkpoint.

Use `--finalize-only` to run the deterministic PNG export workload without downloading a model. It returns a lossless PNG whose pixels are identical to the generated image; nothing is drawn on it, and the coordinator checks every pixel. Browser, Android and iOS devices perform this same small workload; this is not diffusion on a phone.

Use `--generate-only` on the laptop when demonstrating handoff to a phone/browser finalizer. Keep separate identity files when changing capabilities. A 512-pixel image with 24 steps is clearer than the fast 256-pixel default; the verified CPU smoke timings on this host were approximately 29 seconds and 3 seconds respectively, excluding model startup. These are measurements from one host, not performance promises.

The initial model is small and image quality varies. It does not include a safety checker; use public, suitable demo prompts. Each account sees only its own requests and results. A contributor can access the prompt and source pixels for its assigned task, so do not submit sensitive material. Pixel checks verify the export, not the honesty of an untrusted image generator.

## Verification

```sh
workers/python/.venv/bin/python -m pip install pytest
workers/python/.venv/bin/python -m pytest tests/test_worker.py -q
```

Tests check pixel accuracy, cancellation boundaries, source URL token isolation, paused registration, account-pairing isolation, and readiness ordering. Registration tests use mocked HTTP and model loading; they perform no live work or model downloads. The smoke command is the separate proof of real local inference.

## Experimental model comparison

Tiny-SD remains the supported local model; cloud-mode grids use the hosted image endpoint. To test a different local model independently:

```sh
workers/python/.venv/bin/python workers/python/worker.py smoke --model sd-turbo --backend cpu --output .cache/sd-turbo.png
```

The first run downloads weights. Turbo defaults to 512px, four steps and zero guidance. Experimental models are blocked in `run` mode until the coordinator supports model-aware assignment. Use [the benchmark runner](../../benchmarks/README.md) for timed comparisons and image galleries.
