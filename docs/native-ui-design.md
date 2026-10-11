# Native UI design

Design-phase guide, October 10, 2026. Codex owns native macOS/iOS UX and shared presentation; Claude owns the Tauri Android port. Preserve the existing compute system and API. See [team development](team-development.md).

## Audit and reference translation

The working prototype put requesting, contribution controls, setup instructions and accounting into dense views. Users had to distinguish grid access, a connected image worker and active sharing through explanatory text. The redesign separates those actions while keeping current state and the next action visible.

The supplied three-screen parking reference uses soft gray surfaces, large restrained sans-serif type, rounded sculptural panels, floating pill controls and a single vivid orange action. The revised direction gives PocketGrid a spatial device landscape: simple hardware silhouettes summarize live grid device availability on large smooth surfaces, with controls close to their subject. A contribution arc reflects the real remaining session time from server expiry. Device state, availability and time must come from live data; decorative motion must not suggest work occurred. The prompt and finished image remain prominent. Small screens prioritize the task itself. Dark mode uses darker neutral surfaces with the same orange accent. The native Mac debug app has been built and visually inspected; verification scope is recorded below.

Use the system sans-serif stack on Mac/web and native SwiftUI fonts on iOS. Use direct destination titles rather than promotional slogan headers. Numeric credits align clearly, and supporting labels stay secondary. Avoid filling the screen with uniform dashboard cards: use scale, open space, the live device landscape and a focused control surface to establish hierarchy. Preserve readable contrast instead of copying the reference's faint gray text or white labels on orange. Native iOS tabs, forms, disclosure groups and share controls keep the app familiar. Do not recreate a phone frame or parking imagery inside the product.

## Clay material refinement

The refinement gives the existing spatial layout a consistent opaque clay material. One upper-left light source produces paired shadows: a soft highlight above/left and a soft shade below/right. Three elevations make function legible: **raised** panels and device platforms, **floating** controls and status pills, and **recessed** input wells, the device landscape and timer track. Pressed controls move visually into the recessed treatment. Large continuous corners and restrained orange preserve the reference's sculptural quality.

This uses shadow softness, not backdrop blur, glass effects or particles. It adds no explanatory copy: short labels, visible state and the same primary actions remain. Web increased-contrast mode replaces shadow dependence with stronger borders; iOS adds explicit outlines. Reduced-motion settings remove the optional press animation. These implementations still need a complete accessibility review in context.

## Three journeys

Joining comes first: grid address, name and join code → **Join grid**. Show the connected grid identity afterward. Sharing remains off.

| Destination | Primary journey | Details on demand |
| --- | --- | --- |
| Create | Prompt → image count/budget → Create → Planning / Waiting / Generating / Finishing → image, Save/Share and charge/refund | Model options, planner details, per-stage device and full receipt |
| Contribute | Mac: Download model once → Connect worker → Connected · paused → limits → Start sharing → Pause or Disconnect. iPhone: limits → Start → Pause; stay foregrounded. | Installed worker settings, resource measurements, manual pairing and technical role |
| Activity | Recent work, earned credits and notifications | Ledger entries and accounting detail |

The device landscape is functional: counts derive from live grid state, while device controls identify each actual device and its connected/sharing state. A remaining-time arc must show unknown or paused state honestly and must not invent progress. Failed and cancelled requests remain visible. Cancellation preserves accepted work and returns unused credits. A refresh error must not erase an acknowledged request or revive a cancelled one. Device labels distinguish offline, connected/paused, loading and sharing; neither joining nor connecting implies contribution.

## Minimal text rule

Users should understand the screen through its labels, state and actions. Prefer one short helper line only where it changes a decision. Put infrastructure names, file paths, processor details and pairing tokens behind disclosure. Keep errors actionable and contextual. Keep the meaning of credits clear with a compact **Sandbox credits · no cash value** label; show charges and refunds in the result, with a breakdown on demand.

Use **Connect**, **Start sharing**, **Pause**, **Disconnect**, **Create**, **Save** and **Share** consistently. A connected worker can hold model memory while paused. State that in worker details; do not imply CPU threads, image size or session duration are hard GPU-percent or RAM caps. Resource measurements are observations, separate from limits.

## Shared tokens and contrast

Light colors align across web and iOS. Each platform has a distinct adaptive dark palette:

| Token | Light web/iOS | Dark web | Dark iOS |
| --- | --- | --- | --- |
| Canvas | `#F4F6F8` | `#202328` | `#1C1E21` |
| Surface | `#F5F6F8` | `#272B31` | `#282C31` |
| Inset | `#E5E7EB` | `#1B1E23` | `#171A1E` |
| Main text | `#1C1E21` | `#F1F3F6` | `#F1F3F5` |
| Secondary text | `#606770` | `#B4BBC6` | `#ABB3BD` |
| Primary action | `#FF5A09` | `#FF5A09` | `#FF5A09` |
| Action text | `#271405` | `#271405` | `#271405` |

SwiftUI expresses the orange/action ink as normalized RGB values that round to the listed 8-bit tokens. Calculated sRGB relative-luminance contrast for these opaque token pairs:

| Text / background | Ratio |
| --- | --- |
| Action text / orange | 5.65:1 |
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

White on orange is 3.13:1, so normal-size action labels use dark ink. These token calculations do not establish a full accessibility audit: opacity, shadows, disabled/pressed states and actual rendered combinations require inspection.

Web controls have at least 44px height, visible keyboard focus, reduced-motion handling and a stronger-border option for increased contrast. iOS uses native controls and Dynamic Type. Status always includes words rather than relying on color. Confirm keyboard order, VoiceOver labels, large text, light/dark modes and narrow layouts during rendered QA.

## Bundled worker integration

The Mac Contribute journey includes one-time **Download model · 1 GB** with progress and Cancel. Once ready, **Connect worker** loads the cache offline and registers paused; **Start sharing** remains a separate action. Grid communication still requires the coordinator. Ordinary users do not need Python paths or pairing tokens. Processor and worker details stay behind disclosure, preserving the minimal clay interface.

`npm run build:desktop` packages the frozen Python worker; model weights download into app data. Source builds retain the prepared-checkout development fallback. Connecting does not install packages or fetch models, and switching destinations must not disconnect the managed worker.

## Android integration

The React journeys and API state are shared. `platformFlags` in `apps/web/src/platform.ts` recognizes `TAURI_ENV_PLATFORM` target names including `darwin` and `androideabi` (plus friendly aliases), and only falls back to the user agent when metadata is absent. Preserve Vite’s `TAURI_ENV_` prefix. `isMacDesktop` gates `DesktopWorkerPanel` and Mac-only behavior; generic Tauri detection must not activate Mac commands on Android. Keep the panel mounted across navigation because cleanup disconnects the managed worker. Showing/hiding destinations must not change native worker ownership or silently resume sharing.

Tauri window configuration uses `create: false`; shared setup in `apps/web/src-tauri/src/lib.rs` explicitly builds each configured window on all targets with `WebviewWindowBuilder::from_config`, preserving configured properties while adding the macOS download handler. Do not add a second automatically created window. The macOS handler accepts only authenticated image blobs already fetched by the frontend and reports download completion; it does not download arbitrary remote URLs or carry credentials. Android owns its download integration.

The Android workstream owns native credentials, notifications, save/share, lifecycle and permissions. Isolate those behind Android adapters. Do not infer that mobile background generation is supported, or port macOS Python-launch and filesystem assumptions into common components. The iOS app remains native SwiftUI, independent of Tauri mobile scaffolding, while sharing product language and state semantics.

## Verification scope

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
