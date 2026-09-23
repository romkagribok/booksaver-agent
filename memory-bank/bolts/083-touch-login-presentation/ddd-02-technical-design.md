---
stage: design
bolt: 083-touch-login-presentation
created: 2026-09-23T16:38:10Z
---

# Technical design and decision

- `LoginDevice.framebuffer_for`: width = clamp(viewer width, 480, 1024) for mobile; height from
  the aspect within 640–1200; desktop unchanged.
- `browser_runner.py`: the x11vnc argv stays a literal list (the packaged probes read it from
  the AST) and gains `-nocursor` only when the work's device is mobile.
- ADR analysis: no new decision; this refines ADR-054 (full-framebuffer mobile login window)
  without changing any boundary, so no separate ADR is recorded.
- Tests: framebuffer cases for iPad portrait/landscape and mid-size tablets; x11vnc argv per
  device; the window-fit probe adds a tablet case.
