# TASK-006 — Deploy the portal to CT 301

Status: target staged and validated; production is not live. Steps 1–3 complete. Google client/IdP and the dedicated tunnel exist. Access app permissions need a connection reload; DNS and activation are pending. The owner changed domains to public `atheena.online`, member `dashboard.atheena.online`, admin `console.atheena.online`, and approved replacing the existing apex website when ready.

The owner selected CT 301 (`10.10.10.31`, `/opt/atheena`) and asked for SSH via CT 300. Current owner instructions supersede historical VM 999/CT 110 restrictions in project documents. CT 100 must not be accessed. CT 102 remains the existing isolated preview.

## Work and verification

1. Verify the target, its `deploy` user, Docker, and empty destination directory.
2. Back up and add only the two missing guest rules: CT 300 to CT 301 SSH, and CT 301 to CT 300 port 20129. Use a dedicated restricted deploy key and pin the host key obtained from the trusted host console. Verify both paths.
3. Stage only application source and built public assets in `/opt/atheena`, preserving environment files. Build the application image and validate Caddy on CT 301. Include Docker context exclusions for every environment variant.
4. Connect Cloudflare via official OAuth MCP. Configure the three hostnames, tunnel, Google identity provider, approved owner identity, and separate dashboard/console Access audiences. Keep the apex API available to personal API keys. Update Caddy, frontend navigation and host-bound JWT verification; test cross-audience rejection and console member rejection.
5. Generate fresh production secrets and a dedicated upstream key. Start a fresh database, migrate and provision only the owner and verified model catalog. Do not copy sandbox users, balances, or credentials.
6. Start production, verify login, roles, personal keys, provider responses, streaming, usage, and backup/restore. Keep payments off until verified by the owner.

Do not mark complete until public access and the owner's browser login are verified. An MCP OAuth login alone does not configure Cloudflare DNS, Access, or a tunnel.
