---
stage: test
bolt: 083-touch-login-presentation
created: "2026-09-23T16:38:10Z"
status: complete
---

# Touch presentation verification

Evidence appended as recorded.

## 2026-09-23T16:40:19Z — construction evidence

Unit: x11vnc argv carries `-nocursor` exactly for mobile logins; framebuffer cases for iPad
portrait (1000×1300 → 1000×1200), iPad landscape (1180×700 → 1024×640), mid tablet
(820×1000 → 820×1000), phone (390×590 → 480×726) and wide phone landscape (1000×300 →
1000×640); invalid hints keep the default. Full suite 2,990 passed, Ruff, mypy125, validator
clean. Packaged window-fit probe evidence for the tablet case is recorded at release.

## 2026-09-23T19:34:36Z — release evidence

Exact image `touch-c8b2aa6` passed all seven dev probes (tablet window-fit case 1000×1200
fullscreen, 99.99% coverage) and was promoted at 2026-09-23T16:44Z with verified backup and
rollback tag; Bugbot passed. Physical phone and iPad acceptance remain user-observed.
