---
stage: test
bolt: 022-telegram-privacy-boundaries
created: 2026-07-19T03:05:03Z
---

# Test Walkthrough: Telegram Privacy Boundaries

## Automated Results

- Focused integrated privacy suite: **213 passed**.
- Final full suite: **763 passed** in 6.67 seconds.
- Ruff: clean across source and tests.
- mypy: clean across 78 source files.
- `git diff --check`: clean.
- Artifact validator: no new issues; the same 38 historical story-ID/reference findings remain in
  completed legacy artifacts.

## Acceptance Evidence

- Non-private command/callback tests prove invite codes remain unused, usernames unchanged, dialogs
  unopened, and crafted delete callbacks side-effect free.
- Two-user status and selector tests prove caller scoping; foreign register/edit confirmation tests
  prove the global uniqueness oracle is masked.
- Admin sentinel tests seed keys, active/archived bookings, and failures, then fail if Booking list
  methods are invoked and assert every exact sentinel is absent.
- Coordinator Event-driven tests prove post-plan revocation opens no browser, consumes no quota, and
  writes no cap result; mid-flight history persists while external effects are suppressed.
- Rebook Event-driven tests prove a 600-second wait exits within one second after revocation, sends no
  later handoff/edit/reply, and releases the active-session guard.
- Active-owner notification and invalid-key/cap notice tests cover delivery-time access state.

## Formal Closure

The product owner approved the combined implementation review. The final full run passed 763 tests,
Ruff, mypy, and diff checks before Bolts 021 and 022 were closed in dependency order.
