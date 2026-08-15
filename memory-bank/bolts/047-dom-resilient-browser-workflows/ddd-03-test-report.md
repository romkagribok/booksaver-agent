---
unit: 002-dom-resilient-browser-workflows
bolt: 047-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-15T16:06:12Z
---

# Test Report - Remote Authentication Review-Race Closure

## Summary

- **Focused tests**: 41 passed across remote-auth lifecycle races, HTTP cookie behavior, and the
  executable Bugbot gate.
- **Full repository tests**: 1,563 passed with 55 known configuration-deprecation warnings.
- **Lint**: Ruff clean across `src`, `tests`, and `scripts`.
- **Formatting**: All changed Python files are Ruff-formatted. The optional repository-wide
  format check remains a pre-existing non-gate baseline affecting 122 untouched files; none were
  mechanically rewritten.
- **Types**: Strict mypy clean across 117 source files.
- **Smoke**: CLI help succeeds with `PYTHONPATH=src`.
- **AI-DLC**: Artifact validator reports zero issues; status integrity reports zero inconsistencies
  across 47 bolts and 22 intents.
- **Diff hygiene**: `git diff --check` clean.

## Acceptance Criteria Validation

- ✅ **US-140 / finalizing expiry**: A controllable verified runner crosses ordinary `expires_at`;
  viewer state remains `FINALIZING`, then encrypted capture, recovered incident, and success complete
  in order.
- ✅ **US-140 / viewer lifetime**: The hardened viewer capability is session-scoped in the browser,
  while the server keeps ordinary expiry authority and exposes a bounded terminal result after late
  finalization.
- ✅ **US-140 / higher authority**: Administrative purge/revocation and daemon shutdown still cancel
  in-flight work and prevent session capture.
- ✅ **US-140 / ordinary terminal races**: Viewer cancellation and ordinary expiry may retain their
  public terminal state while a delayed `FAILED` result records its eligible sanitized incident once.
- ✅ **US-140 / privacy erasure**: Administrative cancellation permanently suppresses a late failure
  occurrence so purge cannot be followed by recreated encrypted evidence.
- ✅ **US-140 / shutdown**: Daemon teardown suppresses best-effort late incident writes.
- ✅ **Merge gate / current head**: A current-head Bugbot review or successful Cursor-app check with
  resolved Cursor threads passes, including clean runs that create no review object.
- ✅ **Merge gate / fail closed**: Missing review, stale reviewed head, unresolved Cursor thread, closed
  PR, invalid target, and unavailable GitHub state all block admission.
- ✅ **Merge gate / pagination**: Multiple review and thread pages are aggregated before evaluation.
- ✅ **Repository process**: `AGENTS.md`, the VPS runbook, and the pull-request template require the
  executable final-head gate before merge.

## Bugbot Concern Disposition

1. **Expiry discards finalizing verified session**: Confirmed and fixed by excluding `FINALIZING`
   from ordinary TTL transitions, with the exact expiry/capture regression requested by Bugbot.
2. **Terminal races drop failure incidents**: Confirmed and fixed for ordinary viewer/expiry races.
   Bugbot's unconditional publication suggestion was narrowed because it would recreate evidence
   after administrative purge. The implementation records under the manager lock when publication
   remains eligible and permanently suppresses purge/shutdown cases.
3. **Viewer cookie expires during finalization**: Confirmed and fixed by removing the client-side
   `Max-Age` while retaining server-side expiry, plus a bounded post-finalization result window.

## Issues Found

No remaining functional, privacy, or safety defect was found in the changed scope. Incident sink
failure remains best effort and cannot modify the remote-auth terminal outcome, matching the
existing contract.

## Remaining Human Gate

After the branch is pushed and the follow-up pull request is ready, Cursor Bugbot must review that
exact head. Every new Cursor thread must receive a tested fix or evidence-backed disposition and be
resolved; `scripts/bugbot_merge_gate.py` must then pass before merge approval is requested.
