---
stage: test
bolt: 027-remote-auth-display-reliability
created: 2026-07-26T18:12:24Z
---

## Test Report: Remote Authentication Display Reliability

### Summary

- **Tests**: 871/871 passed
- **Coverage**: Not separately collected; the focused gateway tests cover the changed response path
- **Ruff**: Clean across `src` and `tests`
- **mypy**: Clean across 93 source files
- **Generated JavaScript syntax**: `node --check` passed
- **AI-DLC artifact validator**: 0 issues
- **Diff hygiene**: Clean

### Test Files

- [x] `tests/unit/test_remote_auth_gateway.py` - Exact CSP image capability, RFB event wiring,
  terminal-state preservation, safe viewer messages, origin checks, cookies, and static traversal.
- [x] `tests/unit/test_remote_auth_deployment.py` - Caddy/noVNC deployment boundary regression.
- [x] Full `tests/` suite - Cross-component regression.
- [x] Generated inline bootstrap script - JavaScript syntax smoke check.

### Acceptance Criteria Validation

- ✅ **Render compressed framebuffer images**: CSP requires exactly `img-src data:`.
- ✅ **Keep other CSP boundaries**: Existing nonce, same-origin/WSS, frame, form, and default-deny
  assertions remain passing.
- ✅ **Reject broad image capabilities**: The exact directive excludes `'self'`, `blob:`, external
  origins, and wildcards.
- ✅ **Explain viewer failures**: Security failure and unclean disconnect paths render generic retry
  messages.
- ✅ **Preserve terminal outcomes**: Viewer error updates are guarded by terminal server state.
- ✅ **Protect secrets**: Messages interpolate no event reason, token, cookie, path, or topology.

### Issues Found

- The initial status-integrity check correctly found the new unit/intent still marked at inception
  states after construction began. The deterministic `--fix` path aligned both and logged the
  maintenance entry; the artifact validator remained clean.

### Remaining Acceptance

A production build and real `/connect` attempt in Telegram mobile and desktop are intentionally
deferred until explicit commit/push/deployment approval.
