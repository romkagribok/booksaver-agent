---
stage: model
bolt: 083-touch-login-presentation
created: 2026-09-23T16:38:10Z
---

# Touch presentation model

Login window geometry (Bolt 082) gains a width dimension: the mobile framebuffer width follows
the touch viewer's width within 480–1024, so phones stay at 480 and tablets render natively.
A touch viewer has no pointer, so the streamed X cursor is suppressed for mobile logins. Both
are presentation only; the Android profile, capture rules and gesture forwarding are unchanged.
