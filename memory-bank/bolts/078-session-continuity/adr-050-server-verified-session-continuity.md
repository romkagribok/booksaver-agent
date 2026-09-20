---
adr: ADR-050
status: accepted
created: "2026-09-20T20:09:01Z"
bolt: 078-session-continuity
amends: ADR-024, ADR-025, ADR-035, ADR-048
---

# ADR-050: Server-verified session continuity

## Context

The current import expires the whole session at the earliest expiry of any cookie, and refresh
retains that original cutoff. Grouped inventory cannot export desktop-mutated cookies while
price assumes inventory already renewed the saved session. The current path therefore loses
renewal opportunities. Failed authentication predicates also conflate temporary responses with
sign-out. The user approved quiet background continuity and bounded recovery in Intent 025.

## Decision

Use code-owned positive protected-account response evidence to renew an existing caller's
mobile cookie bundle. Never rewrite provider cookie expiry values or guarantee a minimum
login lifetime. Preserve the original mobile context before desktop inventory use. Keep
interactive `/connect` receipt/negative-control rules unchanged; maintenance only revalidates
an already stored caller bundle and cannot import an unrelated session or authenticate a new
caller. Maintenance uses the established negative baseline and two independent positive proofs for
the exact candidate cookie snapshot, plus the explicit negative redirect classification;
202 pending and uncertain/challenged responses are retryable, never positive or forced logout.

Admit maintenance through the same browser gate, with no LLM, fixed GET-only destination,
60-second total deadline including launch and cleanup, and at most two complete verification
attempts (three fixed GET observations each, six maximum, no nested retries). Changed cookie
material requires its own full verification before persistence. A successful
foreground verification suppresses redundant daily maintenance. Persist daily due time and
15-minute/1-hour/6-hour/24-hour retry backoff in the encrypted per-user aggregate. One notice
per revision covers confirmed interactive need or 48 hours of uncertainty; success is silent.

Provide a separate verification-only migration path for legacy ACTIVE bundles expired solely
by the old aggregate policy. Ordinary resolution remains closed until fresh positive proof.
Do not revive explicit reauthentication, missing/corrupt data, revoked users or purged sessions.
Revision-and-attempt compare-and-set, owner locking and access checks protect concurrent login,
disconnect and revocation. No database cookie storage or second browser service is introduced.

## Bounded process ownership exception

A cancellable asynchronous future does not prove Chromium has exited. Maintenance therefore
uses a supervised ephemeral Linux worker under the existing sole browser gate. It is neither
a persistent service nor another scheduler. A private bounded socket carries cookie bytes;
no cookies enter argv, disk or logs. Linux child-subreaper ownership and `/proc` descendant
tracking include detached browser process groups; PID start identities prevent signaling a
reused PID. Cleanup confirmation remains inside the hard deadline. If ownership cannot be
cleared, a distinct fatal error stops daemon admission before gate release. Broad process
killing is forbidden. Other platforms disable only background maintenance, silently retaining
session state and producing an operator diagnostic; they must not generate retry/reconnect
nudges due to unsupported process supervision. Exact Linux image qualification exercises real
detached descendants and Chromium timeout cleanup in addition to unit tests.

## Consequences

Users avoid BookSaver-imposed early expiry and can retain server-valid sessions through normal
activity and daily maintenance. Booking.com can still revoke them at any time. Additional
bounded background requests require exact-image qualification and durable retry discipline.
Unknown response changes reduce availability instead of relaxing authentication. A crash after
claiming a notification can suppress that one message rather than duplicate sensitive nudges;
manual `/connect` and status remain available. Existing price/inventory evidence, admission,
cost/action budgets and reservation authority are unchanged.

The user's approval covers the documented scope and routine construction checkpoints; a new
authentication predicate or request expansion requires a consequential-decision review.
