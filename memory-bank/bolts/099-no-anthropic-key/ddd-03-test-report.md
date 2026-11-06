---
unit: 002-no-anthropic-key
bolt: 099-no-anthropic-key
stage: test
status: complete
created: 2026-11-06T00:40:00Z
updated: 2026-11-06T00:40:00Z
---

# Test Report - No Anthropic Key

## Summary

- Full suite: 3,270 passed, 1 skipped; Ruff and mypy clean; AI-DLC validators 0 errors.
- Updated: five legacy-inventory tests now select the legacy path explicitly (that code stays until
  bolt 100); routing, probe and disclosure-string tests assert the ADR-062 behaviour.
- New: invitee informed once (no record or stale record), owner never, no message without a ready
  session, a failed send records nothing and is retried; executor builds with an empty key.
- Not unit-tested: the runtime branch that returns a provider failure when the grouped reader
  cannot read the page and no key is set (the runtime needs a live browser to reach it).

## Live replay (kit `releasea-20261106`, cloned data, `BOOKSAVER_LLM_API_KEY` empty)

- Owner, dad and the third invitee: syncs complete (6, 2 and 0 discovered); the dad's four refundable
  stays and the owner's stay eligible.
- Owner's price check through Jev: success at USD 581.
- Anthropic model calls during the run: 0.
