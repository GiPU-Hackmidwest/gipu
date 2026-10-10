# PocketGrid team development

Keep the working device-compute demo available while improving image quality, routing, reliability and presentation. The following ownership split is proposed and can be reassigned.

## Current baseline

Python coordinator with SQLite, AWS Strands planning through the Akamai chat endpoint, Python Tiny-SD laptop workers, SwiftUI phone finalizers and React/Tauri clients. Image tasks are independent whole-image computations. Phones do final processing, not distributed diffusion layers. Credits are sandbox units. Linode SSH is verified; application deployment remains pending. Cloud image generation is not implemented.

## Ownership

| Workstream | Proposed owner | Main files | First deliverable |
| --- | --- | --- | --- |
| Model quality and routing | Teammate with Claude | workers/python/, new services/routing/, new benchmarks/ | Reproducible Tiny-SD versus SD-Turbo versus SDXL-Turbo benchmark and pure routing interface |
| Reliability and deployment | User with Codex | services/coordinator/, deploy/, coordinator tests | Durable asynchronous submission, reliable recovery and public HTTPS deployment |
| UI and demo | User with Codex initially | apps/web/, apps/ios/ | Clear planning, waiting, generating, finishing and completed states; actionable sharing controls |

Coordinator integration, schemas, pricing and shared dependency changes require a coordinated PR. Avoid two people editing agent.py or store.py simultaneously. UI work can move to the teammate after the model PR merges.

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

## Claude handoff

Read AGENTS.md, README.md, docs/protocol.md and this guide. Own model benchmarking and a standalone routing module. Preserve Tiny-SD and existing worker protocol. Compare Tiny-SD, SD-Turbo and SDXL-Turbo using real local measurements. Propose model capability metadata and a pure routing interface before modifying coordinator schemas. Keep cloud execution disabled until its provider, user permission and budget enforcement are implemented. Submit focused PRs with evidence and setup instructions.

## Codex handoff

Own coordinator reliability, deployment and initially UI. Preserve the ledger and worker lease invariants. Replace synchronous long-running submission with durable planning and fast job acknowledgement. Coordinate routing integration with the teammate through a reviewed schema change. Expose real stage timings and actionable device status, then validate the image flow across physical devices and Linode HTTPS.
