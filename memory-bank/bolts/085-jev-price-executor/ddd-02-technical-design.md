---
stage: technical-design
bolt: 085-jev-price-executor
created: "2026-09-27T17:00:00Z"
status: complete
---

# Jev price executor — technical design

## Modules

| Module | Responsibility |
|---|---|
| `infrastructure/llm/typesafe_client.py` | stdlib HTTPS client for `POST https://api.typesafe.ai/v1/systemone`; bearer key; ≤ 3 attempts on 408/429/5xx/529 with bounded backoff honoring retry-after; 401/403 and other 4xx not retried; deadline-aware; strict answer validation |
| `infrastructure/browser/jev_page_snapshot.py` | Fixed read-only snapshot JS + bounded parser (≤ 15 rooms × 4 rates × 30 lines × 200 chars) |
| `infrastructure/browser/jev_price_executor.py` | `LocalJevPriceRuntime` (host reuse, bounded navigation, extraction, grounding), `JevPriceBrowserExecutor` (sync facade, terminal mapping), `JevArmMeter`, `MeteredJevDecider` |

## Runtime

1. Start `BrowserUseSessionHost`, restore the lease, prove authentication with the same account
   probe as baseline, discard the verified refresh.
2. Navigate to the shared trusted entry URL; poll the snapshot ≤ 10 s for room cards.
3. If none: ≤ 6 Jev navigation decisions. Options: `CLICK` (target among ≤ 150 controls from
   Browser Use's selector map that already pass `node_chain_click_decision`), `SCROLL_DOWN`,
   `WAIT`, `BLOCKED`. The chosen control is re-fetched and re-guarded at execution; popup links
   become guarded same-tab navigation; invariants (single target, observable URL, no dialog) are
   rechecked after every action. Each action counts toward the 15-action cap.
4. Extraction (≤ 6 concurrent requests): property heading, room name per room, 4 questions per rate.
5. Grounding in code: the chosen total line must parse to exactly one amount in a currency
   compatible with the booking (bare `$` only for USD) and must not be a per-night line; stated
   nights, if present, must equal the stay; "free cancellation" requires the chosen line to say so
   and not "non-refundable" (deadline continuation lines are appended); "taxes included" requires
   included-tax text and no excluded-tax text, otherwise `conflicting`; stay facts come from
   Booking.com's current URL parameters, otherwise the query is `incomplete`.
6. Map to `TypedObservation` via the shared mapper; validators run in the unchanged service.

## Decisions and plan departures (first functional pass)

- Jev spend is **not** written to the Anthropic reservation ledger (`llm_cost_reservations` keeps
  its Anthropic-only CHECKs). It is recorded per arm in `price_comparison_arms.cost_nano_usd` and
  capped by `jev_comparison.max_daily_cost_usd`, checked before each arm; per-call reservation is the
  arm meter's own envelope. Rationale: avoids a table-rebuild migration of the spend ledger for a
  provider that costs ~USD 0.001 per check. Revisit if Jev is promoted.
- No confidence threshold is applied yet; grounding in code is the safety boundary. Confidence
  calibration is left to the comparison data.
- Environment secret `BOOKSAVER_TYPESAFE_API_KEY` added to the approved list (AGENTS.md); the
  Anthropic key is never reused for TypeSafe.
