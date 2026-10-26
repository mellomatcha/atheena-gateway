# TASK-010 — Model sections and custom Sol/Astra packages

Owner request, 27 October 2026: show every retail package by default in ordered sections:
DeepSeek highlight (three cards), GPT models, Chinese models, then other models such as
Gemini. Selecting a model pins its packages above recommendations without hiding the rest.
Hide the SG variant from the public catalog and package selection, retaining provider
metadata internally. Every 1x model uses the same daily/weekly/monthly DeepSeek base prices.

GPT 5.6 Sol: 50M tokens/day for Rp30,000 or 50M/week for Rp54,900. GPT 6 Astra:
50M/day for Rp39,000 or 50M/week for Rp64,900. The owner explicitly confirmed that
each weekly package includes one additional shared 50M-token pool for GPT 5.6 Luna and
DeepSeek V4.1 Flash. Bonus tokens cannot fulfill the primary-model quota. No monthly
Sol/Astra price was supplied, so offer only daily and weekly for those two models.

Implement server-owned offer metadata/quotes, bonus display and clear calculator quotas,
model sections and pinning in frontend. Do not enable checkout, subscriptions, billing
entitlements or previously unverified upstream models. Test prices, quotas, public hiding,
calculator boundaries, promo behavior and default/filter presentation. Validate backend
in isolated CT102; build frontend locally; back up/deploy CT301 and inspect live pricing.
Never access CT100. Keep the unrelated Cloudflare browser-permission blocker recorded.


## 27 October 2026 — Model sections, fixed GPT pricing and SG hiding

Implemented 46 public offers for 16 visible models, three DeepSeek highlight cards,
ordered GPT/China/other sections, selected-model pinning above recommendations, and
server-owned fixed Sol/Astra prices. Weekly offers explicitly separate the 50M primary
quota from one shared 50M Luna/DeepSeek bonus pool. Unspecified Sol/Astra monthly offers
return 404. SG is absent from public catalog, homepage and quote endpoint while original
provider metadata/upstream routes remain intact. Checkout/entitlements stay disabled.

Validation before deployment: 233 backend tests passed in isolated CT102 (21.53s),
ruff check/format and mypy passed across 79 files. Nineteen frontend tests, lint and
production build passed. No CT100 access and no provider inference required.
