---
stage: test
bolt: 056-agentic-inventory-executor
created: 2026-08-27T23:26:06Z
status: complete
---

# Test Report: Agentic Inventory Destination Policy

## Acceptance Coverage

- Benign unfamiliar Booking.com entry routes, added query keys, and non-sensitive fragments reach
  Stagehand semantic extraction without a selector or exact path update.
- Unknown Booking.com pages are observable but reject generic computer-use actions; semantic replay
  still requires a code-owned inventory task and inspected DOM role, label, and destination.
- Authentication, MFA, captcha, bot-wall, mutation, external, HTTP, user-info, nonstandard-port,
  popup, and post-action escape cases fail closed.
- Detail actions tolerate changed read-only Booking.com routes when inspected evidence matches the
  code-owned detail task.
- Diagnostics contain only closed destination/host classes, a sanitized route template, query-key
  names, fragment presence, phase, terminal status, and rejection reason. Tests prove raw hostnames,
  email-like identifiers, and query/path values do not enter logs.

## Verification Results

- `python3 -m ruff check src tests`: passed.
- `python3 -m mypy src`: passed for 127 source files.
- `python3 -m pytest`: 1779 passed, 55 pre-existing deprecation warnings.
- Focused agentic inventory suite: 44 passed.
- AI-DLC artifact validator: 0 issues.
- AI-DLC status-integrity validator: 0 inconsistencies before completion cascade.
- Stagehand runtime smoke: pinned `stagehand==4.0.1` imported successfully.
- CLI smoke: passed.
- `git diff --check`: passed.

## Environment Note

The local Docker Desktop context was present but its daemon did not respond, so a new exact-image
build was not performed on this Mac. The change does not alter packaging or dependencies; container
build and live Telegram verification remain operations checks rather than substitutes for the
completed code, safety, and repository gates above.

## Residual Risk

Booking.com may introduce new mutation terminology. Unknown destinations remain observation-only,
task-specific inspected evidence is still required before semantic replay, every action is checked
again after execution, and sanitized rejection diagnostics now expose the route family needed for a
bounded deny-policy update.
