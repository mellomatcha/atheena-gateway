# TASK-008 — Retail factors, member onboarding and usable API access

Owner request, 27 October 2026: normalize retail pricing against GLM5.3 provider multiplier0.79; DeepSeekV4.1Flash, GLM5.3, HY4, GPT5.6Luna and Gemini3.5Flash are1x. Other normalized factors below1 become0.45x. Keep the existing rupiah base packages and exact decimal/upward-Rp100 rounding. Preserve original provider metadata separately.

Add a first-login username/full-name setup step, enforce completion before creating personal keys, and preserve established profiles. Verify member-owned keys route to official9Router and cannot access another member's usage/admin endpoints. Default usage charts to tokens, refresh data on demand/while visible, and cover refresh and isolation with tests. Ask the owner for a separate Google test email and confirm invitation versus public-pending onboarding before changing Access policy.

Files: public pricing API/tests/docs, frontend pricing/home catalog, user model/migration/profile/key endpoint, onboarding UI and tests, usage chart/overview tests, runbook. Test in isolated CT102 only, then back up and deploy CT301 via CT300. Never access CT100. Manual real-provider QA uses only cheap DeepSeek Flash, with temporary personal keys revoked afterward; never record prompt/response content.

Validation: full backend tests/ruff/mypy and frontend tests/lint/build, migration compatibility, live price quotes, Google member onboarding when the owner supplies an account, own-user usage chart, public API/auth boundaries and key revocation. Record exact pending items if external permissions or user login prevent a check.

Owner clarified: public Google signup, no invitations; newly signed-in members await admin activation. Test member email supplied directly by owner. Implementation adds opt-in `PUBLIC_SIGNUP_ENABLED`, concurrent-safe pending-user creation after verified Access JWT, pending-only profile access, and keeps suspended/admin/API permissions enforced. Google basic identity scopes are exempt from the Testing allowlist according to official documentation; do not unnecessarily add all users as Google test users.

Pre-deploy validation: 214 backend tests passed in isolated CT102, ruff check/format and mypy passed; 14 frontend tests passed, lint and production build passed. CT301 readiness and ten origin routing checks passed before changes. Generic Python urllib still receives Cloudflare 1010; identified app User-Agent reaches the expected unauthenticated API response.
