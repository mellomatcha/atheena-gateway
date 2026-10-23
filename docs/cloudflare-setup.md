# Cloudflare production handoff

Status 23 October 2026: prepared, not published. The owner confirmed Access is not configured.
The working CT 102 instance is an isolated sandbox; never attach a public tunnel to its development-auth service.

## Account setup

1. In Cloudflare Zero Trust, add Google as an identity provider. Create a self-hosted Access application for `ai.atheena.online/app` and `ai.atheena.online/app/*`. Allow only explicitly approved email addresses. Use the same email when creating the ATHEENA user.
2. Copy the team's `*.cloudflareaccess.com` domain and the application's AUD into `.env.production`. ATHEENA verifies JWT signatures, issuer, audience, expiry, and email, then checks that the database user is active. An Access allow rule alone does not create an ATHEENA account.
3. Create a remotely managed tunnel. Its public hostname is `ai.atheena.online`, service `http://caddy:80`. Store its token in the server's protected environment file. No inbound ports or DNS record to a private IP are required.
4. Protect only the portal paths with Access. Keep `/` public and `/v1/*` available to API clients: the gateway itself requires a personal `sk-ath-…` key. A blanket interactive Access rule for the hostname would make OpenCode receive a login page instead of an API response.

The environment template is `deploy/production.env.example`; copy it to `.env.production` outside Git. Run compose with `--env-file .env.production -f deploy/docker-compose.yml`. Production rejects missing Access settings and the development bypass. The origin has no published host ports; cloudflared connects inside the same compose network.

## Before first production run

- Select a deployment target explicitly. This session deploys only to the isolated CT 102 sandbox. CT 100 must not be touched.
- Use a fresh production database, real owner identity, dedicated upstream key, and audited initial balance. Do not carry over sandbox credentials, balances, or test users.
- Run migrations before API/worker, initialize the owner and selected current models, then verify Google login, member/admin separation, key revocation, streaming and usage.
- Verify database backup and restore to a separate database. Scheduled backups and production recovery remain part of deployment.
- Payments stay off until an owner-verified QRIS is installed and `TOPUP_ENABLED=true` is set.

References: [Access application JWT](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/application-token/), [Tunnel setup](https://developers.cloudflare.com/tunnel/get-started/), [cloudflared runtime options](https://developers.cloudflare.com/tunnel/reference/run-parameters/).
