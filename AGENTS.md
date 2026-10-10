# PocketGrid development instructions

Read docs/project-context.md first, then README.md, docs/protocol.md and docs/team-development.md before changing behavior.

- Preserve explicit device opt-in, Pause, session expiry, lease fencing and exactly-once credit settlement.
- Keep secrets, worker identity files, generated images and local databases out of Git. Use .env.example for configuration names only.
- Treat cloud image generation as a new optional capability. Never silently replace local computation with cloud output. Enforce user permission and budget in server code.
- Keep agent model-provider selection separate from image-model and device selection. Akamai chat currently powers Strands planning; laptop workers generate images.
- Ownership: Arboy with Codex owns models, workers, standalone routing and UI; the teammate with Claude owns coordinator reliability and deployment. Coordinate API contracts before cross-boundary changes.
- Use one branch per focused change. Coordinate protocol, ledger and dependency changes across workstreams.
- Do not replace the working Tiny-SD path until a replacement has measured results and a fallback.
- Run checks relevant to changed behavior. Record actual measurements and hardware; do not present vendor timings as local results.
- Do not commit personal Xcode signing changes as required project defaults.
