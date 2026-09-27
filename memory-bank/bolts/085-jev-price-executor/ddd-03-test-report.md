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
