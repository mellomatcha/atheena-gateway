# CT 301 production deployment — 23 October 2026

Production target: CT 301, hostname `portal`, LAN `10.10.10.31`, source and public assets `/opt/atheena`, owner `deploy` (UID 1000, Docker group). Docker 29.8.1 and Compose v5.5.1 were already installed. The destination and container inventory were empty before staging.

## Current verified state (public activation)

Production is live with six containers: API, worker, PostgreSQL 16, Redis 7, Caddy and cloudflared. Fresh `.env.production` is mode 0600, uses distinct dashboard/console Access audiences, and disables development login. A dedicated official 9Router key serves this deployment. No sandbox data was copied.

The public apex and both private hostnames point to the dedicated CT301 tunnel. Google login has completed in the owner's browser for dashboard and console; separate member/admin navigation is visible. Anonymous API requests receive JSON 401 when the client passes Cloudflare's browser check. Real OpenAI completion, SSE, Anthropic completion, token accounting and Windows OpenCode have passed public tests:7 successful requests,10,433 tokens. The temporary QA key was revoked and immediately returned 401. The Python default user-agent encountered Cloudflare 1010; the owner reported enabling a scoped rule, but verification still returns 403. This remains unresolved, not an API-key failure.

The database contains only the owner, the17-model CLI catalog (3 inference-verified entries active), default settings and production QA metadata. There is a labelled Rp 10,000 owner testing adjustment; sales/payments/entitlements remain disabled. Google OAuth remains in Testing, with the owner registered.

Backup/restore into an isolated database passed, including migration and user/model counts; daily local backups are scheduled. See `RUNBOOK.md` for operations, onboarding, backup and remaining release boundaries.

## Historical staging evidence

- Application source, Docker context exclusions and built frontend are staged. No sandbox environment, users, keys, balances, database or Redis data were copied.
- Application image `atheena-api:local` built successfully on CT 301; image ID `sha256:0b307dff3b0c9edf6787cfa9c9da885da0552ce928219d68909af32919ed9828`.
- PostgreSQL 16, Redis 7, Caddy 2 and cloudflared images downloaded. Production Compose validates against the non-secret example, using `config --no-env-resolution --quiet`; Caddy validates successfully.
- No production containers are running and `.env.production` does not exist yet. The public hostname is not deployed by this work.
- The existing CT 102 preview remains `http://127.0.0.1:4173/app` through the PC's local SSH tunnel. HTTP checks returned 401 anonymously, 200 with the protected sandbox credentials, and an active admin from `/app/api/me`. The owner's repeated browser prompt has not been independently reproduced; it must not be reported as fixed merely because HTTP authentication passed.

## Network and deployment access

Two narrow rules were added without changing existing rules or restarting the global firewall:

- CT 301 permits `10.10.10.30` to TCP 22.
- CT 300 permits `10.10.10.31` to TCP 20129.

Original guest firewall files are backed up on the Proxmox host under `/var/backups/atheena-portal/20261023T064938Z/`. No CT 100 access occurred.

On CT 300, the dedicated private deployment key is `/root/.ssh/atheena-portal-301`, mode 0600. The CT 301 host key is pinned in the adjacent `.known_hosts` file using the trusted host console's copy. Its public key is authorized only for `deploy`, restricted to source `10.10.10.30` with SSH forwarding/PTY restrictions. From CT 300:

```sh
ssh -i /root/.ssh/atheena-portal-301 \
  -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/root/.ssh/atheena-portal-301.known_hosts \
  deploy@10.10.10.31
```

This connection returned hostname `portal`. From that session, the official gateway at `http://10.10.10.30:20129/v1/models` returned 401 without an API key: network connectivity and the authentication gate are working. This is not yet a production inference test.

## Historical Cloudflare connection notes

The official MCP endpoint `https://mcp.cloudflare.com/mcp` was added as `cloudflare` to the PC's Codex configuration. OAuth completed successfully with read/write permissions scoped to DNS, Tunnel and Access plus account discovery. The owner supplied their admin email; it is retained in the private workspace deployment notes, not this repository.

Cloudflare tools are now visible and account/zone/DNS/tunnel/IdP access works. The dedicated tunnel and Google IdP exist. Apps and Policies still use old scopes despite a successful new OAuth login requesting access.read/access.write. Reload through the documented local control socket failed with error 10050. Restart/reload the connection before creating Access applications. Do not read or copy OAuth token storage to bypass connection setup.

Next: create separate Google-only Access applications for the entire dashboard.atheena.online and console.atheena.online hostnames; leave atheena.online public with personal-key /v1/* authentication. Provision fresh production secrets and owner; migrate; start; verify browser login, inference, streaming, usage and backup restore. Replace the apex DNS only when ready, as approved. Keep payments disabled. See cloudflare-setup.md and tasks/TASK-006.md. Historical image IDs above describe earlier stages; current source/image evidence is in progress.md and /opt/atheena/deployment.json.
