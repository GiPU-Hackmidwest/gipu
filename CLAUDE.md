# PocketGrid

Read docs/project-context.md, AGENTS.md, docs/team-development.md and docs/native-ui-design.md before starting. README.md contains setup commands; docs/protocol.md defines the current API.

The teammate using Claude owns the **Tauri Android port**. Arboy using Codex owns the native macOS Tauri and iOS SwiftUI UX, shared visual language and platform-neutral frontend components. Earlier coordinator/deployment ownership is retired for this design phase. Preserve the working coordinator, Python workers, deployment and protocol unless both workstreams agree a specific UI requirement needs a change.

Coordinate shared React/Tauri file edits before implementing them. Reuse the Create, Contribute and Activity journeys, keeping text minimal and technical detail behind disclosure. `isMacDesktop` gates the Mac worker integration; do not invoke Mac subprocess commands merely because a Tauri runtime exists. Keep `DesktopWorkerPanel` mounted across navigation on macOS. Android lifecycle, credentials and notification integrations belong in Android-specific adapters; do not assume mobile background contribution is supported.
