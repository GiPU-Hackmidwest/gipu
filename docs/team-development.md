# PocketGrid team development

Keep the working device-compute demo available while improving image quality, routing, reliability and presentation. The agreed split is: Arboy with Codex owns models, routing and UI; the teammate with Claude owns reliability and deployment.

Read [the full project context](project-context.md) for the detailed architecture, actual device roles and verified status.

## Current baseline

Python coordinator with SQLite, AWS Strands planning through the Akamai chat endpoint, Python Tiny-SD laptop workers, SwiftUI phone finalizers and React/Tauri clients. Image tasks are independent whole-image computations. Phones do final processing, not distributed diffusion layers. Credits are sandbox units. Linode SSH is verified; application deployment remains pending. Cloud image generation is not implemented.

## Ownership

| Workstream | Owner | Main files | First deliverable |
| --- | --- | --- | --- |
| Model quality and routing | Arboy with Codex | workers/python/, new services/routing/, new benchmarks/ | Reproducible Tiny-SD versus SD-Turbo versus SDXL-Turbo benchmark and pure routing interface |
| Reliability and deployment | Teammate with Claude | services/coordinator/, deploy/, coordinator tests | Durable asynchronous submission, reliable recovery and public HTTPS deployment |
| UI and demo | Arboy with Codex | apps/web/, apps/ios/ | Clear planning, waiting, generating, finishing and completed states; actionable sharing controls |

Claude owns coordinator integration, including agent.py, store.py, persistence and server-side routing enforcement. Codex owns the standalone routing decision module, model adapters, worker changes and client presentation. Agree request/response fields in docs/protocol.md before implementing cross-boundary changes. Coordinator schemas, pricing and shared dependencies require a coordinated PR; avoid editing the same files simultaneously.

## Routing design

Do not equate short prompts with easy images. Typography, exact object counts, relationships, reference images, resolution and requested quality affect model suitability.

1. Code filters options by supported task, available device memory, loaded model, sharing limits, queue, deadline, permission and budget.
2. A rules baseline selects among eligible options. An optional classifier can advise model suitability and confidence.
3. Server code validates the choice. Classifier failure falls back to an eligible local option or an explicit waiting/unavailable state; it never silently spends cloud money.
4. Record the selected model, execution location, reason, estimate and actual outcome.

Proposed pure interface: route(request, candidates, policy) -> decision.
Request includes prompt, count, resolution, quality, deadline and cloud permission. Candidates include model ID and revision, local/cloud location, device or provider ID, task support, memory needs, queue estimate, measured latency, availability and price. Decision includes local/cloud/wait/unsupported, model ID, optional device/provider ID, reason, confidence and estimates. These are proposed fields, not the current API.

A Jev or other Decision API adapter must be optional and evaluated against the rules baseline. Verify the exact provider and API before implementation. A text-model routing product is not automatically an image-quality classifier. Do not add a second expensive planning chain ahead of every image.

Cloud generation requires a real image provider, credentials, cost accounting, timeouts and an output adapter. Akamai chat authentication does not verify its image API. Any cloud output must be labeled as cloud-generated; the phone finishing step should be optional unless the user needs it.

## Evaluation and milestones

1. Commit the known working baseline and reproduce one local image on a second developer machine.
2. Benchmark fixed seeds and a small prompt set: simple illustration, multiple objects, spatial relations, typography and a detailed scene. Use comparable resolution; keep cold and warm timings separate.
3. Record human quality ratings, peak memory, generation time, failures and hardware/backend. Test GPU responsiveness and contributor controls, not just image throughput.
4. Measure full request latency: planning, queue, model loading, generation, transfers, finalization and display. Compare routing overhead with compute time saved. Use enough repeated samples before claiming p95 improvements.
5. Add routing behind a configuration flag, with tests for absent devices, unsupported models, budget rejection, classifier failure and explicit cloud permission.
6. Add a durable planning state and return a job ID quickly. Make retries, disconnect recovery and worker reconnects safe. The longer iOS timeout is a temporary mitigation.
7. Improve UI against the settled contract, then deploy and test two real laptops plus the phone. A completed test includes balanced receipts, rejected stale completions and no work after pause/session expiry.

## Git workflow

Use a private shared repository initially. Each developer clones separately, creates a feature branch from main, and opens small PRs. Keep main runnable. Suggested branches: feat/model-benchmarks, feat/image-routing, fix/job-submission, feat/grid-status-ui. Merge contract changes first, then dependent implementations.

Do not share .env through Git or chat. Use separate credentials where possible and configure each machine independently. Local session balances, identities and installed model weights do not travel with a clone. Read README.md for installation and verification commands.

## Teammate onboarding and access

The reliability and deployment work does not require local image models. Start with the coordinator environment and deterministic tests. Use fake workers in tests to exercise leases, retries and accounting; do not describe those tests as proof of real image generation. Arboy supplies a real laptop worker for the joint end-to-end test.

First tasks:

1. Clone the repo, read AGENTS.md and docs/protocol.md, and follow README.md setup. Keep credentials in the ignored local .env.
2. Run the coordinator tests listed in README.md before changing behavior. Start in manual mode for provider-independent development; use the Akamai planner only when credentials are configured.
3. On a fix/job-submission branch, add durable planning and prompt acknowledgement, retry idempotency and recovery after process restart. Coordinate the new client-visible states with Arboy before changing response contracts.
4. On a separate deployment branch, prepare Linode Docker/Caddy HTTPS hosting, persistent data, health checks, restart behavior and documented recovery. Follow deploy/README.md and deploy/workshop.md. The coordinator does not need image-model weights or a GPU.
5. Run a joint test with Arboy's real laptop worker and the physical phone, including disconnects, pause/session expiry and balanced receipts.

For SSH access, the teammate generates or reuses their own key pair and sends only the public .pub contents to Arboy. Install that public key in the intended server account's ~/.ssh/authorized_keys on the existing Linode; adding a key to Cloud Manager alone does not install it retroactively. Preserve existing keys. Allow the teammate's current public IP on the SSH firewall rule and verify login. Share the server address and username separately; private SSH keys and API keys never go into the repository. Server access has not been granted by this document.

## Claude handoff

Read AGENTS.md, README.md, docs/protocol.md and this guide. Own coordinator reliability and Akamai Linode deployment. You do not need local image models to start. Run the deterministic coordinator tests, then create a feature branch for durable asynchronous job planning, fast acknowledgement, retry idempotency and restart recovery. Preserve device opt-in, session expiry, lease fencing and exactly-once settlement. Own services/coordinator/, deploy/ and their tests. Coordinate API changes with Arboy, who owns the model workers, standalone routing module and UI. Keep model weights off the coordinator. Prepare Docker/Caddy HTTPS deployment and validate the real device flow with Arboy's worker. Submit focused PRs with tests and deployment instructions.

## Codex handoff

Own local image-model quality, benchmarks, model-selection logic and the web/Tauri/SwiftUI interfaces. Preserve Tiny-SD as a working fallback. Benchmark model quality, latency and memory on the actual laptop before selecting a replacement. Implement routing as a separate module with a reviewed contract for Claude to integrate into the coordinator. Expose local/cloud execution, planning and queue states, actual stage timings, workload controls and receipts. Coordinate server schema and pricing changes with the teammate; do not independently rewrite agent.py or store.py. Supply the real image worker for joint reliability and deployment validation.
