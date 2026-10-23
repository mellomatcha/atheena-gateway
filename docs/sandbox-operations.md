# ATHEENA sandbox — 23 October 2026

## Access

- Windows preview: http://127.0.0.1:4173/ ; dashboard `/app`; API `/v1`.
- If the SSH preview is no longer running, run `scripts/Start-SandboxPreview.ps1` from PowerShell. It binds only to localhost and does not alter server services.
- Sandbox username: `sandbox`. The generated password is in the parent workspace's `private/atheena-sandbox-access.json`, protected by the current Windows user's ACL. Do not commit or share that file.
- This is a password-protected shared sandbox identity, `Dafin · Sandbox`; it does not demonstrate live Google identity. Production uses Cloudflare Access with distinct active database users.
- The initial Rp 10,000 is a recorded test adjustment with no cash value. Model prices are Rp 0 for this sandbox. Token/request counts remain real.

## Location and isolation

CT 102: `/opt/atheena-sandbox`, compose project `atheena-sandbox`, listener `10.10.10.12:20131`, separate PostgreSQL/Redis volumes and bridge. Existing ERPNext services are outside this project and unchanged. CT 100 was not accessed during this continuation.

Official 9Router: CT 300, `http://100.75.171.91:20129/v1`. CT 102's LAN path to `10.10.10.30:20129` timed out, while the existing Tailscale path worked. Only the sandbox upstream URL was changed; no firewall rules were altered.

The portal has its own dedicated 9Router key (`atheena-sandbox-ct102`) stored server-side. Personal ATHEENA keys are hashed in PostgreSQL and only shown at creation. The initial `sandbox-opencode` key is restricted to `deepseek-v4.1-flash`; a protected PC copy exists for the successful OpenCode smoke test. Revoke it from API key management if no longer needed.

## Checks and maintenance

From `/opt/atheena-sandbox`, prefix commands with `docker compose --env-file .env.sandbox -f deploy/compose.sandbox.yml`:

- `ps`: this project's five services only.
- `restart api worker`: reload backend changes.
- `exec -T web caddy validate --config /etc/caddy/Caddyfile`: check gateway config.
- `run --rm api pytest -q -p no:cacheprovider`: rebuilds only `atheena_test`, uses Redis database 15 and fake upstreams. Never point test environment variables at a production database.
- `stop`: pause only this sandbox, preserving its data. Avoid volume deletion.

Source and built assets are uploaded separately with explicit exclusions for credentials, environment files, private folders, node_modules and Git metadata. The production compose is prepared but has never been started. Keep this sandbox's development authentication behind its password gate; do not publish it using Cloudflare.

## Evidence

- 174 backend tests passed; ruff lint/format and mypy passed for 74 files.
- 6 React interaction tests passed; TypeScript/Vite build and oxlint passed; npm audit reported zero vulnerabilities.
- Real HTTP smoke: anonymous dashboard/API rejection, valid password login, hashed personal key, public model names, OpenAI and Anthropic responses, SSE completion, and usage recording.
- Windows OpenCode returned `ATHEENA_PORTAL_OK`, exit 0, through the portal with tools disabled (12.5 seconds). Persistent existing OpenCode configuration was unchanged; QA used its isolated config.
- Both Caddy configurations and prepared production compose validated. Cloudflare Google login/public hostname remain unconfigured, confirmed by owner.
- Visual desktop/mobile QA is not claimed: browser access was denied. No alternate browser automation was used.

## Manual acceptance

Open `/app`, enter sandbox credentials, inspect the three or more real requests in Ringkasan. Create a new API key; copy it while visible. Use Mulai's client examples with the public model name `deepseek-v4.1-flash`. Review Admin → Status sistem, Katalog & harga, Pemakaian global, and Audit log. QRIS payments remain disabled. Admin user/model/settings changes are audited; financial adjustments retain append-only ledger history.
