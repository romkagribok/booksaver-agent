---
stage: test
bolt: 112-minimum-saving
created: 2026-11-10T14:54:13Z
---

# Test Report: minimum-saving

- Unit: 2,575 passed, 1 skipped; ruff, mypy, AI-DLC validation clean. Savings of 0.01, 1.00 and
  4.99 are rejected as below the minimum; exactly 5.00 is an opportunity. No other test relied on
  savings under 5.
- Staging check on the built image against today's production values is recorded in the release.
