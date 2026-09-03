---
intent: 023-replaceable-agentic-browser-executor
created: 2026-08-14T02:46:26Z
completed: 2026-09-02T23:44:45Z
status: amended
---

# Inception Log: Replaceable Agentic Browser Executor

## Overview

**Intent**: Separate BookSaver's trusted control plane from replaceable read-only Booking.com
perception and navigation.
**Type**: Brown-field architecture refactoring and resilience enhancement.

## Checkpoint Approvals

The product owner's accepted implementation plan on 2026-08-16 resolves the original four
checkpoints. On 2026-08-25 the owner approved an amendment that advances Stagehand inventory for
every authorized user, accepts positive-only reconciliation, removes duplicate `/checknow`
inventory execution, and authorizes the amended AI-DLC flow through final merge. Deployment and
production data access remain separate operations.
On 2026-08-27 the first live agentic inventory run proved local Stagehand launch/navigation but
failed before semantic extraction because exact destination admission rejected the resulting
Booking.com route. The owner approved replacing exact path/query admission with layered
observation-versus-interaction policy and adding privacy-safe destination diagnostics.
On 2026-08-28 the next live run passed destination admission but exposed a coordinator-created
SQLite spend-ledger connection being reused by the dedicated async browser thread. The owner
approved a narrow thread-affinity correction through final merge and production redeployment.
On 2026-08-28 the first run with a valid Anthropic key exposed two pre-inference schema
incompatibilities: Stagehand rejected 18 union parameters against its limit of 16, and Anthropic
computer use rejected `maxItems`. The owner approved the bounded provider-schema correction through
final merge and production redeployment.
On 2026-08-29 a production inventory run exposed a Booking.com OAuth redirect loop only in the
desktop-identity Stagehand browser. The same encrypted session reached the protected inventory in
the accepted Pixel 7 identity. The owner approved a corrective design that treats mobile browser
identity as a session compatibility invariant, classifies transport failures before model work,
and proceeds through final merge and production redeployment without adding DOM verification.
On 2026-08-30 the owner approved a reliability-first Browser Use OSS slice for Telegram
`/bookings` only. Stagehand remains active for post-connect, `/checknow`, scheduled inventory, and
price execution. The owner authorized the amended AI-DLC flow through implementation, Bugbot,
merge, and production redeployment.
On 2026-08-31 production evidence showed the accepted replay had re-observed one caller-owned saved
stay through a code shortcut and had not exercised discovery. The owner required continued work
until `/bookings` can discover inventory as expected. The correction defines empty-repository live
rediscovery as the acceptance gate and does not broaden absence or browser action authority.
On 2026-09-01 an exact coordinator-level VPS replay waited for Browser Use to terminate, accepted
one current reservation, and exited nonzero only because the Telegram outcome treated every
positive-only result as a failed refresh. The owner required the command to distinguish successful
positive observation from authoritative completeness and to pass the same waiting replay before
release.
On 2026-09-02 the owner approved making Browser Use the default price executor for both `/checknow`
and scheduled checks, retaining Stagehand and the deterministic path as explicit future-job
rollback choices without same-job fallback. The owner accepted an initial USD 0.25/check canary
average with the existing USD 0.50 p95 and USD 1 hard cap, while retaining USD 0.10/check for
invited-user promotion, and authorized construction through Bugbot review when available, merge,
production deployment, and a production-equivalent price replay.

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | Amended | `requirements.md` (FR-1 through FR-20) |
| System Context | Amended | `system-context.md` |
| Architecture Decisions | Accepted | `architecture-decisions.md`, ADR-036 through ADR-044 |
| Units | Amended | `units.md` and six unit briefs |
| Stories | Amended | 27 story files (US-143 through US-169) |
| Bolt Plan | Amended | Bolts 050 through 064, with 052 live-gated and 055 blocked |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 20 |
| Non-Functional Requirements | 7 |
| Units | 6 |
| Stories | 27 |
| Bolts Planned | 6 plus corrective bolts 054 and 056 through 064 |

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-08-14 | Create intent 023 on a separate `codex/` branch | Trust boundaries and production browser routing are consequential | Yes |
| 2026-08-16 | BookSaver remains the trusted control plane | Executor evidence must not acquire domain authority | Yes |
| 2026-08-16 | Use local Stagehand then one guarded Sonnet computer-use episode | Semantic-first cost control plus visual resilience without a managed browser | Yes |
| 2026-08-16 | Keep browser/session custody local and transient | Cookies and credentials never reach providers | Yes |
| 2026-08-16 | Preserve legacy as default through qualification | Enables comparison and immediate rollback | Yes |
| 2026-08-16 | Do not build cached recovery or selector learning | Avoid duplicating harness capabilities before evidence demands it | Yes |
| 2026-08-25 | Advance agentic inventory for every authorized user | Legacy inventory blocks price-canary evidence and no invitees currently use the deployment | Yes |
| 2026-08-25 | Preserve positive-only reconciliation | Current-run evidence can unblock a known reservation without trusting model-declared absence | Yes |
| 2026-08-25 | Remove duplicate `/checknow` inventory execution | One selected operation must share one inventory verification, budget, and deadline | Yes |
| 2026-08-27 | Separate destination observation from interaction authority | Benign Booking.com route churn must not block Stagehand perception or silently expand action authority | Yes |
| 2026-08-27 | Log only sanitized destination shape and rejection codes | Live failures need local diagnosis without raw URLs, query values, page content, or session data | Yes |
| 2026-08-28 | Keep persistent cost accounting thread-affine | Stagehand's async runner must not reuse the coordinator thread's SQLite connection | Yes |
| 2026-08-28 | Keep provider schemas within active runtime subsets | Stagehand and Anthropic must accept typed schemas before inference while code retains all bounds | Yes |
| 2026-08-29 | Bind restored sessions to the accepted mobile browser identity | Capability access proved browser-identity-sensitive; matching the producer identity is more robust than endpoint-specific DOM verification | Yes |
| 2026-08-29 | Classify browser transport failures before perception | Internal Chrome errors and OAuth loops must not become unsafe destinations or trigger model spend | Yes |
| 2026-08-30 | Use local Browser Use OSS only for `/bookings` | Test a more established full agent without risking other inventory triggers or price execution | Yes |
| 2026-08-30 | Keep Browser Use bounded and fail closed | Existing session, budget, action, validation, positive-only, privacy, and no-same-job-fallback boundaries remain authoritative | Yes |
| 2026-08-30 | Enter `/bookings` at canonical HTTPS `mytrips` | The legacy HTTPS `myreservations` entry redirected through HTTP and BookSaver correctly blocked it before Browser Use could run; direct HTTPS entry restores reliability without weakening egress | Yes |
| 2026-08-30 | Recover from harmless pre-action guard rejections | Live Browser Use selected structural footer/app-install controls; no unsafe action executed, so bounded correction is more reliable than terminating the entire episode while all physical replay guards and caps remain binding | Yes |
| 2026-08-31 | Require discovery rather than cached-row re-observation | A saved-stay fast path prevented the Browser Use agent from looking for unknown reservations; qualification must begin without saved reservation rows | Yes |
| 2026-08-31 | Admit only Booking-required AWS WAF token subresources | The authenticated trips bootstrap stayed blank while the guard blocked randomized `token.awswaf.com` subdomains; narrow subresource admission restores rendering without granting agent navigation | Yes |
| 2026-09-01 | Distinguish positive refresh from authoritative completeness | Browser Use accepted a current reservation, but the presentation layer mislabeled the intentionally positive-only result as a failed refresh | Yes |
| 2026-09-02 | Make Browser Use the default price executor for manual and scheduled checks | One provider-neutral adapter removes trigger-specific selector dependence while BookSaver retains price authority | Yes |
| 2026-09-02 | Keep Stagehand and deterministic execution as explicit rollback only | Avoid masking Browser Use failures or doubling model spend while preserving reversible future-job routing | Yes |
| 2026-09-02 | Qualify Browser Use under a new policy identity and production replay | Old Stagehand evidence cannot prove the new adapter; live deployed execution must terminate with accepted evidence | Yes |
| 2026-09-03 | Expand Browser Use to every agentic inventory trigger | The exact `/checknow` replay stopped at its Stagehand inventory prerequisite before Browser Use price execution; the already-proven Browser Use inventory adapter removes that reliability dependency without expanding authority | Yes |

## Ready for Construction

- [x] All requirements documented.
- [x] System context defined.
- [x] Architecture decisions accepted.
- [x] Units decomposed.
- [x] Stories created for all units.
- [x] Bolts planned.
- [x] Human review and construction authorization complete.

## Next Steps

1. Execute bolt 064 to extend the proven local Browser Use runtime to price execution and all
   agentic inventory prerequisites.
2. Verify the exact deployed price path through the operator-only isolated replay.
3. Continue Browser Use-specific owner-canary evidence under the amended cost gates.
4. Keep bolt 055 blocked until price promotion and the 30-day rollback window complete.
