---
id: 001-full-width-login-stream
unit: 004-full-width-stream
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-23T15:43:35Z"
assigned_bolt: 082-full-width-stream
implemented: true
---

# US-202: Full-width login stream on phones

As a phone user, I want the streamed Booking.com page to fill the screen width and be readable,
so that signing in is not a squint through grey bars.

## Acceptance criteria

- Mobile remote Chromium enters fullscreen inside Xvfb and its page viewport equals the 480x960
  framebuffer; no tab strip or address bar is streamed.
- On touch phones the viewer scales the stream to the full width and scrolls it vertically;
  desktop logins keep fit-to-screen behaviour.
- Status is one compact line, help is collapsed behind a header button, and the dock is a single
  row including Cancel.
- Existing keyboard, paste, resume and capture behaviour is unchanged.
