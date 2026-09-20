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

The accepted root contract supports either exact accessible-list aria-setsize/posinset evidence or
the narrowly qualified embedded page-cache contract observed on the actual caller's Booking.com
root. Both require selected Active tab/panel binding, no busy/progress/pending pagination, stable
pre/post root/group membership and exact counts, no direct-root unknown or unresolved/truncated
work, and final authentication/guards.

For the page-cache alternative, accept only bounded data from the qualified
`b-trips-frontend-trip-xp-mfe` script namespace: exact `getTrips` CURRENT/UPCOMING scope, explicit
null first-page token, rowsPerPage10 and explicit null next-page token/backfill. Resolve unique Trip
references and match their identities/non-cancelled counts exactly to the selected Active panel's
rendered anchors. Missing/unsupported/nonterminal/conflicting cache data fails closed. The cache
is rendered-page evidence read through the existing browser, not an API integration or executable
script. It never independently establishes scope without matching rendered membership.

Explicit cancellation still requires the recognized cancellation detail heading plus unique numeric
confirmation and no contradictory status. This supersedes ADR039's unconditional prohibition only
for separately validated trusted proof; unsupported evidence remains positive-only.

Fresh caller login is valid September20–24. The first cloned replay reproduced the unsupported ARIA
root and preserved both the old EUR104 and new EUR94 active records. The captured real root then
qualified the two-trip cache/rendered-membership proof in offline Chromium with script execution
and network disabled; 57 parser regressions passed. The second live replay is in progress. These
facts do not yet establish successful real-account retirement, final quality or release acceptance.
Related: US192–194; ADR027/028 reservation authority, ADR039 default, ADR048 grouped reader.

## Guarded root re-navigation amendment

History restoration on actual caller replays 2–4 kept the same root cards/cache but removed the
selected Active tab role/aria bindings. Do not relax the proof to tabindex, cached evidence or card
counts. After a short guarded passive settle, permit at most one metered code-owned GET navigation
to the exact freshly observed qualified current root in the same tab, using the existing safety,
authentication, source/focus, deadline and action limits. No Page.reload, form replay, model action,
or old-proof reuse is introduced. The resulting page must independently satisfy the original full
selected Active/cache evidence and identical pre/post membership/count requirements; otherwise
retain positive-only incomplete reconciliation. This is a bounded evidence reacquisition step,
not weaker completeness authority. Refined live acceptance remains pending.

## Construction qualification completed

Live6 on the affected caller's cloned normal-coordinator state established full trusted scope and
correct absence retirement: four discovered/two eligible, old EUR104 absent/ineligible, separate
EUR94 upcoming/eligible. Final source gate passed2803tests/Ruff/mypy123 and the official cascade
completed Bolt077/US192–194/Unit012. Earlier pending/failed replays above remain historical evidence.
Exact installed-image qualification, current-head review, merge and production release are separate
pending Operations gates; cloned acceptance does not claim native Telegram or production execution.
