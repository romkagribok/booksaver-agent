---
id: 003-seamless-mobile-paste
unit: 002-remote-login-paste
intent: 025-session-continuity-and-paste
status: complete
priority: must
created: "2026-09-23T00:03:03Z"
assigned_bolt: 080-seamless-mobile-paste
implemented: true
---

# US-200: Seamless mobile paste

As a user signing in on my phone, I want Paste to put my copied code or password into the selected
Booking.com field with as few taps as the platform allows, so that the streamed login is not clunky.

## Acceptance criteria

- Tapping Paste tries the browser clipboard, then Telegram's Mini App clipboard read, and only then
  shows the masked box; each attempt is bound to the same trusted gesture and connection.
- A native paste, a suggested one-time code or a keyboard clipboard chip arriving in the box is
  sent immediately, paced at 50 ms per character; single typed characters still require Insert.
- The same multi-character arrival in the Keyboard capture field is paced and does not close the
  keyboard; single characters and unsupported text keep the immediate typing path.
- Both local fields advertise `one-time-code`; nothing is stored, logged or submitted.
- Packaged-stack probes cover shortcut, box paste, Insert, suggestion and six-box auto-advance.
