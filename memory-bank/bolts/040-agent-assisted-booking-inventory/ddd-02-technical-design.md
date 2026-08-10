---
unit: 002-agent-assisted-booking-inventory
bolt: 040-agent-assisted-booking-inventory
stage: design
status: complete
updated: 2026-08-10T16:40:38Z
---

# Technical Design - Current-Evidence Inventory Recovery

## Architecture Pattern

Retain the existing hexagonal, deterministic-first inventory adapter and ADR-030 guarded recovery.
This is a local handoff correction inside the infrastructure adapter: safety classification reads a
fresh current observation, while the existing pre-navigation observation remains a verifier input.
No application, domain persistence, Telegram contract, schema, provider, or deployment topology
changes.

## Recovery Handoff

```text
capture pre-navigation baseline
             |
attempt deterministic open/readiness
             |
        exception raised
             |
obtain fresh bounded current observation
       /          |             \
 unavailable   unapproved      approved
     |             |               |
 fail unavailable  fail blocked    auth/captcha gates
     |             |               |
 zero LLM/actions  zero LLM/actions guarded recovery
                                      |
                     verifier compares current progress
                     with pre-navigation baseline
```

## Component Changes

### BookingComAccountInventorySource

- `_recover_navigation` obtains `_safe_observe(browser)` after the exception even when a
  pre-navigation observation was supplied.
- The fresh observation alone drives captcha, authentication, and route-allowlist checks.
- If fresh observation fails, record `UNAVAILABLE` and return without constructing the agent.
- Keep `before or current` only as the progress baseline supplied to the named recovery verifier.
- Preserve the existing post-agent fresh observation and allowlist verification.

### Content-Free Logging

- Add one warning when a navigation exception enters recovery.
- Emit only the named recovery step, `type(trigger).__name__`, and one destination category:
  `approved`, `unapproved`, or `unavailable`.
- Never log `str(trigger)`, raw/sanitized URL, title, text, element labels, user/reservation identity,
  cookies, screenshots, or model/provider content.
- Keep the durable schema-v13 audit unchanged; no URL-like field is added to recovery traces.

## API and Persistence

No public API, CLI, Telegram message, configuration, database table, migration, or repository method
changes. Existing failure details and recovery outcomes remain caller-scoped and redacted.

## Security Design

- **Destination authority**: Fresh current evidence is mandatory after an exception.
- **No stale fallback**: Missing current evidence cannot fall back to a previously approved page.
- **Allowlist**: Existing HTTPS Booking.com `myreservations`, `mytrips`, and confirmation routes stay
  unchanged.
- **Authentication/captcha**: Existing specific classification runs against the fresh page before
  provider construction.
- **Action safety**: Existing inventory guard and ADR-030 post-action destination checks remain
  unchanged.
- **Privacy**: Diagnostics use categories and exception class only.

## Error Handling

- Current observation unavailable → `InventoryRecoveryOutcome.UNAVAILABLE`, existing safe-page
  evidence detail, zero agent creation/calls/actions.
- Current captcha → `BLOCKED` plus `BOT_WALL`, zero agent creation/calls/actions.
- Current auth-required evidence → `BLOCKED` plus `AUTH_REQUIRED`, zero agent creation/calls/actions.
- Current unapproved destination → `BLOCKED`, existing approved-pages detail, zero agent
  creation/calls/actions.
- Current approved reservation page → existing guarded recovery and verifier outcomes.

## Test Strategy

1. Reproduce fresh `about:blank`, then move to an authenticated allowlisted page and raise a
   readiness-style exception; assert the agent observes the current page and recovery is attempted.
2. Make current observation unavailable after a previously available baseline; assert unavailable
   and zero agent construction.
3. Move from `about:blank` to an external/private-query destination; assert blocked, zero agent
   construction, and content-free logs.
4. Retain existing authentication, captcha, prohibited-action, completeness, and reconciliation
   regressions.
5. Run focused inventory tests, full Ruff, strict mypy, full pytest, CLI/config smoke, artifact
   validation, status integrity, and whitespace checks.

## ADR Analysis

No new ADR is warranted. ADR-030 already requires observing and validating the controllable page
before provider disclosure and action. ADR-027 and ADR-028 preserve authoritative account state and
completeness-gated absence. This bolt corrects implementation conformance to those decisions.
