---
stage: implement
bolt: 027-remote-auth-display-reliability
created: 2026-07-26T18:11:07Z
---

## Implementation Walkthrough: Remote Authentication Display Reliability

### Summary

The Telegram remote-auth bootstrap now permits only the inline image representation required by
the packaged noVNC decoder. The viewer also reports safe connection/security failures and preserves
authoritative terminal session outcomes.

### Structure Overview

The change remains inside the existing stdlib remote-auth HTTP adapter. No domain model, persistence,
Telegram identity, Caddy, VNC topology, browser profile, or dependency boundary changed.

### Completed Work

- [x] `src/booksaver/infrastructure/remote_auth/gateway.py` - Emits the narrow noVNC-compatible CSP
  and wires safe RFB viewer status events.
- [x] `tests/unit/test_remote_auth_gateway.py` - Locks down the exact image directive and viewer
  failure feedback in the generated bootstrap page.
- [x] `memory-bank/intents/014-remote-auth-display-reliability/` - Records the defect requirements,
  boundaries, unit, and stories.
- [x] `memory-bank/bolts/027-remote-auth-display-reliability/` - Records the execution plan and
  implementation evidence.

### Key Decisions

- **Permit only `data:` images**: This matches the installed noVNC decoder and avoids broader
  `blob:`, same-origin, wildcard, or external image access.
- **Keep server outcomes authoritative**: Viewer errors remain visible during active sessions but
  cannot replace succeeded, failed, expired, or cancelled state.
- **Use generic messages**: RFB event details and network topology are never interpolated.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

The targeted gateway and deployment tests passed after first demonstrating both regressions against
the old implementation. Production acceptance still requires Telegram mobile and desktop clients.
