# GiPU handoff

For any engineer or coding agent picking up GiPU (formerly PocketGrid). It tells you where things are, what must not break, how to add something new and what is still open. State as of **October 23, 2026**, `main` at `08b406a`.

This document summarizes; it does not replace the sources below. When they disagree, trust them in this order: **source code and a fresh test run** → [v1-progress.md](v1-progress.md) (newest entries) → [protocol.md](protocol.md) → [v1-plan.md](v1-plan.md) → this file → older docs ([project-context.md](project-context.md), [team-development.md](team-development.md), [completion-audit.md](completion-audit.md)), which contain historical snapshots.

## Read first

1. This file.
2. [v1-progress.md](v1-progress.md): the status table and the newest five log entries. Look for **Handoff** and **Open questions** addressed to you.
3. [protocol.md](protocol.md): the API contract every client and worker relies on.
4. [README.md](../README.md): setup and run commands.
5. [native-ui-design.md](native-ui-design.md) before touching anything a user sees.
6. `AGENTS.md` (Codex) or `CLAUDE.md` (Claude) for your agent's standing rules.

## The product in one paragraph

A user asks for an image. A coordinator splits the request into one **generation** task per image and one **finishing** task per generated image. Laptops that their owners have explicitly opted in claim generation tasks; phones, browsers and the Android app claim finishing tasks. Every accepted task pays its contributor sandbox credits exactly once, and the requester gets a receipt. In the hosted demo, generation pixels come from Akamai's hosted model through the coordinator (`cloud` mode); with no key, laptops run Tiny-SD locally (`local` mode). Finishing is a lossless PNG re-export that the coordinator checks pixel-for-pixel against the source.

What it is **not**: model sharding (one image never spans devices), peer-to-peer (everything goes through the coordinator over HTTPS polling), background mobile compute (phones finish only while the app is open), real money out (credits can be bought in Stripe **test mode** but never cashed out), or proof of honest generation (only format, size and finishing pixels are verified).

## Current state

| Area | State |
| --- | --- |
| Hosted grid | `https://66-228-53-243.ip.linodeusercontent.com` (Akamai Linode, Docker + Caddy). Last recorded deployed commit `21a4372` (leaderboard); later `main` commits are docs and build scripts only. Cloud generation on (`akamai/hackathon-image`), Stripe test key configured. Confirm with `curl …/api/health` and `/opt/pocketgrid/DEPLOYED_COMMIT` on the server. The join code lives only in the server's `deploy/.env`. |
| Releases | **v0.3.0** published (Mac DMG + debug-signed Android APK). **v0.4.0** draft: its Mac DMG is defective (unsealed signature), do not use. **v0.4.1** draft: Mac only, corrected signature, installed and verified on one Mac; awaiting a second-Mac check and publication. |
| V1 criteria | C1–C15 and L1 are done or in review; see the status table in [v1-progress.md](v1-progress.md#status). |
| Repository | Renamed to `GiPU-Hackmidwest/gipu`; old `pocketgrid-hackmidwest/pocketgrid` URLs redirect. Bundle IDs (`dev.pocketgrid.*`), env vars (`POCKETGRID_*`) and many internals intentionally keep the old name. |

Test results from a clean worktree of `main` on this date are under [Run and test](#run-and-test).

## Architecture map

```text
 Mac (Tauri+React) · Android (Tauri+React) · iPhone (SwiftUI) · browser (React)
                │  HTTPS, Bearer session/device tokens, ~2 s polling
                ▼
 services/coordinator  FastAPI + one SQLite file + images on disk
   app.py      routes, pydantic request models, auth deps, background loops
   store.py    every DB transaction: sessions, devices, jobs, tasks, leases, ledger, privacy views
   agent.py    optional Strands planner + reviewer (akamai | ollama | bedrock | manual)
   cloud_images.py  Akamai image API (key never leaves the coordinator)
   payments.py      Stripe Checkout, test mode only, money in only
   leaderboard.py   weekly opt-in rankings
                ▲  devices claim → heartbeat → progress → complete/fail
 workers/python/worker.py   laptop worker: LocalRenderer (Tiny-SD) or CloudRenderer
 apps/web/src/browserWorker.ts  browser/Android finisher
 apps/ios/PocketGrid/ImageProcessor.swift  iPhone finisher
```

| Path | What lives there | Owner |
| --- | --- | --- |
| `services/coordinator/app.py` | Routes, `Strict` pydantic models (extra fields rejected), `owner`/`worker`/`member` auth dependencies, rate limiting (`guarded`), body size limit, lifespan loops (`store.tick` every 1 s, planner every 1 s, reviewer every 2 s) | Claude |
| `services/coordinator/store.py` | `Store`: schema in `__init__`, `tx()` (one `BEGIN IMMEDIATE` per call, under a process lock), `event()`/`ledger()` helpers, pricing (`price_for`, `quote`, `reserve_job`), lease logic (`claim`, `heartbeat`, `sweep`, `retry`), `complete` (verification + settlement), privacy views (`snapshot`, `public_job`, `public_events`, `grid_counts`, `image_path`) | Claude |
| `services/coordinator/agent.py` | `_model(mode)` picks the provider; `plan_once`/`review_once` run bounded `@tool`s; code validates every agent choice | Claude |
| `workers/python/worker.py` | `DeviceWorker` loop, `LocalRenderer`/`CloudRenderer`, `finalize_image`, identity file, `--generator auto\|cloud\|local`, `--share`/`--connect-paused`/`--generate-only` | Claude |
| `apps/web/src/api.ts`, `types.ts` | HTTP client and the TypeScript mirror of the protocol; also exports the platform flags | Claude |
| `apps/web/src/identity.ts` | Platform-neutral sign-in logic: QR payloads (`parseGridLink`, `gridLinkPayload`), join/link/login, sessions, `SessionStore` | Claude |
| `apps/web/src/jobSync.ts` | Keeps acknowledged jobs through stale or failed snapshots | Claude |
| `apps/web/src/android.ts` + `src-tauri/gen/android/**` | Android adapters: Keystore storage (`SecureStoragePlugin.kt`), `gipu://` deep links, QR scanner | Claude |
| `apps/web/src/App.tsx`, `DesktopWorkerPanel.tsx`, `GridScene.tsx`, `style.css`, UI components | Shared React presentation for Mac, Android and browser | Codex |
| `apps/web/src-tauri/src/worker.rs`, `mac_session.rs` | Mac: launches the bundled Python worker, Keychain session | Codex |
| `apps/web/src-tauri/src/lib.rs`, `Cargo.toml`, `package.json`, `capabilities/*.json`, `platform.ts` | Plugin registration, permissions and dependencies | Coordinate first |
| `apps/ios/**` | Native SwiftUI app. It does **not** share code with React; `Models.swift` and `GridModel.swift` mirror the protocol and `identity.ts` rules by hand | Codex |
| `deploy/`, `scripts/`, `.github/workflows/release.yml` | Docker/Caddy stack, setup and build scripts, manual-only release workflow | Claude |
| `brand/` | Logo sources and generated icons | Sithabo |

### Request lifecycle (what to trace when debugging)

1. `POST /api/jobs` → `Store.create_job` (or `create_planning_job` with `use_agent`) reserves the full budget, locks prices into `plan.pricing` and creates one `image_generate` task per image. The `request_id` makes it idempotent.
2. An enabled worker's `POST /devices/{id}/claim` → `Store.claim` returns any task the device already holds (one per device), otherwise picks a queued task the device passes `is_eligible` for (enabled, online, capability, `max_pixels`) and that agent routing preferences (`preferred_ready`) allow, and issues a 15 s lease. Expired sharing sessions are paused by `sweep`.
3. Heartbeats every 3 s renew the lease. `store.tick` → `sweep` expires stale leases and requeues through `retry`, excluding the device that just failed.
4. `POST /tasks/{id}/complete` → `Store.complete` validates the live lease, decodes the PNG, checks its size (and, for finishing, exact pixel equality with the source, plus the legacy teal frame while `POCKETGRID_ACCEPT_LEGACY_FRAME` ≠ `0`), writes an `earned` ledger row once, and creates the `image_finalize` task.
5. When every task is done, the job charges its 1-credit fee and refunds the rest. Clients see it via `GET /state` → `Store.snapshot`, already scoped to the caller.

## Invariants you must not break

Each has tests. If your change touches one, extend those tests rather than editing them to pass.

- **Explicit opt-in.** Joining, connecting or installing never starts contribution. Turning on **Create images** / **Finish images** is the Start. New devices register `enabled:false`. Pause revokes the lease immediately. Sharing sessions expire.
- **Lease fencing.** Only the live lease ID can report progress, complete or fail. A stale result never earns. Lease expiry runs on its own loop and must never wait on a model or provider call.
- **Exactly-once settlement.** Reservation, earned payments, fee and refund happen in one transaction each; duplicate completions return `duplicate:true` and pay nothing. Completed work and receipts are immutable. The balance has a `CHECK(balance>=0)`.
- **Locked pricing.** A job pays the prices locked at reservation, whatever supply does later.
- **Privacy (C3/C7/C8).** `/state`, `/jobs/{id}`, `/images/{id}` and events return only the caller's data. Other users' devices appear only as anonymous `grid` counts and `device_kind`. Event messages and planner text never contain another user's device name, device ID, prompt or artifact ID. Use allowlisted generic messages (see `public_events`); do not try to redact free text.
- **Secrets out of Git, URLs and logs.** Session tokens, device tokens, link codes, join codes, API keys, Stripe keys, worker identity files, databases, model weights and generated images. Tokens go in headers only; QR payloads are parsed locally and never sent to the server.
- **Money flows in only.** No payout, withdrawal or card-refund route exists, and a test asserts that. Live Stripe keys are refused. iOS has no purchase UI (App Store rules).
- **Cloud is labeled, never silent.** Cloud output carries `generated_in:"cloud"` and clients show "Cloud-generated". Never swap local computation for cloud output without that label and server-side permission.
- **Agent is bounded.** The planner cannot change prompt, count or budget; code validates every route it proposes; workers never run generated code. Manual mode never calls a model.
- **Platform gates.** `isMacDesktop` (not "is Tauri") gates the Mac worker. `DesktopWorkerPanel` stays mounted across navigation because unmounting disconnects the worker. Android logic lives in Android adapters. Mobile contribution is foreground-only.
- **One coordinator, one SQLite file.** No replicas, no network filesystem.

## Ownership and coordination

Two people, two agents: **Sithabo with Claude** (server, protocol, identity/privacy logic, worker/finishing contract, Android, README, releases, deploy) and **Arboy with Codex** (Mac and iOS presentation). File-level ownership is in [v1-plan.md](v1-plan.md#file-ownership).

If you are a new engineer or agent, find out which person you are working for and take that side's files. To change a file the other side owns, or any **Coordinate first** file, ask in the progress log first. A person's explicit request in their own chat counts as authorization for a focused change; record it in your log entry.

The progress log is the team's shared memory. After every PR, contract change, new dependency or end of session, update your column in the status table and add a newest-first entry with: branch/PR, what changed, the verification you actually ran (commands, device or simulator names), **Handoff** and **Open questions**. Never record a simulator, emulator, mockup or fixture as a physical-device result.

Workflow rules:

- One focused branch per change, PR into `main`, keep `main` runnable.
- Other sessions share the main checkout. Use `git worktree add ../gipu-<topic> -b <branch> origin/main` instead of switching branches there, and never stage files you did not create.
- Never commit personal Xcode signing changes (`project.pbxproj` team edits).
- Do not add automatic triggers to, or remove, `.github/workflows/release.yml` without both Sithabo and Arboy agreeing.

## Run and test

Setup is in the [README](../README.md#build-from-source). The short version:

```bash
cp .env.example .env
./scripts/setup.sh
./scripts/server.sh
```

```bash
./scripts/setup-worker.sh
workers/python/.venv/bin/python workers/python/worker.py run --join-code pocketgrid-demo --device-name "My laptop" --share
```

Tests, from the repository root:

```bash
.venv/bin/python -m pytest tests -q --ignore=tests/test_worker.py --ignore=tests/live_agent_routing.py --ignore=tests/live_worker_recovery.py --ignore=tests/container_smoke.py
```

```bash
workers/python/.venv/bin/python -m pytest tests/test_worker.py -q
```

```bash
cd apps/web && node --experimental-strip-types --test tests/*.test.mjs && npm run build && cargo test --manifest-path src-tauri/Cargo.toml
```

Results on `08b406a` (October 23, 2026, Sithabo's Mac): coordinator **118 passed**, worker **36 passed**, frontend **83 passed**, and the production web build succeeded. `cargo test`, the slow live checks, app builds and devices were not run for this handoff.

Test conventions: coordinator tests build a real app with `TestClient(create_app(tmp_path))` and set `POCKETGRID_AGENT_MODE=manual`; reuse the helpers in `tests/test_coordinator.py` (`LIMITS`, `png`, `request`) and the multi-account `grid` fixture in `tests/test_privacy.py`. External services (Stripe, Akamai) are faked with `httpx` mock transports; no test needs a real key. Frontend tests are plain `node:test` files over pure modules, so keep logic out of React components to keep it testable. Slow end-to-end checks (`live_worker_recovery.py`, `live_agent_routing.py`, `container_smoke.py`) are described in [verification.md](verification.md).

## Integrating something new

Pick the playbook that matches. Every playbook ends the same way: tests, `docs/protocol.md` if the contract changed, a progress-log entry, and a hosted deploy only after a backup.

### A new API endpoint or field

1. Add a `Strict` request model and route in `app.py`. Choose the auth dependency deliberately: `owner` (session token), `worker` (device token) or `member` (either, then authorize per object).
2. Put the logic in a `Store` method that opens exactly one `with self.tx() as db:`. Use `self.event(...)` and `self.ledger(...)` inside that transaction; never touch balances outside it.
3. If the data reaches clients through `/state`, add it in `snapshot` and make sure it is scoped to `user_id`. Anything about another account must be a count or an allowlisted generic string.
4. Update `docs/protocol.md`, `apps/web/src/types.ts` and `api.ts`. Mark new fields optional where older coordinators may not send them, because installed apps talk to whatever the hosted grid runs. Tell Codex in the log so iOS `Models.swift` can mirror it.
5. Test the happy path, another account getting 404 (not 403), a device token where a session is required, and the idempotent retry.

### A schema change

There is no migration framework. The schema is `CREATE TABLE IF NOT EXISTS` statements in `Store.__init__`, followed by one-off idempotent data migrations (see the `users.token` → `user_sessions` move). Prefer **additive new tables** keyed by the existing ID (as `leaderboard_profiles`, `purchases` and `cloud_outputs` do) over altering existing tables. If you must add a column, add an idempotent guarded `ALTER TABLE` (check `PRAGMA table_info` first) and test startup against a database created by the previous version. Before deploying, back up the hosted volume (see [deploy/README.md](../deploy/README.md#operations-and-recovery)), and never delete hosted rows without team confirmation.

### A new kind of work (beyond image generate/finalize)

This touches the contract in several places; agree it with the other side first.

- Capability name: the `Literal` in `DeviceRegistration` (`app.py`), `types.ts`, iOS models.
- Task creation: `Store.new_task`, and where `complete` chains the next stage.
- Eligibility: `Store.is_eligible` (capability, size limits) and `validate_routes` for the planner.
- Verification and payment: the `complete` branch for the kind. Be explicit about what is and is not verified.
- Pricing: `price_for`/`quote` and the locked `plan.pricing`. Keep old jobs on their locked prices.
- Privacy: `public_job` and `public_events` must cover the new kind.
- Leaderboard: `leaderboard.py` finds accepted work by joining `earned` ledger rows to tasks on the note text `Accepted <kind> <task id>`. Keep that note format, and decide whether the new kind counts.
- Executors: `worker.py`, and `browserWorker.ts` / `ImageProcessor.swift` if phones run it. Phones stay foreground-only.

### A new image generator or model

Follow `cloud_images.py` plus `CloudRenderer`: the provider key stays on the coordinator; the worker still claims, holds the lease, reports progress and submits through `/complete`; output is labeled through `generated_in` and `model`; the mode shows in `/health` and `/state.generation`; the worker picks it with `--generator`. Respect provider rate limits inside a bounded wait (Akamai is 6 images/minute per team). Do not replace the Tiny-SD local path until a replacement has measured results and a fallback. Record real timings and hardware; vendor numbers are not local results.

### A new planner provider

Add a branch in `agent._model(mode)` and its env vars, update the `POCKETGRID_AGENT_MODE` list in the README and `.env.example`, and fail with an explicit error (no reservation) when credentials are missing. Keep planner choice separate from image-model choice. Tests in `tests/test_agent.py` and `tests/test_routing.py` show how to drive the tools without a live model.

### A client feature

- **Shared React (Mac, Android, browser):** logic goes in a pure module under `apps/web/src/` with a `node:test` test; the component only renders. Use `isMacDesktop`/`isAndroidApp` from `api.ts`. Keep user-facing text to a label and one next action; technical detail goes in **Developer options**.
- **Android-only:** add to `android.ts` and, for native code, a Kotlin plugin next to `SecureStoragePlugin.kt` registered in `lib.rs` under the Android `cfg`. Permissions go in `capabilities/android.json`.
- **iOS:** separate SwiftUI implementation in `apps/ios/PocketGrid/`. Build with the `xcodebuild` command in the README.
- **Mac worker:** `src-tauri/src/worker.rs` (Codex). Never invoke Mac subprocess commands just because Tauri is present.

### A new dependency or Tauri plugin

Announce it in the progress log before merging. A Tauri plugin needs `package.json`, `Cargo.toml`, registration in `lib.rs` and a narrowly scoped permission in `capabilities/*.json` (for example, the opener is limited to `https://checkout.stripe.com/*`). The coordinator avoids new Python dependencies where the standard library or `httpx` suffices; update `services/coordinator/requirements.lock` when it cannot.

### Configuration

New settings use the `POCKETGRID_` prefix (third-party keys keep their vendor names, like `AKAMAI_API_KEY` and `STRIPE_SECRET_KEY`). Add the name with an empty or local-default value to `.env.example` and `deploy/.env.example`, and pass it through `deploy/compose.yaml`. Real values live only in local `.env` and the server's `deploy/.env` (mode 0600).

## Deploy and release

**Hosted coordinator** ([deploy/README.md](../deploy/README.md)): check there are no active jobs; back up the `grid-data` volume to `/root/backups/`; upload committed files only with `git archive <commit> | ssh root@HOST …`; write `DEPLOYED_COMMIT`; `docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build`; check `/api/health` and do one small job. Never `down -v`. Deploy the coordinator before shipping clients that depend on new server behavior. SSH access is per-person; this document grants none.

**Installers** ([releasing.md](releasing.md)): build locally, or run **Actions → Release → Run workflow** (manual only; `android`, `macos` or `both`; optional draft). Verify checksums, `hdiutil verify` and `codesign --verify --deep --strict` on the Mac app before publishing. Publishing a draft is a manual, team-agreed step.

## Open work

Roughly in priority order. Check the newest progress entries first; some may have moved.

1. **Publish a release.** Second-Mac install of the v0.4.1 draft, then publish. Delete or clearly mark the defective v0.4.0 Mac draft. Produce a properly signed Android APK (the signing key script exists; repository secrets are not set, so CI APKs are debug-signed).
2. **Physical-device evidence (V1 Phase 4).** QR link scanning with a real camera (Android and iPhone), real-phone finishing on the current invisible contract, and a two-account, three-platform end-to-end run. All of these are pending; only emulator, simulator and browser checks exist.
3. **Android finish notification icon** (C11, Claude).
4. **Retire the legacy teal frame.** Once no installed client draws it, set `POCKETGRID_ACCEPT_LEGACY_FRAME=0` on the hosted grid, then remove the code path and its tests.
5. **Mac Keychain prompt on unsigned builds.** Each unsigned build has a new signature, so macOS asks before reading the saved session. Options: Developer ID signing and notarization (needs an Apple Developer account), or treat a denied read as signed out. The Mac session code is Codex's.
6. **iOS distribution.** No TestFlight; source build only. Native iOS tab interactions and a full accessibility review are still pending.
7. **Production-hardening gaps** if GiPU goes beyond a demo: Postgres and object storage instead of SQLite and local files, abuse controls, worker trust and stronger verification, real payment compliance. See [deploy/README.md](../deploy/README.md).

## Gotchas

- Physical phones cannot reach `127.0.0.1`. Run the coordinator with `POCKETGRID_HOST=0.0.0.0` and use the computer's LAN address; event Wi-Fi often isolates clients. The Android emulator uses `http://10.0.2.2:8787`.
- Android release builds refuse plain `http://`; use a debug build for a local grid.
- Older installed iOS builds show a fixed price and can be refused when dynamic pricing quotes 9; the 422 message states the required amount.
- Changing the join code does not revoke existing sessions. Revoking a session does not pause that account's devices.
- Akamai's 6 images/minute team quota is shared by everyone using the key, including tests against the hosted grid.
- The hosted grid's accounts and balances are real demo data. Use throwaway accounts for checks, pause their devices and log them out afterwards.
- Codex's main checkout on Arboy's Mac is now `gipu/`; this Mac's is still `pocketgrid/` with the old remote URL, which redirects.
- Historical docs mention Arboy's Mac IPs, old commits and "no cloud API is called". Those are snapshots; recheck live state before a demo.

## Before you open a PR

- [ ] Branch from current `origin/main` in a worktree; the diff contains only your change.
- [ ] Relevant tests pass, with new tests for new behavior and any invariant you touched.
- [ ] `docs/protocol.md`, `types.ts` and `api.ts` updated together for any contract change.
- [ ] No secrets, tokens, databases, images, model weights or Xcode signing edits staged.
- [ ] User-facing text is minimal; technical detail is in Developer options.
- [ ] Progress log updated: status row, newest-first entry with real verification, Handoff, Open questions.
