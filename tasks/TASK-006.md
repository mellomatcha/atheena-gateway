# TASK-006 — Deploy the portal to CT 301

Status: production is live on the three approved domains. Google owner login, console, public inference, OpenCode, streaming, usage, key revocation and database restore have passed. Final compatibility verification remains open: default Python urllib receives Cloudflare 1010. The owner reported a scoped Browser Integrity Check rule was enabled, but the subsequent check still returned403. MCP lacks Rulesets permission and the browser permission gate still blocks dash.cloudflare.com. Do not mark this remaining check complete. Google OAuth remains in Testing; sales/payment/package entitlements are not enabled.

The owner selected CT 301 (`10.10.10.31`, `/opt/atheena`) and asked for SSH via CT 300. Current owner instructions supersede historical VM 999/CT 110 restrictions in project documents. CT 100 must not be accessed. CT 102 remains the existing isolated preview.

## Work and verification

1. Verify the target, its `deploy` user, Docker, and empty destination directory.
2. Back up and add only the two missing guest rules: CT 300 to CT 301 SSH, and CT 301 to CT 300 port 20129. Use a dedicated restricted deploy key and pin the host key obtained from the trusted host console. Verify both paths.
3. Stage only application source and built public assets in `/opt/atheena`, preserving environment files. Build the application image and validate Caddy on CT 301. Include Docker context exclusions for every environment variant.
4. Connect Cloudflare via official OAuth MCP. Configure the three hostnames, tunnel, Google identity provider, approved owner identity, and separate dashboard/console Access audiences. Keep the apex API available to personal API keys. Update Caddy, frontend navigation and host-bound JWT verification; test cross-audience rejection and console member rejection.
5. Generate fresh production secrets and a dedicated upstream key. Start a fresh database, migrate and provision only the owner and verified model catalog. Do not copy sandbox users, balances, or credentials.
6. Start production, verify login, roles, personal keys, provider responses, streaming, usage, and backup/restore. Keep payments off until verified by the owner.

Do not mark complete until public access and the owner's browser login are verified. An MCP OAuth login alone does not configure Cloudflare DNS, Access, or a tunnel.
