---
unit: 002-dom-resilient-browser-workflows
bolt: 047-dom-resilient-browser-workflows
stage: design
status: complete
updated: 2026-08-15T15:59:19Z
---

# Technical Design - Remote Authentication Review-Race Closure

## Architecture Pattern

Retain the existing single-process hexagonal architecture. The application-layer
`RemoteAuthenticationManager` remains the sole owner of lifecycle precedence, encrypted capture,
and post-cleanup incident publication. Add one attempt-local closed publication policy rather than
moving incident persistence outside the manager lock or teaching the incident repository about
remote-auth cancellation.

Add an executable repository-operations gate for Cursor Bugbot. It queries GitHub's thread-aware
GraphQL state through the authenticated `gh` CLI, compares the latest Bugbot-reviewed commit with
the PR's current head, and refuses merge admission while any Cursor review thread is unresolved.

No database migration, runtime dependency, model prompt, browser authority, endpoint, or external
service is introduced.

## Layer Responsibilities

### Domain and Application

- Preserve `RemoteAuthStatus.FINALIZING` as non-terminal but exclude it from ordinary TTL expiry.
- Add a private closed `FailureIncidentPolicy` value to each in-memory attempt. Default is
  `PUBLISH`; administrative purge/revocation changes it permanently to `SUPPRESS_PRIVACY_ERASURE`;
  daemon shutdown changes it to `SUPPRESS_SHUTDOWN`.
- Viewer cancellation, internal replacement, and ordinary expiry leave `PUBLISH` unchanged.
- When a runner returns `FAILED`, evaluate the draft independently from whether the attempt is
  already terminal. Publish exactly once while holding the manager lock only when policy remains
  `PUBLISH`.
- Keeping the sink call inside the manager lock makes purge ordering atomic: either failure evidence
  publishes first and purge subsequently deletes it, or purge marks suppression first and later
  worker return cannot recreate it.
- Successful assisted-recovery evidence remains on the existing path: encrypted cookie capture
  must commit before publication. Capture rejection still discards the recovered draft.

### Incident and Privacy Boundary

- Do not change `IncidentDraft`, encrypted diagnostic serialization, retention, or repository APIs.
- Administrative purge/revocation suppresses the entire later occurrence, not only the encrypted
  bundle, because the sink may atomically create both incident metadata and source evidence.
- Shutdown suppression avoids new best-effort incident writes after lifecycle teardown begins.
- Ordinary viewer cancellation or expiry does not erase data and therefore does not suppress a
  real model-diagnosed/code-maintenance failure prepared while the page existed.

### Repository Operations

- Add `scripts/bugbot_merge_gate.py`, a stdlib-only wrapper around `gh api graphql`.
- Required input: PR number or URL; optional repository override for deterministic tests/automation.
- Query: PR state, head commit, reviews with author/body/commit, and paginated review threads with
  resolution state and authors.
- Admission requirements:
  1. At least one completed Cursor Bugbot review exists for the current head commit.
  2. The review body carries Bugbot's stable review marker.
  3. Every Cursor-authored review thread is resolved.
  4. The PR is open and mergeable state is not used as a substitute for review completion.
- Output only PR number, reviewed head, and aggregate counts. Never print comment bodies, URLs with
  capabilities, tokens, or repository secrets.
- Nonzero exit codes distinguish missing/stale review, unresolved threads, invalid input, and GitHub
  access failure.
- Add the command and semantics to `AGENTS.md` and the VPS deployment runbook. Absence of a review
  is a blocked gate, not a clean pass.

## Contracts

### Expiry Policy

```python
if (
    not attempt.status.is_terminal
    and attempt.status is not RemoteAuthStatus.FINALIZING
    and now >= attempt.expires_at
):
    transition_to_expired()
```

`FINALIZING` remains observable after ordinary expiry until the worker commits success, returns a
typed capture failure, or higher-authority purge/shutdown cancellation wins.

### Failure Incident Policy

```text
runner FAILED + sanitized draft
  |
  +-- PUBLISH ----------------------> record once under manager lock
  +-- SUPPRESS_PRIVACY_ERASURE ----> no occurrence/evidence recreation
  `-- SUPPRESS_SHUTDOWN -----------> no teardown-time best-effort write
```

The attempt's public terminal status remains whatever lifecycle race already won. Incident recording
does not change user notification or session-capture outcomes.

### Bugbot Merge Gate

```text
current PR head SHA
  -> completed Bugbot review exists for exact SHA?
  -> all Cursor review threads resolved?
  -> yes: exit 0
  -> no: exit nonzero with aggregate reason
```

Any pushed fix changes the PR head and invalidates the prior pass until Bugbot reviews the new head.

## Security and Privacy

- Purge/revocation remains authoritative over both encrypted sessions and diagnostic evidence.
- Failure incident publication cannot race after purge because the decision and sink invocation are
  serialized by the same manager lock used for cancellation.
- The merge-gate script shells out without `shell=True`, passes GraphQL through stdin, and returns no
  review text or authentication material.
- GitHub access uses the operator's existing scoped `gh` authentication; no token is stored by
  BookSaver or added to configuration.
- No model output gains lifecycle, incident, or merge authority.

## Reliability and Failure Handling

- A stuck finalization is still bounded by runner/process cleanup and remains administratively
  cancellable through purge or daemon shutdown; ordinary viewer TTL is intentionally no longer a
  post-verification authority.
- Incident sink failure remains best effort and cannot change the attempt's terminal status.
- Gate pagination covers more than 100 reviews/threads; malformed or missing GraphQL state fails
  closed.
- Network/auth/rate-limit errors fail the gate closed with a concise operator action.

## Test Design

### Remote-Auth Concurrency

1. Move the trusted clock beyond `expires_at` while the runner is latched in `FINALIZING`; viewer
   state stays finalizing and capture/incident/success complete after release.
2. Viewer cancel wins before a delayed runner returns `FAILED`; the public state stays cancelled and
   the eligible failure draft records exactly once.
3. Ordinary expiry wins before a delayed `FAILED` result; the public state stays expired and the
   failure draft records exactly once.
4. Administrative purge/revocation wins before delayed `FAILED`; no session, occurrence, or evidence
   is recreated.
5. Daemon shutdown wins before delayed `FAILED`; no teardown-time incident is written.
6. A normal non-raced failure still records exactly once; success and capture rejection behavior is
   unchanged.

### Merge Gate

1. Final-head Bugbot review plus zero unresolved Cursor threads exits zero.
2. No Bugbot review fails closed.
3. Bugbot review of an older head fails closed after a push.
4. Any unresolved Cursor thread fails closed, including informational-looking comments until a human
   records a disposition and resolves the thread.
5. Resolved threads, non-Cursor discussions, pagination, invalid input, GraphQL errors, and missing
   `gh` are deterministic and content-safe.

### Repository Gate

- Focused remote-auth and merge-gate tests.
- Ruff across source/tests/scripts, strict mypy across source, full pytest, CLI smoke, AI-DLC
  artifact/status validators, and `git diff --check`.

## ADR Analysis Input

This design applies existing ADR-024 encrypted sessions, ADR-026 remote auth, ADR-032/033 guarded
semantic verification, and ADR-034 encrypted incident/purge operations. The executable review gate
is repository process automation using existing GitHub CLI access, not a runtime architectural
choice. No new ADR is warranted.
