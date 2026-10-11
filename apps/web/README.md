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

Install and launch the Python generation worker separately using its README. Use the advanced setup panel to copy your session pairing token, and pass it as `POCKETGRID_SESSION_TOKEN` when launching the worker. A matching display name is not account linking. After it has downloaded and loaded the model, it appears in the device list; its owner can start/pause it and change CPU thread, image pixel, and session duration limits from this client. The desktop app does not silently download a model or start a process. CPU thread limits do not promise a GPU percentage cap.

## Behavior and security

- Contribution is off after joining and after page reload, and starts only when the owner presses Start.
- Each browser has a distinct device token. Owner sessions and device tokens are separate. Tokens are stored locally for this prototype, sent only in Authorization headers, never image URLs.
- Closing, hiding, or leaving this window stops its canvas worker and requests server-side lease revocation. Sessions also expire server-side.
- The canvas worker can only read a supplied image, apply the agreed 4-pixel RGB(36,203,166) border, and submit PNG output. No arbitrary code from jobs executes.
- Browser notifications may require HTTPS and platform support. The activity list works without notification permission. The Mac app uses native notifications after explicit opt-in.
- Submitting again after an ambiguous network failure reuses the request ID for an unchanged form. A successful submission clears the ID so a later intentional request is a new job.
- The model generates a whole image on one laptop. Multiple variants may run on different laptops; exports can run on other devices. Retried generation starts again, not from a transferred checkpoint.

## Checks

```sh
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
```

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
