# Native Mac worker connection verification

Observed October 10, 2026 on Arboy's M4 Pro Mac with 48GB unified memory, using the debug Tauri app built from this change. The coordinator was local; this is not evidence of public Akamai application deployment or physical multi-laptop failover.

## Actual app and model test

1. Built and launched `apps/web/src-tauri/target/debug/bundle/macos/PocketGrid.app`.
2. Used **Connect installed worker** in the existing Mac demo account. The default checkout was found, cached Tiny-SD loaded, and Automatic selected MPS. No dependency installation or model download was performed.
3. The coordinator reported **This Mac image worker** online, `enabled: false`, no active task, and `backend: mps`. Its separate identity file had mode `0600`.
4. Explicitly pressed **Start** and submitted one manual image job: a cat riding a bicycle, 256×256, twelve steps, budget ten sandbox credits. Agent planning was off for this launcher test.
5. The new worker completed generation in one attempt. Accepted task metrics reported `backend: mps`, `model: segmind/tiny-sd`, and `elapsed_seconds: 4.06`. The coordinator credited six units. The returned PNG was downloaded and visually inspected; it contained a generated illustration rather than a blank image.
6. Pressed **Pause**, then **Disconnect worker**. The app displayed Disconnected. Reconnected to the same device identity and verified it was paused again, with no active task.
7. The physical iPhone could not reach the Mac's LAN endpoint, so export on that phone was not tested. Cancelled only this new test job to release the unused reservation: contributors six, fee zero, refund four. The generated preview remains available.
8. Quit the Mac app normally while its reconnected worker was paused. The worker's Python processes disappeared; the previously running coordinator and independent Python processes remained.

The 4.06 seconds is one generation-only smoke measurement. It excludes cold model loading, planning, queueing, final export and full delivery. It is not directly comparable to the earlier 512px CPU benchmark and does not establish image quality, energy savings or throughput.

## Automated checks

- Python worker tests: 33 passed, covering existing cancellation/token isolation plus owner/server identity checks, paused registration, failed registration and readiness ordering.
- Native Rust tests: 11 passed. One intentionally ignored subprocess fixture is invoked by the passing lifecycle tests. Checks include fixed process arguments, environment-only credentials, bounded output, private identities, duplicate-launch prevention, startup timeout, stop/reap and retry.
- TypeScript command-queue tests: three passed, including a delayed cleanup Pause blocking a later Connect.
- Existing job-status tests: seven passed.
- TypeScript/Vite production build and Tauri debug application build: passed.
- An independent agent reviewed the final frontend/native/Python integration and found no release-blocking issue.

## Remaining limits

The Python environment and cached model must already exist in a trusted local checkout. This does not bundle Python or provide a model installer. Normal Disconnect, Leave/reload cleanup and app exit are implemented; automated ordering covers account changes, while live checks above cover Connect, Pause, Disconnect, reconnect and normal Quit. Forced termination and OS crashes were not exercised. Workload controls are not hard GPU-percent or RAM quotas. Physical iPhone finalization, public HTTPS deployment and multi-laptop recovery remain separate verification work.
