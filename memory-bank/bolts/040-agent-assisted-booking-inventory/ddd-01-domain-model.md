---
unit: 002-agent-assisted-booking-inventory
bolt: 040-agent-assisted-booking-inventory
stage: model
status: complete
updated: 2026-08-10T16:39:46Z
---

# Static Model - Current-Evidence Inventory Recovery

## Bounded Context

This corrective bolt remains inside authenticated Booking.com inventory discovery. It changes how
one navigation failure is classified and handed to the existing guarded recovery controller; it
does not change reservation identity, synchronization completeness, reconciliation, monitoring
eligibility, action authority, or caller/session ownership.

## Domain Concepts

### Inventory Navigation Attempt

One deterministic attempt to open a named read-only reservation view. It owns:

- the target operation and required inventory scope;
- a pre-navigation observation used only as a progress baseline;
- a post-failure current observation used as destination and safety evidence;
- the normalized exception category that triggered recovery;
- the existing recovery outcome and failure code.

### Current Page Evidence

A bounded observation collected after the navigation exception. It is authoritative only for
classifying the current browser destination, authentication/captcha state, and the evidence exposed
to guarded recovery. It contains the adapter's existing sanitized observation surface and never
becomes persisted reservation evidence by itself.

### Progress Baseline

The bounded observation captured before navigation. It may prove that a subsequent current
observation changed, but it cannot describe the browser's current safety state after navigation was
attempted.

### Destination Category

One content-free operational category:

- `approved`: current evidence is an allowlisted HTTPS Booking.com reservation/detail page;
- `unapproved`: current evidence exists but is outside that allowlist;
- `unavailable`: the current page cannot be observed safely.

## Aggregate and Invariants

### Inventory Discovery Episode

Members:

- caller-scoped authenticated browser lease;
- pending and visited inventory operations;
- current navigation attempt;
- existing guarded recovery budget and verifier;
- positive reservation observations and completeness state.

Invariants:

1. Available current evidence always supersedes pre-navigation evidence for destination, auth, and
   captcha safety classification after an exception.
2. The pre-navigation observation remains eligible only as the verifier's progress baseline.
3. Missing current evidence fails unavailable; recovery never acts from stale evidence.
4. Authentication, captcha, unapproved destination, and prohibited-action boundaries stop before
   any LLM disclosure or browser action.
5. Approved current evidence may enter only the existing named, bounded guarded recovery step.
6. No new route, selector, browser action, LLM capability, or completeness authority is introduced.
7. Failed or incomplete discovery retains the last conclusive account inventory and cannot start a
   price check from stale data.
8. Diagnostics expose only the step, exception class, and destination category; exception messages,
   URLs, page text, identities, cookies, screenshots, and provider content remain excluded.

## Domain Services

- **Post-failure evidence classifier**: Re-observes the browser, applies authentication/captcha and
  reservation-page allowlists, and returns approved, unapproved, or unavailable.
- **Inventory recovery controller**: Reuses ADR-030 with current evidence as its controllable page
  and the pre-navigation observation as the verification baseline.
- **Completeness-gated reconciler**: Reuses ADR-028 unchanged; this bolt cannot authorize absence.

## Domain Outcomes

- **Recovered**: Existing guarded recovery verifies the named operation from current approved
  evidence.
- **Gave up / provider error / budget exhausted**: Existing bounded recovery outcomes remain intact.
- **Blocked**: Current auth, captcha, unapproved, or prohibited evidence stops safely.
- **Unavailable**: No fresh current observation can be obtained after the navigation exception.

## Repository Interfaces

No repository or schema change is required. The existing synchronization run and content-free audit
remain authoritative for durable outcomes.

## Ubiquitous Language

- **Current evidence**: Observation obtained after the exception and used for safety classification.
- **Stale baseline**: Observation obtained before navigation and used only to compare progress.
- **Recovery handoff**: Transfer from a failed deterministic navigation to the existing guarded
  controller after current evidence passes all safety gates.
- **Content-free diagnostic**: Step, exception type, and bounded category without page/account data.

## Story Coverage

- **US-129**: Separates current safety evidence from the stale baseline, preserves every fail-closed
  boundary, and makes the incident shape locally diagnosable without private content.
