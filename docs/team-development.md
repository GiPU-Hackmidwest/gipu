# PocketGrid team development

The current design phase improves the existing native apps. Keep the working distributed-compute system available. This ownership split replaces earlier models/UI versus reliability/deployment handoffs.

Read [project context](project-context.md), [protocol](protocol.md) and [native UI design](native-ui-design.md) before changing behavior.

## Current ownership

| Workstream | Owner | Scope |
| --- | --- | --- |
| Native macOS and iOS UX | Arboy with Codex | React/Tauri Mac interface, SwiftUI app, shared visual language and platform-neutral frontend components |
| Tauri Android port | Teammate with Claude | Android shell, native adapters, mobile lifecycle and Android verification; reuse shared React UI |
| Existing compute system | Preserve; coordinate changes | Coordinator, Python workers, deployment and protocol change only for an agreed requirement |

The baseline is FastAPI/SQLite, Strands planning, Python Tiny-SD generation, and phone/browser image finishing. Each laptop generates a whole image; a phone applies the verified four-pixel frame. Credits are sandbox units. Hosting and agent availability must be checked live; historical evidence is in [verification](verification.md).

## Integration rules

- Agree shared React/Tauri file ownership before parallel edits. Keep native operations behind platform adapters; common views and API state remain reusable.
- Gate `DesktopWorkerPanel` with `isMacDesktop`, not generic Tauri presence. Android must not call the prepared Python-worker commands or inherit Mac filesystem assumptions.
- Keep `DesktopWorkerPanel` mounted across Create/Contribute/Activity navigation. Its cleanup intentionally disconnects the managed process; hide inactive sections instead of unmounting it.
- SwiftUI uses native tabs and system controls. Android owns its lifecycle and permission behavior. Foreground-only finishing, explicit Start, Pause and expiry remain product requirements.
- Preserve durable acknowledgement, accepted/cancelled jobs during refresh failures, stale-response fencing, idempotency and exactly-once settlement. Do not change endpoint or pricing contracts as a styling shortcut.
- User-facing copy must be minimal. Show status and the next action; put setup, planning, telemetry and full accounting behind disclosure. See the design guide for the three journeys.

## Focused branches and review

Start from current main and use a branch per coherent change. The native UX work is on `feat/native-ui-journeys`; the Android owner chooses a separate focused branch. Keep main runnable, review shared-file changes together and merge agreed contract changes before dependent implementations.

Do not commit `.env`, credentials, worker identities, databases, model weights, generated test images or personal Xcode signing changes. Preserve the local `apps/ios/PocketGrid.xcodeproj/project.pbxproj` signing edits without including them in the UX commit.

A UI PR should describe the visible outcome, Android integration points and actual verification. Separate production builds, automated tests, simulator visuals and physical-device evidence. A rendered mockup or an earlier real-device run does not verify the redesigned app.

## Claude handoff

Port Tauri to Android using shared Create, Contribute and Activity views. Read the platform gate and lifecycle rules above before changing `apps/web/`. Isolate Android credentials, native notifications, downloads and lifecycle integration. Coordinate shared layout changes with Codex. Do not rewrite coordinator reliability, deployment, model selection or accounting based on the retired handoff. Test on Android and report device/emulator scope explicitly.

## Codex handoff

Implement and verify the macOS Tauri and iOS SwiftUI journeys using the attached visual reference. Keep common React presentation reusable. Preserve native worker startup/shutdown, token handling, opt-in and pause semantics. Build both apps, visually inspect rendered screens, and exercise the real request/contribute/result path when devices are available. Record any device-dependent gap rather than presenting simulated success as a live result.

## Retired workstream context

Earlier collaboration assigned Codex models, benchmarks and routing, and Claude coordinator reliability/deployment. Durable asynchronous planning and hosted deployment now have implementation and historical verification. The earlier proposal below is retained for context; it is not an instruction to repeat that work or extend scope during the native UX phase.

## Historical routing proposals (outside the native UX scope)

Do not equate short prompts with easy images. Typography, exact object counts, relationships, reference images, resolution and requested quality affect model suitability.

1. Code filters options by supported task, available device memory, loaded model, sharing limits, queue, deadline, permission and budget.
2. A rules baseline selects among eligible options. An optional classifier can advise model suitability and confidence.
3. Server code validates the choice. Classifier failure falls back to an eligible local option or an explicit waiting/unavailable state; it never silently spends cloud money.
4. Record the selected model, execution location, reason, estimate and actual outcome.

Proposed pure interface: route(request, candidates, policy) -> decision.
Request includes prompt, count, resolution, quality, deadline and cloud permission. Candidates include model ID and revision, local/cloud location, device or provider ID, task support, memory needs, queue estimate, measured latency, availability and price. Decision includes local/cloud/wait/unsupported, model ID, optional device/provider ID, reason, confidence and estimates. These are proposed fields, not the current API.

A Jev or other Decision API adapter must be optional and evaluated against the rules baseline. Verify the exact provider and API before implementation. A text-model routing product is not automatically an image-quality classifier. Do not add a second expensive planning chain ahead of every image.

Cloud generation requires a real image provider, credentials, cost accounting, timeouts and an output adapter. Akamai chat authentication does not verify its image API. Any cloud output must be labeled as cloud-generated; the phone finishing step should be optional unless the user needs it.

## Earlier evaluation plan (historical; not the current task list)

1. Commit the known working baseline and reproduce one local image on a second developer machine.
2. Benchmark fixed seeds and a small prompt set: simple illustration, multiple objects, spatial relations, typography and a detailed scene. Use comparable resolution; keep cold and warm timings separate.
3. Record human quality ratings, peak memory, generation time, failures and hardware/backend. Test GPU responsiveness and contributor controls, not just image throughput.
4. Measure full request latency: planning, queue, model loading, generation, transfers, finalization and display. Compare routing overhead with compute time saved. Use enough repeated samples before claiming p95 improvements.
5. Add routing behind a configuration flag, with tests for absent devices, unsupported models, budget rejection, classifier failure and explicit cloud permission.
6. Add a durable planning state and return a job ID quickly. Make retries, disconnect recovery and worker reconnects safe. The longer iOS timeout is a temporary mitigation.
7. Improve UI against the settled contract, then deploy and test two real laptops plus the phone. A completed test includes balanced receipts, rejected stale completions and no work after pause/session expiry.

## Access and historical test evidence

Fake workers are useful for lease, retry and accounting checks; they do not prove real inference. Multiple processes on one Mac do not prove physical multi-laptop failover. The current UI flow needs a fresh live check with available laptops and, separately, a physical iPhone.

Each developer configures local credentials independently. If server access is needed, exchange only the teammate's public SSH key, install it in the intended server account while preserving existing keys, and configure the current public IP firewall rule. This document does not grant server access. Keep private keys and API keys out of Git and chat.
