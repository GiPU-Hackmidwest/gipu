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
| C2 | QR sign-in, same credit account | review: contract + `identity.ts`, server (`feat/v1-server-identity-privacy`); todo: Android scanner, hosted deploy | todo: Mac/iOS sign-in + link UI, iOS scanner |
| C3 | Private sessions | review: server scoping; todo: hosted deploy | todo: own-only presentation |
| C4 | No black text on orange | — | todo |
| C5 | Developer options page | — | todo |
| C6 | Create images / Finish images toggles | todo: verify on Android | todo |
| C7 | Activity without sensitive info | review: server sanitizing | todo: Activity presentation |
| C8 | Device counts, no test devices | review: `grid` counts (stale devices excluded); todo: hosted DB cleanup if still needed | todo: landscape on Mac/iOS |
| C9 | Logo | blocked on Phase 0: Tauri icons | blocked on Phase 0: iOS icon, in-app mark |
| C10 | Rename to GiPU | todo: docs, Tauri/Android names | todo: in-app copy |
| C11 | Shimmer + notification, no border | review: coordinator accepts both + `verified`; todo: Python/browser finisher after deploy, Android notify | todo: shimmer, iOS finalize, Mac/iOS notify |
| C12 | Replicable README | todo | review iOS/Mac sections |
| C13 | Desktop sidebar | — | todo |
| C14 | Remove "About this grid" | — | todo |
| C15 | Contribute layout on large screens | — | todo |

Phase 0 (Sithabo): confirm the name GiPU and add the logo to `assets/brand/`. Status: **todo**.

## Log

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

### 2026-10-11 · Claude · planning (no branch yet)

- Split the V1 success criteria into Claude and Codex workstreams: [v1-plan.md](v1-plan.md), this log, `CLAUDE.md` and `AGENTS.md`, plus the ownership section of `team-development.md`.
- Findings that shaped the split. `GET /state` currently returns **every** device and the latest 30 jobs from **all** users (`services/coordinator/store.py` `snapshot`). That is why C3/C7/C8 are server work. `POST /sessions` creates a new user on every call, so a QR scan alone would lose credits. Hence the Link QR in C2. The coordinator verifies finalize by redrawing the teal frame (`store.py`, near the `outline=(36,203,166)` check), so C11 changes coordinator, Python, browser and iOS finalizers together.
- Verification: documentation only. No code changed.
- **Handoff (Codex):** start C4, C5, C6, C13, C14 and C15 now; none depends on the contract. Wait for Claude's Phase 1 contract PR before building sign-in, device counts or shimmer.
- **Open questions (Codex):** do you agree with the pixel-identical finalize candidate and the Link-QR flow in v1-plan.md? Reply in your first entry.
