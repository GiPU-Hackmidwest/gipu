# PocketGrid web and Mac client

This client is intentionally small: join a grid, submit image jobs, share a foreground browser export worker, control owned devices, inspect accounting, and opt into notifications. Actual image inference runs in the separate Python worker. Browsers and phones execute a fixed image export transform; they do not run diffusion.

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

`npm run build:desktop` (`scripts/build-desktop-app.sh`, needs `uv`) freezes the Python worker with PyInstaller into `src-tauri/resources/worker/`, builds the app with `tauri.bundled-worker.conf.json`, which ships that folder as an app resource, then restores the symlinks Tauri expands so PyTorch is not stored twice. The app is about 650 MB, mostly PyTorch. Model weights are not bundled: on first use, **Download image model** fetches the pinned Tiny-SD revision (about 1 GB) from Hugging Face into PocketGrid's app data, shows progress and can be cancelled. A successful download writes a ready marker only after the worker loads the model once. Connect then runs the bundled worker with `--local-only` and that cache; it still never downloads anything. The frozen worker is built for the machine's own platform and architecture, and is not yet code-signed or notarized.

### Checkout worker (development)

Builds without the bundled worker (`npm run tauri dev`, `npm run tauri build`) keep the prepared-checkout flow below. Prepare the Python environment and cache Tiny-SD once using [the worker setup](../../workers/python/README.md). Then join the grid in the Mac app and use **Connect installed worker** under Devices. The app finds its build checkout by default; **Installed worker settings** accepts another prepared PocketGrid folder and lets you choose Automatic, Apple GPU or CPU.

Connect explicitly starts one local Python process, loads the cached model and registers it **paused** under the current account. It never installs packages or downloads models. Once connected, set CPU threads, image size and session duration on **This Mac image worker**, then press **Start sharing**. Connecting consumes model memory even while paused. CPU thread limits are not GPU percentage or RAM quotas.

**Pause** stops accepting work and cancels active inference at a denoising boundary, while keeping the model loaded. **Disconnect worker**, **Leave**, reloading the interface or closing/quitting the app stops the managed process. Disconnect also asks the coordinator to pause the device; if the network is unavailable, its unfinished lease expires. Reconnecting always pauses the device again before it can claim work. A sharing session may continue while the Mac app is in the background, within the chosen limits; the canvas exporter still pauses when hidden.

In both modes the app passes the account token through the child's environment, never a command argument or clipboard. It stores a separate private worker identity per coordinator origin and session under app data. Existing command-line workers remain independent and are not stopped by the app. For manual pairing, use **Copy worker pairing token** and `POCKETGRID_SESSION_TOKEN`; a matching display name alone is not account linking.

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
node --experimental-strip-types --test tests/eventNotifications.test.mjs
cargo check --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
```

From the repository root, `node --experimental-strip-types --test apps/web/tests/desktopWorker.test.mjs` checks native-command ordering across disconnects and account changes. `workers/python/.venv/bin/python -m pytest tests/test_worker.py -q` checks paused registration and owner/server identity validation. Native process tests use an isolated fixture rather than image inference; one ignored test is that subprocess fixture.

## Verified in this checkout

- `npm run build`: TypeScript and production Vite build passed.
- `cargo check`: passed on macOS with a repository-local Cargo cache.
- `npm run tauri build -- --debug`: produced `src-tauri/target/debug/bundle/macos/PocketGrid.app`.
- Browser UI joined a live grid, explicitly shared a canvas worker, exported a real Python-generated image, earned 1 credit, and displayed a receipt reserving 10 / paying contributors 7 / fee 1 / refund 2.
- Browser Create submitted a job that completed through a Python generator and a native Swift exporter.
- Built Mac app joined via `tauri://localhost`, created a job, exported the Python-generated result inside WebKit, showed the image and receipt, and opted into native notifications. OS banner delivery depends on system notification settings and was not asserted.
- The active worker stopped on coordinator network loss; UI polling reconnects, while sharing requires another explicit Start.

## Job status checks

Run `node --experimental-strip-types --test apps/web/tests/jobStatus.test.mjs` from the repository root with Node 22. Status uses current API tasks, capabilities, limits and server time; it does not guarantee the next server assignment. Generation and verified export have separate counts, and contribution always requires an explicit action.
