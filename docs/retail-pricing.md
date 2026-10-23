# Retail packages and catalog

The owner's 23 October 2026 request defines the DeepSeek V4.1 Flash base prices:

- Daily: Rp9,900; 100 million total tokens; one day.
- Weekly: Rp34,900; 250 million total tokens; seven days.
- Monthly: Rp49,900 promotional price, Rp59,900 regular price; 500 million total tokens; 30 days.

These are retail prices. No account acquisition cost, provider account identifiers, balances or credentials are included in the public API, JavaScript or this document. Checkout is disabled: selecting a card or using the calculator does not create an entitlement, extend expiry, deduct a balance or initiate payment. Existing metered gateway billing remains unchanged.

## Source and pricing policy

`backend/app/data/codebuddy_catalog.json` is a timestamped snapshot of the international `product.json` in the official `@tencent-ai/codebuddy-code` package, version 2.173.0. The installed CT300 CLI matched that version. Its 17 concrete model IDs exclude automatic routing aliases. The cloud-hosted variant is a separate product configuration and is not mixed into this catalog.

DeepSeek Flash currently has multiplier 0.00. A zero multiplier cannot be a divisor. The retail calculator therefore uses the separately identified Flash SG variant (0.03) as its nonzero reference:

`model price = ceil_to_Rp100(base package price * max(1, model multiplier / 0.03))`

This is ATHEENA's provisional relative retail pricing policy, not a provider conversion between credits and tokens. Zero-credit models retain the base service price. Model names, multiplier, context and capabilities come from the CLI; availability badges distinguish successful bounded inference checks, listing in the gateway, and unverified provider catalog entries. No user should interpret the full catalog as a claim that all models have passed inference QA.

The calculator rounds token demand up to a whole number of packages. The same input, output and cache token categories must be consistently accounted for if entitlements are implemented later. Multiplying package count does not extend expiry automatically. Weekly pricing has a higher price per token than daily pricing; its longer validity is a separate benefit. Keep the owner's prices unless they request a change.

## Updating and verification

Update the snapshot from the installed official CLI product metadata, review every ID and multiplier, preserve explicit verification flags and timestamp, then run the public pricing tests and frontend tests. Do not scrape authenticated account data into this public snapshot. A catalog update alone must not silently enable an upstream model in the billable gateway catalog.

Backend tests cover exact base prices, promo selection, upward rounding, free-model floor, package boundaries, malformed/oversized quantities, unknown models, concurrent read-only quotes and absence of private account fields. Frontend tests cover anonymous pricing, model deep links, promo changes, quantity validation and persistent theme preferences.

The private cost review uses observed account quotas separately from retail pricing. Official documentation describes credit consumption as depending on model, task complexity and context length; CLI multipliers alone do not establish a fixed cost per million tokens. Keep expired/expiring bonuses separate from recurring quotas, and do not claim a guaranteed package margin from a short inference sample.

References: [CodeBuddy credits](https://www.codebuddy.ai/docs/ide/Account/credits), [CLI cost management](https://www.codebuddy.ai/docs/cli/costs).
