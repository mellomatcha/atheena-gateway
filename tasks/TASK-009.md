# TASK-009 — Username-only signup with Google profile name

Owner clarification on 27 October 2026 overrides TASK-008's manual full-name setup:
retrieve the private full name from the authenticated Google identity through Cloudflare
Access; ask the member only to choose a public username during signup.

Update Access profile lookup, pending-user provisioning/backfill, profile completion and
onboarding UI. Validate the Access JWT before any identity lookup, bind the response to
the same email, use only the configured HTTPS team endpoint and never follow redirects
with the cookie. An unavailable name must not block username setup or relax activation,
key or admin checks. Keep established profiles and public leaderboard privacy intact.

Run backend tests/lint/types in isolated CT102 and frontend tests/lint/build locally.
Back up and release to CT301 through CT300; verify readiness and the deployed UI. Never
access CT100. No real AI inference is needed for this profile change. Independently retry
Cloudflare browser access only after the owner changes its saved permission; do not bypass
a denied browser gate.

Validation before release: 222 backend tests passed in isolated CT102 (21.09s), with
ruff check/format and mypy passing across 79 files. Sixteen frontend tests, lint and
production build passed on the owner's PC. Tests cover verified Google name import,
empty-name backfill, no lookup for invalid JWTs, email mismatch, timeout/503/malformed
responses, refusal to follow redirects, username-only completion and pending key denial.
Profile settings display the imported name read-only; usernames remain editable.

Live member login is still pending: the intended test email has no portal row yet.
The owner reports Browse Always allow for dash.cloudflare.com, but the browser's saved
permission gate still refuses navigation; no circumvention attempted.
