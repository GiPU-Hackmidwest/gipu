# Full-goal completion audit

The requested end state is a usable device-compute prototype, including actual Akamai coordination, meaningful Strands routing/recovery, native controls and settlement. A local repository or a green unit suite alone does not prove all of it.

| Requirement | Evidence or missing input | Status |
|---|---|---|
| Project at the requested path | Git repository, source, dependencies and run instructions exist at `/Users/arboy/dev/hackathon-projects/hackmidwest/pocketgrid`. | Implemented |
| Ordinary image-generation request executed off cloud inference | Actual Tiny-SD CPU generation and accepted outputs; isolated container confirmed it has no PyTorch runtime. | Verified locally |
| Distributed workers and disconnect recovery | Two independent worker processes, abrupt SIGKILL, new fenced lease on the same task, completed result and no payment to lost worker. | Verified on one host; physical multi-device test pending |
| AWS Strands selects execution devices | Real Strands/Ollama selected device IDs; an unselected client could not take preferred work. Stage preferences and fallback are validated by the coordinator. | Verified with a local model and controlled clients |
| Strands checks outcomes and adjusts failed plans | Live model rerouted an injected worker failure to another device, inspected actual diffusion output references and the terminal receipt. Durable claims reject stale reviews; a slow review cannot block lease expiry. | Verified locally; Bedrock invocation pending credentials |
| Akamai hosts coordinator | Deployable image and Caddy/Compose config have been built/validated locally; no Akamai host or domain provided. | Missing external target |
| Native Mac app | Tauri app built/launched; actual generation-to-Mac export job and receipt observed; native notification opt-in and pairing control exercised. | Verified locally |
| Native mobile app | SwiftUI simulator/device builds; actual iOS Simulator UI completed two real image jobs, displayed images/receipts, processed exports, and stayed paused after Home/reopen. | Verified in Simulator; physical iPhone pending |
| Explicit start, limits, live usage and stop | Server/worker tests plus live pause cancellation; shorter-session and partial-limit regressions fixed. Native/browser lifecycle guards prevent delayed Start after backgrounding. | Verified at tested scope |
| Notifications for work and credits | In-app events observed; native notification opt-in verified on Mac and iOS. Actual iOS banner for started work observed in Simulator. Closed-app push is outside this prototype. | Verified at tested scope |
| Budget reserve, accepted-work payment, unused refund, receipt | Conserved integer ledger; duplicate submissions/completions do not pay twice; end-to-end receipt10=7+1+2. | Verified sandbox credits; no real-money payout claim |
| DevRev | User described it as optional. No connector added to this compute prototype. | Optional, omitted |

The Akamai workshop repository confirms a separate activated cloud account/SSH access is needed for its VM deployment path. PocketGrid now also supports the workshop's `hackathon-chat` model through Strands; adapter tests use simulated HTTP responses, and a live authenticated call is pending the saved team key's location. The team inference key does not grant cloud-management access. See `deploy/workshop.md`.

Valid AWS credentials are needed only if testing the optional Bedrock provider. The real AWS Strands SDK is already verified with local Ollama and can use the Akamai adapter without Bedrock. No cloud deployment, physical-device execution or cash payout is inferred from local tests.
