---
stage: plan
bolt: 027-remote-auth-display-reliability
created: 2026-07-26T17:57:48Z
---

## Implementation Plan: Remote Authentication Display Reliability

### Objective

Restore the Telegram `/connect` framebuffer with the narrowest noVNC-compatible CSP allowance and
replace silent viewer failures with safe, actionable status text.

### Deliverables

- A regression test that isolates the `img-src` directive and requires exactly `data:`.
- Regression assertions for noVNC connection, security-failure, and unclean-disconnect handlers.
- A one-directive CSP correction in the generated remote-auth bootstrap response.
- Viewer-state logic that prevents polling from overwriting a client-side connection failure while
  preserving authoritative succeeded, failed, expired, and cancelled server outcomes.
- Construction and verification walkthroughs with no credential or capability data.

### Dependencies

- **RemoteAuthHttpApp**: Existing stdlib bootstrap page and response security headers.
- **Packaged noVNC**: `Display.imageRect()` uses `new Image()` with a `data:` source for compressed
  framebuffer rectangles.
- **Existing remote-auth lifecycle**: Terminal state, cancellation, and cleanup remain authoritative.

### Technical Approach

1. Extend `test_bootstrap_is_locked_down_and_never_cacheable` to parse the CSP directives and pin
   `img-src data:` without permitting `'self'`, `blob:`, HTTPS origins, or wildcards.
2. Add a focused bootstrap-page test for safe RFB event wiring and generic retry messaging.
3. Change only the image directive from `img-src 'none'` to `img-src data:`.
4. Track whether the server has reached a terminal outcome and whether a viewer error is active.
5. Attach `connect`, `securityfailure`, and `disconnect` listeners to the RFB instance. Never
   interpolate event detail, URLs, tokens, cookies, or server topology.
6. Keep polling for authoritative server outcomes, but do not replace an active viewer error with
   repetitive `ready` state text.

### Acceptance Criteria

- [ ] Compressed noVNC data-image rectangles are permitted to render.
- [ ] No remote, same-origin, wildcard, or blob image source is added.
- [ ] Script nonces, same-origin HTTP/WSS restrictions, frame blocking, and form blocking remain.
- [ ] Security failures and unclean disconnects show safe retry guidance.
- [ ] Clean or terminal disconnects do not replace the authoritative server status.
- [ ] Targeted tests, full pytest, Ruff, mypy, and `git diff --check` pass.
- [ ] A real Telegram mobile and desktop `/connect` test remains the production acceptance gate.

### Rollback

Revert the gateway and its test changes. This returns to the known gray-screen behavior but does not
affect stored user sessions, database schema, Caddy configuration, or Booking.com bookings.
