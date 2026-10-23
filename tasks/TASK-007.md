# TASK-007 - Public catalog, plan calculator, identity and visual refinement

The owner's 23 October request supersedes the previous presentation scope. Keep the original wise, decisive Athena identity; use Renaissance editorial composition and restrained motion as references, without copying assets or layouts.

Implement a public pricing page with daily/weekly/monthly plan cards and a calculator sourced from verified CB CLI model metadata. Retail prices are DeepSeek V4.1 Flash: Rp 9,900/100M/1 day, Rp 34,900/250M/7 days, Rp 49,900 promo (Rp 59,900 regular)/500M/30 days. Account capacity and fulfillment remain the owner's responsibility. The latest clarification also requests a separate private internal-cost calculation; it must never enter the public bundle or catalog. Scale other model prices against the separately identified 0.03x paid Flash SG reference, with base-price floor for zero-credit models. Payment/entitlement activation is not part of this pricing-page request. Never expose account acquisition costs or credentials publicly.

Add separate private full names and unique public usernames with a migration; expose only usernames on leaderboards. Preserve server-side admin checks and member-only navigation. Add persistent light/dark/system themes, orange currency treatments, a subtle orange dotted background, accessible homepage/catalog animation, model filters and a complete footer.

Validate migrations, username uniqueness/privacy, model-source mapping and calculator edge cases (including zero multiplier), member restrictions, theme persistence, responsive markup and builds. Use isolated CT 102 tests. Deploy updated source to CT 301 when verified; public rollout depends on Cloudflare MCP availability. CT 100 must not be accessed.

## Verification result

- Backend: 193 tests, ruff and mypy passed in isolated CT102.
- Frontend: 9 tests, lint and production build passed on the owner PC.
- Sandbox: backup, migration and HTTP/auth/privacy checks passed.
- Public rollout: awaiting Cloudflare tool connection reload; checkout remains disabled.
- Visual browser inspection: unavailable due to browser-origin restrictions in this session.
