---
stage: test
bolt: 082-full-width-stream
created: "2026-09-23T15:43:35Z"
status: complete
---

# Full-width stream verification

Evidence is appended as recorded: runner and manager unit tests, viewer browser layout tests,
packaged-stack window probe, full gate and release.

## 2026-09-23T15:56:18Z — construction evidence

Design change during construction: an always-on full-width, locally scrolling stream was
rejected because the canvas owns touch gestures, which would leave the lower page reachable only
through remote scrolling. Instead the viewer measures its area at exchange and the remote
framebuffer adopts that aspect (width fixed per device, height bounded 640–1200), so
fit-to-screen fills the area with no bars; the keyboard-open rule uses the negotiated aspect.

Unit (91): mobile framebuffer follows the viewer aspect within bounds and ignores invalid hints;
desktop unchanged; first exchange fixes the framebuffer and reopenings never resize a running
browser; runner calls CDP fullscreen for every device, sizes Xvfb/window from the work
framebuffer, and gives the mobile context a framebuffer-sized viewport while keeping the Android
profile; gateway forwards the untrusted hint; manager message shortened.
Browser (79): exchange carries the measured area, `--stream-aspect` matches it, help is collapsed
behind the header control and toggles, dock is one row of five with unclipped labels, status is
at most two compact lines, keyboard-open stream height equals width × aspect; all prior paste,
resume and geometry tests pass with updated expectations.
Packaged stack (working-tree image, `window_fit_probe.py`, Xvfb `-fbdir` framebuffer read):
mobile 480×726 and 480×960 windows report fullscreen, page viewport equals the framebuffer, and a
full-bleed page covers 99.97–99.98% of framebuffer pixels (no tab strip or address bar);
desktop 1280×800 covers 99.79% with a one-pixel viewport tolerance, unchanged from before.
Physical phone acceptance remains user-observed.

## 2026-09-23T16:06:21Z — review correction (Cursor Bugbot, PR #63)

Valid finding: a resumed viewer never measured its area, so the keyboard-open rule fell back to
the default aspect. The viewer state now carries the negotiated framebuffer and the viewer sets
`--stream-aspect` from it on every poll, so resume and reopen use the server's size. Regressions:
manager/gateway expose `display_size`; browser reload adopts 726/480 and sizes the keyboard-open
stream from it. 168 remote-auth tests pass.

## 2026-09-23T16:13:15Z — release evidence

Exact image `fit-9a783f4` passed all seven dev probes and was promoted to production at
2026-09-23T16:12Z with verified backup and rollback tag; Bugbot passed on the final head.
Physical phone acceptance remains user-observed.
