---
unit: 002-dom-resilient-browser-workflows
bolt: 049-dom-resilient-browser-workflows
stage: test
status: complete
updated: 2026-08-16T16:34:00Z
---

# Test Report - Edge-Pending Negative Control

## Summary

- **Focused tests**: 92 passed across the server verifier, headed runner, remote-auth manager,
  deployment wiring, viewer lifecycle, incidents, and schema persistence.
- **Full repository tests**: 1,574 passed with 55 known configuration-deprecation warnings.
- **Lint**: Ruff clean across `src`, `tests`, and `scripts`.
- **Types**: Strict mypy clean across 118 source files.
- **Smoke**: CLI help succeeds with `PYTHONPATH=src`.
- **AI-DLC**: Artifact validation and status integrity report zero issues/inconsistencies across 49
  bolts and 22 intents.
- **Diff hygiene**: `git diff --check` clean.

## Live Contract Evidence

Content-free production inspection established the exact cookie-free response that contract v1 had
misclassified: status `202`, media `text/html`, zero response bytes, no redirect, and the unchanged
literal protected-account endpoint. The tuple was reproduced with three bounded HTTP probes and a
fresh isolated Playwright context. No response content, headers, query values, cookie values,
principal, or reservation data was retained.

## Acceptance Criteria Validation

- ✅ **Negative-only admission**: The exact production `202` tuple maps to `SIGNED_OUT`, so it may
  admit the viewer but can never produce an authentication receipt.
- ✅ **Candidate behavior**: Either isolated candidate probe returning the exact `202` keeps the
  session interactive and schedules only the existing bounded recheck.
- ✅ **Positive authority unchanged**: A receipt still requires two independent exact direct
  bounded `200 text/html` responses for the same immutable cookie snapshot.
- ✅ **Version separation**: Contract and verifier identifiers advanced to v2; v1 evidence and
  receipts are rejected at the domain boundary.
- ✅ **Malformed variants fail closed**: Body content, wrong media, query, fragment, wrong path,
  redirect, challenge marker, declared oversize, and actual oversize never authenticate.
- ✅ **Original negative retained**: The exact Booking OAuth redirect remains `SIGNED_OUT`.
- ✅ **No DOM/model authority**: Page structure and model output remain absent from `/connect`
  authentication proof; predictable negative evidence incurs zero model calls.
- ✅ **Privacy**: Diagnostics retain only closed status/media/redirect/size codes under the v2
  verifier category.

## Security Review

The amendment adds no positive authentication condition. In particular, status alone, a `2xx`, an
empty body, the protected URL, cookie presence, or page appearance cannot authorize persistence.
All five negative fields must match exactly, while successful persistence still requires the
separate two-probe receipt and the existing atomic finalization checks.

## Remaining Human Validation

After merge and deployment, a real Telegram `/connect` remains required. Expected behavior: the
viewer opens on the edge-pending negative control, stays open while signed out, closes only after
the two-probe server receipt enters atomic finalization, and Telegram reports the connected state.
