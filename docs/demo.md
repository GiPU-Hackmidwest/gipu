# Five-minute prototype check

1. **Start the coordinator.** From the repository root run `./scripts/server.sh`, then open `http://127.0.0.1:8787`. Join using the configured code. For a shared Wi-Fi demo, set `POCKETGRID_HOST=0.0.0.0` in the shell before starting and use the Mac's LAN address in every client.
2. **Connect a generation laptop.** Follow the worker setup in the root README. Start it with `--share --generate-only`. Use a separate identity file for each worker process. The device should appear online with `image_generate`; signing up alone never enables contribution.
3. **Connect the phone or Mac app.** Set the coordinator URL, join, choose an image-size and session limit, then tap **Start sharing**. It contributes the fixed image export. Enable notifications using the app's explicit permission button if desired.
4. **Ask for the cat.** Request “a cheerful orange cat riding a tiny blue bicycle,” one image,256px,12steps,10credits. Direct scheduling exercises the compute pipeline without a planning model. Enable Strands only with a configured provider. Watch generation on the laptop, export on the phone/app, and the completed image.
5. **Inspect the receipt.** The buyer reserves10, contributors receive6+1 for accepted work, the successful job fee is1, and2 returns. These are sandbox units. Pause contribution and verify the device accepts no new work.

For a visible failover, connect a second generation worker, choose512px/30steps, and stop only the active worker process after progress begins. The same image task restarts on the surviving worker after its lease expires (15seconds without a renewal). Partial work earns nothing; a stale result cannot earn a second payment. If the image finishes before disconnection, submit another job rather than presenting that run as a failure test.

`tests/live_worker_recovery.py` automates abrupt termination, reassignment, actual inference and settlement on one host. `tests/live_agent_routing.py` separately exercises real local Strands decisions and outcome review with controlled clients and the actual image kernel. The verification document distinguishes these tests from a physical-device or Akamai deployment.

Phones do not run the diffusion model in this prototype. Multiple laptops can generate independent variants concurrently; losing a laptop restarts its whole image. This is the demo's honest boundary.
