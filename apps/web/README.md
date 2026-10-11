# PocketGrid web and Mac client

This client is intentionally small: join a grid, submit image jobs, share a foreground browser export worker, control owned devices, inspect accounting, and opt into notifications. Actual image inference runs in the separate Python worker. Browsers and phones execute a fixed image export transform; they do not run diffusion.

## Native design phase

Arboy with Codex owns the Mac and SwiftUI UX; the teammate with Claude owns the Tauri Android port. The shared client has **Create**, **Contribute** and **Activity** destinations. Keep visible text short and expose technical setup through disclosure. See [design and Android integration notes](../../docs/native-ui-design.md).

Mac worker controls are gated by `isMacDesktop`. A Tauri runtime alone is insufficient because Android also uses Tauri. Keep `DesktopWorkerPanel` mounted when navigation changes: its cleanup deliberately stops the managed Python process. The shared UI and HTTP API must remain platform-neutral; Android native adapters and lifecycle work belong to the Android owner.

Tauri windows use `create: false` in configuration and are explicitly bootstrapped from each window configuration in Rust setup, preserving configured properties. The macOS-only download handler accepts frontend-fetched `blob:` images and reports completion. Android owns its download integration; do not assume macOS WebKit download handling works there or create a duplicate automatic window.

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

Prepare the Python environment and cache Tiny-SD once using [the worker setup](../../workers/python/README.md). Then join the grid in the Mac app and use **Connect installed worker** in **Contribute**. The app finds its build checkout by default; **Installed worker settings** accepts another prepared PocketGrid folder and lets you choose Automatic, Apple GPU or CPU.

Connect explicitly starts one local Python process, loads the cached model and registers it **paused** under the current account. It never installs packages or downloads models. Once connected, set CPU threads, image size and session duration on **This Mac image worker**, then press **Start sharing**. Connecting consumes model memory even while paused. CPU thread limits are not GPU percentage or RAM quotas.

**Pause** stops accepting work and cancels active inference at a denoising boundary, while keeping the model loaded. **Disconnect worker**, **Leave**, reloading the interface or closing/quitting the app stops the managed process. Disconnect also asks the coordinator to pause the device; if the network is unavailable, its unfinished lease expires. Reconnecting always pauses the device again before it can claim work. A sharing session may continue while the Mac app is in the background, within the chosen limits; the canvas exporter still pauses when hidden.

This is a prepared-checkout prototype, not a bundled worker installer. The app passes the account token through the child's environment, never a command argument or clipboard. It stores a separate private worker identity per coordinator origin and session under app data. Existing command-line workers remain independent and are not stopped by the app. For manual pairing, use **Copy worker pairing token** and `POCKETGRID_SESSION_TOKEN`; a matching display name alone is not account linking.

## Behavior and security

- Contribution is off after joining and after page reload, and starts only when the owner presses Start.
- Each browser has a distinct device token. Owner sessions and device tokens are separate. Tokens are stored locally for this prototype, sent only in Authorization headers, never image URLs.
- Closing, hiding, or leaving this window stops its canvas worker and requests server-side lease revocation. Sessions also expire server-side.
- The canvas worker can only read a supplied image, apply the agreed 4-pixel RGB(36,203,166) border, and submit PNG output. No arbitrary code from jobs executes.
- Browser notifications may require HTTPS and platform support. The activity list works without notification permission. The Mac app uses native notifications after explicit opt-in.
- Earnings notifications require the event's recipient to match the signed-in user. Payments to other contributors still appear in job activity and receipts, without a personal earnings alert.
- Submitting again after an ambiguous network failure reuses the request ID for an unchanged form. A successful submission clears the ID so a later intentional request is a new job.
- The model generates a whole image on one laptop. Multiple variants may run on different laptops; exports can run on other devices. Retried generation starts again, not from a transferred checkpoint.

## Checks

```sh
npm run build
node --experimental-strip-types --test tests/*.test.mjs
cargo check --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
```

From the repository root, `node --experimental-strip-types --test apps/web/tests/desktopWorker.test.mjs` checks native-command ordering across disconnects and account changes. `workers/python/.venv/bin/python -m pytest tests/test_worker.py -q` checks paused registration and owner/server identity validation. Native process tests use an isolated fixture rather than image inference; one ignored test is that subprocess fixture.

## Design-phase checks

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
