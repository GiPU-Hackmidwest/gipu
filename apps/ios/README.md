# PocketGrid for iPhone and iPad

A native SwiftUI app (iOS 17+) for requesting grid images, managing this phone’s contribution, and seeing receipts/activity.

## Run

1. Start the coordinator using the repository README. For a physical phone, bind it to `0.0.0.0:8787` and connect the phone and server to the same trusted Wi-Fi network.
2. Open `PocketGrid.xcodeproj` in Xcode 26.2 or later. Select the **PocketGrid** scheme.
3. For a real phone, choose your Apple development team under **Signing & Capabilities**, choose your connected iPhone, and run. A signing team is not needed for simulator builds.
4. Enter `http://YOUR-MAC-LAN-IP:8787`, a name, and the configured join code (`pocketgrid-demo` for local development). `127.0.0.1` works in the simulator on the coordinator Mac; it points at the phone itself on a physical phone.
5. Allow Local Network access when iOS asks. Joining does **not** start contribution.
6. In **Contribute**, set limits and tap **Start contributing**. Keep the app visible. Start a Python generation worker on a laptop and request an image in **Create**.

If the network isolates clients (common on event Wi-Fi), use a trusted hotspot or the HTTPS cloud coordinator. This prototype permits HTTP for local development; use an HTTPS coordinator for deployment.

## What actually runs here

The phone advertises `image_finalize`, never `image_generate`. It downloads an image produced by a laptop’s model, applies a four-pixel RGB `(36,203,166)` inner frame using local CoreGraphics pixel operations, and uploads the PNG. The coordinator verifies the border and **every interior pixel** before paying the fixed sandbox credit amount. No cloud generation call is made by this app.

- One active image at a time, using one CPU thread. The CPU-thread control is an upper bound, not a system-wide percentage cap.
- Maximum image pixels and timed contribution session are enforced by the coordinator, with a second pixel-limit check in the phone worker.
- Heartbeats every three seconds; snapshots every two seconds; idle claims every second.
- **Pause**, leaving the foreground, or losing coordinator contact stops local work. A pause update revokes the lease; lease expiry covers sudden disconnects. Returning to the app requires another explicit **Start**.
- Contribution generations reject delayed Start/heartbeat/claim replies from an older session. New starts wait for outstanding Start/Pause updates to settle; a delayed Start after backgrounding is revoked again.
- Credentials persist in the iOS Keychain. The app never puts bearer tokens in image URLs. Relaunching pauses any old contribution session.
- **Activity → Enable notifications** requests native notification permission only after a tap. In-app activity always works. Native notifications are generated from newly received work/credit/job events while the app runs; remote push after app closure is not implemented.
- Grid inputs are visible to participating workers. Use public demo prompts and images. Credits are sandbox units with no cash value.

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

Verified on October 10, 2026:

- The simulator app compiled for arm64 and x86_64, and the unsigned physical-iOS app compiled for arm64, with Xcode 26.2.
- The pixel test passed all 65,536 pixels and rejected an image exceeding the configured limit.
- Lifecycle regression scenarios passed: delayed Start across background/foreground, stale replies after restart, and overlapping Pause requests.
- The shared-code Swift integration harness submitted real generation job `d17f4488fb9746ab87dfb9ba04b3f641`, finished two real image exports, and received `duplicate: true` on repeated completions without additional credits. The job receipt showed 7 contributor credits, 1 service credit, and 2 refunded credits. After pausing, the native worker received no tasks.
- The actual SwiftUI app was then built and launched through Xcode's normal **Run** action on the installed **iPhone 17 Pro Max / iOS 26.2 Simulator**. It joined the live coordinator as `Native iOS Demo`, began paused, accepted a 256 × 256 image limit and a 25-minute session, and started only after an explicit tap.
- From that iOS interface, a real 256 × 256 / 12-step cat-on-bicycle request completed using the Python model worker and the native app's image finalizer. Both generated and teal-framed images appeared. The receipt showed `workers 7 + service 1 = 8 charged; 2 returned`, with available balance 93, reserved 0, and earned 1. In-app events recorded the phone's assigned work and accepted credit.
- The native **Pause** button worked. After explicitly starting again, going Home and reopening PocketGrid left contribution **Paused** with a **Start contributing** button. The notification opt-in button displayed the iOS permission prompt, and its status changed to **Enabled** after allowing notifications.
- A second real image request completed after notification opt-in. A native PocketGrid banner visibly announced `Native iOS Demo started image_finalize`; the account reached available 86, reserved 0, and earned 2. The tested simulator was left **Paused**.

The sandboxed `simctl` command could not access CoreSimulatorService; ordinary Xcode GUI build/run succeeded without changing security settings. Physical-iPhone testing remains outstanding and needs a connected device plus your Apple development signing team. Simulator validation does not establish physical-device battery, thermal, or mobile-network behavior.
