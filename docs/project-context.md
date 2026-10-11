# PocketGrid project context

This is the starting context for a developer or coding agent joining PocketGrid. Read it before planning work. It describes the implementation and decisions as of October 10, 2026. Current design-phase ownership is native macOS/iOS UX with Codex and the Tauri Android port with Claude; earlier models-versus-reliability handoffs are retired. Source code and fresh test results take precedence over historical status notes; do not assume an old local process, IP address or credential is still available.

## Product and purpose

PocketGrid puts voluntarily contributed device compute to work on everyday digital tasks. A requester submits a job and a sandbox budget; available devices execute supported tasks; a coordinator verifies acceptable outputs, tracks payments and delivers results. The intended user experience is simple: ask for an image, see where it is being generated, receive it, and understand what it cost. Contributors choose when to share, see activity and earnings, set limits and stop.

The hackathon example is an image of a cat riding a tiny bicycle: does every such request need cloud image-generation infrastructure when an available laptop can do it? The value proposition is using available devices where suitable, reserving powerful cloud compute for work that needs it. It is not a promise of zero cloud usage, lower total energy, lower cost, perfect verification or arbitrary workloads on every device. Those claims need measurements.

There are two roles, and one person can have both:

- Requester: submits work, authorizes a budget, sees progress, downloads outputs and receives a receipt.
- Contributor: explicitly enables a device, accepts compatible tasks within limits and earns sandbox credits for accepted work.

Clicking Generate does not enable contribution. Joining does not enable contribution either. Start sharing is a separate action.

## Actual workload today

The only implemented compute pipeline is text-to-image generation followed by a deterministic image export step. A Python laptop worker generates a whole image with a locally installed diffusion model. A phone, browser or Python finalizer applies a four-pixel teal border and exports a PNG. The coordinator validates the border and unchanged interior pixels.

This is task distribution, not model sharding. Four requested images create four independent generation tasks. Multiple laptops can process different images. A single image's neural network is not partitioned across laptops and phones. A lost generation restarts that image on a compatible worker; no diffusion checkpoint transfer exists.

The phone's export is real computation but intentionally modest. It demonstrates cross-device handoff and accounting, not evidence that shipping an image to a phone saves time or energy. More valuable phone tasks and optional finalization are product proposals, not implemented behavior. Video generation, general code execution and phone-based image-model inference are not implemented.

## Distinguish the two AI systems

| System | Purpose | Execution location | Current implementation |
| --- | --- | --- | --- |
| Planner | Inspect capacity, quote, select preferred workers, submit and review work | Strands SDK in coordinator; model invocation goes to configured provider | Akamai hackathon-chat, local Ollama or optional Bedrock |
| Image generator | Turn prompt into actual image pixels | Contributing laptop | PyTorch/Diffusers with Tiny-SD |

AWS Strands is an agent framework, not an image model or proof that AWS hosts the application. Ollama is a local model runtime; llama3.2 was used for planning during earlier testing. Tiny-SD is a separate image model loaded by the Python worker. The Akamai API key authenticates the hosted planning model; it is not required for SSH or local image inference. Bedrock is an alternative planner provider and needs AWS credentials; it does not use the Akamai key.

Akamai does not discover hardware or install image models automatically. PocketGrid workers report capabilities and limits. Local setup downloads model weights, then caches them. Device benchmarking, model-aware assignment and a richer onboarding installer are future work.

## Components and boundaries

| Path | Responsibility |
| --- | --- |
| services/coordinator/app.py | FastAPI routes, authentication, validation and lifecycle loops |
| services/coordinator/store.py | SQLite transactions, devices, jobs, leases, artifacts and credit ledger |
| services/coordinator/agent.py | Strands tools, provider adapters, routing preferences and bounded reviews |
| services/coordinator/server.py | Load local environment and launch coordinator |
| workers/python/worker.py | Device registration, heartbeats, claims, local image inference, cancellation and completion uploads |
| apps/web/ | React/TypeScript interface and browser image finalizer |
| apps/web/src-tauri/ | Rust/Tauri desktop shell; explicit Connect launches a prepared Python inference worker as a managed local process, initially paused |
| apps/ios/ | SwiftUI app, Keychain sessions, foreground image processing and local notifications |
| deploy/ | Coordinator Docker image, Compose, Caddy HTTPS and workshop instructions |
| benchmarks/ | Independent local-model tests and recorded exploratory CPU evidence |
| tests/ | Coordinator, routing, adapter, lifecycle, worker and live integration checks |

Historical hosting evidence: the earlier shared demo used a coordinator on Arboy's Mac. The Akamai Linode subsequently served the coordinator over public HTTPS. A real local Tiny-SD worker completed generation, export, delivery and settlement through it in manual mode on October 10; image computation stayed on the Mac. That check observed server commit 3544d5f; it does not establish the currently deployed revision. At the design-phase handoff, the user reported hosted Akamai agent mode enabled and two laptop workers previously online/sharing. Recheck live health and device availability before a demo. See [hosted verification](verification.md#hosted-real-worker-check).

## Request through delivery

1. A client joins through POST /api/sessions with the grid join code, receives a session bearer token and registers its device. New devices are paused. A fresh session receives 100 sandbox credits; a manual top-up of one local demo account to 1000 did not change this default.
2. The requester submits POST /api/jobs with prompt, image count, dimensions, steps, budget, request_id and use_agent. With an agent selected, the endpoint persists the request, reserves the budget and returns `planning` immediately; a background planner then queues tasks or fails the job with a refund (see docs/protocol.md).
3. With agent planning enabled, the background planner claims the request and Strands invokes the configured chat model and executes bounded tools to inspect devices, quote, submit and inspect the job. The model cannot authorize a larger budget or alter the user's prompt/count. Without agent planning, the deterministic pipeline is explicitly labeled manual.
4. The store reserves the authorized budget transactionally and creates generation tasks. If no eligible workers are available, the job waits in the queue. This is not a request-delivery failure.
5. Enabled workers poll POST /api/devices/{id}/claim. Eligible work gets a lease. The worker sends heartbeats and progress, respecting its session and pixel limits.
6. The laptop executes the image model locally, encodes PNG bytes and uploads them to POST /api/tasks/{id}/complete with its device token and lease ID. No cloud image-generation API is called by this path.
7. The coordinator validates the live lease and output format/dimensions, stores the image, credits the accepted generation task and creates a finalization task. Format/dimension checks do not establish prompt fidelity or prove an untrusted worker performed honest computation.
8. An enabled finalizer claims that task, downloads the source image through the authenticated coordinator API, applies the fixed transform and uploads the result. The coordinator verifies expected pixels before crediting the task.
9. Clients poll /api/state and fetch images through /api/images/{artifact_id}. They receive the output from the coordinator, not through direct peer-to-peer connections. After all tasks finish, the store charges the job fee and returns unused credits.

Workers use HTTP polling, not a WebSocket mesh. There is no peer discovery, peer-to-peer transport or automatic installation on phones.

## Essential invariants

- Contribution is explicit, timed and revocable. A phone/browser pauses on backgrounding and requires another explicit Start on return.
- One active task per device. Current controls include CPU-thread count, maximum pixels and session duration. They are not hard system-wide CPU/GPU-percent or RAM quotas.
- Worker heartbeats normally occur every three seconds; task leases last fifteen seconds. Stale lease IDs cannot publish accepted results or earn payment.
- Python workers stop active work after prolonged loss of heartbeat confirmation. Cancellation is checked at denoising boundaries; it is not an instantaneous interruption of GPU instructions. Model memory stays allocated until the worker exits.
- Lease expiry must remain independent of slow model calls. Routing is a preference with fallback, not a guarantee that a worker will stay available.
- Reservations, accepted work, refunds and fees must remain transactionally consistent. Duplicate completion must not pay twice. Completed work is immutable.
- Agent actions are bounded and validated by code. Workers execute fixed supported functions, not generated arbitrary code.
- Credentials are bearer tokens. Do not put them in URLs, logs, screenshots or Git. Workers must not forward credentials to task-supplied external URLs.

Initial routing preferences last up to 45 seconds; finalization receives its own window when ready. Failed attempts can fall back. Failure/terminal events have separately claimed agent reviews with bounded retries. Review updates are fenced to the task attempts they inspected. See docs/protocol.md and tests/test_routing.py for the exact contract.

## Credits and sponsor roles

Current prices are six credits per accepted generated image, one per accepted export, and one platform fee per successfully completed job. The full chosen budget is reserved first. Unused reservation is refunded. Cancelling preserves payments for completed work, refunds the remainder, and does not charge a success fee.

Examples:

- One image with budget 10: 6 generation + 1 export + 1 fee, refund 2.
- Two images with budget 29: 12 generation + 2 export + 1 fee, refund 14.
- Four images with budget 40: 24 generation + 4 export + 1 fee, refund 11.

These are integer sandbox credits, not dollars, cash payouts or purchased AI credits. Flex's proposed relevance is the reserve/settle/refund/receipt flow; no Flex API or real-money integration exists. Do not invent Flex endpoints or claim sponsor eligibility without checking the actual competition requirements.

Akamai has two separate roles: hosted chat-model access, already authenticated, and verified Linode coordinator hosting in manual mode. Strands supplies agent orchestration. DevRev was optional and has not been integrated. A sponsor reference in a pitch does not prove a completed integration.

## Historical model work and future proposals

Tiny-SD is the live default. Benchmark PR #1 was merged into main before this guide was written. It adds pinned Tiny-SD, SD-Turbo and SDXL-Turbo profiles, but blocks experimental models in worker run mode because the coordinator currently has no model-selection contract. They can be prepared and tested without joining the grid.

The initial 512px CPU comparison used two threads and six measured images per model: Tiny-SD at twelve steps had a 16.725-second median; SD-Turbo at four steps had a 5.372-second median. Sampled peak process RSS was 7898.5 MiB and 11236.3 MiB. The baseline overlapped model downloading/loading and had uncontrolled background activity. These are exploratory generation-only measurements, not end-to-end latency, GPU performance or proof of quality superiority. Visual prompt-following errors occurred in both. See benchmarks/cpu-baseline.json.

Two threads were a conservative demo setting, not the Mac's capacity. Arboy's Mac has an M4 Pro and 48GB unified memory. The tool process reported MPS unavailable, while the user's normal Terminal reported it available. A subsequent native Mac app test loaded Tiny-SD on MPS, connected paused, and generated a real 256px image at twelve steps in 4.06 seconds, accepted by the coordinator for six credits. This is one generation-only smoke measurement, not a quality or throughput benchmark and not comparable to the 512px CPU baseline. Broader GPU comparisons and a better image model were earlier workstream goals; they are outside the current native UX scope.

Future routing may choose a local model or an explicitly permitted cloud image provider. Filter by capabilities, hardware, loaded model, queue, quality requirements, deadline and budget before any optional classifier. Short prompts are not necessarily easy images. Jev/Decision API integration is only a proposal; no classifier or cloud image fallback is currently implemented. Keep planning-provider choice separate from image-model choice.

## Historical verification and checks still to reproduce

Verified during development: actual local Tiny-SD generation; accepted results and sandbox settlement; native Mac and simulator export; live Strands/Ollama routing/recovery with controlled clients; local Docker coordinator with a real laptop worker; successful Akamai chat authentication; a real Akamai Strands job submission; Linode SSH login; a real laptop image job through the hosted HTTPS coordinator with a balanced receipt; physical teammate iPhone installation, joining and job submission.

The latest observed physical-phone job had two completed laptop generations and queued finalization tasks while phone sharing was paused. Do not claim successful physical-phone finalization from that observation. Do not claim multi-laptop physical failover from tests using multiple processes on one Mac.

Recheck the deployed revision and hosted planner before the current UI end-to-end test. Physical-phone finalization and two physical laptops recovering a lost task still require direct evidence. AWS Bedrock, GPU model comparisons and real payment integration remain separate future work if selected. Source docs may contain earlier snapshots; this status does not substitute for checking fresh runtime state.

Known issues and lessons:

- Generate could time out on iPhone after 20 seconds while Strands was still working. A temporary client fix allows 180 seconds for job creation and reuses request IDs for unchanged retries in the same app session. The coordinator now acknowledges agent requests immediately with a durable `planning` state, so clients can return to the normal timeout once they display and cancel `planning` jobs.
- Sharing sessions expire. A connected worker can be paused and unavailable. Show this explicitly in the UI.
- Returning from background pauses phone contribution. Keep it foregrounded during the current demo.
- A LAN coordinator must bind to 0.0.0.0; physical devices use the Mac's current LAN address, not localhost. Same-network connectivity is necessary and some networks isolate clients.
- SSH firewall /32 rules use public IPs and can go stale when hotspots or networks change. API keys and SSH keys solve different problems.
- An earlier Akamai 401 was resolved by saving the working workshop key. Do not assume the provider remains down based on old docs.

## Current design-phase ownership

- Arboy with Codex: native macOS Tauri and iOS SwiftUI UX, shared visual language, supporting platform-neutral React components, and focused client verification.
- Teammate with Claude: port the Tauri application to Android, reusing shared UI while isolating Android lifecycle and native integrations.
- Preserve coordinator, Python model workers, deployment and protocol. A specific UI requirement that needs a contract change must be agreed across workstreams first.

The earlier split of Codex models/routing/UI versus Claude reliability/deployment is retired. Durable asynchronous planning and hosted deployment have implementation and historical verification already; do not treat the old handoff as a request to rebuild them. Model experiments and proposed routing contracts above are background, not current deliverables.

Use three destinations: **Create**, **Contribute**, **Activity**. Joining precedes those journeys. Keep user-facing text very short; reveal setup, processor, planning and accounting detail only when needed. See [native UI design](native-ui-design.md) for the reference translation, screen map, tokens and Android integration constraints.

Coordinate shared React/Tauri edits before starting. `isMacDesktop` must gate Mac worker integrations; a Tauri runtime can also be Android. Keep `DesktopWorkerPanel` mounted when changing destinations because its cleanup stops the managed worker. SwiftUI retains native tab navigation and foreground-only contribution. Preserve explicit opt-in, durable request acknowledgement, stale-response fencing, cancellation and receipts.

Read [team development](team-development.md) for the current handoffs. Historical test evidence describes its stated devices and revision, not today's live availability.

## Deployment and trust boundaries

The prepared stack is one FastAPI coordinator with SQLite and stored images in a persistent Docker volume, behind Caddy on ports 80/443. Port 8787 stays internal in the cloud stack. Do not add multiple coordinator replicas over a shared SQLite file. A database migration is a separate design change, not necessary for the current small demo.

Contributors connect outbound to the coordinator. They do not need public inbound ports. For local testing, the coordinator can use HTTP on a trusted LAN; internet deployment needs HTTPS. Joining creates a new session rather than a durable email/password account. The invite-only demo exposes assigned inputs and job outputs to grid members/workers; do not present it as tenant-isolated confidential processing.

Generation verification is deliberately limited. Receiving a valid PNG of the requested dimensions does not prove honesty, model identity or semantic accuracy. Stronger verification, abuse handling, real financial settlement, robust account recovery and production isolation are separate launch work.

## Repository workflow

Use separate clones and feature branches, open focused PRs and keep main runnable. Do not commit .env, SSH keys, session/device tokens, local database files, generated images, downloaded weights or personal Xcode signing-team settings. Clone setup does not recreate local demo balances or device identities. Share necessary credentials through a private channel, never a PR.

Begin with README.md for commands, docs/protocol.md for interfaces, docs/team-development.md for ownership, deploy/README.md for hosting and benchmarks/README.md for model experiments. Historical evidence files document their original test conditions and are not a live status dashboard.
