---
intent: 016-device-aware-remote-auth-viewer
phase: inception
status: units-decomposed
updated: 2026-07-26T22:45:44Z
---

# Device-Aware Remote Authentication Viewer - Unit Decomposition

## Units Overview

This intent decomposes into one cohesive viewer unit.

### Unit 1: `001-device-aware-remote-auth-viewer`

**Description**: Add capability-aware controls, the noVNC native-keyboard bridge, adaptive viewport
behavior, safe lifecycle cleanup, and browser-level regression coverage to the existing Mini App
viewer.

**Assigned Requirements**: FR-1 through FR-7.

**Deliverables**:

- Device/touch-aware viewer presentation.
- Native mobile software-keyboard bridge using packaged noVNC modules.
- Touch input dock with Keyboard, Next, Enter, and Cancel controls.
- Verified app-like/kiosk remote Chromium presentation without misleading desktop browser chrome.
- Dynamic viewport, safe-area, accessibility, and lifecycle behavior.
- Best-effort close cancellation and immediate same-user retry.
- Automated and real-device acceptance evidence.

**Dependencies**:

- Completed remote-auth gateway, framebuffer reliability, and direct-Booking-auth work.
- Existing Telegram Mini App, noVNC, websockify, x11vnc, Xvfb, and mobile Playwright context.

**Estimated Complexity**: Medium implementation and high cross-platform acceptance risk.

## Requirement-to-Unit Mapping

- **FR-1**: Discover viewer input capabilities → `001-device-aware-remote-auth-viewer`
- **FR-2**: Open the native software keyboard → `001-device-aware-remote-auth-viewer`
- **FR-3**: Relay mobile text input through noVNC → `001-device-aware-remote-auth-viewer`
- **FR-4**: Provide touch-first input dock and guidance → `001-device-aware-remote-auth-viewer`
- **FR-5**: Adapt to viewport and safe areas → `001-device-aware-remote-auth-viewer`
- **FR-6**: Preserve lifecycle and recovery states → `001-device-aware-remote-auth-viewer`
- **FR-7**: Release abandoned viewers and permit safe same-user retry → `001-device-aware-remote-auth-viewer`

## Execution Order

Execute the single unit in two risk-separated bolts after completed Bolts 026, 027, and 029:

1. **Bolt 030**: device-adaptive viewer, keyboard input, viewport, kiosk compatibility, and security.
2. **Bolt 031**: immediate same-user reclamation, bounded teardown, and concurrency tests.

Bolt 031 follows Bolt 030 so its viewer lifecycle hook integrates against the reviewed viewer shell.
