## Summary

- Describe the user-visible or operational change.

## Validation

- [ ] Targeted tests for the changed behavior
- [ ] Ruff, mypy, pytest, and `npm run test:aidlc-validator`
- [ ] `npm run validate:aidlc` (canonical artifact and status validation)

## Review and merge gate

- [ ] Codex code review completed on the final proposed commit
- [ ] Every Codex review thread has a tested fix or evidence-backed disposition and is resolved
- [ ] `python3 scripts/codex_merge_gate.py PR_NUMBER` passes for the final head

Do not merge when the Codex review is missing or stale; absence of comments is not a clean pass.
