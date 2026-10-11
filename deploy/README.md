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

## Linode deployment without a domain

Every Linode has a provider hostname, `A-B-C-D.ip.linodeusercontent.com` (its IPv4 address with dashes), that already resolves to the instance and is its reverse DNS name. Let's Encrypt issues certificates for it, so it can be `POCKETGRID_DOMAIN` until the team has a domain. Switching to a real domain later only changes that value; clients must then use the new URL.

The current team instance was set up from a plain Ubuntu 24.04 image, not this cloud-init file. Install and start the stack as root:

```sh
apt-get install -y docker.io docker-compose-v2 && systemctl enable --now docker
# A 2GB plan needs swap for the web build inside docker build.
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

From a clean local checkout, upload only committed files for the chosen commit. This excludes `.env`, data, virtualenvs and model caches by construction:

```sh
git archive --format=tar.gz <commit> | ssh root@HOST 'mkdir -p /opt/pocketgrid && tar -xzf - -C /opt/pocketgrid && echo <commit> > /opt/pocketgrid/DEPLOYED_COMMIT'
```

On the server, run `openssl rand -hex 16` in the shell to generate the join code. Create `/opt/pocketgrid/deploy/.env` once with mode 0600 and set `POCKETGRID_JOIN_CODE` to the resulting hexadecimal value, along with the domain and planner settings. Compose `.env` files do not execute shell commands; do not put the generation command in the file. Edit it over SSH only; never paste the join code or provider key into the repository or a PR. Then run, from `/opt/pocketgrid`:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
```

Verify: `curl https://HOST/api/health`; HTTP redirects to HTTPS; port 8787 is unreachable from outside; a job completes with a balanced receipt; and after `docker compose ... down && ... up -d` (never `down -v`) the job, images, sessions and certificate remain. Containers use `restart: unless-stopped`, and Docker is enabled at boot.

## Operations and recovery

All commands run from `/opt/pocketgrid` with `--env-file deploy/.env -f deploy/compose.yaml`.

- **Status and logs:** `docker compose ... ps`, `docker compose ... logs --tail 100 coordinator` (or `https` for certificates).
- **Upgrade:** upload the new commit as above, update `DEPLOYED_COMMIT`, then `up -d --build`. The `grid-data` volume keeps the database and images. Active leases expire and are reassigned if the coordinator is down longer than a lease.
- **Change settings** (join code, planner, Akamai key): edit `deploy/.env`, then `up -d` to recreate the coordinator. Changing the join code does not revoke existing sessions.
- **Backup:** stop the coordinator, copy the volume, start again. The SQLite file and `images/` must be copied together:
  `docker compose ... stop coordinator && docker run --rm -v deploy_grid-data:/data -v /root/backups:/out alpine tar -czf /out/grid-$(date +%F-%H%M).tgz -C /data . && docker compose ... start coordinator`
- **Restore:** stop the coordinator and preserve the current volume for rollback. Validate the backup, then extract its database and images together into a new, empty volume; preserve ownership for the coordinator user (UID/GID 10001). Point the Compose `grid-data` volume at that restored volume with an override specifying `external: true` and its `name`, and include that override in subsequent Compose commands before starting the coordinator. Never extract over an existing database directory: leftover SQLite WAL files can replay changes that are not in the backup.
- **Certificates:** Caddy stores them in `caddy-data`. Keep that volume; deleting it forces reissue and can hit Let's Encrypt rate limits.
- **SSH firewall:** contributor and client traffic only needs 80/443. Restrict the port 22 rule to known addresses when possible.

Deployment has not been claimed as live until an actual Akamai host is configured and a job is tested there. Building a local repository does not establish sponsor hosting eligibility. The Linode deployment above has been tested with simulated workers; a real laptop worker and a physical finalizer against the public URL remain to be verified.

The deployment image has been built and tested locally with a real laptop model worker and correct final settlement. To reproduce without touching the demo grid:

```sh
docker build -f deploy/Dockerfile -t pocketgrid-prototype:local .
.venv/bin/python tests/container_smoke.py
```
