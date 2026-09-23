---
stage: design
bolt: 082-full-width-stream
created: 2026-09-23T15:43:35Z
---

# Technical design

- `browser_runner.py`: `_new_login_context` overrides the mobile descriptor's viewport with the
  framebuffer size before `new_mobile_context`; `_prepare_login_window` enters CDP fullscreen for
  every device (previously desktop only).
- `application/remote_auth.py`: the READY/CONNECTED viewer message is one sentence; the provider
  note moves into the viewer's help text.
- `viewer.py`: CSS rule `body.touch-first:not(.desktop-login) #screen{height:auto;
  min-height:max(100%,200vw)}` makes the stream full width with vertical scrolling on phones at
  all times (previously only while the keyboard was open); the desktop keyboard rule is kept.
  Header: status (14 px, compact) + "?" help toggle + full-screen button; help paragraph hidden by
  default and expanded on tap; dock is a single non-wrapping row of five controls with Cancel.
- Tests: runner (mobile fullscreen call and viewport override), manager message, gateway
  bootstrap, browser layout (full-width stream, single-row dock, collapsed help) and a packaged
  probe asserting the real window state and viewport inside the image.
