---
id: ADR-049
status: accepted
created: 2026-09-19T22:04:01Z
bolt: 077-trusted-inventory-reconciliation
amends: ADR-039, ADR-048
---

# ADR-049: Trusted current-list reconciliation

## Context

ADR039 deliberately forbids absence retirement from model-observed inventory. The accepted grouped
reader now provides code-owned navigation, but its diagnostic counts alone still cannot prove a
complete current list. Indefinitely treating removed/cancelled/rebooked saved entries as current
misrepresents the user's account. The user explicitly authorized this follow-up and scoped checkpoints.

## Decision

Supersede only ADR039's unconditional positive-only rule when BookSaver validates a separate,
code-owned, caller/run/session-bound current Active scope proof. Require positive root exhaustion,
exact resolved group/card membership, stable pre/post membership, no unknown/conflicting/truncated
or unresolved work, and final authentication/safety/limit checks. Model assertions and count equality
alone remain incapable of granting authority. ADR048 audit counters remain diagnostic unless the
stronger proof is established.

A qualified complete refresh may atomically retire absent saved UPCOMING/CURRENT identities from
active/monitoring projections while preserving history. Out-of-scope saved states are untouched.
Absence retirement does not mean cancellation. Explicit cancellation is a positive exact-confirmation
transition; new confirmation identities remain distinct after a rebooking. Without proof, preserve
unseen records and label them saved/unverified. All price eligibility and current-run receipt gates remain.

## Alternatives and consequences

Permanent positive-only reconciliation prevents false absence but cannot satisfy accurate current
inventory. Model completeness is rejected because it grants untrusted output destructive authority.
Deleting historical rows or matching a replacement by hotel/dates is rejected because it destroys
identity/history. A narrow proof is auditable but intentionally leaves unsupported layouts incomplete.
Atomic caller-scoped reconciliation and adversarial tests limit false-retirement risk; existing
backup, exact-image qualification and rollback remain mandatory.

## Acceptance and live boundary

The main agent and reviewer agreed the contract within the user's approved scope: selected Active
tab/aria-controls panel, complete accessible list aria-setsize/posinset, no busy/progress/pending
pagination, stable pre/post root/group membership and exact counts, no direct-root unknown or
unresolved/truncated work, and final auth/guards. Explicit cancellation additionally requires the
recognized cancellation detail heading plus unique numeric confirmation and no contradictory status.

This supersedes ADR039's unconditional prohibition only for that separately validated trusted
proof. The current Booking.com DOM is not yet qualified and the father's login is expired; live
acceptance remains pending. Unsupported evidence remains positive-only. No release gate is waived.
Related: US192–194; ADR027/028 reservation authority, ADR039 default, ADR048 grouped reader.
