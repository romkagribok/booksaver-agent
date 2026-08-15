---
unit: 002-dom-resilient-browser-workflows
bolt: 047-dom-resilient-browser-workflows
stage: model
status: complete
updated: 2026-08-15T15:55:59Z
---

# Static Model - Remote Authentication Finalization Race Closure

## Bounded Context

This corrective context owns the terminal precedence of an already code-verified remote-auth
attempt and the eligibility of its already-sanitized failure evidence after browser cleanup. It
does not change DOM classification, browser/model authority, encrypted cookie format, incident
content, retention duration, or user-purge authority.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `RemoteAuthAttempt` | lifecycle status, ordinary expiry, cancellation authority, worker ownership, optional result | `FINALIZING` has admitted code verification and cannot transition through ordinary expiry |
| `FinalizationCommit` | verified cookie result, encrypted capture outcome, terminal transition | Capture and terminal success remain one manager-locked critical section |
| `FailureIncidentCandidate` | sanitized draft, runner outcome, cancellation authority, cleanup-complete fact | May publish only when the runner actually failed and no privacy-erasure authority suppresses publication |
| `ReleaseCandidate` | final commit, local gates, Bugbot review state, thread dispositions, follow-up review | Merge admission requires a completed review of the final proposed commit and zero unresolved actionable concerns |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| `CancellationAuthority` | viewer, ordinary expiry, internal replacement, administrative purge/revocation, daemon shutdown | Purge/revocation and shutdown remain higher authority than finalization; viewer/expiry/replacement cannot revoke admitted verification |
| `IncidentPublicationDisposition` | publish, suppress-privacy-erasure, suppress-no-draft, suppress-non-failure | A purge/revocation disposition can never later become publish for the same attempt |
| `BugbotThreadDisposition` | thread ID, actionable classification, fix/evidence response, resolution state | Every unresolved thread needs a documented fix or evidence-backed rejection before merge |
| `ReviewedCommit` | commit SHA, review-completed flag, clean-follow-up flag | A review of an older commit cannot satisfy the gate for new code changes |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| `RemoteAuthAttempt` | attempt, finalization commit, cancellation authority, failure incident candidate | Ordinary TTL expiry stops at the `FINALIZING` boundary; privacy erasure suppresses all later evidence publication; terminal state and capture remain consistent |
| `ReleaseCandidate` | reviewed commit, Bugbot threads and dispositions, verification evidence | Merge is refused until the final commit has a completed Bugbot pass and zero unresolved actionable threads |

## Domain Events

| Event | Trigger | Safe Payload |
|-------|---------|--------------|
| `FinalizationAdmitted` | Fresh code verification enters `FINALIZING` | Attempt-local lifecycle code only |
| `OrdinaryExpiryIgnoredDuringFinalization` | Viewer/poll observes elapsed ordinary expiry after admission | Lifecycle outcome code only |
| `FailureIncidentPublishedAfterTerminalRace` | Failed runner result returns after viewer cancel, replacement, or expiry | Existing sanitized incident draft only |
| `FailureIncidentSuppressedForPrivacyErasure` | Purge/revocation won before failed runner result returned | Closed suppression reason only |
| `BugbotMergeGatePassed` | Final reviewed commit has no unresolved actionable review threads | PR and reviewed commit identifiers |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| `RemoteAuthExpiryPolicy` | Decide whether ordinary expiry may transition the current lifecycle state | Current status and trusted clock |
| `FailureIncidentPublicationPolicy` | Decide whether a failed result's sanitized draft may publish after cleanup | Runner status, draft presence, cancellation authority |
| `RemoteAuthFinalizationService` | Preserve capture/cancellation precedence and release worker/gate ownership | Encrypted capture adapter and manager lock |
| `MergeReviewGate` | Fetch thread-aware review state, require dispositions, recheck final commit | GitHub PR metadata and review threads |

## Repository Interfaces

No new persistence repository is introduced. Existing encrypted session capture and incident
recording ports remain unchanged. The merge gate is a repository working agreement and operations
runbook rule, not a runtime database feature.

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Ordinary expiry | The viewer/session TTL used before code verification is admitted |
| Finalizing | A code-verified, non-terminal commit phase that can end only in capture success, typed capture failure, or higher-authority cancellation |
| Terminal race | A cancellation or expiry transition that wins before the browser worker returns its already-sanitized result |
| Privacy erasure | Administrative user purge or revocation that forbids recreating encrypted source evidence after deletion |
| Thread disposition | A fix or evidence-backed rejection attached to an unresolved review concern |
| Clean follow-up pass | Bugbot review of the final proposed commit with zero unresolved actionable concerns |

## Invariants

1. Ordinary `expires_at` may expire `STARTING`, `READY`, or `CONNECTED`, but never `FINALIZING`.
2. Administrative purge/revocation and daemon shutdown retain authority to cancel `FINALIZING` and
   prevent encrypted cookie capture.
3. A runner `FAILED` result with an eligible sanitized incident draft remains publishable after
   viewer cancellation, replacement, or ordinary expiry wins the terminal race.
4. Administrative purge/revocation permanently suppresses later incident publication for that
   attempt so deleted evidence cannot be recreated. Shutdown may suppress best-effort publication
   without changing the failure outcome.
5. A successful assisted-recovery draft remains publishable only after encrypted capture commits;
   capture rejection never publishes recovered evidence.
6. Browser cleanup still precedes all session capture and incident persistence.
7. A PR cannot merge merely because no review is present yet. Bugbot must have completed against the
   final proposed commit, every concern must have a disposition, and the follow-up state must be
   clean.

## Story Coverage

US-140's atomic finalization guarantee is extended with the missing expiry and terminal-race cases.
The release-process gate prevents the same class of delayed post-merge review from escaping again.
