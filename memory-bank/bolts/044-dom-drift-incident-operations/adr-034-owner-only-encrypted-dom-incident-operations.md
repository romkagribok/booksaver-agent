---
bolt: 044-dom-drift-incident-operations
created: 2026-08-13T03:10:00Z
status: accepted
superseded_by:
---

# ADR-034: Owner-Only Encrypted DOM Incident Operations

## Context

Adaptive recovery can keep BookSaver working after a Booking.com DOM change, but silent recovery
would leave maintainers unaware that deterministic code has drifted. Conversely, page observations,
screenshots, model responses, URLs, and reservation details are private and must not enter Telegram,
ordinary logs, or plaintext diagnostic storage. Notifications must not delay browser cleanup or be
lost silently on daemon restart.

## Decision

1. Correlate only maintenance-worthy model-assisted outcomes using a SHA-256 fingerprint of stable
   allowlisted machine fields. Predictable auth/provider/budget/etc outcomes create no incident.
2. Open immediately for `code_maintenance_required`; otherwise require two identical eligible
   occurrences within six hours. Resolve only on later deterministic success.
3. Persist content-free incident/alert metadata transactionally in schema v15 and deliver only to
   the configured owner chat through a typed dedicated notifier with durable retry/suppression.
4. Retain exactly one bounded sanitized diagnostic bundle per incident as a Fernet-encrypted SQLite
   BLOB for seven days. Never reuse plaintext snapshot storage or fall back to plaintext.
5. A visual may be retained only after text/images/form values and other content are hidden in the
   live page before capture; otherwise omit it explicitly.
6. Capture the in-memory draft while the page exists, but persist/encrypt/notify only after browser
   cleanup and coordinator release. A lifecycle worker owns retries and retention.
7. Expose content-free owner counts in `/status` and local-only list/inspect CLI commands. Invited
   users receive no incident existence or evidence disclosure.

## Consequences

The owner learns when DOM maintenance is needed even when LLM recovery succeeds, without leaking
caller evidence to chat or logs. Restart-safe delivery and exact retention add schema, worker, and
encryption complexity. Diagnostic images are intentionally less informative because privacy-safe
structural capture takes precedence over raw-page fidelity.

## Related

- **Stories**: US-137, US-138, US-139
- **ADRs**: ADR-019, ADR-021, ADR-024, ADR-030, ADR-031, ADR-032, ADR-033
