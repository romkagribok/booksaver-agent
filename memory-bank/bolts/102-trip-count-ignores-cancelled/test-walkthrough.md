---
stage: test
bolt: 102-trip-count-ignores-cancelled
created: 2026-11-06T00:21:42Z
---

# Test Walkthrough

- Unit: a trip with a cancelled card verifies against the count without it and with it, not
  against a third count, and the cancelled card is still read. Full suite 3,261 passed, 1 skipped;
  Ruff and mypy clean.
- Live replay on cloned data (kit `tripcount-20261106`): the dad's sync completed (six discovered),
  the superseded Best Western (USD 521.11) is no longer upcoming, the new one (USD 503.65) and the
  other refundable stays stay eligible. The owner's sync also completed instead of incomplete.
