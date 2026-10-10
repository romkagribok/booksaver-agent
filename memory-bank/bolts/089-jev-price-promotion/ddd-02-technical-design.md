---
stage: technical-design
bolt: 089-jev-price-promotion
created: "2026-10-10T01:45:40Z"
status: complete
---

# Jev as the price method — technical design

## Selection seam

`cli/commands.py:_make_price_executor_factory(cfg, anthropic_key)` returns the single factory
handed to `CheckCoordinator(agentic_executor_factory=...)`:

- `jev` → `JevPrimaryPriceExecutor` when `BOOKSAVER_TYPESAFE_API_KEY` is set, else `None` (checks
  fail closed with `provider_authentication`, a startup warning says why).
- otherwise → the existing Browser Use / Stagehand adapter when the Anthropic key is set.

Nothing else in the coordinator or monitor changes: `_run_booking_price` already routes through
`AgenticPriceExecutionService` → validators → `_agentic_check_result` → history, session refresh,
canary metrics, savings pipeline.

## Modules

| Module | Change |
|---|---|
| `domain/browser_executor.py` | `PriceExecutorKind.JEV`, `JEV_PRICE_POLICY_VERSION` |
| `application/load_config.py` | reject `jev` together with paired mode |
| `infrastructure/browser/jev_primary_executor.py` (new) | daily cap check, run, ledger record |
| `infrastructure/browser/jev_price_executor.py` | `allow_session_refresh`; discount-aware total grounding; unpriced reasons |
| `infrastructure/browser/jev_page_snapshot.py` | strike-through detected on ancestors |
| `infrastructure/persistence/` | schema v20 `jev_price_runs`; repository; purge and booking removal |
| `cli/commands.py` | factory; Jev-only section in `comparison report` |

## Total grounding

Each price candidate is offered to Jev with its neighbouring label lines ("preceded by",
"followed by"). `_ground_total` first classifies **every** amount on the card:

| Class | Rule |
|---|---|
| `per_night` | the line a per-night label applies to (itself, else the amount before it, else after) |
| `current` | the amount after "current price" on the same line, or an amount-only line under a line that is exactly that label; the remainder must not be a nightly or component wording |
| `original` | the line, or the label line above it, names an original/previous price |
| `not_total` | tax, fee, charge, deposit, saving, discount, "from", "due", per-person wording on the line or its label |
| `price` | a line that starts with "Price"/"Total"/"Total price" followed by exactly one amount, or an amount-only line under a line that is exactly such a label |
| `bare` | anything else |

The chosen amount is accepted only when: it is not nightly/original/component; it parses as one
en-US amount in the booking's currency; if a current price exists it is that amount; otherwise no
other candidate amount differs or is unreadable; an unlabelled amount is used only for one-night
stays; and, for longer stays, it does not equal the card's own nightly amount. Label status is
deliberately narrow: "Total savings", "Member price", "Price per night" and "Price for:" are not
labels. Tax wording is matched within one line or two adjacent lines, never across the card.

The first version of this change accepted a "current price" line before running the other
checks and treated any line containing "price" or "total" as a label; an independent review
showed both could ground a lower, wrong amount, and the rules above replaced them.

## Persistence

`jev_price_runs` (additive, v20). The primary executor opens short-lived connections by path,
the same way the Anthropic ledger does during a run. `INSERT OR REPLACE` by execution id.

## Session handling

`LocalJevPriceRuntime(allow_session_refresh=True)` keeps the snapshot verified by the shared
account probe; the executor stores it on the lease and marks the result refresh-eligible, exactly
as the Browser Use adapter does. The comparison candidate keeps `False`.

## Rollout and rollback

Phase 1: deploy this code with production unchanged (`browser_use` + paired mode) so the fixed
candidate runs beside the LLM method on the affected booking. Phase 2: set
`price_executor = "jev"`, `jev_comparison.enabled = false`, recreate the container. Rollback is the
reverse config edit; schema v20 is additive and both images tolerate it. An image older than
this release rejects `price_executor = "jev"` at config load, so when rolling back the image the
config must be reverted first or in the same step.

`price_executor = "jev"` requires a non-legacy `routing`; with legacy routing the scripted method
would run and Jev never would, so that combination is rejected. Users the routing policy does not
admit (for example an invitee without current disclosure consent) keep using the scripted legacy
method, as before. Automatic regression to legacy applies only after an explicit promotion under
the Jev policy version, which production has never performed.

## Plan departures

- Jev spend is not in the Anthropic reservation ledger (see requirements amendment, FR-5).
- The per-user daily LLM-call counter does not count Jev requests; the Jev daily cost cap and the
  per-check call cap bound them instead.
- `ExtractionMethod` recorded in history stays `llm` for model-assisted observations of either kind.
- `[jev_comparison] participants` applies to paired mode only. As the price method Jev serves every
  user the routing policy admits, and `disclosure_version` still names Anthropic although price
  page text now goes to TypeSafe.
- A purge or booking removal deletes that day's Jev run rows, which lowers the counted daily spend;
  a failed ledger write (for example a locked database) is logged and not counted. The per-check
  call cap bounds the exposure.

## Error-page recovery (US-219)

`_navigate_until_offers` receives the trusted entry URL. After the readiness wait, while the page
is Booking.com's error page (error wording, no rooms), it pauses 4 s and re-navigates to that
URL, at most twice, checking the single-target and allowed-destination invariants before and
after each reload and counting each as a browser action. Only then does the Jev decision loop
start. The error page is recognised by error wording in the title or a heading (not page body
text) with no bot-check wording. The diagnostic records each `>RELOAD`.
