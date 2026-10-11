# V1 progress log

Shared record of what each workstream did, so either agent (and either person) can see it later. The plan and criteria IDs (C1–C15) are in [v1-plan.md](v1-plan.md).

**Rules for both agents**

- Read this file before starting work and when a branch or PR from the other side lands.
- Update your rows in the status table whenever a criterion changes state.
- Add a log entry (newest first) when you open or merge a PR, change a contract, add a dependency, or stop for the day with work in progress.
- Record actual verification: the commands run, real devices or simulators used, and what was not checked. Do not record a mockup or a simulator as a device result.
- Put anything the other side must do under **Handoff**. Put a question for the other side under **Open questions**, and answer it in your next entry.

## Status

States: `todo`, `in progress`, `review`, `done`, `blocked`.

| # | Criterion | Claude | Codex |
| --- | --- | --- | --- |
| C1 | Downloadable, easy app | todo: Mac DMG + Android APK releases | done: documented iOS source-build fallback; review: first run; TestFlight unavailable |
| C2 | QR sign-in, same credit account | review: contract/server merged; review: Android adapters (#24); todo: hosted deploy | review: Mac/iOS account/link UI implemented; browser two-client link verified; physical camera check pending |
| C3 | Private sessions | review: corrected server scoping merged; todo: hosted deploy | review: own-only presentation and Mac Keychain implemented; cross-account live journey passed |
| C4 | No black text on orange | — | done: implemented and checked; iOS interaction check pending |
| C5 | Developer options page | — | done: implemented and checked; iOS interaction check pending |
| C6 | Create images / Finish images toggles | todo: verify on Android | done: implemented; Mac live flow and lifecycle tests pass; iOS interaction check pending |
| C7 | Activity without sensitive info | review: corrected public summaries merged | review: generic Activity/credit labels implemented and live-checked; final regression pass pending |
| C8 | Device counts, no test devices | review: `grid` counts merged; todo: hosted deploy/cleanup if needed | review: anonymous `state.grid` landscape implemented; missing counts remain unavailable |
| C9 | Logo | blocked on Phase 0: Tauri icons | blocked on Phase 0: iOS icon, in-app mark |
| C10 | Rename to GiPU | todo: docs, Tauri/Android names | in progress: GiPU text implemented; current icon retained pending Phase 0 |
| C11 | Shimmer + notification, no border | review: coordinator accepts both + `verified`; todo: Python/browser finisher after deploy, Android notify | partial: authoritative verification/shimmer and notifications implemented; tested invisible iOS encoder staged; runtime remains legacy until deploy |
| C12 | Replicable README | done: fresh-clone README #21 | done: reviewed Mac/iOS commands and corrected setup order |
| C13 | Desktop sidebar | — | done: implemented and checked; iOS interaction check pending |
| C14 | Remove "About this grid" | — | done: removed on Mac/iOS |
| C15 | Contribute layout on large screens | — | done: Mac and 320 px browser layout checked |

Phase 0 (Sithabo): confirm the name GiPU and add the logo to `assets/brand/`. Status: **todo**.

## Log

### 2026-10-11 · Codex · Android adapter review and integration (#24)

- **Coordination:** Arboy explicitly requested review, conflict resolution and merge of incoming PRs. This narrow review updates Claude-owned Android session cleanup and regression tests, and preserves both workstreams in this log.
- Merged current main into the stacked Android branch; retained the privacy fixes and simpler contribution UI.
- Secure storage cleanup now reports an unsuccessful durable delete, and loading a secure session removes a stale plaintext copy. Storage errors continue to fail closed.
- Verification: frontend production build, macOS Rust (15 passed, one ignored) and 61 frontend tests pass, including stale plaintext cleanup, fail-closed storage, listener teardown and camera cancellation. Camera scans accept an AbortSignal so the UI can stop them on teardown/backgrounding. A failed cold-link read releases the warm-link listener. Physical Android QR decoding remains a team device check.
- **Handoff:** integrate the adapters into the new shared sign-in screen; retain Android-only plugin gates and unchanged bundle IDs.

### 2026-10-11 · Claude · Android QR sign-in adapters (branch `feat/v1-android-identity`, stacked on the README PR)

- **New dependencies (Android only), please review.** `tauri-plugin-deep-link` 2.6.1 and `tauri-plugin-barcode-scanner` 2.5.2, plus the matching npm packages.
  - The Rust crates sit under `[target.'cfg(target_os = "android")'.dependencies]` and register only under `#[cfg(target_os = "android")]` in `lib.rs`.
  - Their permissions are in a new `capabilities/android.json` with `platforms: ["android"]`, so the Mac build ignores them. `cargo check` and `cargo test` on macOS still pass (15 passed, 1 ignored).
- **Shared files touched (coordinate):**
  - `lib.rs`: Android-only plugin registration.
  - `build.rs`: declares the ACL for the app-local `secure-storage` plugin.
  - `package.json` and `Cargo.toml`.
  - Nothing in `App.tsx` or `style.css`.
- **Keystore storage.** `gen/android/.../SecureStoragePlugin.kt` is an app-local Kotlin plugin. It seals values with AES-256-GCM under a non-exportable Android Keystore key and stores only ciphertext in private SharedPreferences. There is no official Tauri Keystore plugin, and stronghold is slated for removal. The manifest now sets `allowBackup="false"` with backup and data-extraction rules that exclude all app data, including webview storage.
- **Deep links.** `gipu://join` and `gipu://link` are configured in `tauri.android.conf.json`. The plugin injected the intent filters into the committed manifest; other hosts are rejected by Android.
- **`apps/web/src/android.ts`** (new, logic plus one self-contained scan overlay):
  - `secureStorage` and `secureSessionStore`: a `SessionStore` that migrates an existing `pocketgrid.session.v1` out of localStorage once.
  - `listenForGridLinks`: cold and warm links, delivered once. Only fingerprints are remembered, because invite links contain the join code.
  - `scanGridLink`: asks for camera permission first, then runs a windowed scan behind a transparent page with a frame and a **Cancel** button; Back also cancels.
  - `androidAdapters()`: loads the real plugins on demand.
- **Upstream bug worked around.** In `tauri-plugin-barcode-scanner` 2.5.2, `cancel()` clears the pending scan before rejecting it, so a cancelled `scan()` never settles. `scanGridLink` settles Cancel itself.
- **Verification.**
  - Web: 49 Node tests (7 new in `tests/android.test.mjs`), `tsc -b` and `npm run build` passed. macOS: `cargo check` and `cargo test` passed.
  - The Android debug APK built. Emulator checks used a DevTools connection to the debug WebView:
    - Secure storage round-trips. `shared_prefs/secure_storage.xml` holds only base64 ciphertext (0 plaintext matches). The value survives a force-stop and relaunch, and delete clears it.
    - The `ALLOW_BACKUP` flag is absent from the installed package.
    - A cold-start `gipu://link` and a warm `gipu://join` both reach `get_current`. The warm link also arrives as a `deep-link://new-url` event. `gipu://pay` does not resolve to the app.
    - The camera prompt appeared and was granted. A windowed scan showed the camera behind the page, and cancel stopped the camera and restored the page.
    - Notifications: Activity → **Enable notifications** showed the Android 13+ permission dialog. After Allow, a real job produced "A grid laptop started work on your images" and "Images ready…" notifications.
  - **Not verified:** decoding a real QR code. The emulator's virtual camera would not turn toward the QR poster; parsing is covered by unit tests. Also not verified: a physical Android phone.
- **Handoff (Codex):** the sign-in screens can use these on Android. Gate with `isMobileApp` (Android is the only Tauri mobile target):
  ```ts
  const android = await androidAdapters();
  const session = await android.sessionStore.load();             // replaces localStorage on Android
  await android.listenForGridLinks(link => signInWithGridLink(new Api(link.server, ''), link, 'Android'));
  const scanned = await android.scanGridLink();                  // null if cancelled; CameraPermissionError → android.openCameraSettings()
  ```
  Restyle `.qr-scan` freely, but keep the page transparent while `html[data-scanning]` is set.
- **Brand.** The GiPU logo is on `feat/gipu-brand` (`c4cbde6`, `brand/`, including `brand/android/` launcher layers and `ic_stat_gipu.svg`). Once it merges, Claude will wire the Tauri desktop and Android launcher icons and the Android notification icon (`plugins.notification.icon`).

### 2026-10-11 · Codex · account UI review (`feat/v1-account-ui`)

- PRs #18–#22 are merged, including the #19 contract, #20 privacy correction (`ed8cbec`), #21 README (`e8db6fd`) and #22 controls (`eb365a9`). This work implements Mac/iOS sign-in and account linking, private presentation, anonymous grid counts and verification shimmer against that baseline. C2/C3/C7/C8 are in review, not complete; C11 remains partial until finisher rollout.
- **Shared-file coordination/dependencies:** `qrcode.react` **4.2.0** renders QR SVGs locally; macOS-only `security-framework` **3.7** stores sessions in Keychain through the existing `SessionStore` boundary. Package/Cargo locks and `lib.rs` registration change together. `ApiError.status` supports safe handling of revoked sessions. Shared origin parsing rejects credentials and malformed URLs. These changes are coordinated across `api.ts`, `identity.ts`, types and platform storage; Android adapters remain separate. QR contents never go to an external rendering service.
- **Behavior:** Link QR/code retains the same account and balance; New account creates a separate account. Mac migrates the earlier locally stored session to Keychain. Leaving stops owned contribution before credentials are discarded. Jobs/devices are filtered to the current account; Activity uses generic labels. `state.grid` supplies anonymous counts, with missing/invalid counts shown as unavailable. Only explicit `verified: false` shimmers, `true` confirms verification; a missing field does not imply verification.
- **Verification:** **65 frontend tests** passed, including five storage and ten identity tests. The native Mac build passed; Rust passed **16**, with one ignored fixture. In actual browsers on two origins, a new account generated a link code and the second client redeemed it into the same account with **100** credits. The native Mac app migrated an existing V1 session into Keychain with its **99**-credit balance. A real teapot request was generated by that Mac account and finished by the linked browser account. Both linked clients showed the same image, **93 available / 0 reserved / 1 earned** (8-credit cost plus 1 credit earned finishing). The Mac account showed **105 available / 13 earned** after earning 6 for generation, and retained only its own earlier cat image; the other account’s teapot was absent. Activity labels stayed generic without Mac device names. Native relaunch retained the 105-credit account, Show QR rendered, and Sign out returned to sign-in. Captures: `outputs/v1-mac-account.png` and `outputs/v1-linked-account-result.png`. Shimmer CSS/selection behavior is tested; its transient animation was not captured. A further foreign-earnings presentation regression is being checked; no additional passing test count is claimed here.
- **iOS:** arm64/x86_64 simulator and unsigned arm64 device builds passed. IdentityPrivacy, JobStatus, LifecycleRace and all **17** NotificationOwnership checks passed. The staged invisible encoder preserved all **65,536** RGB pixels across RGB, RGBA and indexed PNG inputs and rejected oversized input; production legacy frame/interior parity also passed. `GridModel` still uses the legacy finalizer. Rendered V1 UI testing is blocked by CoreSimulatorService sandbox access; no physical-phone or camera/scanner result is claimed.
- **Handoff:** preserve the new Mac commands, storage boundary and QR dependency when adding Android adapters. iOS remains native SwiftUI with Keychain and an on-demand scanner/manual fallback. Confirm compatible hosted coordinator deployment before switching any finalizer; `grid`/`verified` fields are not version negotiation. Brand assets, release distribution and physical-device verification remain outstanding. Earlier log entries retain their original historical verification scope.

### 2026-10-11 · Codex · README review (PR #21 · `fix/v1-readme-review`)

- Reviewed the Mac/iOS setup against actual scripts and merged #22 controls. Corrected root-relative Mac/Android commands, explicit worker `--join-code` (the worker does not load `.env`), `--connect-paused` for an existing identity, standalone/development cache differences and edit-before-start deployment order.
- **Coordination:** README is Claude-owned; these narrow review fixes are part of Arboy's explicit request to review/fix/merge the open PRs. No runtime or dependency change.
- **Verification:** command paths, worker flags and iOS signing/build instructions checked against source; whitespace check passes. The existing PR's fresh-clone build evidence remains in its log; these documentation corrections do not claim a new installation or deployment.
- **Handoff:** preserve #22 UI terminology and #20 privacy fix when updating this stacked branch. No open question from the Mac/iOS README review.

### 2026-10-11 · Claude · README from a fresh clone (branch `docs/v1-readme`, stacked on the server PR)

- **README.md** is rewritten as numbered paths:
  1. one computer
  2. Mac app
  3. Android
  4. iPhone
  5. phones and laptops on a LAN
  6. hosted grid
  7. optional planner
  8. tests

  It adds a prerequisites table, a troubleshooting table and honest prototype limits.
- **Scripts.**
  - `scripts/python.sh` (sourced) picks a working Python 3.12 or 3.11, or honors `POCKETGRID_PYTHON`. Before this, `setup.sh` hard-coded `python3.11`, which fails on Macs that have only 3.12 or a pyenv shim.
  - New `scripts/setup-worker.sh` creates the worker environment and downloads the model in one step.
- **Verification** from a fresh `git clone`, on this Mac (macOS 26.6.2, Apple silicon):
  - `setup.sh` passed in 30 s; `setup-worker.sh` passed in 3 min, including the PyTorch install and the Tiny-SD download.
  - The coordinator served the web app and `/api/health`.
  - The README worker command connected on MPS.
  - **First native Android build of this app:** `npm run tauri android build -- --debug --target aarch64 --apk` passed in 1 min 19 s, at the README's APK path. Installed on the `Medium_Phone` emulator, it joined `http://10.0.2.2:8787`, submitted a request, the worker generated it (5.6 s) and finished it, and the app showed the image, "completed", 92 available and an 8-credit receipt.
  - The README test block passed: 70 coordinator, 33 worker, 42 web, `npm run build`, and Rust 15 passed with 1 ignored.
  - **Not verified:** the iOS build (this Mac has no iOS simulator platform installed, so `xcodebuild` cannot find a destination), launching the Mac app with `tauri dev`, `build:desktop`, the Docker deploy, and any physical phone.
- **Seen on Android with the scoped server:** the "Your grid" card showed **0 laptops / 0 connected** while a laptop was sharing, because the current UI counts `state.devices`, which now holds only your own devices. The page still says "Shared with grid members" and shows the green border; the border is expected until the finishers switch.
- **Handoff (Codex):** switching the device landscape to `state.grid` is needed before the server PR is deployed, or every member will see an empty grid. Please review README sections 2 (Mac) and 4 (iPhone).


### 2026-10-11 · Codex · PR #20 review correction (`fix/v1-server-privacy-review`)

- The user explicitly requested review, fixes and integration of the remaining PRs. This authorizes a limited correction in Claude-owned coordinator/tests for the reproduced PR #20 privacy leak; Codex is recording the cross-workstream change here before editing.
- Scope: replace member-facing free-form planner/event text with safe summaries, preserve useful own-device controls/status and accounting, add short-name/raw-ID/renamed-device regressions, and review migration/auth compatibility. No new dependencies, deployment, push or merge in this worktree.
- Fixed: public plans/events now use allowlisted fields and generic summaries, including events without `device_id`; arbitrary foreign-worker metrics and planner refund reasons cannot carry device names/IDs. Internal traces are retained. Own device names/routes/metrics, sharing-expiry feedback, numeric timing/progress, balances and receipts remain available. Regression coverage includes short and renamed devices, duplicate own/foreign names, raw IDs and arbitrary planner fields.
- Image authorization now sweeps expired leases and requires a running or completed assignment. Cancelled/expired finishers lose source access; the owning member and completed producer retain access.
- Verification: primary coordinator environment `python -m pytest tests --ignore=tests/test_worker.py -q` passed **77**; worker environment `python -m pytest tests/test_worker.py -q` passed **33**. Migration regression preserves the original account, 90 available/10 reserved, the existing job and ledger; linking creates no new grant; a revoked legacy token stays revoked after restart. Cross-account session revocation is denied. Web **42** tests and `npm run build -- --configLoader runner` passed using existing dependencies; the runner avoids writing a Vite config temporary file into the read-only shared dependency directory. `git diff --check` passed. No deployed or physical-device check is claimed.
- Shared type coordination: root authorized `SessionInfo.last_used_at?: number | null` to represent migrated sessions accurately, without inventing a last-use timestamp.
- Handoff: root reviewed the fix, integrated current main including #22, and is updating PR #20. Privacy and image-access blockers are resolved by the regression-tested correction. PR #20 merged as `ed8cbec`; integrated checks passed 77 coordinator, 33 worker and 50 frontend tests plus frontend build. Claude's entries below describe the submitted PR before this correction.

### 2026-10-11 · Claude · coordinator V1 (branch `feat/v1-server-identity-privacy`, stacked on the contract PR)

- **Identity (C2).**
  - New `user_sessions`, `link_codes` and `credentials` tables. Existing `users.token` values migrate idempotently into sessions, so current signed-in apps keep working.
  - `POST /sessions` takes optional `name`/`client_name` (default `Guest XXXX`) and returns `session_id`.
  - New endpoints: link codes (10 characters, 120 s, single use, a new code replaces the old), `POST /sessions/link`, `POST /account/credentials` (scrypt; changing a login needs the current password), `POST /sessions/login`, `GET /sessions`, `DELETE /sessions/{id}` and `POST /sessions/logout`.
  - Link and login allow 5 failures per client address per minute, then return 429. The limit is in memory and resets on restart. `deploy/Dockerfile` now passes `--forwarded-allow-ips '*'` so the limit sees real client addresses behind Caddy; only Caddy can reach the port.
- **Privacy (C3/C7/C8).**
  - `/state` returns only the caller's jobs, devices and events, plus `grid` counts of online devices. Offline test devices drop out of the counts.
  - Jobs in snapshots, `POST /jobs`, cancel and `GET /jobs/{id}` go through `public_job`, which removes other members' `device_id`s, filters routes, drops planner `tools`/`reviews` traces and replaces other members' device names in explanations.
  - Events: other contributors' `credits_earned` is dropped. Another member's device shows as "A grid laptop started work on your images". Your own device's work on someone else's job keeps no `job_id`.
  - `GET /jobs/{id}` and `GET /images/{id}` are limited to the owner or a device assigned to the task (a finisher can read its source).
  - The Strands planner now reads `store.grid_devices()` instead of the member snapshot.
- **Finalize (C11).** The coordinator accepts pixel-identical output. It still accepts the teal frame unless `POCKETGRID_ACCEPT_LEGACY_FRAME=0`. `images[].verified` is set. The finishers (Python, browser, iOS) still draw the frame. Switch them only **after** this coordinator is deployed, because today's hosted coordinator rejects frameless output.
- **Verification.**
  - Coordinator suite: `.venv/bin/python -m pytest tests -q`, excluding the live/container harnesses and `test_worker.py`. 70 passed, 15 of them new in `tests/test_identity.py` and `tests/test_privacy.py`.
  - Worker suite: `workers/python/.venv/bin/python -m pytest tests/test_worker.py -q` passed 33.
  - Three `test_agent.py` tests now read planner traces from the internal job record, because the member snapshot strips them.
  - A live HTTP check against a local uvicorn with a fresh database confirmed: anonymous join, link to the same user, a second account seeing no jobs or devices, the session list, logout returning 401 and the CORS `DELETE` preflight.
  - Not run: the Docker/Caddy deployment, the live/container harnesses and any device.
- **Not deployed.** The hosted coordinator still runs the old code. Redeploying it is a separate, confirmed step.
- **Handoff (Codex):**
  - After this merges, "Devices in the grid" in `App.tsx` lists only the viewer's own devices. Switch to `state.grid`.
  - "Shared with grid members" is now false; please remove it.
  - Task rows for other members have `device_id: null`; use `device_kind`.


### 2026-10-11 · Codex · simple controls verified (PR #22 · `feat/v1-simple-controls`)

- Completed C4/C5/C6/C13/C14/C15 implementation and C10 in-app text. No dependency added. Technical controls are hidden by default on a persisted Developer options page; contribution stays an explicit choice.
- **Verification:** final production frontend and bundled debug Mac builds passed; all 50 frontend tests passed (including 8 contribution lifecycle/acknowledgement tests and 9 contract tests). In the actual Mac app, Create images and Finish images enabled work, persisted through navigation and Developer options changes, and paused through their switches. A local real image completed with receipt `10 = 7 + 1 + 2`. The final rebuilt Mac switch acknowledges Start/Pause immediately; quitting/reopening leaves sharing off. Browser Developer options persisted across reload. The 320 px layout has no horizontal overflow; account controls now remain a compact row. iOS build and harness evidence/limitations are recorded below.
- **Handoff:** Claude should check the shared Finish images control on an Android device. Physical iPhone and rendered iOS checks remain; source-build distribution is documented. PR #20 requires the privacy correction below before merge. The accepted #19 contract now unblocks the next separate QR/privacy/counts/shimmer UI branch. Frameless finishers must wait for a compatible coordinator deployment.
- **Open questions:** brand assets and TestFlight publishing are still unavailable. Existing model-ready startup was exercised; the already downloaded 1 GB model was not deleted/redownloaded for this pass.

### 2026-10-11 · Codex · contract sign-off and simple-controls review (`feat/v1-simple-controls`)

- **Contract accepted:** [PR #19](https://github.com/pocketgrid-hackmidwest/pocketgrid/pull/19) passed 42 frontend tests and the production build, and merged as `0e022b4`. This branch now includes it. Link QR preserves the existing credit account; Invite QR creates a new one. The ten-character typeable code is enough; a separate numeric code is unnecessary. Generic contributor activity about the user's own job is useful, provided it cannot expose another user's device or asset identifiers.
- **Contract answers:** times use Unix seconds; link codes last 120 seconds and sessions end on revocation/logout rather than age. Connected counts online devices; ready counts add enabled, unexpired sharing and capability. The implementation uses the 15-second lease window for online status and does not promise idle/model-ready or size-compatible capacity. Image `stage` stays `image_generate` / `image_finalize`; `verified` is authoritative, including accepted legacy framed output. There is no wire-version negotiation: deploy the accepting coordinator before frameless finishers. Missing `grid`/`verified` means older-coordinator data, not zero capacity or proof of verification.
- **PR #20 merge blocker:** reviewed server head `fb62d298`. In `services/coordinator/store.py:721–749`, privacy filtering replaces selected names but leaves short names and foreign device IDs in planner explanations. `public_events` at lines 788–798 also leaves IDs in `routing_updated` messages without a `device_id`. Reproduced against that code in an isolated scratch database: another account's device named `Pi`; create an owner job with `plan.explanation = "Selected Pi with device ID <foreign-id>"`, then add a `routing_updated` event containing that ID. Both `Pi` and the ID survived the owner job view, and the event ID survived its snapshot. This violates the merged no-other-device-name/ID contract. Use generic/allowlisted public summaries and test short names, raw IDs and historical/renamed devices before merging [PR #20](https://github.com/pocketgrid-hackmidwest/pocketgrid/pull/20).
- **UI implementation:** C4/C5/C6/C13/C14/C15 are ready for final review, not yet marked done. GiPU text is implemented for C10; existing icons remain until Phase 0 assets. Developer options is a separate local preference, off by default. Contribution toggles preserve explicit opt-in, model-download consent and the mounted Mac worker controller. No new dependencies.
- **Actual verification:** production web build and 41 pre-contract frontend tests passed, including eight contribution-lifecycle checks. Native Mac build passed. In the actual local Mac UI, Create images and Finish images were enabled explicitly; navigation and turning Developer options on/off preserved the workers. A real image request completed with a balanced receipt: 10 reserved = 7 contributors + 1 fee + 2 refunded. Browser checks confirmed Developer options defaults off, persists across reload, and the Finish images toggle works.
- **iOS scope:** arm64 and x86_64 simulator builds and an unsigned arm64 device build passed. The notification-ownership harness passed 17 checks; the lifecycle-race and job-status harnesses also passed. V1 rendered interaction testing was blocked by CoreSimulator sandbox access. These builds/harnesses are not physical-iPhone evidence. The documented source-build path satisfies the C1 fallback; TestFlight is unavailable.
- **Remaining final check:** rebuild the native Mac app after the latest acknowledgement fix. Prior Mac interaction evidence does not verify that final rebuilt artifact. Contract-dependent QR/privacy/count/finalize UI is still separate work; PR #19's merge does not imply PR #20 is safe or deployed.
- **Handoff (Claude):** correct and retest PR #20's public text filtering. Preserve legacy framed finishing until the new coordinator is deployed, and confirm the shared Finish images control on Android. Keep session revoke/logout separate from device pause; clients must stop their worker before discarding credentials when leaving the grid.
- **Open questions / minor contract follow-up:** migrated sessions return `last_used_at: null`, so `SessionInfo` should allow null or the server should omit it. Error responses remain HTTP status plus `detail` text; no stable typed error/retry-after field is defined. Use conservative UI errors until that is specified.

### 2026-10-11 · Claude · Phase 1 contract (branch `contract/v1-identity-privacy`)

- **Contract** in `docs/protocol.md`; every new item is marked **(V1)**:
  - **Identity.** `POST /sessions` has an optional name and returns `session_id`. New: `POST /sessions/link-codes`, `POST /sessions/link`, `POST /account/credentials`, `POST /sessions/login`, `GET /sessions`, `DELETE /sessions/{id}`, `POST /sessions/logout`. Tokens move to `user_sessions`. Link codes are 10 characters, single-use, 120 s and rate-limited.
  - **QR payloads.** `gipu://join?grid=&code=` and `gipu://link?grid=&code=`. The client builds the Link QR itself; the coordinator does not return a payload, because behind Caddy it does not know its public address.
  - **Scoped state.** `/state` returns only the caller's jobs and devices, plus `grid:{connected,ready_to_create,ready_to_finish}` and `user.username`. Tasks show `device_id` only for the caller's own devices and always show `device_kind`. Event messages are sanitized. `GET /jobs/{id}` and `GET /images/{id}` are limited to the owner or an assigned device.
  - **Finalize.** The finisher returns a pixel-identical lossless PNG and the server checks exact RGB equality. The legacy teal frame is accepted during rollout. `images[].verified` drives the shimmer; `job_completed` drives the notification.
- **Code.** `apps/web/src/types.ts` adds `GridCounts`, `JobImage.verified`, `Task.device_kind`, `SessionResponse`, `SessionInfo`, `LinkCode`, `GridLink` and `Session.userId`. The V1 snapshot fields are optional so the UI tolerates the current hosted coordinator. New `apps/web/src/identity.ts` contains `parseGridLink`, `gridLinkPayload`, `linkQrPayload`, `joinGrid`, `redeemLinkCode`, `signInWithPassword`, `signInWithGridLink`, `createLinkCode`, `addLogin`, `listSessions`, `revokeSession`, `signOut`, plus the `SessionStore` interface and `webSessionStore` (same `pocketgrid.session.v1` key as `App.tsx`). Sign-in calls refuse to send an existing token. It uses only type imports, so it runs under Node tests.
- **Not yet implemented.** The coordinator has none of the (V1) endpoints or scoping yet; that is the next Claude PR. `api.ts` is unchanged.
- **Verification** (apps/web): `node --experimental-strip-types --test tests/*.test.mjs` passed 42 tests, 9 of them new in `tests/identity.test.mjs`. `tsc -b` and `npm run build` passed. No server, device or UI checks were run.
- **Handoff (Codex):**
  - Review the (V1) items in `docs/protocol.md` and reply here.
  - After merge, build sign-in on `identity.ts`. Store sessions through `SessionStore` (iOS: Keychain, with parsing that mirrors `parseGridLink`).
  - Show the Link QR from `linkQrPayload(session.server, code, location.origin)`.
  - Shimmer images where `verified === false`.
  - Treat a missing `grid`/`verified` as "older coordinator", not as zero devices.
- **Open questions (Codex):**
  1. Is the 10-character typeable link code enough as the fallback, or do you want a separate short numeric code?
  2. Should Activity show other contributors' work on your job at all (generic "A grid laptop started image 2"), or only your own actions?

### 2026-10-11 · Codex · V1 simple controls (`feat/v1-simple-controls`)

- Started C4, C5, C6, C13, C14 and C15 from main `2a7f937`, after PR #18 merged the V1 plan. C10 in-app text changes to **GiPU** per Phase 0; the current logo/icon remains until Sithabo supplies the brand assets. No new dependencies.
- Direction: white `#FFFFFF` action labels on orange `#C34400` (calculated 5.06:1); a separate, locally stored Developer options page, off by default; plain Create images / Finish images toggles; distinct contribution cards in responsive columns and a tidier sidebar. Remove About this grid on Mac/iOS. Preserve model-download consent, explicit contribution opt-in and the mounted Mac worker controller.
- **Contract response:** agree with the **Link QR** attaching to an existing credit account and the **Invite QR** creating a new account. Agree with pixel-identical lossless PNG as the invisible-finalize candidate, subject to reviewing the actual Phase 1 contract, rollout and verification fields. This is not approval of an unreviewed schema.
- **Verification:** documentation and source-baseline review only at this entry; no V1 build, visual or live-flow result yet. Earlier native checks do not verify these changes.
- **Handoff (Claude):** no QR, privacy/scoping, aggregate-count or new finalize/shimmer UI will ship before the Phase 1 contract merges. Please preserve the current finalizer while that review is pending. Review the shared Finish images toggle on Android after this UI PR; iOS remains native SwiftUI.
- **Open questions (Claude):** confirm `grid.connected` counts online devices regardless of sharing, while ready counts require online, enabled, unexpired and compatible capability; define the online cutoff and whether readiness includes loading/model-ready state. Specify link/session expiry units, revocation behavior, typed error codes and retry semantics (expired/used code, invalid credentials, expired/revoked session). Specify old/new finalize version negotiation, exact accepted stage values and image selection semantics, and whether an accepted old framed output is still `verified` during rollout. The UI must not infer verification from border presence or an unknown stage.

### 2026-10-11 · Claude · planning (no branch yet)

- Split the V1 success criteria into Claude and Codex workstreams: [v1-plan.md](v1-plan.md), this log, `CLAUDE.md` and `AGENTS.md`, plus the ownership section of `team-development.md`.
- Findings that shaped the split. `GET /state` currently returns **every** device and the latest 30 jobs from **all** users (`services/coordinator/store.py` `snapshot`). That is why C3/C7/C8 are server work. `POST /sessions` creates a new user on every call, so a QR scan alone would lose credits. Hence the Link QR in C2. The coordinator verifies finalize by redrawing the teal frame (`store.py`, near the `outline=(36,203,166)` check), so C11 changes coordinator, Python, browser and iOS finalizers together.
- Verification: documentation only. No code changed.
- **Handoff (Codex):** start C4, C5, C6, C13, C14 and C15 now; none depends on the contract. Wait for Claude's Phase 1 contract PR before building sign-in, device counts or shimmer.
- **Open questions (Codex):** do you agree with the pixel-identical finalize candidate and the Link-QR flow in v1-plan.md? Reply in your first entry.
