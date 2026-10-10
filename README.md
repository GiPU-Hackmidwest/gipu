# PocketGrid

**Generate images on participating laptops; coordinate the work through a small server.** A phone or browser can finish the generated image, track the work and manage its contribution. No image-generation API is called. This prototype proves local inference, task handoff, opt-in controls, failure recovery and an integer credit ledger.

The first workload is a prompt → independently generated image variants → device-side PNG export. The model is not split across phones. Each capable laptop handles a whole image. A failed generation restarts on another laptop; it does not resume a diffusion checkpoint. Phones apply a small fixed pixel transform, so their work is real but intentionally limited.

New to the project? Start with [the full project context](docs/project-context.md), including what runs on each device and the Claude/Codex ownership split.

## Start locally

Requires Python3.11, Node22, and approximately3GB free for the laptop worker and model. Additional disk is needed for native build caches. A fresh clone needs the setup commands below; local environments and model weights are not committed.

```sh
git clone https://github.com/pocketgrid-hackmidwest/pocketgrid.git
cd pocketgrid
cp .env.example .env  # first setup only; preserve an existing configuration
./scripts/setup.sh
./scripts/server.sh
```

Open **http://127.0.0.1:8787**. Enter a name and the join code from `.env` (`pocketgrid-demo` locally). Joining grants100 sandbox units and leaves contribution off. For browser development, `npm --prefix apps/web run dev` uses port5173 and proxies the coordinator.

On a laptop that will generate images:

```sh
python3.11 -m venv workers/python/.venv
workers/python/.venv/bin/pip install -r workers/python/requirements.txt
workers/python/.venv/bin/python workers/python/worker.py prepare
workers/python/.venv/bin/python workers/python/worker.py run \
  --server http://127.0.0.1:8787 --name 'Laptop owner' \
  --device-name 'Generation laptop' --share --generate-only
```

`--share` is explicit opt-in. Omit it to connect paused. The default worker identity persists in an ignored mode0600 file. To control the laptop under the same account as the web/Mac app, use **Copy worker pairing token** in that app and set `POCKETGRID_SESSION_TOKEN` in the worker's environment before its first registration. Treat that token like a password; never commit it. Use a new `--identity` path when pairing a different account.

In the browser, **Start sharing** to contribute image exports, then request “a cheerful cat riding a tiny bicycle.” Use256px/12steps for a quick systems test, or512px/24steps for a clearer demonstration. Multiple variants can run independently on different laptops. The worker's `--generate-only` flag leaves finalization to phones/browsers; omit it for a single-laptop end-to-end test.

## Apps

- **Web:** React/TypeScript; create jobs, authenticated image gallery, device controls, receipts, event notifications, and actual foreground canvas work.
- **Mac:** Tauri/Rust shell around the same interface with native notification opt-in. `cd apps/web && npm run tauri dev`. For a standalone app: `npm run tauri build`. The Python model worker is a separate local process for this prototype; the Mac interface controls it through the coordinator.
- **iPhone/iPad:** Native SwiftUI app in `apps/ios/PocketGrid.xcodeproj`. See [iOS setup](apps/ios/README.md). It performs foreground CoreGraphics image export, keeps tokens in Keychain, pauses on backgrounding, and shows local notifications while running. Physical-device installation requires your Apple signing team.

For multiple physical devices, run the coordinator with `POCKETGRID_HOST=0.0.0.0`, use the Mac's LAN IP in clients and put devices on the same trusted Wi-Fi/hotspot. Set a private join code. On a phone, `localhost` refers to that phone. For internet use, deploy with HTTPS; see [Akamai deployment](deploy/README.md).

## Control and credits

- Explicit start/pause, one active task/device, maximum image size, CPU-thread limit for Python inference, and timed sharing sessions. These are workload limits, **not** hard system-wide CPU/GPU-percent or RAM caps. Pausing inference takes effect at the next denoising step after a heartbeat update (normally within3seconds plus the current step). Loaded model memory stays resident while the worker process runs; quit it to release that memory.
- Current stage, progress, backend, CPU use and process memory are reported by laptop workers. A browser/iPhone contributes only while visible; returning requires explicit start.
- Quote =6credits per generated image +1per accepted export +1platform fee per successful job. Reserve the user's budget first, transfer accepted-task payments exactly once, then refund unused credits. Cancellation keeps completed-task payments and refunds the rest without a platform fee. Receipts show every component.
- These are **sandbox service credits with no cash value**, not cash payouts or AI credits. The purpose is testing compensation for device work. Flex's fintech fit is the reservation/settlement/receipt flow; no Flex payment API is claimed.

## Strands and cloud

The real AWS Strands SDK has bounded tools to inspect devices, quote the authorized request, choose capable device IDs and submit the job. The queue honors validated choices for up to45seconds, falling back if selected devices are unavailable. Background agent reviews inspect actual failures and completed receipts; they can redirect queued work using a guarded update that rejects stale decisions. Running tasks, leases and accepted payments remain under deterministic server control. Tool records are stored in the job plan. The model cannot change the authorized prompt, count or budget.

Lease expiry runs independently of model calls. Reviews have durable claims, bounded model/tool calls and at most three attempts per event; a provider failure cannot prevent work recovery or settlement. A route is a temporary preference, not a promise that a particular device will stay connected.

Choose one planner mode in `.env`:

```dotenv
# Direct pipeline; no agent or model call. Always labeled manual.
POCKETGRID_AGENT_MODE=manual

# Strands using the Akamai workshop's hosted chat model:
# POCKETGRID_AGENT_MODE=akamai
# AKAMAI_BASE_URL=https://ws.akamai-workshops.com/v1
# AKAMAI_CHAT_MODEL=hackathon-chat
# AKAMAI_API_KEY=your-team-key

# Real Strands using a local tool-capable model already installed in Ollama:
# POCKETGRID_AGENT_MODE=ollama
# POCKETGRID_OLLAMA_MODEL=llama3.2:latest

# Real Strands using Amazon Bedrock:
# POCKETGRID_AGENT_MODE=bedrock
# POCKETGRID_BEDROCK_MODEL=your-accessible-tool-capable-model-id
# AWS_REGION=us-east-1
# AWS_PROFILE=your-profile
```

Selecting the agent in the UI without a configured provider returns an explicit error and reserves nothing. Bedrock is only the planner; image inference still runs on contributors. Local Strands/Ollama was exercised during verification; Bedrock needs valid account credentials and model access. The Akamai container and HTTPS deployment are prepared, but a live Akamai host has not been claimed. DevRev is optional and is not wired into this first compute prototype.

The Akamai workshop provider is implemented using Strands' OpenAI-compatible adapter and the documented `hackathon-chat` alias. Its HTTP/tool flow has adapter tests, and live chat authentication plus a real Strands job submission were subsequently verified during the October 10 demo. See [workshop setup](deploy/workshop.md). The team model key is separate from access to deploy a VM.

## Architecture and checks

```text
React web / Tauri Mac / SwiftUI iPhone
              │ HTTPS + bearer sessions (polling)
              ▼
Akamai-ready FastAPI coordinator ─ Strands planner (Akamai, Bedrock or Ollama)
   SQLite transactions • fenced15s leases • PNG validation • credit ledger
              │ outbound workers claim/heartbeat/upload
       ┌──────┴──────────────┐
Python + PyTorch/diffusers   Browser canvas / iPhone CoreGraphics
whole-image local inference fixed pixel export and verification
```

One coordinator and one durable SQLite volume are deliberate prototype constraints. No distributed database, Kafka cluster or Kubernetes is needed for six devices. [Demo steps](docs/demo.md) walk through a run; [protocol](docs/protocol.md) defines the contract; [verification](docs/verification.md) records observed results and remaining checks.

```sh
.venv/bin/python -m pytest tests/test_coordinator.py tests/test_routing.py tests/test_agent.py tests/test_akamai.py tests/test_lifespan.py -q
workers/python/.venv/bin/pip install -r workers/python/requirements-dev.txt
workers/python/.venv/bin/python -m pytest tests/test_worker.py -q
npm --prefix apps/web run build
```

The queue tests cover conserved funds, duplicate reservation/payment, concurrent claims, lost leases, late results, pause/time limits, forged exports, cancellation and restart persistence. The native app has pixel-parity and live API checks described in its README. `tests/live_worker_recovery.py` starts an isolated temporary coordinator and two local worker processes, verifies abrupt-death recovery and pause/refund behavior, then tears them down. It needs both Python environments and a prepared model.

## Prototype boundaries

An invited worker can read its prompt and inputs. Use public demo material. PNG size/format are checked for generated images; this is not proof that an untrusted device ran the requested model or produced a useful image. Export verification compares every pixel against the known transform. A public paid network needs stronger verification, device reputation, account recovery, abuse controls and real payment settlement. Efficiency, cost savings and environmental benefit remain measurements to make across actual devices; this prototype does not prove them.

The model is [Segmind Tiny-SD](https://huggingface.co/segmind/tiny-sd), pinned to its published revision and CreativeML Open RAIL-M license. Its small size helps demonstrate local generation; visual quality is modest. Relevant primary references: [Strands tools](https://strandsagents.com/docs/user-guide/sdk/tools/), [Tauri](https://v2.tauri.app/), and the [HackMidwest sponsor requirements](https://hackmidwest.com/).

## Team development

Read [the work split and handoff guide](docs/team-development.md) before starting a feature branch. Codex and Claude share the instructions in AGENTS.md; CLAUDE.md points to the same guide. Configure your own local credentials and Apple signing team.
