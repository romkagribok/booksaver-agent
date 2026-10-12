---
id: ADR-058
status: accepted
created: 2026-10-10T02:01:25Z
bolt: 092-confirmation-booked-total
amends: ADR-048
---

# ADR-058: Page-verified booked total replaces a saved total

## Context

Saved reservation facts are authoritative once stored: an agentic refresh that observes a
different booked total fails the whole reconciliation, and an unknown total keeps the saved one
(ADR-039, ADR-048). That rule protects saved facts from untrusted provider output. It also makes a
wrong saved total permanent. The owner's dollar reservation carries USD301 from the retired
trips-list reader while the confirmation page states USD346.08, so every price check compares
against a baseline about USD45 too low and a real saving in that gap would be reported as none.
Once the confirmation reader can read that page, the unchanged rule would turn the correct total
into a persistence conflict and fail every refresh for that caller.

## Decision

Distinguish where a total came from. A total reconciled by BookSaver's own confirmation reader,
from the caller's own confirmation page, with its components summing exactly in one printed
currency, is page-verified. A page-verified total that differs from the saved amount or currency
replaces it, together with the monitoring baseline, in the same caller-scoped transaction, and
savings opportunities computed against the old baseline are removed. Every total that is not
page-verified, including anything a provider submits, keeps failing closed against a saved total.
The booked total is recorded in the currency the page prints; BookSaver never converts.

## Rationale

The confirmation page is the most direct statement of what the guest owes, and the reader accepts
it only under strict reconciliation, so it is better evidence than any earlier saved figure. A
reservation's total can also change legitimately when the guest modifies the booking. The same
split already governs property names (a code-owned anchor may rename a saved hotel; provider
output may not), so this extends an accepted pattern rather than adding a new kind of authority.

## Alternatives considered

- Keep saved totals immutable: leaves known-wrong baselines in place and would break refreshes
  once the page becomes readable.
- One-off data correction of the affected row: fixes one booking, not the rule, and bypasses the
  reader that should own the fact.
- Let any observed total replace the saved one: gives untrusted provider output authority over
  the baseline that savings alerts are computed from.
- Re-register the reservation as new: loses check history and identity continuity.

## Consequences

- A stale baseline corrects itself on the next refresh that reads the confirmation page.
- A reader defect that reconciles a wrong total would now overwrite a correct saved one. The
  exposure is bounded by exact component reconciliation, single-currency agreement and identity
  binding to the same caller and confirmation, and by adversarial tests.
- Savings opportunities for a booking whose baseline changed are discarded and re-evaluated at the
  next price check.
- No schema change and no change for provider-submitted facts.

## Acceptance boundary

Accepted for construction under the owner's waiver of per-step approval for this task. The dollar
layout itself is not yet verified against the real page; that qualification is tracked by US-228
and is independent of this decision.
Related: US-226–228; ADR-027 reservation authority, ADR-039 positive-only inventory, ADR-048
grouped confirmation facts, ADR-049 trusted reconciliation.

## Qualification 2026-10-12T22:18:02Z

The decision was exercised on the affected caller's real confirmation page in an isolated replay
(candidate `bookedtotal-wip-0478f4c`, cloned state, production paused 2026-10-12T22:15:36Z to
22:17:07Z and restored on its original image). The page-verified USD346.08 replaced the saved
USD301 on the reservation and on the same monitoring booking, check history was kept, the booking
stayed eligible, and no other caller's row changed. The earlier boundary note about the unverified
dollar layout is superseded by this result.
