# Native UI design

V1 guide, October 11, 2026. Codex owns Mac/iOS presentation; Claude owns the server, protocol, identity/privacy logic, finalize contract, Android and releases. [V1 plan](v1-plan.md) and [progress](v1-progress.md) supersede earlier design-phase ownership. Preserve existing compute behavior until an agreed contract change merges.

## Current V1 direction

Use **GiPU** and the supplied in-app mark on Mac/iOS. PR #23 delivered `brand/` and Tauri/Android icons; native SwiftUI AppIcon and mark assets are now implemented. Bundle identifiers and environment names stay unchanged. C4/C5/C6/C13/C14/C15 are implemented in merged PR #22. Merged work through main `3e1c6e9` includes account/privacy presentation, anonymous counts, verification states, brand assets and Android adapters. PR #27 also completed GiPU Tauri product/window and Android naming. Release publication remains a separate manual handoff. Review and rollout limits are tracked below.

Primary actions use white labels on the deeper orange below. **Developer options** is a separate page, off by default and remembered locally. CPU threads, largest image, measured usage, worker paths and pairing tokens, plus plan/device diagnostics, belong there. Technical settings must retain their existing values when hidden; opening or closing the page cannot start or stop contribution. Keep ordinary receipts and usable failure messages in the main journey.

Contribute presents separate **Create images** and **Finish images** cards, using responsive columns on wide screens and a simple stack on narrow screens. The public controls are plain toggles: turning one on is the explicit Start, and turning it off pauses. First-time model download still asks before fetching roughly 1 GB; downloading or connecting alone must not silently enable work. Retain the connected/paused distinction and native disconnect behavior, with the Mac worker controller mounted across navigation. iOS exposes Finish images and remains foreground-only. The desktop sidebar becomes more compact and orderly. Remove the About this grid panel on both platforms.

Account sign-in/link, private presentation, anonymous grid counts and verification shimmer now use the merged Phase 1 contract. Link QR/code retains the existing account; New account creates a separate account. Link codes expire after 120 seconds and are single-use; sessions end through revocation/logout. Leaving must stop owned contribution before credentials are discarded. The compatible hosted coordinator deployment of `a34aef0` was recorded before cutover. Python, browser/Android and iOS runtime finishers now use pixel-identical output; the coordinator still accepts legacy framed outputs from older installed apps. There is no version negotiation: counts or verification fields alone do not authorize a cutover.

## Audit and reference translation

The working prototype put requesting, contribution controls, setup instructions and accounting into dense views. Users had to distinguish grid access, a connected image worker and active sharing through explanatory text. The redesign separates those actions while keeping current state and the next action visible.

The supplied three-screen parking reference uses soft gray surfaces, large restrained sans-serif type, rounded sculptural panels, floating pill controls and a single vivid orange action. The revised direction gives PocketGrid a spatial device landscape: simple hardware silhouettes summarize live grid device availability on large smooth surfaces, with controls close to their subject. A contribution arc reflects the real remaining session time from server expiry. Device state, availability and time must come from live data; decorative motion must not suggest work occurred. The prompt and finished image remain prominent. Small screens prioritize the task itself. Dark mode uses darker neutral surfaces with the same orange accent. The native Mac debug app has been built and visually inspected; verification scope is recorded below.

Use the system sans-serif stack on Mac/web and native SwiftUI fonts on iOS. Use direct destination titles rather than promotional slogan headers. Numeric credits align clearly, and supporting labels stay secondary. Avoid filling the screen with uniform dashboard cards: use scale, open space, the live device landscape and a focused control surface to establish hierarchy. Preserve readable contrast instead of copying the reference's faint gray text; white action labels use the deeper accessible orange below. Native iOS tabs, forms, disclosure groups and share controls keep the app familiar. Do not recreate a phone frame or parking imagery inside the product.

## Clay material refinement

The refinement gives the existing spatial layout a consistent opaque clay material. One upper-left light source produces paired shadows: a soft highlight above/left and a soft shade below/right. Three elevations make function legible: **raised** panels and device platforms, **floating** controls and status pills, and **recessed** input wells, the device landscape and timer track. Pressed controls move visually into the recessed treatment. Large continuous corners and restrained orange preserve the reference's sculptural quality.

This uses shadow softness, not backdrop blur, glass effects or particles. It adds no explanatory copy: short labels, visible state and the same primary actions remain. Web increased-contrast mode replaces shadow dependence with stronger borders; iOS adds explicit outlines. Reduced-motion settings remove the optional press animation. These implementations still need a complete accessibility review in context.

## Three journeys (V1 target)

Sign-in comes first: scan/paste a Link QR or type its code to keep an existing account; use New account for a separate account, or password sign-in after adding a login. Keep the grid address and manual fallback available without surrounding instructions. Camera access is requested only after Scan QR. Show the connected account afterward. Sharing remains off.

| Destination | Primary journey | Details on demand |
| --- | --- | --- |
| Create | Prompt → image count/budget → Create → Planning / Waiting / Generating / Finishing → image, Save/Share and charge/refund | Developer options: model/planner and stage/device diagnostics; receipt breakdown on demand |
| Contribute | Mac: consent to one-time model download if needed → Create images on/off or Finish images on/off. iPhone: Finish images on/off; stay foregrounded. | Developer options: limits, worker setup, measurements and device diagnostics |
| Activity | Recent work, earned credits and notifications | Ledger entries and accounting detail |

The device landscape is functional: anonymous connected/ready counts come from `state.grid`, while contribution controls identify only the current account’s devices. Missing or invalid counts show unavailable, never an invented zero or a count of only local devices. Public Activity uses generic labels, and client presentation filters jobs/devices to the current account; server authorization remains necessary. One result is shown per variant, preferring explicit verification. Only `verified: false` activates shimmer, `true` confirms verification, and missing verification stays neutral. Respect reduced motion. A remaining-time arc must show unknown or paused state honestly and must not invent progress. Failed and cancelled requests remain visible. Cancellation preserves accepted work and returns unused credits. A refresh error must not erase an acknowledged request or revive a cancelled one. Device labels distinguish offline, connected/paused, loading and sharing; neither joining nor connecting implies contribution.

## Minimal text rule

Users should understand the screen through its labels, state and actions. Prefer one short helper line only where it changes a decision. Move infrastructure names, file paths, processor details and pairing tokens to the separate Developer options page. Keep errors actionable and contextual. Keep the meaning of credits clear with a compact **Sandbox credits · no cash value** label; show charges and refunds in the result, with a breakdown on demand.

Use **Create images** and **Finish images** for contribution toggles, with concise state labels; use **Create**, **Save** and **Share** for requests/results. Preserve explicit Connect/Pause/Disconnect behavior in the underlying controller. A connected worker can hold model memory while paused. State that in Developer options; do not imply CPU threads, image size or session duration are hard GPU-percent or RAM caps. Resource measurements are observations, separate from limits.

## Shared tokens and contrast

V1 tokens below replace the earlier dark-on-bright-orange action pair. Mac/browser controls have been inspected; iOS builds passed, while rendered V1 and comprehensive accessibility checks remain outstanding. Light colors align across web and iOS; each platform has a distinct adaptive dark palette:

| Token | Light web/iOS | Dark web | Dark iOS |
| --- | --- | --- | --- |
| Canvas | `#F4F6F8` | `#202328` | `#1C1E21` |
| Surface | `#F5F6F8` | `#272B31` | `#282C31` |
| Inset | `#E5E7EB` | `#1B1E23` | `#171A1E` |
| Main text | `#1C1E21` | `#F1F3F6` | `#F1F3F5` |
| Secondary text | `#606770` | `#B4BBC6` | `#ABB3BD` |
| Primary action | `#C34400` | `#C34400` | `#C34400` |
| Action text | `#FFFFFF` | `#FFFFFF` | `#FFFFFF` |

Calculated sRGB relative-luminance contrast for the opaque token pairs:

| Text / background | Ratio |
| --- | --- |
| White action text / orange | 5.06:1 |
| Light main text / surface | 15.45:1 |
| Light secondary text / surface | 5.29:1 |
| Light secondary text / canvas | 5.28:1 |
| Light secondary text / inset | 4.62:1 |
| Dark web main text / surface | 12.80:1 |
| Dark web secondary text / surface | 7.36:1 |
| Dark web secondary text / canvas | 8.15:1 |
| Dark iOS main text / surface | 12.63:1 |
| Dark iOS secondary text / surface | 6.63:1 |
| Dark iOS secondary text / canvas | 7.89:1 |

White on `#C34400` is 5.06:1, meeting the 4.5:1 target for normal-size labels. This replaces the previous dark action labels on `#FF5A09`; do not reuse that earlier orange behind white labels. These token calculations do not establish a full accessibility audit: opacity, shadows, disabled/pressed states and actual rendered combinations require inspection.

Web controls have at least 44px height, visible keyboard focus, reduced-motion handling and a stronger-border option for increased contrast. iOS uses native controls and Dynamic Type. Status always includes words rather than relying on color. Confirm keyboard order, VoiceOver labels, large text, light/dark modes and narrow layouts during rendered QA.

## Bundled worker integration

The existing Mac model download has progress and Cancel. V1 preserves its explicit consent and cached offline model loading, then uses **Create images** as the explicit sharing control. Native Connect still registers paused before a separately authorized Start. Grid communication requires the coordinator. Ordinary users do not need Python paths or pairing tokens; processor and worker details move to Developer options.

`npm run build:desktop` packages the frozen Python worker; model weights download into app data. Source builds retain the prepared-checkout development fallback. Connecting does not install packages or fetch models, and switching destinations must not disconnect the managed worker.

## Android integration

PR #24 supplies Android-only deep-link 2.6.1 and barcode-scanner 2.5.2 plugins plus the Keystore adapter. Shared sign-in selects that secure store only on Android. Scanning requests permission on demand and accepts AbortSignal so teardown/backgrounding stops the camera. Received links require confirmation before changing accounts; retain worker cleanup before discarding credentials. Failed durable deletion must be reported, a secure session removes stale plaintext, and failed cold-link reads release listeners. The native iOS path remains independent.

The React journeys and API state are shared. `platformFlags` in `apps/web/src/platform.ts` recognizes `TAURI_ENV_PLATFORM` target names including `darwin` and `androideabi` (plus friendly aliases), and only falls back to the user agent when metadata is absent. Preserve Vite’s `TAURI_ENV_` prefix. `isMacDesktop` gates `DesktopWorkerPanel` and Mac-only behavior; generic Tauri detection must not activate Mac commands on Android. Keep the panel mounted across navigation because cleanup disconnects the managed worker. Showing/hiding destinations must not change native worker ownership or silently resume sharing.

Tauri window configuration uses `create: false`; shared setup in `apps/web/src-tauri/src/lib.rs` explicitly builds each configured window on all targets with `WebviewWindowBuilder::from_config`, preserving configured properties while adding the macOS download handler. Do not add a second automatically created window. The macOS handler accepts only authenticated image blobs already fetched by the frontend and reports download completion; it does not download arbitrary remote URLs or carry credentials. Android owns its download integration.

The Android workstream owns native credentials, notifications, save/share, lifecycle and permissions. Isolate those behind Android adapters. Do not infer that mobile background generation is supported, or port macOS Python-launch and filesystem assumptions into common components. The iOS app remains native SwiftUI, independent of Tauri mobile scaffolding, while sharing product language and state semantics.

## Verification scope

### Current integrated verification and local release handoff

Main `3e1c6e9` includes PRs #27–#31. Checks passed: 83 frontend, 77 coordinator and 34 worker tests; native iOS simulator build; and strict native fixture settlement with legacy acceptance disabled. The updated Mac debug bundle also passed, measured 671 MiB, and retained all 24 worker symlinks matching the fresh frozen source. A fresh PyInstaller bundle build passed before #31. Release packaging is local: the Actions workflow is deleted and manually disabled; publication remains separate. Physical QR decoding, phone finishing and comprehensive accessibility validation remain open.

### V1 account/privacy UI baseline (historical)

- Shared changes add `qrcode.react` 4.2.0 for local SVG QR rendering and macOS-only `security-framework` 3.7 for Keychain. `SessionStore` remains the platform boundary. `ApiError.status` supports revoked-session handling; shared URL validation rejects embedded credentials/malformed origins. No QR service receives account-link contents. Mac migration preserves an existing account before removing the earlier local token.
- The pre-Android account baseline passed 66 frontend tests, including five storage and ten identity checks. The native Mac build passed; Rust passed 16 with one ignored fixture. Two real browser origins linked a new account into a second client with the same 100-credit balance. The native Mac app migrated an existing 99-credit account to Keychain. A real teapot request used that other account’s native Mac for generation and the linked browser for finishing: both linked clients showed the same image and 93 available / 0 reserved / 1 earned. The Mac account showed 105 available / 13 earned, retained only its own earlier cat image, and did not show the other account’s teapot. Activity labels were generic. Native relaunch preserved the 105-credit account; Show QR rendered and Sign out returned to sign-in. Captures are `outputs/v1-mac-account.png` and `outputs/v1-linked-account-result.png`. Shimmer selection/CSS is tested, but the transient animation was not captured. That baseline includes the foreign-earnings privacy regression; current integrated results are above.
- iOS arm64/x86_64 simulator and unsigned arm64 device builds passed, along with IdentityPrivacy, JobStatus, LifecycleRace and 17 NotificationOwnership checks. The staged invisible encoder preserved 65,536 RGB pixels for RGB, RGBA and indexed-color inputs; size rejection and production legacy-frame parity passed. At that baseline runtime still called the legacy finalizer; PR #30 subsequently switched native iOS after confirmed deployment.
- PRs #23/#24 merged as `80d6a2d` / `f9a32a7`; account integration is `e5e458d`. The separate Android adapter review passed 61 frontend tests, its production build and 15 Rust tests with one ignored; combined checks were pending at that point. The terminal asset build was blocked by simulator-service access, but host Xcode later built the catalog successfully; PR #30 also passed a simulator app build. Earlier source-build evidence alone did not cover the catalog.
- Physical QR decoding and phone finishing, release publication and comprehensive accessibility review remain outstanding; this is not full V1 sign-off. The static brand orange `#FF5A09` does not replace the deeper `#C34400` action color or signal active contribution.

### V1 simple controls (merged #22)

Production web and bundled Mac builds passed with 50 frontend tests. Actual Mac Create images / Finish images toggles survived navigation and Developer options changes, then paused; reopening left sharing off. A real local image completed with receipt `10 = 7 contributors + 1 fee + 2 refunded`. Browser Developer options persisted across reload, and the 320px layout had no horizontal overflow. iOS builds and status/lifecycle/notification harnesses passed, without a rendered V1 or physical-phone claim.

The following sections are historical pre-V1 checks and retain their original scope. In particular, the earlier missing Android SDK describes that pass; PR #21 later recorded a native Android emulator build/journey in the progress log.

### Merge integration

- Frontend: 33 Node tests passed, including `darwin`/`androideabi` platform detection. Rust: 15 passed, one ignored subprocess fixture. Python worker: 33 passed. Packaging: 7 passed.
- The bundled Mac debug app built successfully with a custom Cargo target directory and measured 670 MB. Its actual UI passed Download, Cancel and Retry checks and completed the real model download. Connect began paused; explicit Start enabled sharing. Navigating to Create preserved the managed worker.
- Real request `551049f0` completed through **This Mac image worker** generation and **Mac Demo desktop window** finishing. The receipt balanced 10 reserved = 7 contributor credits + 1 fee + 2 refunded. Native Save showed **Saved to Downloads**. Both workers paused, then Disconnect showed **Disconnected**.
- The Android frontend production build passed and native source was reviewed. Native Android compilation was unavailable because SDK/NDK tools are absent. SDK license consent was not provided, and no license was accepted.

This integrated end-to-end run used one physical Mac for generation and desktop-window finishing. It adds no physical-phone or multi-laptop failover evidence. Results below retain their earlier build scope.

### Clay refinement

- Production web and native Mac debug builds passed. iOS simulator and unsigned arm64 device builds passed.
- The actual native Mac Create screen and iOS simulator Create/Contribute screens were visually inspected with the refined materials. On the simulator, explicit Start produced a live remaining-time countdown and Pause stopped contribution.
- The web layout at 320px had no horizontal DOM overflow after the compact navigation fix. This is a layout check, not a full accessibility audit.
- Screen capture worked for these inspections. On reopening, the Mac app showed Disconnected, confirming the earlier Disconnect took effect. The earlier capture interruption is historical, not a current blocker.

The earlier real generation and settlement checks below were not rerun for this material refinement. Their behavior was preserved, but they remain evidence of the preceding implementation. Comprehensive dark-mode and large-text inspection was not completed.

### Earlier native UI baseline

Verified before the clay refinement:

- Production web build and 28 Node regression tests passed; 45 coordinator tests passed. Rust checks passed with 11 tests passed and one ignored subprocess fixture.
- The native Mac debug `.app` built and rendered. Connecting the prepared managed worker left it paused; explicit Start and Pause controls worked.
- A real local request used native Mac image generation and iOS simulator finishing. The receipt reserved 10 credits, charged 8 and returned 2. Native Mac Save reported successful completion in Downloads.
- Against the hosted coordinator through a loopback same-origin proxy, a browser request completed with real Laptop2 generation and browser finishing. A planner request was durably acknowledged, then cancelled with a full refund. This does not establish successful hosted planner completion.
- Final iOS simulator and unsigned arm64 device builds passed, along with 17 notification ownership checks. The iOS 320-point dial geometry compiled; that check alone is not a narrow-screen visual review.
- The web layout at 390px had no horizontal DOM overflow. This is a layout check, not comprehensive accessibility verification.

The earlier screen-capture interruption prevented immediate confirmation of Disconnect; later reopening showed Disconnected as noted above. The iOS ShareLink compiled, but its system share sheet was not exercised in either recorded pass.

The finishing device in the local native journey was an iOS simulator. Physical-phone end-to-end behavior, comprehensive dark-mode/Dynamic Type/VoiceOver review, and physical multi-laptop failover were not verified by these checks. Earlier platform README results remain historical evidence. Live device availability must be rechecked before a demo.
