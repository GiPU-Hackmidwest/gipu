# GiPU for iPhone and iPad

A native SwiftUI app (iOS 17+) for requesting grid images, managing this phone’s contribution, and seeing receipts/activity.

## Native design phase

Arboy with Codex owns SwiftUI and Mac UX; the teammate with Claude owns the separate Tauri Android port. SwiftUI keeps native **Create**, **Contribute** and **Activity** tabs, system forms, Dynamic Type and foreground lifecycle behavior. **Finish images** starts or pauses this phone. Technical controls live under **Activity → Developer options**, which is off by default and saved locally. Receipt breakdowns remain in the result. See [the shared design guide](../../docs/native-ui-design.md).

Preserve each developer's local signing settings in `PocketGrid.xcodeproj/project.pbxproj`; do not commit personal team or signing changes as project defaults.

## Install from source

There is no published iOS download or TestFlight invitation in this repository yet. The supported distribution path is a source build on a Mac with Xcode 26.2 or later and the iOS SDK. The app supports iOS 17+. No separate Swift packages or model download are required for the phone app.

Clone the repository, then open `apps/ios/PocketGrid.xcodeproj`. Its project and scheme remain named **PocketGrid**; the installed app displays **GiPU**. Bundle identifiers and Keychain identifiers are unchanged. The official GiPU icon and adaptive in-app mark are included in `PocketGrid/Assets.xcassets`. The light/dark AppIcon PNGs preserve the shared brand pixels with their fully opaque alpha channel removed; the in-app mark uses the original light/dark SVGs.

For a simulator, choose an installed iPhone simulator and select **Product → Run**. For a physical phone, connect the iPhone, select it as the destination, and choose your own Apple development team under **Signing & Capabilities**. Follow Xcode's device preparation and signing prompts. Preserve these personal signing settings locally. The unsigned command-line build below cannot be installed on a phone.

TestFlight distribution needs an Apple Developer Program team, App Store Connect setup, a signed archive and a published invitation; none is established by a simulator or unsigned-device build.

## Join and use

1. Start the coordinator using the repository README. For a physical phone, bind it to `0.0.0.0:8787` and connect the phone and server to the same trusted Wi-Fi network.
2. Launch **GiPU** and choose **Scan QR**. Scan the Link QR from **Account → Link a device** on an already signed-in device to keep its account and balance. An Invite QR creates a new account instead. Review the displayed grid before continuing; replacing a signed-in account requires confirmation and stops sharing. If camera scanning is unavailable (including the simulator), expand **Sign in another way** for a link code, username/password, or a new account with the grid/name/join code. `127.0.0.1` refers to the Mac in its simulator but to the phone itself on physical hardware. Use the intended hosted HTTPS grid or the Mac’s LAN address.
3. Allow Local Network access when iOS asks. Joining does **not** start contribution.
4. In **Contribute**, choose **Stop after** and turn on **Finish images**. Turning it off pauses immediately. Keep the app visible. The phone does not offer **Create images** contribution; image generation needs a prepared laptop worker.
5. Request an image in **Create**. **Activity → Developer options** optionally exposes maximum image size, the fixed CPU-thread count, device telemetry, planner selection and request/device diagnostics. Enable the page explicitly; opening it or turning Developer options on does not start sharing. Pause finishing before changing image limits.

If the network isolates clients (common on event Wi-Fi), use a trusted hotspot or the HTTPS cloud coordinator. This prototype permits HTTP for local development; use an HTTPS coordinator for deployment.

## Accounts and compatibility

**Activity → Account** shows a short-lived Link QR/code and an optional login for recovery. Link codes last 120 seconds and are single use; requesting a new code invalidates the previous code. Passwords and codes are not persisted by this app. Session and device credentials remain in Keychain. Sign-out pauses this phone before requesting session revocation and clearing local credentials. Sign-in requests never carry the previous account’s token, including when a QR points to another grid.

The native parser follows `apps/web/src/identity.ts` and additionally rejects embedded username/password credentials in a grid origin. `gipu://join` and `gipu://link` URLs are registered with iOS. Camera access is requested only after **Scan QR**. VisionKit scanning requires supported hardware; the typeable code/manual route remains available.

A V1 coordinator is required for linking, login, aggregate counts and authoritative verification. Missing counts display as unavailable. Own-job/device filtering and generic event text also protect the presentation when an older coordinator returns broad snapshots; server-side authorization is still required. Only `verified: false` activates shimmer; `true` shows Verified. Missing verification fields use neutral Ready/Preview labels without a verification claim.

## What actually runs here

The phone advertises `image_finalize`, never `image_generate`. **Runtime rollout is intentionally still legacy:** it downloads an image produced by a laptop’s model, applies a four-pixel RGB `(36,203,166)` inner frame using local CoreGraphics pixel operations, and uploads the PNG. The coordinator verifies the border and **every interior pixel** before paying the fixed sandbox credit amount. No cloud generation call is made by this app.

`ImageProcessor.finalizeInvisible` is a separately tested pixel-identical PNG re-encoder, ready for V1 cutover. `GridModel` does not call it yet. Do not infer finisher compatibility from `grid` or `verified`; the contract has no version negotiation. Switch the runtime only after the accepting coordinator deployment is explicitly confirmed.

- One active image at a time, using one CPU thread. The native phone worker has no adjustable CPU-thread control.
- Maximum image pixels and timed contribution session are enforced by the coordinator, with a second pixel-limit check in the phone worker.
- Heartbeats every three seconds; snapshots every two seconds; idle claims every second.
- Turning **Finish images** off, leaving the foreground, or losing coordinator contact stops local work. A pause update revokes the lease; lease expiry covers sudden disconnects. Returning to the app leaves the toggle off and requires another explicit opt-in.
- Contribution generations reject delayed Start/heartbeat/claim replies from an older session. New starts wait for outstanding Start/Pause updates to settle; a delayed Start after backgrounding is revoked again.
- Credentials persist in the iOS Keychain. The app never puts bearer tokens in image URLs. Relaunching pauses any old contribution session.
- **Activity → Notifications** requests native notification permission only after a tap. In-app activity always works. Native notifications are generated from newly received work/credit/job events while the app runs; remote push after app closure is not implemented.
- Assigned inputs remain visible to participating workers. The UI shows the current account’s requests and generic activity only. Credits are sandbox units with no cash value.

## Build and verification

From `apps/ios`:

```sh
xcodebuild -project PocketGrid.xcodeproj -scheme PocketGrid \
  -configuration Debug -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .build/DerivedData \
  CLANG_MODULE_CACHE_PATH="$PWD/.build/ModuleCache" \
  SWIFT_MODULE_CACHE_PATH="$PWD/.build/SwiftModuleCache" \
  CODE_SIGNING_ALLOWED=NO build
```

An unsigned device compilation checks the physical-iOS target without installing it:

```sh
xcodebuild -project PocketGrid.xcodeproj -scheme PocketGrid \
  -configuration Debug -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath .build/DeviceDerivedData \
  CODE_SIGNING_ALLOWED=NO build
```

The actual image processor also runs on macOS for independent pixel validation. Use a Python environment with Pillow (the coordinator environment includes it):

```sh
mkdir -p .build
xcrun swiftc -module-cache-path .build/MacModuleCache \
  PocketGrid/ImageProcessor.swift Tests/PixelParity.swift -o .build/pixel-parity
python3 Tests/check_pixels.py fixture
.build/pixel-parity .build/input.png .build/output.png
python3 Tests/check_pixels.py verify
```

To exercise the app's actual networking, decoders, and pixel code together against the coordinator with a real generation worker available:

```sh
xcrun swiftc -module-cache-path .build/MacModuleCache \
  PocketGrid/Models.swift PocketGrid/ImageProcessor.swift \
  Tests/CoordinatorSmoke.swift -o .build/coordinator-smoke
.build/coordinator-smoke http://127.0.0.1:8787
```

This creates a sandbox account and an image request, contributes native image finishing, checks the receipt and a duplicate completion retry, then pauses the device. It is a macOS harness using shared app code, not an iOS UI test.

The contribution lifecycle regression check runs without a server:

```sh
xcrun swiftc -module-cache-path .build/MacModuleCache \
  PocketGrid/Models.swift Tests/LifecycleRace.swift -o .build/lifecycle-race
.build/lifecycle-race
```

The notification ownership check also runs without a server. Personal earnings require an explicit matching recipient; existing event-kind and device filters remain in place:

```sh
mkdir -p .build
xcrun swiftc -module-cache-path .build/MacModuleCache \
  PocketGrid/Models.swift Tests/NotificationOwnership.swift -o .build/notification-ownership
.build/notification-ownership
```

V1 accounts verification on October 11, 2026:

- Simulator arm64/x86_64 and unsigned iOS arm64 builds passed. No signing/project configuration changes or third-party dependencies were needed.
- `IdentityPrivacy.swift` passed link round trips, malformed/unsafe-origin rejection, old/new session decoding, own-only data filtering, generic event text and the optional verification flag. JobStatus, LifecycleRace and the 17 NotificationOwnership checks also passed.
- The staged invisible encoder preserved all 65,536 decoded RGB pixels for RGB, alpha-bearing RGBA and indexed-color PNG sources; size-limit rejection passed. The production legacy frame/interior parity check also passed.
- Camera scanning, QR transfer, live account linking/login, Keychain behavior across real app launches and rendered shimmer were not exercised in this compile-only pass. These checks do not establish physical-phone or deployed-server compatibility. The frameless runtime cutover remains pending confirmed deployment.

Run the new standalone harnesses from `apps/ios`:

```sh
mkdir -p .build
xcrun swiftc -module-cache-path .build/MacModuleCache \
  PocketGrid/Models.swift Tests/IdentityPrivacy.swift -o .build/identity-privacy
.build/identity-privacy
xcrun swiftc -module-cache-path .build/MacModuleCache \
  PocketGrid/ImageProcessor.swift Tests/InvisiblePixelParity.swift -o .build/invisible-parity
python3 Tests/check_invisible_pixels.py .build/invisible-parity .build/invisible
```

V1 controls verification on October 11, 2026:

- Simulator arm64/x86_64 and unsigned physical-iOS arm64 builds passed with Xcode 26.2. The property list and Git whitespace checks passed.
- Swift JobStatus, LifecycleRace and all 17 NotificationOwnership checks passed. These cover existing durable request/credit behavior, start/pause reply fencing and notification recipients.
- White action labels on `#C34400` have a calculated opaque sRGB contrast of 5.06:1.
- This pass did not install on a physical phone, publish a TestFlight build or exercise the new toggle/Developer options screen in the simulator. Those controls still need rendered interaction checks, including persisted preferences, background/foreground and accessibility.

Design-phase verification:

- Final iOS simulator and unsigned arm64 device builds passed. An unsigned device build does not verify installation or behavior on a physical phone.
- A real local native Mac generation request completed with the iOS simulator performing image finishing. The receipt reserved 10 credits, charged 8 and returned 2.
- All 17 notification ownership checks passed. The responsive 320-point contribution-dial geometry compiled; this does not establish a full narrow-screen visual audit.
- Physical-phone end-to-end behavior and comprehensive dark-mode, Dynamic Type and VoiceOver QA remain unverified by this pass.

Historical verification on October 10, 2026, before the native UI redesign:

- The simulator app compiled for arm64 and x86_64, and the unsigned physical-iOS app compiled for arm64, with Xcode 26.2.
- The pixel test passed all 65,536 pixels and rejected an image exceeding the configured limit.
- Lifecycle regression scenarios passed: delayed Start across background/foreground, stale replies after restart, and overlapping Pause requests.
- The shared-code Swift integration harness submitted real generation job `d17f4488fb9746ab87dfb9ba04b3f641`, finished two real image exports, and received `duplicate: true` on repeated completions without additional credits. The job receipt showed 7 contributor credits, 1 service credit, and 2 refunded credits. After pausing, the native worker received no tasks.
- The actual SwiftUI app was then built and launched through Xcode's normal **Run** action on the installed **iPhone 17 Pro Max / iOS 26.2 Simulator**. It joined the live coordinator as `Native iOS Demo`, began paused, accepted a 256 × 256 image limit and a 25-minute session, and started only after an explicit tap.
- From that iOS interface, a real 256 × 256 / 12-step cat-on-bicycle request completed using the Python model worker and the native app's image finalizer. Both generated and teal-framed images appeared. The receipt showed `workers 7 + service 1 = 8 charged; 2 returned`, with available balance 93, reserved 0, and earned 1. In-app events recorded the phone's assigned work and accepted credit.
- The native **Pause** button worked. After explicitly starting again, going Home and reopening PocketGrid left contribution **Paused** with a **Start contributing** button. The notification opt-in button displayed the iOS permission prompt, and its status changed to **Enabled** after allowing notifications.
- A second real image request completed after notification opt-in. A native PocketGrid banner visibly announced `Native iOS Demo started image_finalize`; the account reached available 86, reserved 0, and earned 2. The tested simulator was left **Paused**.

The sandboxed `simctl` command could not access CoreSimulatorService; ordinary Xcode GUI build/run succeeded without changing security settings. At that historical check, physical-iPhone testing remained outstanding. Project context later recorded physical-phone installation, joining and submission, but not completed physical-phone finishing. Fresh redesigned-app verification needs a connected device plus your Apple development signing team. Simulator validation does not establish physical-device battery, thermal, or mobile-network behavior.

## Job status checks

The Create tab explains generation and export separately and offers an explicit Start this phone action for compatible queued finishing work. Unknown capabilities/session timing produce an uncertain status instead of claiming a worker is ready. The server still chooses assignments.

From the repository root, run the dependency-free status harness:

```sh
swiftc apps/ios/PocketGrid/Models.swift apps/ios/Tests/JobStatus.swift -o /tmp/pocketgrid-job-status
/tmp/pocketgrid-job-status
```
