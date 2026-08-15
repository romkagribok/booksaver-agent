## Summary

- Describe the user-visible or operational change.

## Validation

- [ ] Targeted tests for the changed behavior
- [ ] Full relevant repository quality gate
- [ ] AI-DLC artifact and status validation when applicable

## Review and merge gate

- [ ] Cursor Bugbot reviewed the final proposed head commit
- [ ] Every Cursor review thread has a tested fix or evidence-backed disposition and is resolved
- [ ] `python3 scripts/bugbot_merge_gate.py PR_NUMBER` passes for the final head

Do not merge when Bugbot review is missing or stale; absence of comments is not a clean pass.
