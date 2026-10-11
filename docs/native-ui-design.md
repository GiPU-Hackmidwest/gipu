# Native UI design

Design-phase guide, October 10, 2026. Codex owns native macOS/iOS UX and shared presentation; Claude owns the Tauri Android port. Preserve the existing compute system and API. See [team development](team-development.md).

## Audit and reference translation

The working prototype put requesting, contribution controls, setup instructions and accounting into dense views. Users had to distinguish grid access, a connected image worker and active sharing through explanatory text. The redesign separates those actions while keeping current state and the next action visible.

The supplied three-screen parking reference uses soft gray surfaces, large restrained sans-serif type, rounded sculptural panels, floating pill controls and a single vivid orange action. The revised direction gives PocketGrid a spatial device landscape: simple hardware silhouettes summarize live grid device availability on large smooth surfaces, with controls close to their subject. A contribution arc reflects the real remaining session time from server expiry. Device state, availability and time must come from live data; decorative motion must not suggest work occurred. The prompt and finished image remain prominent. Small screens prioritize the task itself. Dark mode uses darker neutral surfaces with the same orange accent. The native Mac debug app has been built and visually inspected; verification scope is recorded below.

Use the system sans-serif stack on Mac/web and native SwiftUI fonts on iOS. Use direct destination titles rather than promotional slogan headers. Numeric credits align clearly, and supporting labels stay secondary. Avoid filling the screen with uniform dashboard cards: use scale, open space, the live device landscape and a focused control surface to establish hierarchy. Preserve readable contrast instead of copying the reference's faint gray text or white labels on orange. Native iOS tabs, forms, disclosure groups and share controls keep the app familiar. Do not recreate a phone frame or parking imagery inside the product.

## Three journeys

Joining comes first: grid address, name and join code → **Join grid**. Show the connected grid identity afterward. Sharing remains off.

| Destination | Primary journey | Details on demand |
| --- | --- | --- |
| Create | Prompt → image count/budget → Create → Planning / Waiting / Generating / Finishing → image, Save/Share and charge/refund | Model options, planner details, per-stage device and full receipt |
| Contribute | Mac: Connect installed worker → Connected · paused → limits → Start sharing → Pause or Disconnect. iPhone: limits → Start → Pause; stay foregrounded. | Installed worker settings, resource measurements, manual pairing and technical role |
| Activity | Recent work, earned credits and notifications | Ledger entries and accounting detail |

The device landscape is functional: counts derive from live grid state, while device controls identify each actual device and its connected/sharing state. A remaining-time arc must show unknown or paused state honestly and must not invent progress. Failed and cancelled requests remain visible. Cancellation preserves accepted work and returns unused credits. A refresh error must not erase an acknowledged request or revive a cancelled one. Device labels distinguish offline, connected/paused, loading and sharing; neither joining nor connecting implies contribution.

## Minimal text rule

Users should understand the screen through its labels, state and actions. Prefer one short helper line only where it changes a decision. Put infrastructure names, file paths, processor details and pairing tokens behind disclosure. Keep errors actionable and contextual. Keep the meaning of credits clear with a compact **Sandbox credits · no cash value** label; show charges and refunds in the result, with a breakdown on demand.

Use **Connect**, **Start sharing**, **Pause**, **Disconnect**, **Create**, **Save** and **Share** consistently. A connected worker can hold model memory while paused. State that in worker details; do not imply CPU threads, image size or session duration are hard GPU-percent or RAM caps. Resource measurements are observations, separate from limits.

## Shared tokens and contrast

| Token | Light web | Dark web |
| --- | --- | --- |
| Canvas | `#e9eae8` | `#191c19` |
| Surface | `#f7f8f6` | `#252925` |
| Main text | `#20231f` | `#f1f3ee` |
| Secondary text | `#60655e` | `#b4bcb0` |
| Primary action | `#ff690b` | `#ff690b` |
| Action text | `#271405` | `#271405` |

Calculated sRGB relative-luminance contrast for these opaque pairs:

| Text / background | Ratio |
| --- | --- |
| Action text / orange | 6.12:1 |
| Light main text / surface | 14.92:1 |
| Light secondary text / surface | 5.60:1 |
| Light secondary text / canvas | 4.94:1 |
| Dark main text / surface | 13.21:1 |
| Dark secondary text / surface | 7.56:1 |
| Dark secondary text / canvas | 8.81:1 |

White on orange is only 2.89:1, so action labels use dark ink. These token calculations do not establish a full accessibility audit: opacity, disabled/pressed states, platform materials and actual rendered combinations require inspection. SwiftUI uses adaptive system surfaces/text, with the same orange/action-ink pairing.

Web controls have at least 44px height, visible keyboard focus, reduced-motion handling and a stronger-border option for increased contrast. iOS uses native controls and Dynamic Type. Status always includes words rather than relying on color. Confirm keyboard order, VoiceOver labels, large text, light/dark modes and narrow layouts during rendered QA.

## Android integration

The React journeys and API state are shared. `isMacDesktop` gates `DesktopWorkerPanel` and Mac-only behavior; generic Tauri detection must not activate Mac commands on Android. Keep the panel mounted across navigation because cleanup disconnects the managed worker. Showing/hiding destinations must not change native worker ownership or silently resume sharing.

Tauri window configuration uses `create: false`; setup explicitly builds each configured window with `WebviewWindowBuilder::from_config`, preserving configured properties while adding the macOS download handler. Do not add a second automatically created window. The macOS handler accepts only authenticated image blobs already fetched by the frontend and reports download completion; it does not download arbitrary remote URLs or carry credentials. Android owns its download integration.

The Android workstream owns native credentials, notifications, save/share, lifecycle and permissions. Isolate those behind Android adapters. Do not infer that mobile background generation is supported, or port macOS Python-launch and filesystem assumptions into common components. Keep SwiftUI independent while sharing product language and state semantics.

## Verification scope

Verified in this native UI pass:

- Production web build and 28 Node regression tests passed; 45 coordinator tests passed. Rust checks passed with 11 tests passed and one ignored subprocess fixture.
- The native Mac debug `.app` built and rendered. Connecting the prepared managed worker left it paused; explicit Start and Pause controls worked.
- A real local request used native Mac image generation and iOS simulator finishing. The receipt reserved 10 credits, charged 8 and returned 2. Native Mac Save reported successful completion in Downloads.
- Against the hosted coordinator through a loopback same-origin proxy, a browser request completed with real Laptop2 generation and browser finishing. A planner request was durably acknowledged, then cancelled with a full refund. This does not establish successful hosted planner completion.
- Final iOS simulator and unsigned arm64 device builds passed, along with 17 notification ownership checks. The iOS 320-point dial geometry compiled; that check alone is not a narrow-screen visual review.
- The web layout at 390px had no horizontal DOM overflow. This is a layout check, not comprehensive accessibility verification.

Screen capture stopped responding after the final managed-worker Start/Pause check. The following Disconnect click could not be visually confirmed. The iOS ShareLink compiled, but its system share sheet was not exercised.

The finishing device in the local native journey was an iOS simulator. Physical-phone end-to-end behavior, comprehensive dark-mode/Dynamic Type/VoiceOver review, and physical multi-laptop failover were not verified by these checks. Earlier platform README results remain historical evidence. Live device availability must be rechecked before a demo.
