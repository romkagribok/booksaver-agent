---
id: 002-touch-presentation
unit: 004-full-width-stream
intent: 025-session-continuity-and-paste
status: complete
priority: should
created: "2026-09-23T16:38:10Z"
assigned_bolt: 083-touch-login-presentation
implemented: true
---

# US-203: Touch presentation without a cursor, tablet-sized

As a phone or iPad user, I want no stray arrow cursor on the streamed login and a tablet-sized
page on a tablet, so that the stream looks native to my device.

## Acceptance criteria

- x11vnc runs with `-nocursor` for touch (mobile) logins and without it for desktop logins.
- The mobile framebuffer width follows the viewer width within 480–1024; height follows the
  aspect within 640–1200; phones therefore keep 480 wide.
- The packaged window-fit probe covers a tablet-sized framebuffer.
