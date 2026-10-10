# Akamai deployment

The supplied HackMidwest repository confirms this VM + Docker approach. See [workshop mapping](workshop.md) for the exact differences, account requirements and Akamai chat configuration. Its team inference key is separate from cloud-management credentials.

The coordinator stores the queue, outputs and ledger. It never downloads or runs the diffusion model. Contributing laptops connect outbound over HTTPS; browsers/iPhones process image exports. The same container can run on an Akamai Cloud (Linode) compute instance. A small CPU instance is sufficient to begin measuring the prototype; no cloud GPU is needed.

1. Use an existing Akamai Ubuntu instance with Docker Engine and Compose v2. Point a domain's A record at it. Allow inbound TCP80/443; restrict SSH to your own IP. Do not expose8787 publicly.
2. Copy this repository, excluding secrets, model caches and local runtime folders. On the instance, copy `deploy/.env.example` to `deploy/.env`; set the domain and a private join code. Keep that file mode0600.
3. Run `docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build` from the repository root. Caddy obtains HTTPS. SQLite and images remain on the `grid-data` volume.
4. Open `https://YOUR_DOMAIN`. Use this URL in the iPhone app, desktop connection screen, and worker `--server` argument. Every collaborator joins using the private code and explicitly enables sharing.
5. Verify `/api/health`, create a local-device image job, then disconnect the laptop and inspect reassignment and the final receipt.

For Bedrock, enable `POCKETGRID_AGENT_MODE=bedrock`, supply an accessible tool-capable `POCKETGRID_BEDROCK_MODEL` and credentials restricted to invoking that model. Prefer temporary credentials; never paste them into chat or commit `.env`. Plan calls incur provider charges. The deterministic mode requires no AWS account; it is explicitly labeled and is not an agent demonstration.

This is a single coordinator. Do not scale replicas or place the SQLite file on a network filesystem. Back up its database and image directory together before replacing the volume. A production migration needs Postgres transactions/locking, durable object storage, abuse controls, authenticated account recovery, worker trust/verification and a real payment provider. The ledger here is sandbox accounting with no cash value; there is no Flex payment API integration.

Deployment has not been claimed as live until an actual Akamai host is configured and a job is tested there. Building a local repository does not establish sponsor hosting eligibility.

The deployment image has been built and tested locally with a real laptop model worker and correct final settlement. To reproduce without touching the demo grid:

```sh
docker build -f deploy/Dockerfile -t pocketgrid-prototype:local .
.venv/bin/python tests/container_smoke.py
```
