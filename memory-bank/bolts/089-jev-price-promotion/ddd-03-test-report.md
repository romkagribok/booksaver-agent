---
stage: test
bolt: 089-jev-price-promotion
created: "2026-10-10T01:49:40Z"
status: in-progress
---

# Jev as the price method — test report

## 2026-10-10 — construction evidence

Automated (new or extended):

- `tests/unit/browser/test_jev_price_executor.py`: eight discounted-card layouts ground only the
  current price or stay unpriced with the right reason; unpriced-reason counts in the diagnostic;
  error page reloaded at most twice before any Jev decision, non-error pages not reloaded;
  refresh eligibility only when the runtime kept a verified session.
- `tests/unit/browser/test_jev_primary_executor.py`: selectable kind with one behavior version;
  each run recorded with cost and diagnostic; daily cap counts earlier runs, refuses without
  running, resets at the UTC day; unreadable ledger fails closed; a raising run is recorded and
  propagates; purge removes run records.
- `tests/unit/test_jev_comparison_config.py`: `jev` parses; rejected together with paired mode;
  each method needs only its own credential.
- `tests/unit/daemon/test_price_comparison_pairing.py`: with `price_executor = jev` the real
  monitor path writes history, feeds the savings pipeline, refreshes the saved session, records
  canary metrics under `jev-price-v3`, and creates no comparison.

Live model check (TypeSafe `jev-1.13.0`, from the production container with the patched source,
about USD 0.0007): 12 of 12 synthetic rate cards grounded as intended, covering plain cards for
1 and 2 nights in EUR and USD, five labelled discount layouts, a 3-night discount, a discounted
non-refundable rate, nightly-only (unpriced) and two unlabelled amounts (unpriced, `ambiguous`).

**Not verified:** the real signed-in page of the affected booking was never observed. That its
booked room shows an original and a current price is inferred from a 10% difference between the
verified price and the signed-out rate and from exactly four of sixteen rates going unpriced.

## Criterion status

| Story | Status |
|---|---|
| US-216 discounted rate cards | Automated and live-model criteria met; **production confirmation on the real booking pending (phase 1)** |
| US-217 Jev as the price method | Automated criteria met; **production switch pending (phase 2)** |
| US-218 explainable runs | Met; first part delivered earlier in PR #76 |
| US-219 error-page reload | Automated criteria met; the real error page recurs unpredictably, so production confirmation is opportunistic |

Gate results and release evidence are appended below as they are produced.

## 2026-10-10T02:13:10Z — independent review and its disposition

Cursor Bugbot has not run on this intent's pull requests, so a read-only reviewer examined the
uncommitted change, running the grounding functions with adversarial inputs.

| Finding | Severity | Disposition |
|---|---|---|
| "Current price" accepted before the other checks: a nightly amount could become a multi-night total; "per person" and "from" tails accepted | High | Fixed: total grounding rewritten to classify every amount first; nightly-equality guard for stays longer than one night |
| Any line containing "price" or "total" counted as a label ("Total savings", "Price per night", "Member price", "Price for:") | High | Fixed: label status only for an exact label line or a label-then-one-amount line; component wording extended |
| "+ € 12 taxes and fees" not recognised as excluded; "included" matched across the whole card | Medium | Fixed: pattern handles the spaced currency; matching limited to one line or two adjacent lines |
| `price_executor = "jev"` with legacy routing never runs Jev; startup log overstated | Medium | Fixed: config rejected; log states the routing and its limit |
| Reload loop skipped the invariant before its first reload | Medium | Fixed: invariant checked before and after each reload |
| Error page recognised from page body text | Low | Fixed: title or heading only, never with bot-check wording |
| Space-grouped amounts read as a smaller number | Low | Fixed: not parsed and not offered as candidates |
| Ledger write lost under a database lock; purge lowers counted spend; cap check not atomic | Low | Accepted and documented in the design |
| `participants` ignored and disclosure text names Anthropic in primary mode | Low | Accepted and documented; owner chose all users on 2026-09-27 |
| Old image rejects `price_executor = "jev"` | Low | Documented rollback order |
| Auto-regression to legacy | Medium | Not applicable to this deployment: it arms only after an explicit promotion, never performed; documented |

Regressions added: 20 "never a total" cards, 8 "still a total" cards, taxes on top, error-page
classification, hijacked-tab reload, space-grouped amounts, legacy-routing rejection.

Live model recheck with the final rules: 14 of 14 (about USD 0.0008), including a three-night card
whose "current price" equals its nightly amount (unpriced) and taxes added on top (not all-in).

**Consequence to watch in phase 1:** the stricter rules refuse an unlabelled amount on a
multi-night stay. The two bookings Jev verifies today were verified under the looser rules, and
their signed-in card layout was never observed, so their first runs on this release must be
checked before the switch.

## 2026-10-10T03:29:57Z — release evidence, phase 1

Released as `jevprimary-7b18adc` on 2026-10-10T02:42:22Z with production configuration unchanged
(`operations/releases/7b18adc-jev-price-method-phase-1.md`): full gate, Bugbot passed on the PR
head, exact-image checks, and a two-configuration stage probe on a production snapshot passed.

Still open before this bolt can complete: production confirmation of US-216 on the affected
booking, a check that previously verified bookings still verify, and the phase 2 switch (US-217).

## 2026-10-12T23:16:49Z — phase 2: production evidence and the switch

- **US-216 met in production.** 24 paired checks on the phase 1 release: the discounted-room
  booking verified 8 of 8 (0 of 27 before) with all 16 rates priced and the same price as the LLM
  method in the five pairs where both verified. The two other bookings stayed at 8 of 8 under the
  stricter grounding.
- **US-219.** No run met the error page in this period, so the reload is still unobserved live.
- **Defect before the switch.** The meal gate deployed by bolt 091 made the Jev path classify
  breakfast rates as unknown (rate name counted as meal wording). Fixed in PR #86 with a
  regression using the live wording; Bugbot passed.
- **US-217 switch done.** Production runs `price_executor = jev` with paired mode off since
  2026-10-12T23:15:40Z; wiring and config verified inside the container.

**Still open, so this bolt is not complete:** no price check has run in Jev-only mode yet. The
bolt closes when the first scheduled checks (from 2026-10-13T02:03Z) show a canonical Jev result
in `check_history` with a `jev_price_runs` record, and the breakfast reservation selects a
breakfast rate or reports why not.
