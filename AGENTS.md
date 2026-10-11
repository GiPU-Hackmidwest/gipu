# PocketGrid development instructions

Read docs/project-context.md first, then README.md, docs/protocol.md and docs/team-development.md before changing behavior.

- Preserve explicit device opt-in, Pause, session expiry, lease fencing and exactly-once credit settlement.
- Keep secrets, worker identity files, generated images and local databases out of Git. Use .env.example for configuration names only.
- Treat cloud image generation as a new optional capability. Never silently replace local computation with cloud output. Enforce user permission and budget in server code.
- Keep agent model-provider selection separate from image-model and device selection. Akamai chat currently powers Strands planning; laptop workers generate images.
- Ownership (design phase): Arboy with Codex owns native macOS Tauri and iOS SwiftUI UX, the shared visual language and platform-neutral frontend components. The teammate with Claude owns the Tauri Android port. Preserve coordinator, workers, deployment and protocol unless an agreed UI requirement needs a change.
- Keep shared React UI platform-neutral. Gate macOS worker integration with `isMacDesktop`, not merely Tauri detection; keep `DesktopWorkerPanel` mounted across navigation because unmounting disconnects the worker. Do not implement the Android port in the native UX workstream.
- Keep user-facing text minimal: short labels, one clear next action, and technical/accounting detail behind disclosure. Read docs/native-ui-design.md for the screen map and design tokens.
- Use one branch per focused change. Coordinate protocol, ledger and dependency changes across workstreams.
- Do not replace the working Tiny-SD path until a replacement has measured results and a fallback.
- Run checks relevant to changed behavior. Record actual measurements and hardware; do not present vendor timings as local results.
- Do not commit personal Xcode signing changes as required project defaults.
