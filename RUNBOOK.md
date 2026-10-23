# ATHEENA operations

Production runs in CT301 (`10.10.10.31`) under `/opt/atheena`, using Docker Compose. Reach it from CT300 with the pinned deployment SSH key described in `docs/ct301-deployment.md`. Never use CT100. CT102 `/opt/atheena-sandbox` is a separate development environment.

## Public addresses and access

- `https://atheena.online/`: homepage, `/pricing`, public catalog, and `/v1/*` for API clients.
- `https://dashboard.atheena.online/app`: member workspace, Google through Cloudflare Access.
- `https://console.atheena.online/app/admin/users`: admin workspace, a separate Access audience and a server-side admin check.

Only the owner's Google email is initially allowed. The Google OAuth application is in Testing; the owner is a registered test user. To onboard another person, add their email to the **dashboard** Access allowlist and create an active member in the console. While Google remains in Testing, also add that person as a Google OAuth test user. Do not add ordinary members to console Access. Publishing Google OAuth for general onboarding is a separate remaining operation, including accurate public branding/privacy information.

Payments, checkout and package entitlements are disabled. Pricing is a retail calculator, not an active subscription system. Metered model prices currently remain Rp 0 while usage is recorded. The owner has a clearly labelled Rp 10,000 internal testing adjustment in the append-only ledger; it is not payment revenue. Set deliberate prices/entitlements before selling service.

Three inference-verified CodeBuddy models are initially active: DeepSeek V4.1 Flash, its SG variant, and GLM 5.3 Flash. Only the base DeepSeek model has been verified in both OpenAI and Anthropic formats. Other catalog entries are inactive until tested. Public catalog metadata distinguishes availability from successful inference.

## Routine commands

Run on CT301 as `deploy`:

```sh
cd /opt/atheena
docker compose --env-file .env.production -f deploy/docker-compose.yml ps
docker compose --env-file .env.production -f deploy/docker-compose.yml restart api worker
docker exec atheena-api-1 python -c 'import httpx; r=httpx.get("http://127.0.0.1:8000/readyz"); print(r.status_code, r.json())'
```

Readiness checks PostgreSQL, Redis and authenticated 9Router connectivity. No application/container ports are published to the host. Cloudflared is the public entry point. Do not add a host port or enable `DEV_AUTH_EMAIL` in production.

Keep `.env.production` mode 0600. Never print the compose resolved environment or full Docker inspection, which can disclose secrets. Application logs and request tables must contain metadata only, never prompts or model responses.

## Backup and restore

`deploy/backup.py` creates PostgreSQL custom-format dumps in `/opt/atheena/backups`, directory 0700/files 0600, retaining 30 days after a successful new backup. The deploy user's cron runs it daily at 19:17 UTC (02:17 WIB). Backups currently remain on the same CT; configure a separate encrypted backup destination for protection against loss of the whole host. Environment credentials require a separate protected backup; database dumps do not contain them.

Manual backup:

```sh
python3 /opt/atheena/deploy/backup.py
```

Restore into a **new, isolated** database first; never overwrite the live database to test a backup:

```sh
docker exec atheena-postgres-1 createdb -U atheena atheena_restore_check
docker exec -i atheena-postgres-1 pg_restore -U atheena -d atheena_restore_check --exit-on-error --no-owner < backups/SELECTED_BACKUP.dump
docker exec atheena-postgres-1 psql -U atheena -d atheena_restore_check -c 'SELECT version_num FROM alembic_version; SELECT count(*) FROM users; SELECT count(*) FROM models;'
```

Record the selected file hash and counts. A real recovery requires a maintenance window, a new backup of the live database, stopped API/worker, a deliberate database cutover and readiness/account/ledger checks. Do not truncate or rewrite ledger entries. The initial full restore test is recorded in `/opt/atheena/backup-verification.json`.

## Deploy and rollback

Build/test in the isolated sandbox, then stage only source and built frontend files. Preserve `.env.production`, database volumes and backups. Before replacing the application, back up the database and tag the existing image with a release identifier. Apply migrations only after checking compatibility with rollback. Start the new API/worker and validate readiness, Google login and a cheap manual inference.

For an application rollback, restore the prior image and public assets and restart API/worker/Caddy. Do not run `docker compose down -v`. If a migration is incompatible, use a planned database recovery rather than blindly downgrading the schema.

The previous apex DNS was proxied A `2.57.91.91`; its full record is saved in the private operator workspace as `work/dns-apex-before-atheena.json`. Current apex/dashboard/console all point to the dedicated CT301 tunnel. Restoring the old apex is a deliberate website rollback, not a way to repair the member dashboard. Never modify the unrelated ERP tunnel.

## Keys, upstream and Cloudflare

Create personal keys from the member dashboard and store the one-time value in a password manager. Revocation invalidates the key cache immediately. The deployment QA key is temporary and must be revoked after validation.

The upstream production key is dedicated to CT301 in official 9Router on CT300 port20129. To rotate, create another dedicated key in 9Router, replace only `UPSTREAM_API_KEY` in the protected environment, recreate API/worker, validate readiness and then revoke the old key. Do not reuse sandbox or existing OpenCode credentials. The legacy 20128 instance is not this upstream.

If 9Router is unavailable, inspect readiness and CT300's `9router-official` service. Keep the portal's safe upstream-error responses. Do not point production to a legacy instance automatically. Preserve the CodeBuddy compatibility preload when updating official 9Router.

Cloudflare API clients must not receive browser challenges. The intended Configuration Rule is named `ATHEENA API clients`, expression `(http.host eq "atheena.online" and starts_with(http.request.uri.path, "/v1/"))`, setting Browser Integrity Check Off. This applies only to the API path; personal-key authentication and application rate limits remain active. Verify with a standard Python client as well as OpenCode after any rule change. A Cloudflare 1010 response occurs before the portal and is not an API-key error. Do not disable security globally to fix it.

Cloudflare MCP currently grants DNS/Tunnel/Access permissions but not Rulesets. The browser's saved permission gate can independently block `dash.cloudflare.com`; do not bypass it. Use an explicitly authorized connection or ask the owner to apply the narrowly scoped rule.
