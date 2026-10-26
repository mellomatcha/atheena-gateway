# TASK-011 — Real member key and model access verification

The owner supplied their member account's existing personal key and requested a real
OpenCode test plus verification that selecting a model does not grant every model.
Keep the supplied key out of files, command arguments, reports and repository history;
pass it through process input/environment only. Do not revoke or alter this user-owned
key, grant access, add credit, or activate catalog models simply to make tests pass.

Inspect the member/key restrictions and current active catalog read-only on CT301 via
CT300. Read the public authenticated model list with the exact supplied key. Exercise
the permitted cheap models with bounded prompts, then request disallowed catalog IDs
and verify explicit rejection without upstream usage. Run Windows OpenCode with an
isolated configuration and tools disabled. Verify request/token metadata belongs to
this member/key, and compare with account/key allowlists and package behavior.

Record sanitized evidence, actual failures and any gap between retail package selection
and enforced access. Do not claim package entitlements exist while checkout is disabled.
No CT100 access. No production changes unless an actual implementation defect is found
and a tested correction can be made without changing the owner's intended permissions.


## Live results — 27 October 2026

The exact supplied key was matched by its SHA-256 hash, without printing or persisting
plaintext. Google stored the member email without the dot (`dafinyudha08@gmail.com`),
which explains the earlier empty lookup of the dotted spelling. The key belongs to
member `lerayee`, role member, active/basic. Its model_allowlist is null: it may use
all active models allowed for that tier. Existing account balance was Rp100,000;
no credit or permissions were changed during QA.

Windows OpenCode using an isolated configuration and this exact key received model
text, completed one step and exited 0 in 24.7 seconds on DeepSeek V4.1 Flash. The
literal requested marker was not reproduced, so this confirms transport/inference,
not exact instruction compliance. The model response content was not saved in reports.
A separate OpenCode run manually selecting GPT 5.6 Sol emitted model_not_allowed,
returned no response/finished step and exited 1 in 11.2 seconds.

The authenticated model list contains three models. Each returned HTTP200 with text
in a bounded real inference: DeepSeek V4.1 Flash, its SG variant, GLM 5.3 Flash.
All other 14 concrete CLI-catalog model IDs returned HTTP403/model_not_allowed,
including Sol, Astra, Luna, Gemini, HY4, GLM 5.3 and GLM 5.2. A nonexistent model
was also rejected. These are portal access failures; they do not prove an upstream
provider outage. No inactive model was activated to make this test pass.

Read-only production verification tied every probe to this exact key. There were
22 request records: five successful responses (three direct probes plus two OpenCode
requests) and seventeen zero-token, zero-cost denials (fifteen direct probes plus two
Sol requests from OpenCode). Successful input/output totaled 4,147 tokens. Direct
response usage matched database counts. Existing zero metered prices meant no balance
change. Tests were authorized real-provider QA, not mocked-suite runs. Application
code was unchanged; no redundant automated suite run was needed.

Remaining product gaps are explicit: SG is hidden from retail/homepage, but its existing
API route and API model-list entry remain active. Pricing selection is a simulation;
there is no purchased-package entitlement, expiry or token/bonus-pool enforcement.
The current controls are model active status, user tier and optional per-key allowlist.
A key with null allowlist will gain access to future active models within its tier.
Do not claim that selecting a DeepSeek retail card restricts this key to DeepSeek.

No production configuration, permissions, balances, model activity or keys were changed.
The supplied user-owned key remains active. CT100 was not accessed. Local evidence lives
in work/member08-model-list.json, member08-model-probes.json, member08-opencode-result.json,
member08-opencode-denied-result.json and supplied-key-owner-qa.json; these contain metadata
only and stay outside the repository. The working OpenCode config uses an environment
reference for the key and was restored to DeepSeek after the negative test.
