# Retail packages and catalog

The owner's 23 October 2026 request defines the DeepSeek V4.1 Flash base prices:

- Daily: Rp9,900; 100 million total tokens; one day.
- Weekly: Rp34,900; 250 million total tokens; seven days.
- Monthly: Rp49,900 promotional price, Rp59,900 regular price; 500 million total tokens; 30 days.

These are retail prices. No account acquisition cost, provider account identifiers, balances or credentials are included in the public API, JavaScript or this document. Checkout is disabled: selecting a card or using the calculator does not create an entitlement, extend expiry, deduct a balance or initiate payment. Existing metered gateway billing remains unchanged.

## Source and pricing policy

`backend/app/data/codebuddy_catalog.json` is a timestamped snapshot of the international `product.json` in the official `@tencent-ai/codebuddy-code` package, version 2.173.0. The installed CT300 CLI matched that version. Its 17 concrete model IDs exclude automatic routing aliases. The cloud-hosted variant is a separate product configuration and is not mixed into this catalog.

The owner's 27 October update uses GLM 5.3's original provider multiplier **0.79** as the reference. Original CLI metadata is retained as `provider_multiplier` in public responses; `multiplier` is the ATHEENA retail factor:

- DeepSeek V4.1 Flash, GLM 5.3, HY4 Preview, GPT 5.6 Luna and Gemini 3.5 Flash: **1x**.
- Other models: original provider multiplier divided by 0.79. If that ratio is below 1, use **0.45x**; otherwise keep the exact ratio.
- `model price = ceil_to_Rp100(base package price * retail factor)`.
- Display factors with at most two decimals, but calculate money using full Decimal precision. For example GPT 6 Astra is approximately 8.44x, with a daily quote of Rp83,600.
- A 0.45x model costs Rp4,500 daily, Rp15,800 weekly, and Rp22,500 monthly promotional (Rp27,000 regular).

This is ATHEENA's retail policy, not a provider conversion between credits and tokens. Zero-credit models still receive a positive retail price. Model IDs, provider factors, context and capabilities come from the CLI; availability badges distinguish successful bounded inference checks, listing in the gateway, and unverified provider catalog entries. No user should interpret the full catalog as a claim that all models have passed inference QA.

The calculator rounds token demand up to a whole number of packages. The same input, output and cache token categories must be consistently accounted for if entitlements are implemented later. Multiplying package count does not extend expiry automatically. Weekly pricing has a higher price per token than daily pricing; its longer validity is a separate benefit. Keep the owner's prices unless they request a change.

## Updating and verification

Update the snapshot from the installed official CLI product metadata, review every ID and multiplier, preserve explicit verification flags and timestamp, then run the public pricing tests and frontend tests. Do not scrape authenticated account data into this public snapshot. A catalog update alone must not silently enable an upstream model in the billable gateway catalog.

Backend tests cover all five 1x overrides, normalized factors and the 0.45x tier, exact base prices, promo selection, upward rounding, package boundaries, malformed/oversized quantities, unknown models, concurrent read-only quotes and absence of private account fields. Frontend tests cover anonymous pricing, model deep links, promo changes, quantity validation and persistent theme preferences.

The private cost review uses observed account quotas separately from retail pricing. Official documentation describes credit consumption as depending on model, task complexity and context length; CLI multipliers alone do not establish a fixed cost per million tokens. Keep expired/expiring bonuses separate from recurring quotas, and do not claim a guaranteed package margin from a short inference sample.

References: [CodeBuddy credits](https://www.codebuddy.ai/docs/ide/Account/credits), [CLI cost management](https://www.codebuddy.ai/docs/cli/costs).
