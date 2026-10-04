---
stage: test
bolt: 085-jev-price-executor
created: "2026-09-27T17:00:00Z"
status: in-progress
---

# Jev price executor — test report

## 2026-09-27 — construction evidence

- `tests/unit/test_typesafe_client.py` (9): pinned model + bearer auth, typed parsing,
  out-of-set/non-argmax/unnormalized answers rejected and conservatively charged, version drift
  fails closed with usage charged, 401 not retried, 529/429 retried then success without charge,
  timeouts charged conservatively, expired deadline sends nothing, key hidden from repr.
- `tests/unit/browser/test_jev_price_executor.py` (9): money parsing, full extraction →
  unchanged validator accepts only the refundable all-in whole-stay offer, tax-excluded cards never
  become all-in, per-night choice and unsupported refund claim rejected, nights mismatch
  incomplete, missing URL facts incomplete, page state carries no session material, provider
  failure propagates, meter exact + conservative accounting and µUSD mirror.
- `tests/unit/test_jev_comparison_config.py` (9): defaults, caps, fail-closed parsing, daemon
  enablement requires both config and the TypeSafe secret.
- Local browser smoke (see bolt 084). Full suite: 3,065 passed + new tests, Ruff and mypy clean.

Pending (live acceptance): real TypeSafe responses and authenticated Booking.com pages.

## 2026-10-01 — first live TypeSafe qualification

With the owner's key provisioned (the `.env` variable had been named `..._AI_KEY`; renamed to
`BOOKSAVER_TYPESAFE_API_KEY`), the first real requests succeeded: `jev-1.13.0`, ~280 ms, object
instructions/criteria accepted, full probability maps returned. Finding: the whole-stay total
question answered "none" (0.97–0.99) for every one-night rate card, where nightly and total amounts
are equal, and only 0.73 for a two-night card. Fixed by stating the stay length and Booking.com's
`Price $X` labelling (adapter cohort `jev-price-v2`); the patched full request then grounded 10/10
live cases correctly (1/2/4 nights, USD/EUR, tax included/excluded, per-night-only rejected,
0.94–0.99). Other questions (cancellation, cancellation line, taxes, room name, property heading)
were correct at ≥ 0.94 unchanged. Probe spend ≈ USD 0.001.

## 2026-10-03 — run diagnostics after the first unexplained live failure

Live record after three days (cohort `jev-price-v2`): the owner's booking verified on 10 of 11 Jev
runs; one scheduled run (2026-10-03T22:11Z, Jev first) ended `no_valid_observation` after exactly
six navigation decisions (4,003 input tokens, 63 s) while the baseline, run next from the same
snapshot, verified 357.00 USD. Nothing recorded which page the candidate saw or what it chose, so
the cause is **not determined**; candidates are a transient challenge/error page, a load slower
than the 10 s readiness wait, a card layout the snapshot missed, or a click that left the property
page. (The invitee booking fails on both arms every run with `room_mismatch` and is unrelated.)

Added a content-free episode diagnostic: entry kind, stage, readiness seconds, snapshot
error/empty counts, per-decision page signature (page kind, room/heading/text counts, marker
names such as `oops`, `bot`, `chal`, control count, chosen operation and confidence), the terminal
reason, and extraction counts. It is logged at WARNING when no observation results, captured on
timeout, stored in `price_comparison_arms.detail` for every Jev run, listed by
`booksaver comparison report`, and never included in the Telegram report. Tests assert that no
page text, URL, or property name appears in it. Full suite 3,091 passed; Ruff and mypy clean.
