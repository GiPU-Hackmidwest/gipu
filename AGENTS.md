# PocketGrid → GiPU development instructions

Read docs/project-context.md first, then README.md, docs/protocol.md and docs/native-ui-design.md before changing behavior.

## V1 workstream (current)

**Read [docs/v1-plan.md](docs/v1-plan.md) and [docs/v1-progress.md](docs/v1-progress.md) first, every session.** The plan lists the success criteria (C1–C15) and who owns what. The progress log records what you and Claude have done; check it for Claude's handoffs, contract changes and open questions before starting. The V1 plan supersedes earlier design-phase ownership where they conflict.

Arboy works with Codex and owns how the **Mac (React/Tauri) and iOS (SwiftUI)** apps look and behave. Sithabo works with Claude, who owns the server, protocol, identity/privacy logic, worker finalize contract, Android, README and release builds.

### Codex tasks

Start now (no contract dependency):

- **C4** Remove black text on orange. Choose an action colour/label pair with at least 4.5:1 contrast (for example, white on a deeper orange) on web and iOS. Update the tokens and contrast table in docs/native-ui-design.md.
- **C5** Add a **Developer options** page, off by default and stored locally. Move CPU threads, largest image, measured usage, worker paths/tokens and plan/device details there.
- **C6** Replace "This Mac · image creation" and "Worker setup & details" with two plain toggles: **Create images** (Mac generation) and **Finish images** (finishing). Turning a toggle on is the explicit Start. The first-time 1 GB model download still asks first. Keep `DesktopWorkerPanel` mounted and its connect/pause/disconnect semantics intact. The React component is shared, so Claude will check Finish images on Android.
- **C13** Redesign the desktop left sidebar.
- **C14** Remove the "About this grid" panel (React `App.tsx` and iOS `ContentView.swift`).
- **C15** Lay out Contribute for large screens instead of stretching one card.

After Claude's Phase 1 contract PR merges:

- **C2** Build sign-in on Mac and iOS: QR first, with "sign in another way" (grid/name/join code, optional username/password) behind it. On Mac, show the **Link QR** so a phone can join the same account. On iOS, add a scanner (VisionKit/AVFoundation), store the token in Keychain and handle `gipu://` links. Use Claude's `identity.ts` and `api.ts` for logic; do not reimplement it.
- **C3/C7** Show only the user's own requests and results. Remove the "Shared with grid members" copy. Activity shows no other users' device names or asset names.
- **C8** Replace "Devices in the grid" and the per-device list with the counts from `grid`: connected, ready to create, ready to finish. Show the user's own devices only where they control them.
- **C11** Remove the border and shimmer each image until its stage is verified. Notify on Mac/iOS when a job finishes. Update iOS `ImageProcessor.swift` to the new finalize contract.

After Phase 0 (logo in `assets/brand/`):

- **C9/C10** Add the iOS AppIcon and the in-app logo mark. Rename user-visible copy to **GiPU** on Mac and iOS. Bundle IDs and env var names stay unchanged.

Also: **C1** iOS distribution (TestFlight if an Apple account is available; otherwise a documented source build) and first-run ease. **C12** Review Claude's README sections for Mac and iOS.

### What Claude is doing

Claude's tasks are listed in CLAUDE.md and v1-plan.md: the contract PR, `user_sessions`/link-code/login auth, server-side privacy scoping, `grid` counts, the invisible finalize across coordinator/Python/browser, Android scanner/storage/notifications, Tauri/Android icons and names, README, and local builds for GitHub Releases. Their results and handoffs appear in docs/v1-progress.md.

### File boundaries

Codex owns `App.tsx`, `DesktopWorkerPanel.tsx`, `GridScene.tsx`, `style.css`, new React UI components, `deviceStatus.ts`, `eventNotifications.ts`, `apps/ios/**`, docs/native-ui-design.md and the Mac worker Rust. Do not edit Claude-owned files (`services/**`, `workers/**`, `tests/**`, `docs/protocol.md`, `api.ts`, `types.ts`, `browserWorker.ts`, `jobSync.ts`, `identity.ts`, Android adapters, `README.md`, `scripts/**`, `deploy/**`) without asking in the progress log. Coordinate `platform.ts`, `lib.rs`, `Cargo.toml`, `package.json` and `capabilities/default.json` first.

**After every PR, contract question, new dependency or end of session**, update your rows in the status table of docs/v1-progress.md. Add a newest-first log entry with the branch/PR, what changed, actual verification, handoff and open questions.

## Standing rules

- Preserve explicit device opt-in, Pause, session expiry, lease fencing and exactly-once credit settlement.
- Keep secrets, tokens, link codes, worker identity files, generated images and local databases out of Git. Use .env.example for configuration names only.
- Treat cloud image generation as a new optional capability. Never silently replace local computation with cloud output. Enforce user permission and budget in server code.
- Keep agent model-provider selection separate from image-model and device selection. Akamai chat currently powers Strands planning; laptop workers generate images.
- Keep shared React UI platform-neutral. Gate macOS worker integration with `isMacDesktop`, not merely Tauri detection. Keep `DesktopWorkerPanel` mounted across navigation, because unmounting disconnects the worker. Do not implement Android adapters in the Codex workstream.
- Keep user-facing text minimal: short labels and one clear next action. Technical and accounting detail goes in Developer options or disclosure. Read docs/native-ui-design.md for the screen map and design tokens.
- Use one branch per focused change. Coordinate protocol, ledger and dependency changes across workstreams.
- Do not replace the working Tiny-SD path until a replacement has measured results and a fallback.
- Run checks relevant to changed behavior. Record actual measurements and hardware; do not present vendor timings as local results.
- Do not commit personal Xcode signing changes as required project defaults.

## Release cost constraint

Build installers locally by default. On 2026-10-11 Sithabo approved one **manual-only** GitHub workflow (`.github/workflows/release.yml`, Actions → Release → Run workflow) that builds Android, Mac or both on request and can attach them to a draft release. Do not add automatic push, tag or PR triggers, and do not remove that workflow, without both Sithabo and Arboy agreeing. Repository signing secrets are optional and only Sithabo or Arboy uploads them.
