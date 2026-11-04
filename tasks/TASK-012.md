# TASK-012 — Manual top-up and simpler portal UX

Owner requests authenticated top-up quote with amount and bank/e-wallet preference,
WhatsApp handoff to confirmed 082312202002 (6282312202002), no automatic credit.
Fix Greek decorative text to ATHEENA, emoji-prone icons, simplify marketing copy,
allow pasted API keys in integration examples (memory only), compact pricing cards.
Implement endpoint validation and no-ledger-mutation tests; frontend checks; validate
in CT102, deploy backed-up CT301 via CT300, check live. Never access CT100.


## 4 November 2026 — Release verification

Released fcf5c50 on CT301 with backup atheena-20261104T025310Z.dump and rollback
assets under /opt/atheena/releases/fcf5c50. Schema unchanged. 234 backend tests,
ruff/format/mypy across 79 files, 19 frontend tests and production build passed.
Ten origin routes and PostgreSQL/Redis/official9Router readiness passed.

Live authenticated quote: Rp50,000 via DANA generates a preview with the current
account username/email and a link to https://wa.me/6282312202002. No message was sent,
no payment created, and no balance credited. Invalid amounts/methods, unauthenticated
requests and concurrent no-credit behavior are covered by backend tests. The frontend
clears a prepared quote when amount or method changes. Bank/e-wallet choices express
preference; admin supplies actual destination instructions.

Homepage decorative Greek text replaced with ATHEENA; 26 SVG symbols replace emoji-prone
stars/arrows. Mythology identity retained with concise product-focused copy. Public
integration input verified using a dummy key: copied OpenCode config contains a direct
key rather than an environment reference. Inputs do not persist keys in browser storage.
Dashboard Quickstart also accepts pasted keys, validates their format and fills examples.
Pricing has 46 offers with compact cards and horizontally scrollable comparison on
narrow screens. Narrow browser DOM showed no page overflow. No physical iPhone/Safari
was available; SVG removes the problematic platform emoji glyph dependency.

Screenshots: work/task012-topup-live.png and work/task012-home-mobile.png. No CT100
access, inference, payment transfer or WhatsApp message was required.
