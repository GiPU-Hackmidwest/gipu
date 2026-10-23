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
| C1 | Downloadable, easy app | review: local packaging (#27) and approved manual Actions (#33); publication pending | done: documented iOS source-build fallback; review: Mac signature fix merged #45; v0.4.1 installed in Applications with verified signature; rendered release window/second-Mac installation/publication pending; TestFlight unavailable |
| C2 | QR sign-in, same credit account | done (server): live on the hosted grid (`a34aef0`); Android adapters merged; physical camera scan pending | review: Mac/iOS account/link UI implemented; browser two-client link verified; physical camera check pending |
| C3 | Private sessions | done (server): scoping live on the hosted grid | review: own-only presentation and Mac Keychain implemented; cross-account live journey passed |
| C4 | No black text on orange | — | done: Arboy's later direction supersedes the original pair; logo orange with dark ink measures 5.34:1; native Mac inspected |
| C5 | Developer options page | — | done: implemented and checked; iOS interaction check pending |
| C6 | Create images / Finish images toggles | done: Finish images verified on Android emulator | done: implemented; Mac live flow and lifecycle tests pass; iOS interaction check pending |
| C7 | Activity without sensitive info | review: corrected public summaries merged | review: generic Activity/credit labels implemented and live-checked; 83-test integrated regression pass complete |
| C8 | Device counts, no test devices | done (server): `grid` counts live; stale test devices are excluded from counts, no rows deleted | review: anonymous `state.grid` landscape implemented; missing counts remain unavailable |
| C9 | Logo | review: brand assets and Tauri/Android icons merged #23 | done: in-app marks and native iOS AppIcon; desktop bundle icon wired and native Mac package verified |
| C10 | Rename to GiPU | done: GiPU Tauri product/window and Android names merged #27; bundle IDs unchanged | done: GiPU in-app name and mark; bundle IDs/env names preserved |
| C11 | Shimmer + notification, no border | done (server): compatible coordinator deployed; reviewed Python/browser/Android frameless finishers (#29); Android notification icon pending | review: iOS runtime now uses invisible encoder after confirmed deployment; pixel/strict-settlement checks and simulator build pass; physical phone pending |
| C12 | Replicable README | done: fresh-clone README #21 | done: refreshed product README with supplied wordmark, current cloud/local pricing and app journey; reviewed Mac/iOS setup |
| C13 | Desktop sidebar | — | done: implemented and checked; iOS interaction check pending |
| C14 | Remove "About this grid" | — | done: removed on Mac/iOS |
| C15 | Contribute layout on large screens | — | done: Mac and 320 px browser layout checked |
| L1 | Weekly participation leaderboard (Arboy request) | done: additive coordinator rollout at `21a4372`, existing balances/ledger preserved | done: merged #37; hosted API, native Mac and iOS simulator board/metrics/Join/Leave verified; physical-phone checks remain V1 handoff |

Phase 0 (Sithabo): **assets delivered in `brand/`**, accepted through PR #23. This path replaces the proposed `assets/brand/`; no duplicate asset tree is needed.

## Log

### 2026-10-23 · Claude · handoff guide (`docs/handoff`)

- **Request (Sithabo):** a handoff document so other agents and engineers can continue GiPU and integrate new features.
- **Added** `docs/handoff.md`, linked from the README: current state (hosted grid, releases, repository rename), architecture map with owners, request lifecycle, invariants, coordination rules, run/test commands, integration playbooks (endpoint, schema, new work kind, image generator, planner provider, client feature, dependency, configuration), deploy/release summary, prioritized open work and gotchas. It summarizes and links the existing docs; no contract, code or status change.
- **Verification:** on a clean worktree of `08b406a`: coordinator 118 passed, worker 36 passed, frontend 83 passed, production web build passed. `cargo test`, live checks, app builds and devices were not run. Code references in the guide were checked against the source.
- **Handoff (Codex):** please review the Mac/iOS rows and the Keychain/iOS items under Open work, and correct anything Codex-owned.
- **Open questions:** none.

### 2026-10-16 · Codex · repository rename (PR #48, `docs/gipu-repo-rename`)

- Renamed the GitHub repository from `GiPU-Hackmidwest/pocketgrid` to `GiPU-Hackmidwest/gipu` and moved the main local checkout from `pocketgrid/` to `gipu/`.
- Updated `origin`, repaired all 15 linked worktrees after the checkout move and verified each resolves to the new common Git directory. Preserved the uncommitted personal Xcode signing change.
- Updated README download and clone URLs plus historical documentation links to the canonical repository address. GitHub's old URLs continue to redirect.

### 2026-10-11 · Codex · install latest Mac DMG (PR #47, `docs/mac-install-0.4.1`)

- **Installation:** Arboy requested installing the latest repository DMG. GitHub still lists v0.4.1 as the newest Mac draft; its build source `d317a38` includes the latest app changes, with only documentation commits after it. Rechecked the downloaded asset against GitHub's SHA-256 digest, then copied the verified mounted app into `/Applications/GiPU.app` with the granted filesystem permission. The installed version reports 0.4.1 and passes `codesign --verify --deep --strict`. No quarantine attributes or system security settings were changed.
- **Launch:** the older debug app had both contribution toggles off and was quit. Launched the installed app and confirmed its running executable is under `/Applications/GiPU.app`; Finder also shows that installation. Native accessibility inspection of the release window fails, so this is installation/process evidence, not a verified rendered release journey.
- **Handoff / Open questions:** the draft remains unpublished; second-Mac installation and the release app's rendered interaction check remain pending. Existing account/model data and personal Xcode signing changes were preserved. Documentation-only record checked with `git diff --check`.

### 2026-10-11 · Codex · corrected Mac draft and app launch (PR #46, `docs/mac-release-0.4.1`)

- **Build:** packaging fix merged in [PR #45](https://github.com/GiPU-Hackmidwest/gipu/pull/45), main `d317a38`. Dispatched the existing manual-only Release workflow for version `0.4.1`, Mac only, draft enabled. [Run 38140864359](https://github.com/GiPU-Hackmidwest/gipu/actions/runs/38140864359) succeeded; the Android job was skipped. No workflow triggers or signing secrets changed.
- **Artifact verification:** downloaded `GiPU-0.4.1-macos-arm64.dmg` (284,784,771 bytes); SHA-256 `e8111d3104fca8f65f8b827f72a4508a76fe68dbd8b61042b811fe0116a1558d` matches both the uploaded digest and `SHA256SUMS.txt`. `hdiutil verify` passed. The mounted app reports version 0.4.1 with 5,100 sealed resource entries, and `codesign --verify --deep --strict` passed on both the mounted app and its copied installation. Its bundled worker ran `--help`; runner app size was 660M.
- **Launch scope:** the v0.4.1 executable starts, but native automation could not inspect its rendered window. The separately repaired v0.4.0 copy rendered connected earlier. For Arboy's immediate testing, raised the existing native debug app on Create and opened the hosted browser app connected to its existing account. No image request or contribution opt-in was performed. The grid had zero devices ready for generation or finishing at the check.
- **Documentation:** marked the defective v0.4.0 Mac draft unsuitable for installation and added accurate verification/install notes to the corrected v0.4.1 draft. This is an Apple-silicon installer only; the teammate's Mac processor is still unconfirmed. No new Android, iPhone or Windows installation evidence is claimed.
- **Handoff / Open questions:** v0.4.1 remains a draft, pending second-Mac installation and publication. Developer ID signing/notarization is unavailable. CLI download did not exercise browser quarantine; strict integrity verification does not establish Gatekeeper acceptance. Personal Xcode signing remains uncommitted. Documentation-only follow-up verified with `git diff --check`.

### 2026-10-11 · Codex · Mac release install correction (`fix/mac-release-signature`)

- **Coordination:** Arboy reported the other Mac rejects v0.4.0 as damaged and asked to verify/run the releases. This authorizes a focused packaging correction if the artifact is defective. Requesting coordination here for the shared desktop build script, its checks and release documentation; keep the approved manual-only workflow and worker deduplication.
- **Cause:** the actual v0.4.0 draft DMG matches SHA-256 `68e217b6098db8978ada72375ccc9f43d854e6c73788f389eae7055ea52b87c3` and passes `hdiutil verify`, but its app has only a linker ad-hoc signature, `Info.plist=not bound`, and `Sealed Resources=none`. Strict bundle verification fails with "code has no resources but signature indicates they must be present". The worker's own signature is valid. Disk-image checks in the previous build were insufficient to catch this.
- **Fix:** after deduplicating the fresh Mac bundle's worker resources, apply a final outer ad-hoc signature and require `codesign --verify --deep --strict`. Preserve inner PyInstaller signatures, stale/no-bundle safeguards and library symlinks. Fail if signing/verification is unavailable or fails; refuse a configured or detected certificate identity instead of silently replacing it. No automatic workflow trigger added.
- **Verification:** shell syntax and seven artifact-selection checks passed using real signed tiny Mac app fixtures. Extra checks reject resource tampering, failed/missing signing, failed verification and both certificate-identity cases. A copy of the actual v0.4.0 app passed strict verification after final sealing (5,100 resource entries); its frozen worker ran `--help`. The repaired native app opened and rendered connected to its existing account; `lsof` confirmed its executable came from the repaired copy. No job was submitted and sharing was not enabled. The download was through the CLI, so this is launch evidence, not a fresh browser-quarantine approval or second-Mac result.
- **Next:** merge the build fix and request a Mac-only manual v0.4.1 draft build. Keep the defective v0.4.0 Mac draft out of installation advice. No new Android or iPhone installation evidence is claimed.
- **Handoff / Open questions:** Developer ID signing/notarization remains unavailable; determine whether this artifact has an invalid signature separately from normal Gatekeeper trust. The other Mac's processor has not been confirmed.

### 2026-10-11 · Codex · README refresh (PR #44, `docs/gipu-readme`)

- **Coordination:** Arboy explicitly asked Codex to update the README, take structural inspiration from Pitchly, include the actual GiPU wordmark and push. This authorizes the focused README changes normally owned by Claude. Requesting coordination here before editing the root and web/worker guides; no worker, server, protocol or release-workflow behavior will change.
- **Scope:** product overview and app journey first; existing light/dark wordmark; accurate cloud/local generation, dynamic prices, platform availability and source setup. Preserve runnable platform instructions and distinguish published installers from draft builds.
- **Verification:** read-only review against current worker, planner, pricing and UI code passed. Relative Markdown links, heading anchors, image sources and fenced blocks passed automated checks; `git diff --check` passed. GitHub's GFM renderer retained the themed picture and SVG references. The rendered introduction and both existing light/dark wordmarks were visually inspected in a local browser. No app behavior changed, so builds, inference and physical-device checks were not rerun.
- **Handoff / Open questions:** no contract change, dependency or deployment needed. Existing source commands retained; published installers remain separate from the v0.4.0 draft and no release workflow was triggered.

### 2026-10-11 · Codex · manual v0.4.0 build (`docs/release-0.4-handoff`)

- **Coordination:** Arboy asked to run releases from this chat. Dispatched the existing manual-only Release workflow from main `cc506cd`, version `0.4.0`, platforms `both`, draft release enabled. Run: https://github.com/GiPU-Hackmidwest/gipu/actions/runs/38137728928. No workflow triggers or signing settings changed.
- **Scope:** Mac Apple-silicon DMG and Android APK, including leaderboard, test-mode credit checkout and bundled desktop icon. No iOS or Windows installer job exists in this workflow.
- **Verification:** all four workflow jobs succeeded. The Mac packaging job verified the DMG; the final app after worker-library deduplication measured 658M on the runner. Draft assets include `GiPU-0.4.0-macos-arm64.dmg` (287,282,501 bytes), `GiPU-0.4.0-android-arm64-debug.apk` (133,789,875 bytes), and `SHA256SUMS.txt`. Downloaded checksums match GitHub's uploaded asset digests, including the checksum file itself. The large installers were not downloaded or installed locally in this pass; no fresh physical-device result is claimed. Installation/feature notes were added to the draft.
- **Handoff:** review and test installers before publication. A draft does not change the public latest release or deploy the coordinator.
- **Open questions:** none.

### 2026-10-11 · Codex · remove leftover merge marker (`fix/progress-conflict-marker`)

- Removed the stray conflict marker introduced in PR #41 while preserving both teams' progress entries. No criterion status changed.
- Verification: tracked text files checked for conflict markers; `git diff --check` passed. Documentation-only cleanup; no app rebuild or deployment needed.
- **Handoff / Open questions:** none.

### 2026-10-11 · Claude · Stripe test key verified end-to-end and enabled on hosted grid

- **Verification:** Real Stripe test-mode API integration verified end-to-end locally and on the hosted coordinator using the configured `sk_test_` key.
  - Successfully created real Stripe Checkout sessions (`cs_test_...`) and verified session status retrieval against Stripe's live test API.
  - Configured `STRIPE_SECRET_KEY` securely in `/opt/pocketgrid/deploy/.env` (mode 0600) on the hosted grid (`https://66-228-53-243.ip.linodeusercontent.com`) and recreated the coordinator container.
  - Hosted grid `/api/credits/packs` confirmed live and reporting `{"available": true, "test_mode": true}`.
  - End-to-end authenticated checkout creation and purchase status query verified on the hosted coordinator.
  - Added `STRIPE_SECRET_KEY=` configuration placeholder to `.env.example`.

### 2026-10-11 · Codex · wire the desktop app icon (`fix/mac-bundle-icon`)

- **Coordination:** Arboy requested fixing the missing Mac app icon, pushing a PR and merging it. This authorizes the focused `tauri.conf.json` change in the shared packaging configuration; the existing icon assets and Android adapters remain unchanged.
- **Cause and change:** generated GiPU icon files exist, but `bundle.icon` is missing. The current Mac package has neither `CFBundleIconFile` nor a Resources icon. Reference the existing PNG/ICNS/ICO assets so desktop bundling and the compiled default icon use the supplied brand.
- **Verification:** production frontend and native Mac Tauri debug build passed. The resulting app declares `CFBundleIconFile=icon.icns` and contains `Contents/Resources/icon.icns`; SHA-256 matches the existing source ICNS exactly. The source PNG was visually inspected as the supplied GiPU mark. Whitespace checks passed. This checks Mac packaging; Android and Windows builds were not rerun.
- **Handoff:** rebuild existing installers to include the icon; installed older packages retain their original resources.
- **Open questions:** none.

### 2026-10-11 · Codex · leaderboard merged and hosted rollout (`fix/leaderboard-rollout-record`)

- **Merged:** PR #37 is on main as `21a4372f6c10f186c5704c813a693d264af38397`, including the final logo-orange primary buttons and teammate PR #38 payments. No open PR remained at the rollout check. The primary checkout is synchronized; personal Xcode signing changes are preserved outside the PR.
- **Deployed:** the hosted coordinator now runs that exact code commit. Built while the old service served, checked zero active jobs/running tasks, stopped only the coordinator for the data snapshot and switch, and preserved `.env` and the Docker volume. Caddy remained up. Backups are `/root/backups/source-pre-leaderboard-2026-10-11.tgz` and `/root/backups/grid-pre-leaderboard-21a4372-2026-10-11.tgz`; the source archive excludes secrets. Restore inspection confirmed the original 17 accounts, their balances, ledger and jobs survived unchanged.
- **Hosted verification:** healthy coordinator and HTTPS; an isolated account check exercised all four metrics, default-private membership, strict public nickname/metric fields, immediate Leave, authenticated access and unauthenticated 401. Both verification accounts ended private and logged out. No image jobs or cloud calls were made for this check. Akamai availability in health is configuration evidence, not a new inference benchmark. Stripe remains unconfigured; no real checkout claimed.
- **Build and UI:** 118 integrated coordinator tests and 83 frontend tests passed. The merged primary checkout production frontend and Tauri debug build passed; its app measured 30.46 MiB. The final worktree native Mac app rendered Create and the hosted Leaderboard with the exact orange action fill, neutral clay score and actual goal ring. Saved sign-in loaded after Arboy allowed the existing session Keychain read; the earlier blank window was waiting on that prompt. The hosted account showed 10 points, one accepted task helped, zero credits used and zero sharing time. Goal navigation to Contribute left both toggles off. Local browser Join/Leave and 320 px checks remain fixture evidence.
- **iOS:** final source typecheck, contract/lifecycle/privacy harnesses and host Xcode Run passed on iPhone 17 Pro Max / iOS 26.2. Arboy opened the Leaderboard tab; its stale offline test grid produced the expected inline retry state without repeated modal polling errors. Normal Activity sign-out and Password sign-in connected it to the isolated local fixture. The rendered clay screen showed 63 points, two of three goals done and four public members; Available changed the account rank from fourth to third with 20 minutes. Leave immediately removed the public row (four members to three) while retaining 63 private points, then Join restored it. User tab taps bypassed the simulator's missing automation targets; exposed form/filter/membership controls worked through accessibility. These are controlled fixture metrics, not physical phone or live inference results.
- **Handoff:** current source builds can use the deployed endpoints. No release workflow was run and no new installer was published for #37; keep existing release instructions and manual-only workflow. This follow-up records evidence only, so the deployed application commit remains `21a4372`. Physical phone contribution/camera and full accessibility checks remain the V1 handoff, separate from these leaderboard checks.
- **Open questions:** none on rollout or metric/privacy behavior.

### 2026-10-11 · Codex · weekly leaderboard (PR #37, `feat/weekly-leaderboard`, review)

- **Coordination:** Arboy explicitly requested implementing and merging a leaderboard with availability, credits used and participation metrics. This authorizes the focused coordinator/protocol/test changes alongside Mac/shared React and native iOS. No Android adapter or release-workflow change.
- **Behavior:** membership off by default, separate public nickname, no private identity/device/job disclosure. Monday UTC rankings use accepted work for other accounts, net settled credits and prospective sharing time counted once across overlapping devices. Self-payments, grants, reservations and refunds cannot farm circulation points. Three personal goals navigate without enabling sharing; points do not mint credits.
- **Design correction (Arboy):** exact logo orange `#FF5A09` across client accents. Score card uses neutral clay; primary actions retain logo-orange fills with dark ink, with a ring showing actual goals completed out of three. Removed the decorative orbit/star and burnt-orange plaque. Ink focus outlines and narrow navigation labels remain readable.
- **Verified:** integrated coordinator 118 tests (including PR #38 payments); frontend 83 tests and production build; Mac Tauri debug app bundle 29.84 MiB; complete iOS SwiftUI typecheck and leaderboard/lifecycle/privacy harnesses; host Xcode simulator build/run (iPhone 17 Pro Max, iOS 26.2). Additive DB startup preserved existing accounts/credits/sessions. Real local HTTP sharing counted 6 seconds, then stayed at 6 during 4 seconds after Pause. Browser UI Join/Leave immediately restored/removed the public row while preserving private progress; availability ranking matched server totals. Desktop and 320 px layouts inspected (320 px scroll width = viewport); console warnings/errors empty. Fixture images/work were controlled protocol inputs, not live inference or physical-device measurements.
- **Native limits:** Xcode app runs paused, but individual simulator tabs have no reachable accessibility targets and coordinate operations fail `noWindowsAvailable`; native leaderboard interactions remain pending. Worktree Mac package builds but its launched window was blank while the existing main package renders normally; verification from the synced primary checkout is pending. No physical phone check claimed.
- **Handoff:** deploy coordinator first (two additive tables; no balance changes), then updated clients. Existing coordinator shows an unavailable message until updated. Preserve volume and `.env`, back up before switching, never `down -v`. Root SSH access now verified with the existing identity; zero active hosted jobs/tasks observed before rollout. Installer workflow remains manual; no Actions run requested here.
- **Integration:** resolved overlap with teammate PR #38 (test-mode credit purchases), preserving Account payments, purchase routes/table and weekly metrics. Purchase grants do not count as credits used; only settled task payments/fees do.
- **Open questions:** none on the metric/privacy contract. Full native UI and hosted rollout evidence will be appended after merge.

### 2026-10-11 · Claude · buy credits with a card (Stripe test mode, branch `feat/buy-credits`)

- **Why:** FinTech challenge. Sithabo asked for a money → credits pipeline only; credits must never convert back to money.
- **Coordinator:**
  - `payments.py` talks to Stripe's REST API with `httpx` (no new dependency). Fixed packs: 50/$5, 120/$10, 300/$20. Accepts `sk_test_` keys only and refuses live keys. Verifies webhook signatures (HMAC-SHA256, 5-minute tolerance).
  - New `purchases` table. `settle_purchase` grants credits once, and only when Stripe reports paid, not livemode, and the same user/amount/currency the coordinator recorded. It writes a `purchase` ledger entry and a `credits_purchased` event.
  - Routes: GET `/api/credits/packs`, POST `/api/credits/checkout`, GET `/api/credits/checkout/{id}` (own only), GET `/api/credits/return` (Stripe redirect page), POST `/api/stripe/webhook`. `/state.payments`.
  - There is no payout, withdrawal or card-refund route, and a test asserts that.
- **Clients:** a new Buy credits card on the Account page (`BuyCredits.tsx`). It opens Checkout in the system browser via `tauri-plugin-opener` (new dependency, scoped to `https://checkout.stripe.com/*`), or in a new tab on the web, then polls the coordinator until Stripe confirms. iPhone is not included: Apple's rules disallow outside payment for digital credits in iOS apps.
- **Docs:** protocol, README, `deploy/.env.example` and compose (empty Stripe variable names only).
- **Verification:**
  - Coordinator: 96 passed, including 6 new tests in `tests/test_payments.py` against a fake Stripe API: the paid flow, credits granted exactly once, unpaid/wrong amount/currency/user/livemode never credited, other accounts get 404, fixed packs, signed and replayed webhooks, refusal of live keys, and no cash-out route.
  - Web: 83 tests, `tsc -b` and build passed. Rust: `cargo check` passed with the opener plugin.
  - **Not verified:** a real Stripe test-mode checkout (no `sk_test_` key exists yet, locally or on the server), and opening Checkout from the Mac/Android apps.

### 2026-10-11 · Claude · hosted deploy of `aace226` and releases v0.2.0 / v0.3.0

- **Hosted coordinator** now runs `aace226` (main: dynamic pricing #34 plus cloud generation #35).
  - Backed up first to `/root/backups/grid-pre-aace226-2026-10-11-1038.tgz`. The image was built while the old coordinator served; the coordinator was healthy with no log errors.
  - `/api/health` reports `generation: cloud / akamai/hackathon-image / available`.
  - Before switching, a throwaway container made one real Akamai call with the server's key: a 384×384 PNG in 1.8 s.
- **Live check:** a throwaway account (created server-side, so the join code stayed on the server) connected a current worker in `auto` mode, which detected cloud mode. A 384 px request completed in 4 s:
  - Akamai generation took 1.9 s; the image was finished and verified;
  - both stages were labelled `cloud akamai/hackathon-image`;
  - the price locked at 7 (one laptop ready), with receipt `10 = 8 + 1 + 1`.

  Afterwards the test device was paused, the session logged out (then 401), and the local credentials deleted.
- **GitHub workflow (manual):**
  - First Android-only run `38126245236` passed in about 8 min.
  - **v0.2.0** run `38127512308` (both platforms plus draft) passed: Mac job 4 min, Android 8 min. Published with an iPhone note.
  - **v0.3.0** run `38132736630` at `aace226` passed and was published: https://github.com/GiPU-Hackmidwest/gipu/releases/tag/v0.3.0
- **v0.3.0 checks:**
  - Downloaded files match `SHA256SUMS.txt`, and `hdiutil verify` reports the DMG VALID.
  - The DMG app is version 0.3.0, and its bundled worker offers `--generator auto|cloud|local`.
  - The APK is versionCode 3000 / 0.3.0, labelled GiPU.
  - The APK is **debug-signed** (no Android signing secrets yet).
- **Not verified:** the v0.3.0 Mac app connecting in cloud mode through its UI; physical phones; a properly signed Android release.
- **Seen on Sithabo's Mac:** launching downloaded GiPU builds shows a keychain prompt for `dev.pocketgrid.desktop.session`, because each unsigned build has a new code signature and can't silently read the sign-in saved by an earlier build. Fix options: Developer ID signing, or handling a denied keychain read as signed out. The Mac session code was Codex's.

### 2026-10-11 · Claude · cloud image generation for the demo (branch `feat/cloud-image-generation`)

- **Request (Sithabo):** for demoing, generate images with a large hosted model through the same pipeline instead of a local model, keeping the local path available. FLUX.2 [klein] was investigated first and then dropped at Sithabo's request. Findings:
  - the smallest complete build is the MLX 4-bit at 4.6 GB;
  - the SDNQ build needs the GPL-3.0 `sdnq` package;
  - `mflux` requires `transformers` 5.x.
- **Coordinator:**
  - `cloud_images.py` calls the Akamai workshop image API (`/v1/images/generations`, model `hackathon-image`). It requests 512 px, resizes to the task size, waits on `x-ratelimit-reset` within a bounded budget, and runs one request at a time (team quota is 6/min).
  - New `POST /api/tasks/{id}/cloud-image` serves only a running generation task under its live lease. The key stays on the coordinator.
  - The coordinator records cloud outputs in `cloud_outputs`, and `images[]` carry `generated_in`/`model`, so a finished image inherits the label.
  - `/health` and `/state` include `generation`. The mode is cloud when `AKAMAI_API_KEY` is set (or `POCKETGRID_IMAGE_GENERATOR=cloud`), otherwise local Tiny-SD. Compose passes the setting.
- **Worker:** new `CloudRenderer`. `--generator auto|cloud|local`, where `auto` follows `/health`. Claiming, leases, progress, upload and settlement are unchanged, and there's no model load in cloud mode. The local Tiny-SD path stays selectable rather than commented out, so tests and the fallback keep working.
- **Mac app:** `connect_worker` takes optional `cloud_generation` and skips the model-download requirement. `parse_ready` accepts backend `cloud`. The panel passes the grid's mode and doesn't ask for the 1 GB download in cloud mode.
- **Labels:** web/Mac captions and iOS captions add "Cloud-generated".
- **Verification:**
  - Coordinator: 90 passed (7 new in `tests/test_cloud_images.py`). Worker: 36 passed (2 new). Web: 83 and build. Rust: 16 passed, 1 ignored (new `cloud` ready-line assertion). iOS: `swiftc -typecheck` found 0 errors.
  - Live local pipeline against a stand-in Akamai endpoint, with `POCKETGRID_ACCEPT_LEGACY_FRAME=0`:
    - an `auto` worker detected cloud mode without loading a model;
    - a 2-image 384 px request was served at 512 and resized to 384;
    - the worker earned 7 per image (one-laptop dynamic price) and the images were finished and verified;
    - all four images were labelled cloud, and the receipt was `20 = 16 + 1 + 3`.
  - Not yet verified: the real Akamai call (only the hosted server holds the key; checked after deploy), and the Mac app shell in cloud mode.

### 2026-10-11 · Claude · dynamic pricing (branch `feat/dynamic-pricing`)

- **Request (Sithabo):** more available computers make images slightly cheaper; fewer make them slightly more expensive.
- **Coordinator** (`store.py`):
  - `price_for(ready_to_create)` sets generation at 7 credits when 0–1 devices are ready, 6 when 2–3 are, and 5 when 4 or more are. Finishing and the fee stay 1, so one image costs 9, 8 or 7.
  - `reserve_job` quotes from live `grid` counts, rejects a budget below the quote (422 "current quote of N"), and locks the prices into `plan.pricing`. `new_task` and the completion fee use the locked prices, so finishing tasks created later and retries cannot exceed the reservation. Jobs without `plan.pricing` (created before this change) keep 6/1/1.
  - `/state.pricing` now shows the current price. `public_plan` exposes the locked `pricing` to the owner. The earned-credits event allowlist covers 1–9 credits.
  - The Strands `quote_job` tool reports the job's locked quote.
- **Clients:**
  - Web: the estimate already used `state.pricing`, and the budget now follows the live minimum, so Create isn't left disabled when the price rises.
  - iOS (Arboy is out of Codex quota; Sithabo asked Claude to finish features): `Snapshot.pricing` is optional, with a 6/1/1 fallback for older coordinators. The estimate, stepper floor and Create guard use it, and the budget follows the minimum.
- **Docs:** `docs/protocol.md` describes the pricing rule and the locking.
- **Verification:**
  - Coordinator: 83 passed, including 6 new tests in `tests/test_pricing.py` (curve, live snapshot price, budget below quote, price locked through a supply drop with receipt `10 = 6 + 1 + 3`, legacy jobs, owner view).
  - Three fixed-price tests now expect the one-laptop price of 7.
  - Web: 83 tests, `tsc -b` and build passed.
  - iOS: `swiftc -typecheck` against the iOS 17 simulator SDK found 0 errors. No simulator run, because this Mac has no iOS runtime installed.
- **Note:** the coordinator must be redeployed for live pricing. Older iOS builds still show the fixed 8-credit estimate and can be refused when the price is 9; the 422 message states the needed amount.

### 2026-10-11 · Codex · manual workflow integration (PR #33)

- Arboy explicitly approved restoring the workflow and requested this merge. This supersedes the earlier local-only restriction. Preserve the manual Android/Mac build and optional draft-release path.
- Resolved the progress-log conflict by retaining both teams’ entries and the latest UI verification. No app, worker, signing identity or contribution behavior changes.
- Review also fixed partial-platform draft updates: checksums include installers already attached to the draft. Published releases remain untouched.
- Verification: YAML parsed with only `workflow_dispatch`; every embedded shell step passed `bash -n`; whitespace checks passed. Handoff: enable Release after merge. A hosted build has not been dispatched by this review; publication remains manual.

### 2026-10-11 · Claude · manual-only release workflow (branch `ci/manual-release-workflow`)

- **Decision (Sithabo, 2026-10-11):** restore a GitHub build workflow, but manual-only. Arboy removed the automatic version for cost. This one has **no push, tag or PR triggers**; it runs only from Actions → Release → Run workflow. `AGENTS.md` (release cost constraint), `docs/v1-plan.md` and `docs/releasing.md` now record this. Adding automatic triggers or removing the workflow needs both Sithabo and Arboy.
- **`.github/workflows/release.yml`.** Inputs:
  - `version`;
  - `platforms`: `android` (default, Linux only), `macos` or `both`;
  - `draft_release`: creates a draft `v<version>` at the run's commit, or adds files to an existing draft. It refuses to touch a published release.

  The build steps are the same as the earlier verified ones (the DMG step now also runs `hdiutil verify`). The decoded signing key is deleted after the build. Without the signing secrets it builds a debug-signed APK and warns.
- **Repository variable** `GIPU_DEFAULT_GRID` is set to `https://66-228-53-243.ip.linodeusercontent.com`.
- **Verification:**
  - The YAML parses with `workflow_dispatch` as the only trigger.
  - The draft-release script, run locally against a stubbed `gh`, creates a draft when none exists, uploads with `--clobber` to an existing draft, and exits 1 without calling `gh` for a published release. An Android-only run checksums just the APK.
  - The build steps match the version locally verified earlier (DMG 266 MB VALID; signed APK verified).
  - **Not run on GitHub.** The workflow is still `disabled_manually` from the earlier removal and must be re-enabled once after merge: `gh workflow enable Release`.
- **Handoff (Codex/Arboy):** please don't remove this workflow; the guard rule is in AGENTS.md. Signing secrets stay optional; the commands in `docs/releasing.md` set them from the local key without printing anything.

### 2026-10-11 · Codex · local release handoff (`docs/local-release-handoff`)

- PRs #27–#31 are merged through main `3e1c6e9`: local release packaging and GiPU names, Docker brand assets, frameless finishers, native iOS cutover, and account-link/revoked-session recovery. The primary checkout is synchronized and its personal signing diff is unchanged. No open PR remains at this check. Builds and packaging remain local; publication is a separate manual step.
- **Actions cleanup:** the release workflow file is deleted and its repository state is `disabled_manually`. Three old artifacts (about **547 MB**) were downloaded, ZIP-verified and SHA-256 recorded, then deleted remotely; their local copies remain preserved. The remote artifact count is now zero. Two obsolete, reproducible npm CI caches (57.6 MB) were also deleted; the remote cache count is zero. No current bill or charge has been verified.
- **Verification:** **83 frontend**, **77 coordinator** and **34 worker** tests passed. The iOS simulator app build and strict fixture settlement passed: the native invisible encoder retained all RGB pixels, settled with legacy acceptance disabled, and preserved duplicate-completion/Pause behavior. These fixtures are not physical-phone or live diffusion evidence.
- A fresh local PyInstaller worker and bundled Mac debug app built successfully before #31. The final integrated `3e1c6e9` native Mac debug bundle, including #31, also passed and measured **671 MiB**; all **24 worker symlinks** match the fresh frozen source. This documentation-only handoff adds no new build claim beyond those results.
- **Remaining:** physical camera QR decoding and phone finishing, release publication, and comprehensive accessibility/device validation. Keep coordinator legacy acceptance for older installed apps. Local installers/build evidence do not imply a published or notarized release.

### 2026-10-11 · Codex · account recovery runtime check (`fix/account-link-handoff`)

- Final integrated frontend tests: 83 passed; TypeScript/production build passed. In a real browser against an isolated local coordinator, a new test account stored the session label `Browser`. Account showed the loopback warning and disabled QR creation until a phone-reachable grid address is supplied. Revoking only that test session caused automatic return to sign-in; reload stayed signed out. This check did not enable contribution or create an image job; worker stop/clear ordering and retry behavior are covered by lifecycle tests.
- Scope remains minimal: usable QR address, visible/focused incoming-link confirmation, device session labels and safe revoked-session recovery. No hosted state, signing or CI change.

### 2026-10-11 · Codex · account link handoff polish (`fix/account-link-handoff`)

- **Coordination:** Arboy requested the three UX corrections observed during PR #27 review: phone-unreachable loopback QR addresses, an off-screen incoming-link prompt, and indistinguishable session labels. Root explicitly authorized a backward-compatible optional `clientName` argument in Claude-owned `identity.ts` plus its regression test; the existing `/sessions` contract already accepts `client_name`.
- **Implemented:** loopback QR links require a manually supplied Wi-Fi/hosted address for the same grid; incoming signed-in links scroll into view and receive focus; new session labels identify Mac, Android or Browser. No guessed addresses or protocol/dependency changes.
- Root additionally authorized revoked `/state` recovery: only a current live `ApiError(401)` initiates awaited worker shutdown and secure sign-out once. Failed cleanup retains the mounted controller and credentials with a focused retry action. Ordinary errors and stale responses never clear credentials.
- **Verification:** 83/83 frontend tests passed, including loopback address, platform label, stale/duplicate 401, and secure-delete retry regressions; TypeScript and Vite production build passed. Reused identical-lockfile dependencies locally. No CI runs, hosted mutations or new dependency downloads. Native/UI runtime recheck remains with root.

### 2026-10-11 · Codex · iOS frameless runtime (`feat/ios-invisible-finalize`)

- **Coordination/gate:** reviewed PR #28's recorded hosted deployment of `a34aef0` (compatible coordinator on main `7963aca` plus Docker build fix), and PR #29's explicit iOS handoff. This satisfies the coordinator-first rollout gate; neither `grid` nor `verified` is treated as capability negotiation.
- `GridModel` now calls the previously staged `ImageProcessor.finalizeInvisible`. Progress says "Finishing image" and telemetry identifies `Swift/ImageIO`. Existing explicit opt-in, cancellation, background/Pause handling, lease fencing and settlement requests are unchanged. The native coordinator-smoke harness follows the runtime encoder. The legacy frame helper remains for regression checks; the coordinator's legacy acceptance remains enabled for installed older clients.
- **Actual verification:** rebuilt/ran `InvisiblePixelParity.swift` with `check_invisible_pixels.py`: all 65,536 decoded RGB pixels match for each RGB, alpha-bearing RGBA and indexed PNG fixture; pixel-limit rejection passed. Rebuilt/ran `LifecycleRace.swift` and `IdentityPrivacy.swift`: passed. Compiled the updated `CoordinatorSmoke.swift` harness.
- **Strict coordinator fixture integration:** with `POCKETGRID_ACCEPT_LEGACY_FRAME=0`, submitted those native Swift encoder outputs to the real local `Store.complete` path using a temporary database. All three modes settled, exposed `verified: true`, charged 8/refunded 2, accepted duplicate completion idempotently, and a paused native device received no work. Sources were deterministic fixtures, not a live diffusion run or iPhone execution.
- **Build:** the isolated branch's native app, including assets, built successfully in host Xcode for iPhone 17 Pro Max simulator at 03:36 local time. No project, bundle ID or signing settings changed. No physical-device build/install, hosted native job, or physical camera test is claimed.
- **Handoff:** merge with PRs #28/#29; keep coordinator legacy acceptance until older installed clients migrate. Physical-phone QR/finishing and release validation remain open.

### 2026-10-11 · Codex · local release packaging review (PR #27)

- **Coordination:** Arboy requested review/merge and removal of unnecessary cost. This authorizes the narrow release/script/docs changes in Claude-owned files. GitHub-hosted Actions are not required for C1 and are removed, including automatic tag/PR runs and repository-secret setup. Builds stay local; publishing is a separate manual step.
- Keep GiPU product/Android names, stable bundle IDs, optional local Android signing and installer packaging. The README must not claim downloads already exist before a release is published.
- Validation: seven desktop wrapper artifact-selection checks, shell syntax and whitespace checks passed. An isolated local-signing fixture verified owner-only files, escaped paths, no password output/argv and overwrite refusal. Existing PR evidence covers real Mac DMG and signed Android APK builds. No release tag, key upload, hosted deployment or publication is performed by this review. The GitHub Release workflow is disabled at repository level as well as removed from this branch.

### 2026-10-11 · Claude · QR sign-in end-to-end check (local, `ci/v1-releases` at `53698fa`, includes #25)

- **Setup:** a local coordinator on an empty database; the shared web UI in a browser stood in for the Mac side; an Android debug APK built from this branch ran on the `Medium_Phone` emulator; a laptop worker ran under a separate account.
- **Passed:**
  - **Invite.** Pasting a `gipu://join` link showed "Join this grid · Create a new account". Continue created `Guest YR52` with 100 credits.
  - **Link QR.** Account → Show QR displayed a QR code, a typeable code and "Expires in 120s · single use". Rendered to PNG and decoded with the browser's `BarcodeDetector`, the QR reads `gipu://link?grid=http%3A%2F%2F127.0.0.1%3A8787&code=…`, so the code is valid and scannable as an image.
  - **Typed code on Android (path A).** A fresh code plus `http://10.0.2.2:8787` signed the phone into `Guest YR52` with the same 100 credits. Reusing that code returned 400.
  - **Shared credits.** The phone created an image; the worker generated (2.2 s) and finished it. The web side, which created nothing, then showed the same completed job, 92 available and an 8-credit charge. It listed 0 own devices while `grid` showed 1 connected, 1 ready to create and 1 ready to finish, so the other account's laptop stayed anonymous.
  - **Deep link on Android (path B).** A warm `gipu://link` showed "Use this link? Signs out of this account on this device", then "Link your account · Use your existing credits". Continue returned the phone to `Guest YR52` with 92. The session list shows the old phone session revoked and exactly two active sessions.
- **Findings:**
  1. **The Link QR copies the signed-in address.** A desktop signed in through `127.0.0.1`/`localhost` shows a QR code that no other device can use. Hosted `https://` grids are unaffected. Suggestion (Codex, `AccountPage`): warn when the grid address is loopback, or offer the LAN address.
  2. **The incoming-link prompt is easy to miss.** It renders mid-page, so on a scrolled screen a scan looks like it did nothing. Suggestion (Codex): bring it into view or show it as a dialog.
  3. **Sessions can't be told apart.** The browser sign-in sends no `client_name` (it lists as blank) and Android sends "GiPU". Suggestion: send a device label such as Android/Mac/Browser. The UI call site is Codex's; `identity.ts` already accepts the parameter.
- **Not verified:** reading a QR with a real or emulated camera (the scanner opens; decoding the printed code was only checked from the image), the native Mac shell with Keychain storage (the web UI was used for that side), the hosted coordinator (still pre-V1, so these endpoints are missing there) and physical phones.

### 2026-10-11 · Claude · release builds (branch `ci/v1-releases`)

- **`.github/workflows/release.yml`.** A `v1.2.3` tag builds `GiPU-<version>-macos-arm64.dmg` (bundled worker) and `GiPU-<version>-android-arm64.apk`, then creates a **draft** release with `SHA256SUMS.txt` and generated notes. Manual runs and pull requests that change the workflow build both and keep them as artifacts; they publish nothing. Only official `actions/*` are used; `uv` is pinned to `0.11.*`. The optional repository variable `GIPU_DEFAULT_GRID` sets `VITE_DEFAULT_COORDINATOR`.
- **Android signing.** `app/build.gradle.kts` signs release builds only when the gitignored `gen/android/keystore.properties` exists; CI writes it from the `ANDROID_KEYSTORE_*` / `ANDROID_KEY_*` secrets. New `scripts/android-release-key.sh` creates the key once in `~/.gipu-release/` (mode 600) and prints the `gh secret set` commands; it never prints a secret and refuses to overwrite a key. Without secrets the workflow publishes a debug-signed `...-debug.apk` with a warning.
- **Rename (C10).** `productName` and the window title are now GiPU, so the app is `GiPU.app`. The Android label is GiPU. The build scripts use the new bundle path. Bundle IDs are unchanged, so app data, the downloaded model and installed Android data carry over.
- **Docs.** New `docs/releasing.md` covers tagging, secrets, the default grid and what installers see. The README gains a Download section.
- **Verification** (local, in an isolated worktree because this checkout is shared):
  - `build-desktop-app.sh --config '{"version":"0.2.0"}'` passed in 4 min 52 s, producing `GiPU.app` (651 MB).
  - The workflow's DMG step passed: 266 MB, and `hdiutil verify` reports VALID. Mounted, the DMG holds GiPU 0.2.0 with identifier `dev.pocketgrid.desktop`, an ad-hoc signature, all 24 worker symlinks preserved, and a bundled worker that runs. The app launched without crashing.
  - A signed release APK, built with a throwaway key (deleted after), passed in 2 min 20 s. `apksigner` verifies the v2 signature; `aapt2` shows `versionName 0.2.0`, `versionCode 2000` and label GiPU.
  - The release APK installed on the emulator, launched with no plugin or class errors after R8, and accepted a `gipu://join` link.
  - **Not verified:** the workflow on GitHub runners (the pull request triggers it), notarization (no Apple Developer account), and a physical Android install.
- **Needs Sithabo:**
  1. Run `./scripts/android-release-key.sh` and the two `gh secret set` commands it prints, and back up `~/.gipu-release/`.
  2. Optionally set `GIPU_DEFAULT_GRID` once the hosted grid runs the V1 server.
  3. Tag `v0.2.0` when ready.
- **Codex note:** the Mac window and app are now named GiPU. `worker.rs` still says "PocketGrid app data" in one error message (Codex-owned).

### 2026-10-11 · Codex · finisher review (PR #29)

- Reviewed exact-pixel output and unchanged cancellation, privacy and settlement paths. Fresh checks pass: 34 worker, 77 coordinator and 78 frontend tests, TypeScript and production frontend build. No hosted mutation or physical-device test was performed. Compatible deployment evidence is recorded in PR #28 below.
- Merge resolves progress-log overlap while preserving both workstreams; the coordinator continues accepting older clients. iOS cutover is a separate Codex change.

### 2026-10-11 · Claude · border-free finishing (branch `feat/v1-invisible-finish`)

- **Python finisher** (`workers/python/worker.py`): `finalize_image` now decodes the PNG and re-encodes the same RGB pixels. Nothing is drawn; a non-PNG source is refused. `FRAME`/`ImageDraw` are gone.
- **Browser and Android finisher** (`apps/web/src/browserWorker.ts`): the teal border drawing is removed. The image is decoded with `colorSpaceConversion: 'none'`, so the canvas copy stays pixel-identical. The telemetry stage now reads "Finishing image".
- **Coordinator:** unchanged. It still accepts the legacy frame by default, so installed older apps keep settling.
- **Docs:** the worker README, the web README canvas note, project context and team development now describe identical-pixel finishing.
- **Verification:**
  - Worker tests: 34 passed; the frame test was replaced by an identical-pixel test, plus a non-PNG refusal test. Coordinator: 77 passed. Web: 78 passed, plus `tsc -b` and build.
  - Live run on a local coordinator started with **`POCKETGRID_ACCEPT_LEGACY_FRAME=0`**, so only frameless output could settle. A Python laptop generated each image.
    - The new Python `--finalize-only` worker finished job 1.
    - The browser's Finish images switch finished job 2.
    - The Android debug APK built from this branch finished job 3 on the emulator, after a cold-start invite link and the Finish images switch.
    - Every job completed with receipt 10 = 7 + 1 + 2. The finished image downloaded as identical to the generated one, and corner pixels were image colours, not RGB(36,203,166).
  - Not verified: a physical Android phone, and iOS (Codex-owned, below).
- **C6:** the shared Finish images switch works on Android. Off shows "Paused"; on shows "Sharing" and an end time; the phone then finished real work.
- **Handoff (Codex):**
  1. The hosted coordinator (`a34aef0`) accepts frameless output, so the staged invisible iOS encoder can become the runtime finisher.
  2. Leave `POCKETGRID_ACCEPT_LEGACY_FRAME` on until every installed iOS/Android build is frameless; then Claude removes the legacy path.
  3. **Stale session:** a client whose token is no longer valid (revoked from another device, or the server's data reset) stays on the dashboard showing "Coordinator: Invalid or missing credential" and "Updates interrupted" instead of returning to sign-in. Suggest treating 401 from `/state` as signed out, after stopping any local worker.

### 2026-10-11 · Codex · Docker brand build review (PR #28)

- **Coordination:** user-requested review covers the narrow Docker asset fix and this status correction. No deployment or server mutation was performed in this review.
- The web stage now preserves `apps/web` → `brand/` relative imports, and the final stage copies the resulting dist directory. `.dockerignore` includes the brand assets. A scratch copy of tracked web/brand files in the same relative layout passed TypeScript and production Vite build (`--configLoader runner`, existing dependencies); Git whitespace checks passed. The local Docker daemon was unavailable to the sandbox, so this is not a new container-build claim.
- Confirmed in Git that `a34aef0` is `7963aca` plus only the Dockerfile fix. The hosted observations below are Claude's deployment-time evidence; this reviewer did not repeat signed-in hosted checks or independently verify current host revision. Compatible deployment unblocks a separately reviewed finisher cutover; it does not mean those clients have switched or that a physical-phone journey passed.

### 2026-10-11 · Claude · hosted coordinator redeployed (`a34aef0`, branch `fix/docker-brand-assets`)

- **Blocker found on main.** `docker compose build` failed: `Brand.tsx` imports `../../../brand/gipu-wordmark.svg`, but the Dockerfile's web stage copied only `apps/web`. Fix: the web stage now mirrors the repository layout (`/src/apps/web` plus `/src/brand`). This affects anyone building the server image from main, not only the hosted grid.
- **Deployed** `a34aef0`, which is main `7963aca` plus that Dockerfile fix, to the Linode host (`DEPLOYED_COMMIT` updated).
  - Built while the old coordinator kept serving.
  - Smoke-tested the new image in a throwaway container on server-local port 18787 with temporary data: health, web root, anonymous join, `grid`, link code.
  - Then stopped the coordinator, backed up the database and images together to `/root/backups/grid-pre-a34aef0-2026-10-11-0821.tgz` (1.5 MB), and started the new image. Downtime was about a minute.
- **Verification (hosted):**
  - The coordinator became healthy with no errors in its logs; planner mode is still `akamai`, available.
  - `POST /api/sessions/link-codes` without auth returns 401 (it was 405 on the old code). HTTP redirects to HTTPS, port 8787 is unreachable from outside, and the site serves the new GiPU sign-in.
  - Migration: 15 users, 15 active sessions, 0 tokens left on `users`, so existing sign-ins carried over. All 11 jobs and 20 device rows were kept, and 3 devices were online again after the restart.
  - Not done: a signed-in hosted journey, because the join code was not read into this session, and no physical phone was used.
- **Now unblocked:**
  - Frameless finishers (Python, browser, iOS), since the hosted coordinator accepts both formats.
  - Setting the `GIPU_DEFAULT_GRID` release variable to `https://66-228-53-243.ip.linodeusercontent.com`.
  - Real-phone QR checks against the hosted grid.

### 2026-10-11 · Codex · completed integration (`docs/v1-integration-results`)

- PRs #18–#25 are merged into main, through `f59d99f`; the local main checkout is synchronized. Personal Xcode signing changes were preserved exactly and remain uncommitted. No open PR remained at the final integration check.
- Final combined validation: 78 frontend tests, 16 Rust tests (one existing ignored fixture), frontend production build and bundled native Mac build passed. The final iOS catalog also built successfully in host Xcode for iPhone 17 Pro Max simulator at 02:56 local time. No physical-phone test is claimed.
- **Handoff:** Claude owns hosted coordinator deployment, coordinated runtime finalizer rollout, Tauri release/product-name packaging and final Android device validation. Codex's iOS invisible encoder is staged and pixel-tested; keep its legacy runtime until compatible deployment is confirmed. Arboy/Sitha still need real phone QR decoding and phone finishing checks, followed by release/signing validation. The overall V1 is not marked complete.

### 2026-10-11 · Codex · brand and Android account integration (`feat/v1-account-ui`)

- PR #23 merged as `80d6a2d` and #24 as `f9a32a7`; integration commit `e5e458d` preserves the account UI and both platform storage implementations. No account-UI PR number is assigned in this entry.
- **Brand:** `brand/` is the accepted asset source. Tauri/Android icons came from #23; Mac/web and iOS in-app marks plus the native SwiftUI AppIcon catalog are implemented. Bundle identifiers and environment names stay unchanged. The brand dot uses `#FF5A09` as a static mark, while white action labels retain `#C34400`; the logo does not indicate active sharing. Tauri productName, Android/release naming and remaining distribution work stay with Claude.
- **Android:** shared sign-in now selects the Keystore-backed session adapter only on Android. Camera scans honor AbortSignal on cancellation/teardown/backgrounding. Incoming links require confirmation before account changes; worker cleanup and credential ordering remain intact. The reviewed adapter correction rejects failed durable deletion, removes stale plaintext when secure storage wins, and tears down listeners if the cold-link read fails. Dependencies remain Android-only deep-link 2.6.1 and barcode-scanner 2.5.2, alongside the previously coordinated QR/Keychain dependencies.
- **Verification:** the pre-Android account baseline passed **66 frontend tests**, including the foreign-earnings privacy regression. The separate #24 review passed **61 frontend tests**, production frontend build and **15 Rust tests / one ignored**. **Combined integration:** 78 frontend tests, 16 Rust tests (one ignored) and the production frontend/native Mac bundled build passed. The final iOS asset catalog built successfully through Xcode on the iPhone 17 Pro Max simulator destination at 02:56 local time. Terminal builds remain limited by simulator-service sandbox access; the final physical-device build is not claimed. Earlier iOS source builds/harnesses predate the new catalog.
- **Remaining gates:** final integrated checks, confirmed compatible hosted coordinator deployment, physical QR decoding and phone finishing, and release artifacts/distribution. Finishers remain legacy-compatible until deployment is confirmed. No full V1 sign-off or physical-device proof is implied.

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

### 2026-10-11 · Codex · account UI review (PR #25 · `feat/v1-account-ui`)

- PRs #18–#22 are merged, including the #19 contract, #20 privacy correction (`ed8cbec`), #21 README (`e8db6fd`) and #22 controls (`eb365a9`). This work implements Mac/iOS sign-in and account linking, private presentation, anonymous grid counts and verification shimmer against that baseline. C2/C3/C7/C8 are in review, not complete; C11 remains partial until finisher rollout.
- **Shared-file coordination/dependencies:** `qrcode.react` **4.2.0** renders QR SVGs locally; macOS-only `security-framework` **3.7** stores sessions in Keychain through the existing `SessionStore` boundary. Package/Cargo locks and `lib.rs` registration change together. `ApiError.status` supports safe handling of revoked sessions. Shared origin parsing rejects credentials and malformed URLs. These changes are coordinated across `api.ts`, `identity.ts`, types and platform storage; Android adapters remain separate. QR contents never go to an external rendering service.
- **Behavior:** Link QR/code retains the same account and balance; New account creates a separate account. Mac migrates the earlier locally stored session to Keychain. Leaving stops owned contribution before credentials are discarded. Jobs/devices are filtered to the current account; Activity uses generic labels. `state.grid` supplies anonymous counts, with missing/invalid counts shown as unavailable. Only explicit `verified: false` shimmers, `true` confirms verification; a missing field does not imply verification.
- **Verification:** **66 frontend tests** passed in the pre-Android account baseline, including five storage and ten identity tests. The native Mac build passed; Rust passed **16**, with one ignored fixture. In actual browsers on two origins, a new account generated a link code and the second client redeemed it into the same account with **100** credits. The native Mac app migrated an existing V1 session into Keychain with its **99**-credit balance. A real teapot request was generated by that Mac account and finished by the linked browser account. Both linked clients showed the same image, **93 available / 0 reserved / 1 earned** (8-credit cost plus 1 credit earned finishing). The Mac account showed **105 available / 13 earned** after earning 6 for generation, and retained only its own earlier cat image; the other account’s teapot was absent. Activity labels stayed generic without Mac device names. Native relaunch retained the 105-credit account, Show QR rendered, and Sign out returned to sign-in. Captures: `outputs/v1-mac-account.png` and `outputs/v1-linked-account-result.png`. Shimmer CSS/selection behavior is tested; its transient animation was not captured. The foreign-earnings presentation regression passed in the 66-test account baseline; combined Android integration checks are recorded separately above.
- **iOS:** arm64/x86_64 simulator and unsigned arm64 device builds passed. IdentityPrivacy, JobStatus, LifecycleRace and all **17** NotificationOwnership checks passed. The staged invisible encoder preserved all **65,536** RGB pixels across RGB, RGBA and indexed PNG inputs and rejected oversized input; production legacy frame/interior parity also passed. `GridModel` still uses the legacy finalizer. Rendered V1 UI testing is blocked by CoreSimulatorService sandbox access; no physical-phone or camera/scanner result is claimed.
- **Handoff:** preserve the new Mac commands, storage boundary and QR dependency when adding Android adapters. iOS remains native SwiftUI with Keychain and an on-demand scanner/manual fallback. Confirm compatible hosted coordinator deployment before switching any finalizer; `grid`/`verified` fields are not version negotiation. Brand assets have since landed via #23; release distribution and physical-device verification remain outstanding. Earlier log entries retain their original historical verification scope.

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

- **Contract accepted:** [PR #19](https://github.com/GiPU-Hackmidwest/gipu/pull/19) passed 42 frontend tests and the production build, and merged as `0e022b4`. This branch now includes it. Link QR preserves the existing credit account; Invite QR creates a new one. The ten-character typeable code is enough; a separate numeric code is unnecessary. Generic contributor activity about the user's own job is useful, provided it cannot expose another user's device or asset identifiers.
- **Contract answers:** times use Unix seconds; link codes last 120 seconds and sessions end on revocation/logout rather than age. Connected counts online devices; ready counts add enabled, unexpired sharing and capability. The implementation uses the 15-second lease window for online status and does not promise idle/model-ready or size-compatible capacity. Image `stage` stays `image_generate` / `image_finalize`; `verified` is authoritative, including accepted legacy framed output. There is no wire-version negotiation: deploy the accepting coordinator before frameless finishers. Missing `grid`/`verified` means older-coordinator data, not zero capacity or proof of verification.
- **PR #20 merge blocker:** reviewed server head `fb62d298`. In `services/coordinator/store.py:721–749`, privacy filtering replaces selected names but leaves short names and foreign device IDs in planner explanations. `public_events` at lines 788–798 also leaves IDs in `routing_updated` messages without a `device_id`. Reproduced against that code in an isolated scratch database: another account's device named `Pi`; create an owner job with `plan.explanation = "Selected Pi with device ID <foreign-id>"`, then add a `routing_updated` event containing that ID. Both `Pi` and the ID survived the owner job view, and the event ID survived its snapshot. This violates the merged no-other-device-name/ID contract. Use generic/allowlisted public summaries and test short names, raw IDs and historical/renamed devices before merging [PR #20](https://github.com/GiPU-Hackmidwest/gipu/pull/20).
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
