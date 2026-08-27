---
intent: 023-replaceable-agentic-browser-executor
created: 2026-08-14T02:46:26Z
completed: 2026-08-27T23:13:41Z
status: complete
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

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | Complete | `requirements.md` |
| System Context | Complete | `system-context.md` |
| Architecture Decisions | Accepted | `architecture-decisions.md`, ADR-036 through ADR-038 |
| Units | Complete | `units.md` and four unit briefs |
| Stories | Amended | 14 story files (US-143 through US-156, including corrective US-155 and US-156) |
| Bolt Plan | Amended | Bolts 050 through 053 and 055; corrective bolt 054 complete and 056 in progress |

## Summary

| Metric | Count |
|--------|-------|
| Functional Requirements | 11 |
| Non-Functional Requirements | 7 |
| Units | 5 |
| Stories | 14 |
| Bolts Planned | 5 plus corrective bolts 054 and 056 |

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

## Ready for Construction

- [x] All requirements documented.
- [x] System context defined.
- [x] Architecture decisions accepted.
- [x] Units decomposed.
- [x] Stories created for all units.
- [x] Bolts planned.
- [x] Human review and construction authorization complete.

## Next Steps

1. Execute corrective bolt 056 using completed bolt 053 and the accepted safety/privacy ADRs.
2. Re-verify capability-specific agentic inventory for every disclosed authorized user while keeping
   price routing in its current owner-canary state.
3. Keep bolt 055 blocked until price promotion and the 30-day rollback window complete.
