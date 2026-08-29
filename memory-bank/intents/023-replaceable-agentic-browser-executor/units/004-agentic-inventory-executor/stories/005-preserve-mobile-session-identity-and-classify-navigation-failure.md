---
id: 005-preserve-mobile-session-identity-and-classify-navigation-failure
unit: 004-agentic-inventory-executor
intent: 023-replaceable-agentic-browser-executor
status: complete
priority: must
created: 2026-08-29T20:51:44.000Z
assigned_bolt: 059-agentic-inventory-executor
implemented: true
---

# Story: Preserve Mobile Session Identity and Classify Navigation Failure

## User Story

**As a** BookSaver deployment owner
**I want** authenticated sessions restored into the same supported mobile browser identity and
navigation failures classified before agentic perception
**So that** Booking.com capability access is reliable without adding selectors or wasting model
calls on an internal browser error page

## Acceptance Criteria

- [x] Local Stagehand derives its user agent, viewport, scale, touch, and locale from BookSaver's
  configured version-matched mobile-web profile rather than a separate desktop identity.
- [x] Both price and inventory one-shot executors receive that configuration through explicit
  dependency injection; cookies and browser identity remain local and never enter model prompts.
- [x] A production-shaped regression proves that the desktop identity loops through Booking OAuth
  while the configured mobile identity reaches a permitted protected inventory route.
- [x] A failed top-level navigation records only a closed transport-failure category and sanitized
  destination metadata; raw URLs, redirect values, page content, cookies, and account data remain
  absent.
- [x] `ERR_TOO_MANY_REDIRECTS` at the fixed authenticated inventory entry becomes a typed signed-out
  outcome, not `unsafe_action` or `non_allowlisted_destination`; other browser transport failures
  remain fail-closed provider failures.
- [x] Stagehand extraction and Anthropic computer use are not called when the protected Booking.com
  document was not reached, and the execution reports zero model usage and cost.
- [x] No DOM selector, page-text authentication rule, endpoint-specific action allowance, new
  provider, or increased budget is introduced.

## Dependencies

- US-153, US-156, US-157, US-158; ADR-024, ADR-025, ADR-026, ADR-036 through ADR-040.

## Out of Scope

- Changing the human `/connect` experience, persisting browser profiles, weakening action or
  destination guards, or treating inventory evidence as authoritative absence.
