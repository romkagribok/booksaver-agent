---
intent: 026-jev-price-comparison
phase: inception
status: draft
created: "2026-09-26T16:29:30Z"
updated: "2026-09-26T16:29:30Z"
---

# Jev and Browser Use integration research

Checked against official documentation and upstream sources during inception on 2026-09-26.
No authenticated TypeSafe request or Booking.com comparison was executed.

## What Jev Ultrafast is

[Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) is a separate small browser agent by
Browser Use. Jev selects operations/targets from a fresh indexed control table; a separate text LLM
handles free-form typing. Its default loop does not use screenshots. It is not the existing
browser-use ChatAnthropic agent with a model string changed.

Its demo uses Browser Harness and an existing Chrome profile. Documented gaps include frames,
shadow roots, canvas, pop-up tabs and nested scrolling. The published demo evidence is narrow and
is not BookSaver qualification. Therefore use its approach as the design reference; do not embed
its stock Agent, text helper, shared-profile connection or demo service in production.

## Reuse decision for the first bolt

Inspect [package metadata](https://github.com/browser-use/jev-ultrafast/blob/main/pyproject.toml),
[model adapter](https://github.com/browser-use/jev-ultrafast/blob/main/jev_ultrafast/model.py), and
[browser harness](https://github.com/browser-use/jev-ultrafast/blob/main/jev_ultrafast/browser.py).
Prefer small BookSaver-owned components over importing an entire alternate runtime. If code is
copied or a library added, pin the reviewed commit/version, preserve its license, assess dependencies,
and record what was adapted. No upstream revision is qualified merely by reading main.

## Verified provider contract

[TypeSafe API](https://docs.typesafe.ai/api): POST https://api.typesafe.ai/v1/systemone with bearer
credentials; send model, state and named questions. Choice uses a criteria map (maximum 255 options).
Responses include answers, actual model and input/output usage. Validate all transport data locally;
handle malformed replies, authentication errors, 429 and 529 with bounded, metered attempts. All
questions in a request are independent; code must reject incompatible operation/target combinations.

[Model reference](https://docs.typesafe.ai/models): current documented version jev-1.13.0, text-only;
no screenshot input or string generation. Published input rate is $0.042 per million tokens, output
free. The documented limits are 64k total and 32k state plus longest question. Alias versions and
rate limits can move. Pin the version and pricing; reverify before implementation/live admission.
20 requests of 4,000 billed input tokens would be $0.00336 of Jev inference only, not total check cost.

[Known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13): numeric/date reasoning,
indirection, irrelevant state and adversarial content are documented weaknesses. Keep exact parsing,
arithmetic, comparisons, and safety enforcement in code; unknown is preferable to invented evidence.

[Confidence](https://docs.typesafe.ai/confidence): confidence summarizes a probability distribution;
it is not an independently verified probability of a safe browser action. Tune on held-out fixtures.

[Quick start](https://docs.typesafe.ai/introduction/quickstart): obtain the API key through the
TypeSafe console. [Data handling](https://docs.typesafe.ai/legal) documents no customer-data training
and separate enterprise ZDR availability. Verify actual account terms before transmitting user pages;
do not equate no training with zero retention.

## Rejected initial shortcuts

- Swap a Jev model ID into ChatAnthropic or the native screenshot ComputerUseModelPort.
- Use an Anthropic/text helper but label the candidate a complete Jev method.
- Start another daemon or reuse a logged-in personal Chrome profile.
- Let Jev perform monetary/date arithmetic or accept its DONE answer as evidence.
- Import demo benchmark cost as the expected end-to-end BookSaver result.
