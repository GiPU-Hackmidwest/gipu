# GiPU web, Mac and Android client

This client is intentionally small: join a grid, submit image jobs, share a foreground browser export worker, control owned devices, inspect accounting, and opt into notifications. A separate Python worker handles generation tasks: it runs Tiny-SD locally or requests cloud pixels through the coordinator. Browsers and phones perform lossless PNG export; they do not run diffusion.

## Client structure

Arboy with Codex owns the Mac and SwiftUI UX; the teammate with Claude owns the Tauri Android port. The shared client has **Create**, **Contribute**, **Leaderboard** and **Activity** destinations, plus account controls. Keep visible text short and expose technical setup through disclosure. See [design and Android integration notes](../../docs/native-ui-design.md).

Mac worker controls are gated by `isMacDesktop`. `platformFlags` in `src/platform.ts` recognizes `TAURI_ENV_PLATFORM` target names including `darwin` and `androideabi` (plus friendly aliases), falling back to the user agent only when that metadata is absent. Keep Vite’s `TAURI_ENV_` environment prefix: a Tauri runtime alone is insufficient because Android also uses Tauri. Keep `DesktopWorkerPanel` mounted when navigation changes: its cleanup deliberately stops the managed Python process. The shared UI and HTTP API must remain platform-neutral; Android native adapters and lifecycle work belong to the Android owner.

Tauri windows use `create: false` in configuration and are explicitly bootstrapped from each window configuration in `src-tauri/src/lib.rs` setup on all targets, preserving configured properties. The desktop `main.rs` delegates to that library entry point; iOS remains the separate native SwiftUI app. The macOS-only download handler accepts frontend-fetched `blob:` images and reports completion. Android owns its download integration; do not assume macOS WebKit download handling works there or create a duplicate automatic window.

## Run

With the coordinator running at `http://127.0.0.1:8787`:

```sh
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the coordinator. A phone on the same network can visit the laptop’s LAN address on port 5173; use an empty coordinator address to retain that proxy. Browser contribution requires keeping the tab visible. A background event pauses the device immediately when the network is reachable, and lease expiry handles unexpected disconnection.

For a compiled web deployment, serve `dist` behind the coordinator or a reverse proxy that sends `/api` to it. For a separate origin, enter the coordinator’s full URL at join time and allow that origin in server CORS configuration.

## Mac app

```sh
npm run tauri dev
npm run tauri build
```

The release `.app` is placed under `src-tauri/target/release/bundle/macos`. This is an unsigned developer prototype, not a notarized distribution. The Mac app uses the same React client and a minimal Rust/Tauri host with the official notification plugin and user-triggered clipboard writing for device pairing. Set the coordinator URL to `http://127.0.0.1:8787` (or your grid host). Server CORS must allow the Tauri origin (`tauri://localhost` on macOS).

### Bundled worker build

`npm run build:desktop` (`scripts/build-desktop-app.sh`, needs `uv`) freezes the Python worker with PyInstaller into `src-tauri/resources/worker/`, builds with `tauri.bundled-worker.conf.json`, then restores the symlinks Tauri expands so PyTorch is not stored twice. Model weights are not bundled. The worker is frozen for the build machine's platform and architecture; unsigned builds are not notarized.

In **Contribute**, turning **Create images** on connects and starts the worker. For local generation, the app first asks before downloading the pinned Tiny-SD model (about 1 GB) into its app data. Progress and Cancel remain visible; a ready marker is written only after the worker loads the model successfully. Turn the switch on after preparation to start. Cloud-mode grids skip model download and request pixels through the coordinator; the app never receives the provider key.

The native worker registers paused before the toggle enables it. Manual connection from **Developer options** stays paused. Local model loading is cache-only, but grid access still needs a coordinator connection.

### Checkout worker (development)

Builds without the bundled worker (`npm run tauri dev`, `npm run tauri build`) use a prepared checkout. Install the Python environment through [the worker guide](../../workers/python/README.md); local mode also needs cached Tiny-SD weights, while cloud mode does not. Join the grid and enable **Developer options** to set **GiPU project folder** under **Mac image worker** and choose runtime settings. The build checkout is selected by default.

Turn **Create images** on in **Contribute** to connect and explicitly start. **Finish images** separately enables the foreground canvas exporter. CPU threads, image size, session duration and manual worker connection details live in Developer options. A local worker consumes model memory while connected, even when paused. CPU thread limits are not GPU percentage or RAM quotas.

**Pause** stops accepting work and cancels active inference at a denoising boundary, while keeping the model loaded. **Disconnect**, **Leave**, reloading the interface or closing/quitting the app stops the managed process. Disconnect also asks the coordinator to pause the device; if the network is unavailable, its unfinished lease expires. Reconnecting always pauses the device again before it can claim work. A sharing session may continue while the Mac app is in the background, within the chosen limits; the canvas exporter still pauses when hidden.

In both modes the app passes the account token through the child's environment, never a command argument or clipboard. It stores a separate private worker identity per coordinator origin and session under app data. Existing command-line workers remain independent and are not stopped by the app. For manual pairing, use **Copy worker pairing token** and `POCKETGRID_SESSION_TOKEN`; a matching display name alone is not account linking.

## Behavior and security

- Contribution is off after joining and after page reload, and starts only when the owner turns a contribution toggle on.
- Each browser has a distinct device token. Owner sessions and device tokens are separate. The Mac account session uses Keychain; Android uses its secure-storage adapter and browsers use local storage. Tokens are sent only in Authorization headers, never image URLs.
- Closing, hiding, or leaving this window stops its canvas worker and requests server-side lease revocation. Sessions also expire server-side.
- The canvas worker can only read a supplied image and submit it again as a pixel-identical PNG (no border; the coordinator checks every pixel). No arbitrary code from jobs executes.
- Browser notifications may require HTTPS and platform support. The activity list works without notification permission. The Mac app uses native notifications after explicit opt-in.
- Earnings notifications require the event's recipient to match the signed-in user. Payments to other contributors still appear in job activity and receipts, without a personal earnings alert.
- Submitting again after an ambiguous network failure reuses the request ID for an unchanged form. A successful submission clears the ID so a later intentional request is a new job.
- Local mode generates a whole image on one laptop; cloud mode gets it through the coordinator. Multiple variants can use different laptop workers, and exports can run on other devices. Retried generation starts again, not from a transferred checkpoint.
- Account data is scoped to its owner. Assigned workers can read their task prompt/pixels. The public weekly leaderboard is opt-in and uses a separate nickname; grants and credit purchases do not count as credits used.

## Checks

```sh
npm run build
node --experimental-strip-types --test tests/*.test.mjs
cargo check --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
```

From the repository root, `node --experimental-strip-types --test apps/web/tests/desktopWorker.test.mjs` checks native-command ordering across disconnects and account changes. `workers/python/.venv/bin/python -m pytest tests/test_worker.py -q` checks paused registration and owner/server identity validation. Native process tests use an isolated fixture rather than image inference; one ignored test is that subprocess fixture.

## Historical merge integration checks

- The shared frontend passed 33 Node tests, including platform detection for `darwin` and `androideabi`. Rust passed 15 tests with one ignored subprocess fixture; Python worker checks passed 33 tests and packaging checks passed 7.
- The bundled Mac debug app built successfully with a custom Cargo target directory and measured 670 MB. In its actual interface, Download, Cancel and Retry worked, and the real model download completed. Connect began paused; explicit Start enabled sharing, and navigating to Create preserved the managed worker.
- Real request `551049f0` completed through **This Mac image worker** generation and **Mac Demo desktop window** finishing. Its receipt balanced 10 reserved = 7 contributor credits + 1 fee + 2 refunded. Native Save showed **Saved to Downloads**. Pausing both workers left them paused, then Disconnect showed **Disconnected**.
- The Android frontend production build passed and native source was reviewed. Native Android compilation was unavailable because the host lacks the SDK/NDK. SDK license consent was not provided, and no license was accepted.

The integrated end-to-end run used one physical Mac for generation and desktop-window finishing; it adds no physical-phone or multi-laptop failover evidence. Earlier results below retain their original build scope.

## Earlier design-phase checks

- Production web build and 28 Node regression tests passed. Rust checks passed with 11 tests passed and one ignored subprocess fixture; 45 coordinator tests passed.
- The native Mac debug `.app` built and rendered. **Connect installed worker** connected paused, and the managed worker's explicit Start/Pause controls were verified.
- A real local native Mac generation job finished through the iOS simulator, with a receipt of 10 reserved / 8 charged / 2 returned. Native Mac Save confirmed successful completion in Downloads.
- A browser test against the hosted coordinator through a loopback same-origin proxy completed with real Laptop2 generation and browser finishing. A planner request was durably acknowledged and cancelled with a full refund; successful hosted planner completion was not established by that check.
- A 390px web viewport had no horizontal DOM overflow. Comprehensive dark-mode and accessibility QA and physical multi-laptop failover are not established by these checks.

The results below predate the redesign and retain their original scope.

## Historical verification before the native UI redesign

- `npm run build`: TypeScript and production Vite build passed.
- `cargo check`: passed on macOS with a repository-local Cargo cache.
- `npm run tauri build -- --debug`: produced `src-tauri/target/debug/bundle/macos/PocketGrid.app`.
- Browser UI joined a live grid, explicitly shared a canvas worker, exported a real Python-generated image, earned 1 credit, and displayed a receipt reserving 10 / paying contributors 7 / fee 1 / refund 2.
- Browser Create submitted a job that completed through a Python generator and a native Swift exporter.
- Built Mac app joined via `tauri://localhost`, created a job, exported the Python-generated result inside WebKit, showed the image and receipt, and opted into native notifications. OS banner delivery depends on system notification settings and was not asserted.
- The active worker stopped on coordinator network loss; UI polling reconnects, while sharing requires another explicit Start.

## Job status checks

Run `node --experimental-strip-types --test apps/web/tests/jobStatus.test.mjs` from the repository root with Node 22. Status uses current API tasks, capabilities, limits and server time; it does not guarantee the next server assignment. Generation and verified export have separate counts, and contribution always requires an explicit action.
