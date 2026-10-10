# Prototype verification — October 10, 2026

These are observed checks on the development Mac. Multiple worker processes below are **logical devices on one physical host**. A three-laptop/three-phone network test has not been performed.

| Check | Observed result |
|---|---|
| Real local text-to-image | Pinned Segmind Tiny-SD, actual PyTorch CPU inference:256×256/12steps in3.082s;512×512/24steps in28.963s after loading. These are individual observations, not performance guarantees. |
| Real Strands routing and outcome review | SDK1.59.0 with Ollama `llama3.2:latest`; chose actual device IDs, blocked an unselected client, rerouted an injected failure to attempt2, inspected actual local diffusion output references and checked the final8credit charge/2credit refund. The image kernel ran on CPU in4.029s. Controlled clients and an in-process coordinator on one host were used to verify routing order. |
| Browser handoff | Live browser canvas completed the generated image's export, earned1credit and displayed the final image/receipt. |
| Abrupt disconnect | Killed the exact active worker subprocess with SIGKILL. Same task was assigned to the surviving worker with a new lease and attempt2 after14.7s. |
| Recovery result | Actual512×512/30step image completed on surviving worker. Original worker earned0. Receipt:10reserved →7contributors +1fee +2refund. |
| Pause during inference | Denoising cancelled; no accepted image,0spent,10refunded. |
| Swift client + actual image processor | Submitted generation job, claimed/processed actual exports, decoded receipt, retried completions idempotently and paused successfully.2exports accepted,2earned; retries paid nothing extra. |
| iOS native builds | Generic simulator arm64+x86_64 and unsigned physical iOS arm64 compiled with Xcode26.2. |
| iOS native runtime | Xcode launched the app in iPhone17ProMax/iOS26.2 Simulator. Two real image jobs completed with native exports, image display, correct receipts, earned credits and a visible native notification banner. Manual Pause and Start → Home → reopen both left contribution paused. |
| iOS exact pixel check |65,536pixels checked, border/interior exact; over-limit image rejected. Lifecycle race tests also pass. |
| Coordinator and agent regressions |43tests: conservation, duplicate settlement, concurrency, lease recovery, resource limits, exact export verification, selected-device enforcement, fallback, per-stage preference windows, stale review fencing, SDK tool execution/budgets and slow-model isolation. Scripted models in unit tests are separate from the real Ollama check above. |
| Akamai workshop adapter |Actual Strands/OpenAI adapter tested against simulated HTTP responses for tool-based routing and outcome review, missing-key handling and a non-retried401. Docker image rebuilt with the added dependency and Compose configuration validated. Authenticated workshop inference remains unverified until the saved key is available. |
| Python worker regressions |4tests: frame/interior correctness, pause cancellation, denoising-step cancellation, and refusing external source URLs before forwarding credentials. |
| Web bundle |TypeScript and Vite production build passed; live browser workflow exercised. |
| Native Mac app |Tauri debug `.app` bundled and launched. Native login/network calls worked; an image job completed through laptop diffusion → Mac WebKit export. Receipt charged8/refunded2; Mac contributor earned1. Native notification opt-in succeeded; OS banner delivery was not asserted. |
| Deployment container |Final coordinator image rebuilt and ran as uid10001, served the production web bundle, and coordinated a real host-worker image job in3.402s plus export. Receipt correct; runtime confirmed no PyTorch installed in the coordinator. Compose configuration validates. |

[Sanitized recovery evidence](evidence/recovery.json) records task/worker IDs and settlement. [The resulting image](evidence/cat-bicycle.png) was created during this test, not supplied as a placeholder.

[Strands routing evidence](evidence/agent-routing.json) records actual tool choices and recovery/terminal reviews. The local3B model initially called tools out of order and sometimes encoded ID arrays as strings. The final workflow exposes one useful tool per stage within a shared12model-call/12tool-call/90second budget. The Ollama adapter decodes only the two ID-array fields when they contain a valid JSON list of strings; device IDs and permissions still undergo normal server validation. There is no automatic fabricated plan when a model fails.

After restarting the actual HTTP coordinator with the final agent implementation, its background loop reviewed a previously completed Strands job and persisted one successful review. The health endpoint remained available. This checks the runtime wiring in addition to the isolated routing test.

The portable recovery script was also run on a fresh, isolated coordinator. It killed its own worker after nonzero denoising progress, reassigned the same task after15.15s, verified the same accounting and pause behavior, and tore down all its child processes. Its local logs are ignored under `workers/python/.cache/isolated-recovery/`.

[Container evidence](evidence/container.json) records the isolated deployment smoke test. `tests/container_smoke.py` starts a container and a local model worker, checks the full receipt and non-root/model-free server runtime, then stops both. Docker became available after starting the installed desktop app; the earlier daemon limitation was resolved. This local container check is not an Akamai-hosted test.

## Remaining external checks

- **Akamai:** deployment files exist, but no target host/domain has been provided and no live Akamai deployment is claimed.
- **Bedrock:** integration is implemented; the existing default AWS credential check returned `InvalidClientTokenId`. Live AWS model invocation remains unverified. The SDK was tested with a real local model instead.
- **Physical devices:** install on signed iPhones and other laptops, measure Wi-Fi transfer costs, test sleep/background/thermal behavior, and repeat failover. The iOS Simulator UI and notification permission/banner checks passed through ordinary Xcode Run; these do not measure physical-phone power or network behavior.
- **Payments:** a transactionally tested sandbox ledger is implemented; no cash collection, payouts, or Flex API integration.
- **DevRev:** not integrated into this first compute prototype.

There is no evidence yet of lower overall energy use or cheaper total operation. Model warmup, verification, network traffic, device availability and result quality all matter. Generated-image acceptance checks PNG format/dimensions, not the semantic correctness or honesty of an untrusted contributor; export acceptance checks every pixel.
