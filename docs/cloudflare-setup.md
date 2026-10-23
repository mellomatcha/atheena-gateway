# Cloudflare production handoff

Status 23 October 2026: production is not published. CT 301 (`10.10.10.31`, `/opt/atheena`) is the selected target. The dedicated tunnel and Google identity provider now exist; Access applications, production activation and DNS cutover remain pending. The owner requires Google from the first launch; do not substitute email OTP.
The working CT 102 instance is an isolated sandbox; never attach a public tunnel to its development-auth service.

## Account setup

1. Reuse the existing `ATHEENA Google` identity provider, connected to the dedicated Google Cloud project `atheena-portal`. Its callback is `https://atheena.cloudflareaccess.com/cdn-cgi/access/callback`. Google currently remains in Testing with the owner listed as a test user. Complete public branding/publishing before onboarding other customers.
2. Create two self-hosted Access applications: the entire `dashboard.atheena.online` hostname and the entire `console.atheena.online` hostname. Restrict both to the Google IdP; initially allow only the approved owner email. Future member emails belong only in the dashboard policy.
3. Set team domain `atheena.cloudflareaccess.com`, dashboard audience `CF_ACCESS_AUD` and console audience `CF_ACCESS_ADMIN_AUD`. The backend selects the verifier by hostname, rejects cross-application tokens, and requires an active admin for every console API request. Access admission alone does not create a database user.
4. Reuse dedicated tunnel `atheena-portal-ct301`. Its three hostnames (`atheena.online`, `dashboard.atheena.online`, `console.atheena.online`) route to `http://caddy:80`, with a final 404 fallback. Never change the existing ERP tunnel.
5. Keep `atheena.online` public. Its `/v1/*` endpoints require personal API keys, not interactive Google login. This is the API base URL: `https://atheena.online/v1`. Homepage/pricing are public; dashboard `/` redirects to `/app`, console `/` to `/app/admin/users`.
6. The apex currently has an A record pointing to `2.57.91.91`. The owner explicitly approved replacing it only when the new portal is ready. Preserve its old configuration for rollback. Dashboard/console DNS records did not exist at inspection. No DNS changes have been made yet.

The current MCP session still lacks effective `access.read`/`access.write` despite successful reauthorization. The supported local reload failed with socket error 10050. A connection/app restart is needed before retrying Access app creation. DNS, tunnel and IdP operations already work; do not repeatedly recreate those resources or read OAuth storage.

The environment template is `deploy/production.env.example`; copy it to `.env.production` outside Git. Run compose with `--env-file .env.production -f deploy/docker-compose.yml`. Production rejects missing Access settings and the development bypass. The origin has no published host ports; cloudflared connects inside the same compose network.

## Before first production run

- Deploy to the owner's selected CT 301, `/opt/atheena`, using its existing `deploy` user and Docker Compose. Connect via the dedicated CT 300 SSH key. CT 102 remains the isolated preview. CT 100 must not be touched.
- Use a fresh production database, real owner identity, dedicated upstream key, and audited initial balance. Do not carry over sandbox credentials, balances, or test users.
- Run migrations before API/worker, initialize the owner and selected current models, then verify Google login, member/admin separation, key revocation, streaming and usage.
- Verify database backup and restore to a separate database. Scheduled backups and production recovery remain part of deployment.
- Payments stay off until an owner-verified QRIS is installed and `TOPUP_ENABLED=true` is set.

References: [Access application JWT](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/application-token/), [Tunnel setup](https://developers.cloudflare.com/tunnel/get-started/), [cloudflared runtime options](https://developers.cloudflare.com/tunnel/reference/run-parameters/).
