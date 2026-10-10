# Akamai HackMidwest deployment mapping

Source: [official runtime lab](https://github.com/akamai-developers/akamai-workshop-hackmidwest/blob/main/docs/03_body.md), [setup](https://github.com/akamai-developers/akamai-workshop-hackmidwest/blob/main/docs/00_prework.md), and [inference reference](https://github.com/akamai-developers/akamai-workshop-hackmidwest/blob/main/docs/inference.md).

The workshop confirms two separate kinds of access:

- The `team-33` inference key calls `https://ws.akamai-workshops.com/v1`. The chat alias is `hackathon-chat`, and authentication is a Bearer header. No extra team header is documented.
- Deploying an application needs an activated Akamai Cloud account, cloud-management access and an SSH key. The team inference key does not supply those permissions. The workshop advertises a cloud-credit signup link; account activation and credit eligibility must be checked in Cloud Manager.

## PocketGrid adaptation

Use the Linode VM path from the workshop, with Ubuntu24.04 and [cloud-init.yaml](cloud-init.yaml) to install Docker. Prefer a dedicated instance labelled `pocketgrid-team-33` with a dedicated firewall. The workshop's starter script deploys a different application and touches other workshop resources; do not run it unchanged for PocketGrid.

| Workshop starter | PocketGrid |
|---|---|
| `/opt/hackmidwest` | `/opt/pocketgrid` |
| Starter API on public port8000 | Caddy on80/443; coordinator8787 stays internal |
| `/health` | `/api/health` |
| Starter agent plus Valkey | PocketGrid coordinator plus Caddy |
| Optional managed database/object store | Persistent `grid-data` Docker volume for prototype SQLite/images |
| Shared hosted image generation | Local Python workers generate images; hosted chat only plans work |

Point a domain/subdomain at the VM, permit80/443, and permit SSH from the deployment machine. Follow [the PocketGrid deployment steps](README.md) to transfer the source and start `deploy/compose.yaml`. Copy the deployment `.env` separately over SSH, with mode0600; do not put credentials in cloud-init metadata or container build arguments. Source transfer must omit `.env`, `.git`, local data, model caches, virtualenvs, node_modules and native build outputs.

For this reduced VM path, cloud automation needs Linodes and Firewalls read/write; it does not need the workshop starter's database, Object Storage, Kubernetes or NodeBalancer scopes. Existing-VM deployment can use SSH alone. Cloud resources are billed to the chosen account; inspect the plan/region and available promotional credit before provisioning.

## Configure the chat planner

Use these settings in the root `.env` for local testing, and `deploy/.env` on the VM:

```dotenv
POCKETGRID_AGENT_MODE=akamai
AKAMAI_BASE_URL=https://ws.akamai-workshops.com/v1
AKAMAI_CHAT_MODEL=hackathon-chat
AKAMAI_API_KEY=YOUR_TEAM_KEY
```

The repo deliberately uses `AKAMAI_API_KEY`, not a generic `OPENAI_API_KEY`, so another provider's shell credentials cannot be accidentally sent to the workshop. Strands uses its OpenAI-compatible Chat Completions adapter with non-streaming tool calls, bounded call counts, a45second HTTP timeout and no automatic HTTP retry. Neither the hosted image nor embedding API is used.

To verify the real hosted model, after saving the team key:

```sh
.venv/bin/python -m tests.live_agent_routing --provider akamai
```

This uses the actual Strands adapter, controlled local worker clients and the actual diffusion kernel. It records successful evidence in `docs/evidence/agent-routing-akamai.json`; no such evidence is created merely by configuring a key. It consumes the team's chat quota. After cloud deployment, also run a real job against the public URL, repeat failover, and verify retained images/receipts after a container restart. A healthy `/api/health` alone does not prove model access or the complete compute path.
