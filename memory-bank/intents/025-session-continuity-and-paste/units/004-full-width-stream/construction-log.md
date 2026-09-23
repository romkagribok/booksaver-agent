---
unit: 004-full-width-stream
intent: 025-session-continuity-and-paste
created: "2026-09-23T15:43:35Z"
last_updated: "2026-09-23T16:38:10Z"
---

# Full-width stream construction log

2026-09-23T15:43:35Z: User showed a phone screenshot with the stream letterboxed at roughly half width under a
tall header and a wrapped dock. Root causes: the runner only fullscreened the desktop window
(phones streamed Chromium's tab strip and address bar), the mobile viewport was smaller than the
framebuffer, the viewer fit the 1:2 stream into a nearly square area, and the chrome took a third
of the height. Bolt 082 modelled, designed and ADR-054 recorded, then implemented with runner,
manager-message and viewer changes plus unit, browser and packaged-stack regressions.

2026-09-23T15:56:18Z: Implementation complete with unit, browser and packaged evidence (Bolt 082 test report).
Full-gate, review and release evidence follow.

2026-09-23T16:06:21Z: Bugbot review found the resumed viewer lacked the negotiated aspect; fixed by carrying
the framebuffer in the viewer state (Bolt 082 test report).

2026-09-23T16:38:10Z: US-203 approved (cursor off for touch, tablet-sized framebuffer). Bolt 083 modelled and
designed in its bolt file, implemented in the runner and domain with unit and probe coverage.
