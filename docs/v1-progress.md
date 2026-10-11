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
| C1 | Downloadable, easy app | todo: Mac DMG + Android APK releases | todo: iOS distribution, first run |
| C2 | QR sign-in, same credit account | todo: contract, server, `identity.ts`, Android scanner | todo: Mac/iOS sign-in + link UI, iOS scanner |
| C3 | Private sessions | todo: server scoping | todo: own-only presentation |
| C4 | No black text on orange | — | todo |
| C5 | Developer options page | — | todo |
| C6 | Create images / Finish images toggles | todo: verify on Android | todo |
| C7 | Activity without sensitive info | todo: sanitize events/tasks | todo: Activity presentation |
| C8 | Device counts, no test devices | todo: `grid` counts, cleanup | todo: landscape on Mac/iOS |
| C9 | Logo | blocked on Phase 0: Tauri icons | blocked on Phase 0: iOS icon, in-app mark |
| C10 | Rename to GiPU | todo: docs, Tauri/Android names | todo: in-app copy |
| C11 | Shimmer + notification, no border | todo: finalize contract, Android notify | todo: shimmer, iOS finalize, Mac/iOS notify |
| C12 | Replicable README | todo | review iOS/Mac sections |
| C13 | Desktop sidebar | — | todo |
| C14 | Remove "About this grid" | — | todo |
| C15 | Contribute layout on large screens | — | todo |

Phase 0 (Sithabo): confirm the name GiPU and add the logo to `assets/brand/`. Status: **todo**.

## Log

### 2026-10-11 · Claude · planning (no branch yet)

- Split the V1 success criteria into Claude and Codex workstreams: [v1-plan.md](v1-plan.md), this log, `CLAUDE.md` and `AGENTS.md`, plus the ownership section of `team-development.md`.
- Findings that shaped the split. `GET /state` currently returns **every** device and the latest 30 jobs from **all** users (`services/coordinator/store.py` `snapshot`). That is why C3/C7/C8 are server work. `POST /sessions` creates a new user on every call, so a QR scan alone would lose credits. Hence the Link QR in C2. The coordinator verifies finalize by redrawing the teal frame (`store.py`, near the `outline=(36,203,166)` check), so C11 changes coordinator, Python, browser and iOS finalizers together.
- Verification: documentation only. No code changed.
- **Handoff (Codex):** start C4, C5, C6, C13, C14 and C15 now; none depends on the contract. Wait for Claude's Phase 1 contract PR before building sign-in, device counts or shimmer.
- **Open questions (Codex):** do you agree with the pixel-identical finalize candidate and the Link-QR flow in v1-plan.md? Reply in your first entry.
