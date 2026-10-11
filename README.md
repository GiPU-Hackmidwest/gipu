# GiPU

**AI images made on laptops that people choose to share, finished on phones, tracked by one small server.** No cloud image API is called. Each laptop generates whole images with a local model; a phone, browser or Android device finishes and verifies them; a coordinator hands out the work and keeps a sandbox credit ledger.

> The apps are called GiPU. The repository, app identifiers and some internals still say PocketGrid.

```text
 Mac app · Android app · iPhone app · browser
                  │  HTTPS, bearer sessions, polling
                  ▼
     Coordinator (FastAPI + SQLite)  ─ optional Strands planner
       leases · retries · PNG checks · credit ledger
                  │  workers claim, heartbeat, upload
        ┌─────────┴───────────────┐
 Laptop: Python + PyTorch      Phone / browser / Android:
 generates whole images        finishes and verifies images
```

## Download

When published, installers appear on the [Releases page](https://github.com/pocketgrid-hackmidwest/pocketgrid/releases): a Mac app for Apple silicon (`.dmg`) and an Android app (`.apk`). If no release is listed, use the source-build instructions below. Neither comes from an app store yet:
- **Mac:** after moving the app to Applications, allow it once in **System Settings → Privacy & Security → Open Anyway**.
- **Android:** allow **Install unknown apps** for the app you open the `.apk` with.

You still need a grid to join; host one yourself (section 6) or ask for an address and join code. iPhone installs from source (section 4). How releases are built: [docs/releasing.md](docs/releasing.md).

## What you need

| To run | Install |
| --- | --- |
| Coordinator and web app (always) | git, Python 3.11 or 3.12, Node 22+ |
| A laptop that generates images | The same Python, about 3 GB free (PyTorch plus a 1 GB model) |
| Mac app | Rust via [rustup](https://rustup.rs), Xcode Command Line Tools; [uv](https://docs.astral.sh/uv/) for the bundled-worker build |
| Android app | Android SDK Platform 37 and build tools, NDK 27, JDK 17, `rustup target add aarch64-linux-android` |
| iPhone app | Xcode 26.2+ with the iOS platform installed; an Apple team only for a physical phone |
| A hosted grid | A Linux VM with Docker and Compose v2, ports 80 and 443 open |

## 1. Run a grid on one computer

```bash
git clone https://github.com/pocketgrid-hackmidwest/pocketgrid.git
cd pocketgrid
cp .env.example .env
./scripts/setup.sh
./scripts/server.sh
```

`setup.sh` creates `.venv`, installs the coordinator and builds the web app. It picks `python3.12` or `python3.11` automatically; set `POCKETGRID_PYTHON` to use a specific interpreter.

Open **http://127.0.0.1:8787** and join with the code in `.env` (`pocketgrid-demo` locally). You get 100 sandbox credits. Sharing stays off until you turn it on.

To make this computer generate images, open a second terminal in the repository root. Replace `YOUR-CODE` with `POCKETGRID_JOIN_CODE` from `.env` (`pocketgrid-demo` for the local default):

```bash
./scripts/setup-worker.sh
workers/python/.venv/bin/python workers/python/worker.py run --join-code YOUR-CODE --device-name "My laptop" --share
```

`setup-worker.sh` installs PyTorch and downloads the pinned [Tiny-SD](https://huggingface.co/segmind/tiny-sd) model once. `--share` is the explicit opt-in; use `--connect-paused` instead to connect with sharing off, including for an existing worker identity. The worker does not load the coordinator’s `.env`; pass its join code explicitly. Without `--generate-only` this worker also finishes images, so one computer can complete a whole request.

Back in the browser, go to **Create**, describe an image and press **Create**. 256 px and 12 steps is the quick test.

The worker joins as its own account. To run it under your browser account instead, enable **Developer options** and copy the worker pairing token there, then set `POCKETGRID_SESSION_TOKEN` before the worker's first run. Treat that token like a password.

For frontend work with hot reload, run `npm --prefix apps/web run dev` and open http://localhost:5173. It proxies `/api` to the coordinator.

## 2. Mac app

```bash
npm --prefix apps/web run tauri dev
```

Run these commands from the repository root. On the join screen, enter `http://127.0.0.1:8787` for your local grid. For development, enable **Developer options** and point the Mac worker at the checkout prepared with `setup-worker.sh`. Turn **Create images** on in **Contribute** to connect and start sharing.

To build a standalone app with the image worker inside it:

```bash
npm --prefix apps/web run build:desktop
```

The app appears in `apps/web/src-tauri/target/release/bundle/macos/`. The standalone app asks before downloading its own model (about 1 GB) the first time you turn **Create images** on. After the download, turn the switch on to start. Its model cache is separate from the development checkout; a standalone user does not need `setup-worker.sh`. The build is unsigned: on first launch, Control-click the app and choose **Open**, or allow it in **System Settings → Privacy & Security**. More detail: [apps/web/README.md](apps/web/README.md).

## 3. Android app

Point the build at your SDK, NDK and JDK 17 (paths shown for a default Android Studio install on macOS):

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export NDK_HOME="$ANDROID_HOME/ndk/27.1.12297006"
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
```

Run on a connected device or a running emulator:

```bash
npm --prefix apps/web run tauri android dev
```

Or build an installable debug APK and install it:

```bash
npm --prefix apps/web run tauri android build -- --debug --target aarch64 --apk
adb install -r apps/web/src-tauri/gen/android/app/build/outputs/apk/universal/debug/app-universal-debug.apk
```

On the join screen use `http://10.0.2.2:8787` from the emulator, or your computer's network address from a phone (see section 5). Debug builds allow plain `http://`; release builds require an `https://` grid. Android finishes images only, and only while the app is open.

## 4. iPhone app

Open `apps/ios/PocketGrid.xcodeproj` in Xcode, choose the **PocketGrid** scheme and run it on a simulator. For a physical iPhone, pick your Apple team under **Signing & Capabilities** first, and do not commit that change. Join with `http://127.0.0.1:8787` in the simulator, or your computer's network address on a phone. The phone finishes images while the app is open.

Command-line simulator build, from `apps/ios`:

```bash
xcodebuild -project PocketGrid.xcodeproj -scheme PocketGrid -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath .build/DerivedData CLANG_MODULE_CACHE_PATH="$PWD/.build/ModuleCache" SWIFT_MODULE_CACHE_PATH="$PWD/.build/SwiftModuleCache" CODE_SIGNING_ALLOWED=NO build
```

More detail and the pixel checks: [apps/ios/README.md](apps/ios/README.md).

## 5. Phones and other laptops on your network

Start the coordinator so other devices can reach it, and set a private join code in `.env` first:

```bash
POCKETGRID_HOST=0.0.0.0 ./scripts/server.sh
```

Find your computer's address with `ipconfig getifaddr en0` (macOS) and join from other devices with `http://THAT-ADDRESS:8787`. On a phone, `127.0.0.1` means the phone itself. Event and campus Wi-Fi often blocks device-to-device traffic; use a personal hotspot or a hosted grid instead.

Another laptop can generate images for the same grid:

```bash
./scripts/setup-worker.sh
workers/python/.venv/bin/python workers/python/worker.py run --server http://THAT-ADDRESS:8787 --join-code YOUR-CODE --device-name "Second laptop" --share
```

## 6. Host a grid on the internet

On a Linux VM with Docker, from a copy of the repository:

```bash
cp deploy/.env.example deploy/.env
```

Set your domain and a private join code in `deploy/.env`, then start the grid:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
```

Caddy obtains the HTTPS certificate; the database and images live on a Docker volume. Every client then uses `https://YOUR-DOMAIN`. Upgrades, backups, a Linode setup without a domain, and recovery are in [deploy/README.md](deploy/README.md).

## 7. Optional: AI planner

By default the coordinator queues work directly. To have a Strands agent choose devices, set one mode in `.env` and restart the coordinator:

```dotenv
# Default: no model call.
POCKETGRID_AGENT_MODE=manual

# Akamai workshop chat model:
# POCKETGRID_AGENT_MODE=akamai
# AKAMAI_BASE_URL=https://ws.akamai-workshops.com/v1
# AKAMAI_CHAT_MODEL=hackathon-chat
# AKAMAI_API_KEY=your-team-key

# A local tool-capable model in Ollama:
# POCKETGRID_AGENT_MODE=ollama
# POCKETGRID_OLLAMA_MODEL=llama3.2:latest

# Amazon Bedrock:
# POCKETGRID_AGENT_MODE=bedrock
# POCKETGRID_BEDROCK_MODEL=your-tool-capable-model-id
# AWS_REGION=us-east-1
# AWS_PROFILE=your-profile
```

The planner only picks among devices that are online and opted in. It cannot change the prompt, image count or budget, and image generation still runs on contributors' laptops. Choosing the planner without a configured provider returns an error and reserves nothing.

## 8. Run the tests

From the repository root:

```bash
.venv/bin/python -m pytest tests -q --ignore=tests/test_worker.py --ignore=tests/live_agent_routing.py --ignore=tests/live_worker_recovery.py --ignore=tests/container_smoke.py
workers/python/.venv/bin/python -m pytest tests/test_worker.py -q
cd apps/web && node --experimental-strip-types --test tests/*.test.mjs && npm run build && cargo test --manifest-path src-tauri/Cargo.toml
```

`tests/live_worker_recovery.py` (two real workers, needs a prepared model) and `tests/container_smoke.py` (needs a locally built Docker image) are slower end-to-end checks; see [docs/verification.md](docs/verification.md).

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Install Python 3.11 or 3.12` | Install one, or point `POCKETGRID_PYTHON` at it. With pyenv: `POCKETGRID_PYTHON=$(pyenv prefix 3.12.9)/bin/python3.12 ./scripts/setup.sh` |
| `Incorrect grid join code` | Use the code from `.env` (or `deploy/.env`), and restart the coordinator after changing it. |
| A phone cannot connect | Use the computer's network address, not `127.0.0.1`, start the coordinator with `POCKETGRID_HOST=0.0.0.0`, and check the Wi-Fi allows device-to-device traffic. |
| A request stays on "Finishing" | No device is finishing images. Turn on sharing in a browser or phone, or run a worker without `--generate-only`. |
| `xcodebuild`: "iOS 26.x is not installed" | Install the iOS platform in **Xcode → Settings → Components**. |
| Android build cannot find the SDK or NDK | Set `ANDROID_HOME`, `NDK_HOME` and `JAVA_HOME` as in section 3. |
| The release Android app cannot reach a local grid | Release builds block plain `http://`. Use a debug build locally, or an `https://` grid. |
| The Mac app "cannot be opened" | It is unsigned. Control-click → **Open**, or allow it in **System Settings → Privacy & Security**. |
| Worker exits with a missing-model error | Run `./scripts/setup-worker.sh` once while online. |

## What this prototype is and is not

- **Credits are sandbox units with no cash value.** A request reserves its budget, pays 6 per generated image and 1 per finished image exactly once, charges a 1-credit fee on success and refunds the rest.
- **Sharing is always explicit.** Joining or connecting never starts contribution. Pause, timed sessions, image-size and CPU-thread limits apply. These are workload limits, not hard CPU, GPU or memory caps.
- **Each account sees its own requests and images.** Other members' devices show only as anonymous counts. Contributors still receive the prompt and image for the task they run, so use public, suitable prompts.
- **Verification is limited.** The coordinator checks image format and size, and that every pixel of a finished image matches what the finishing step must produce. It cannot prove which model an untrusted device ran or that an image is good.
- **Tiny-SD is small.** It makes local generation practical; image quality is modest. It is pinned to its published revision under the CreativeML Open RAIL-M license.
- One coordinator with one SQLite volume is a deliberate prototype choice. Savings in cost or energy have not been measured.

## Project docs

- [Project context](docs/project-context.md): what runs where and why.
- [Protocol](docs/protocol.md): the API the apps and workers use.
- [V1 plan](docs/v1-plan.md) and [V1 progress](docs/v1-progress.md): current work split and status.
- [Releasing](docs/releasing.md): how the downloadable apps are built and published.
- [Verification](docs/verification.md) and [demo steps](docs/demo.md): recorded results and how to run a demo.
- Component guides: [web and Mac](apps/web/README.md), [iPhone](apps/ios/README.md), [worker](workers/python/README.md), [deployment](deploy/README.md), [benchmarks](benchmarks/README.md).
