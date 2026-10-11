# V1 plan (GiPU)

Agreed split for the V1 release, October 11, 2026. Sithabo works with **Claude**; Arboy works with **Codex**. Both agents read this file, then record their work in [v1-progress.md](v1-progress.md). This plan supersedes the design-phase ownership in [team-development.md](team-development.md) where they conflict.

The split is **logic vs presentation**: Claude owns the server, protocol, identity/privacy logic, worker contract, Android, README and release builds. Codex owns how the Mac (React/Tauri) and iOS (SwiftUI) apps look and behave. Neither waits on the other for work that does not touch the contract.

## Success criteria

| # | Criterion | Owner |
| --- | --- | --- |
| C1 | The app can be downloaded from somewhere and is easy to use. | Claude: release builds (Mac DMG, Android APK) on GitHub Releases. Codex: iOS distribution (TestFlight if an Apple account is available, otherwise a documented source build) and first-run ease on Mac/iOS. |
| C2 | A QR code signs you in as an anonymous user. Optional "sign in another way" with the normal fields. Re-signing in with a QR must re-attach you to your **existing** credit account. | Claude: server auth, protocol, platform-neutral session logic, Android scanner + secure storage. Codex: sign-in/link screens on Mac and iOS, iOS scanner + Keychain, Mac token storage. |
| C3 | Users never see what other people did (e.g. other people's generated images), but always see their own. | Claude: server-side scoping of jobs, images, events and the image endpoint. Codex: remove "Shared with grid members" copy; render own data only. |
| C4 | Black text on orange does not work. | Codex. |
| C5 | Hide technical detail (CPU threads, largest image, telemetry, worker paths) behind a **Developer options** page that is off by default. | Codex. |
| C6 | Replace "This Mac · image creation" and "Worker setup & details" with two plain toggles: **Create images** and **Finish images**. | Codex (shared React + iOS). Claude verifies the shared component on Android (Finish images only). |
| C7 | Activity stays, but does not expose other users' device names or generated asset names/IDs. | Claude: sanitize event messages and task device fields on the server. Codex: Activity presentation. |
| C8 | No test devices and no device identifiers in "Devices in the grid". Show counts only: connected now, ready to finish images, ready to create images. | Claude: aggregate `grid` counts, own-devices-only list, stale/test device cleanup. Codex: device landscape on Mac/iOS. |
| C9 | Product logo. | Sithabo generates it (Phase 0). Claude wires Tauri desktop + Android icons. Codex wires iOS AppIcon and the in-app mark. |
| C10 | Rename to **GiPU**. | Phase 0: Sithabo confirms and shares the logo. Codex: in-app copy on Mac/iOS. Claude: README/docs, Tauri `productName`/window title, Android label. |
| C11 | No green border to show verification. Exported images shimmer until verified; the shimmer stops when verified, and a notification fires when the job finishes. | Claude: new invisible finalize contract (coordinator, Python worker, `browserWorker.ts`), Android notification. Codex: iOS `ImageProcessor` on the new contract, shimmer UI on Mac/iOS, Mac/iOS notifications. |
| C12 | README lets someone with only the repo build and run everything. | Claude (Codex reviews the iOS/Mac sections). |
| C13 | Desktop left sidebar looks bad. | Codex. |
| C14 | Remove the "About this grid" panel. | Codex (React + iOS). |
| C15 | Contribute must not stretch one card across large screens; arrange it meaningfully. | Codex. |

## Phases

0. **Brand (Sithabo, now).** Confirm the name GiPU and generate the logo. Put the files in `assets/brand/`: an SVG master, a 1024×1024 transparent PNG and a single-colour mark. Log it in the progress file. Until then, agents keep the current icon and use the text "GiPU".
1. **Contract first (Claude, first PR).** Update `docs/protocol.md`, `apps/web/src/types.ts` and the `api.ts` client functions for identity, scoped state, grid counts and finalize (proposal below). Codex reviews it. Merge before any UI that depends on it.
   **In parallel (Codex):** C4, C5, C6, C13, C14, C15. These need no contract change.
2. **Implementation.** Claude: server + tests, Python/browser finalize, Android scanner/storage/notifications. Codex: sign-in/link UI, device counts, shimmer, iOS finalize, Mac/iOS notifications.
3. **Brand, docs, distribution.** Icons and the GiPU rename (C9, C10), README (C12), release builds (C1).
4. **End-to-end check.** Two separate accounts on Mac + Android + iOS: link a second device by QR and keep the same balance; confirm neither account sees the other's images, device names or asset names; shimmer → verified → notification. Record real devices and results.

## Contract proposal (Claude finalizes in the Phase 1 PR; Codex signs off)

### Identity and QR (C2)

Scanning an invite QR alone would create a new account every time and lose credits. So there are two QR codes plus an optional login:

- **Invite QR** — joins the grid as a new anonymous account. Payload `gipu://join?grid=<https url>&code=<join code>`. `POST /sessions {join_code, name?}` keeps working; the name becomes optional. Release builds can embed the default grid URL and join code so ordinary users never type them.
- **Link QR** — attaches another device to the **same** account and balance. A signed-in device calls `POST /sessions/link-codes` → `{code, expires_at, payload}` (single-use, about 2 minutes, stored hashed). The new device scans `gipu://link?grid=<url>&code=<code>` and calls `POST /sessions/link {code, client_name}` → `{token, user, balance}`. Typical flow: the Mac shows the Link QR; the phone scans it.
- **Optional login** ("sign in another way") — `POST /account/credentials {username, password}` adds a login to the existing anonymous account (hashed with stdlib `hashlib.scrypt`, no new dependency). `POST /sessions/login {username, password}` returns a new token for the same user. This allows recovery when no other device is signed in.
- **Session management** — tokens move from `users.token` into a `user_sessions` table (one user, many tokens) with a migration for existing rows. `GET /sessions`, `DELETE /sessions/{id}` and `POST /sessions/logout` exist.
- Tokens live in platform secure storage: Keychain (iOS), Android Keystore-backed storage (Android adapter), Tauri-side storage on Mac. Never put tokens or codes in URLs sent to the server or in logs.
- If the only device is lost and there is no login, the credits are lost. The UI should suggest linking a second device or adding a login, once and briefly.

### Scoped state (C3, C7, C8)

- `GET /state` returns only the caller's jobs, events, ledger and devices.
- A new `grid: {connected, ready_to_create, ready_to_finish}` contains counts of online, enabled-capable devices. Devices not seen recently are excluded.
- In the caller's own jobs, tasks run by other users' devices show only `device_kind` (laptop/phone/browser). `device_id` and names are omitted.
- Event messages never contain other users' device names, prompts or artifact IDs.
- `GET /images/{id}` requires the session that owns the job, or a device token assigned to a task that uses that image.
- Test/stale devices on the hosted grid: they are hidden by the online filter. Deleting rows from the hosted database needs a backup and a confirmation from the team first.

### Invisible finalize (C11)

- Finishing no longer draws the 4px teal frame. Candidate contract: the finisher returns a **pixel-identical lossless PNG** of the source with provenance text chunks (job/task ID). The coordinator verifies exact pixel equality with the source. This stays deterministic and keeps settlement exactly-once.
- `images[].stage` tells the UI whether an image is `generated` (shimmer) or `verified` (no shimmer). The `job_completed` event triggers the notification.
- Rollout: the coordinator accepts both the old frame and the new contract during the switch, so an old iOS/Android build does not fail settlement. Remove the frame path after all clients ship.

## File ownership

| Owner | Files |
| --- | --- |
| Claude | `services/coordinator/**`, `tests/**`, `workers/python/**`, `docs/protocol.md`, `apps/web/src/api.ts`, `types.ts`, `browserWorker.ts`, `jobSync.ts`, new `apps/web/src/identity.ts` (session/link logic, no UI), Android adapters (`src-tauri/gen/android/**`, `tauri.android.conf.json`, Android-only Rust), `src-tauri/tauri.conf.json` (name/icons), `README.md`, `scripts/**`, `deploy/**`, `.github/workflows/**` |
| Codex | `apps/web/src/App.tsx`, `DesktopWorkerPanel.tsx`, `GridScene.tsx`, `style.css`, new React UI components (sign-in, link, developer options), `deviceStatus.ts`, `eventNotifications.ts`, `apps/ios/**`, `docs/native-ui-design.md`, Mac worker Rust (`src-tauri/src/worker.rs`) |
| Coordinate first | `platform.ts`, `src-tauri/src/lib.rs`, `Cargo.toml`, `package.json`, `capabilities/default.json`. Announce new dependencies in the progress log before merging (e.g. Claude adds the Tauri barcode-scanner/notification plugins; Codex adds a QR rendering library). |

## Decisions for V1

- Bundle identifiers (`dev.pocketgrid.*`), the repository name and `POCKETGRID_*` environment variables stay unchanged, so installed apps, signing and deployment keep working. Only user-visible names change to GiPU.
- Explicit opt-in still applies: turning on **Create images** or **Finish images** is the explicit Start. The first-time 1 GB model download still asks first. Pause, session expiry, lease fencing and exactly-once settlement are unchanged.
- Mobile background contribution is still not assumed. Finishing on phones is foreground-only.
