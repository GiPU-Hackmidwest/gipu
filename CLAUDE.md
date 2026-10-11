# PocketGrid → GiPU

Read docs/project-context.md, AGENTS.md, docs/protocol.md and docs/native-ui-design.md before starting. README.md contains setup commands.

## V1 workstream (current)

**Read [docs/v1-plan.md](docs/v1-plan.md) and [docs/v1-progress.md](docs/v1-progress.md) first, every session.** The plan lists the success criteria (C1–C15) and the split. The progress log records what you and Codex have done. Check it for Codex handoffs and open questions before starting. The V1 plan supersedes earlier design-phase ownership where they conflict.

Sithabo works with Claude. Arboy works with Codex on the Mac (React/Tauri) and iOS (SwiftUI) presentation. Claude owns the logic underneath plus Android:

1. **Contract first (Phase 1, first PR).** Update `docs/protocol.md`, `apps/web/src/types.ts` and `api.ts` for identity/QR, scoped state, `grid` counts and invisible finalize, as proposed in v1-plan.md. Get Codex sign-off through the progress log, then merge before Codex builds dependent UI.
2. **C2 identity.** Add the `user_sessions` table plus a migration; invite QR, link codes (single-use, short-lived, hashed), optional username/password login via `hashlib.scrypt`, session list/revoke/logout. Add a platform-neutral `apps/web/src/identity.ts` (logic only, no UI). On Android: QR scanner, Keystore-backed token storage and `gipu://` deep links.
3. **C3/C7/C8 privacy.** `GET /state` returns only the caller's jobs, events, ledger and devices, plus `grid: {connected, ready_to_create, ready_to_finish}`. Redact other users' device IDs and names in tasks. Sanitize event messages. Scope `GET /images/{id}` to the job owner or an assigned device. Test devices stay hidden through the online filter. Back up the hosted DB and get team confirmation before deleting any rows.
4. **C11 finalize.** Replace the teal frame with the agreed invisible, coordinator-verifiable finish in the coordinator, `workers/python` and `browserWorker.ts`. Accept both contracts during rollout. Add an Android notification when a job finishes.
5. **C6 on Android.** Verify the shared Finish images toggle on Android.
6. **C9/C10 brand.** After Sithabo adds the logo to `assets/brand/`, generate Tauri desktop and Android icons. Rename user-visible text to GiPU in docs, Tauri `productName`/window title and the Android label. Keep bundle IDs, the repo name and `POCKETGRID_*` env vars unchanged.
7. **C12 README.** Make the README replicable from a fresh clone: prerequisites, coordinator, worker, Mac app, Android, iOS (Codex reviews), deploy and tests.
8. **C1 distribution.** Publish GitHub Releases with a Mac DMG and an Android APK, and document unsigned-app caveats honestly.

Do **not** edit Codex-owned files (`App.tsx`, `DesktopWorkerPanel.tsx`, `GridScene.tsx`, `style.css`, `apps/ios/**`, `docs/native-ui-design.md`) without asking in the progress log. Coordinate `platform.ts`, `lib.rs`, `Cargo.toml`, `package.json` and `capabilities/default.json` before changing them. See the ownership table in v1-plan.md.

**After every PR, contract change, new dependency or end of session**, update your rows in the status table of docs/v1-progress.md. Add a newest-first log entry with the branch/PR, what changed, actual verification, handoff and open questions.

## Standing rules

- Preserve explicit opt-in (a toggle on counts as Start), Pause, session expiry, lease fencing, idempotency and exactly-once credit settlement. Changes to protocol, ledger or dependencies need agreement with Codex.
- `isMacDesktop` gates the Mac worker integration. Do not invoke Mac subprocess commands just because a Tauri runtime exists. Keep `DesktopWorkerPanel` mounted across navigation on macOS.
- Android lifecycle, credentials, notifications, downloads and scanning belong in Android-specific adapters. Do not assume mobile background contribution is supported.
- Keep user-facing text minimal. Put technical detail in Developer options.
- Keep secrets, tokens, link codes, worker identities, databases, model weights and generated images out of Git, URLs and logs.
- Use one branch per focused change. Do not commit personal Xcode signing changes.
- Report verification narrowly and keep device, emulator, simulator and build results separate.
