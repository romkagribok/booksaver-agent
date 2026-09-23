# Remote-login paste construction log

2026-09-20T20:07:05Z: Model, design and ADR051 recorded in order before source implementation. User-approved
requirements and scoped checkpoints cover this design. Implementation and targeted regression
checks in progress. Exact packaged-stack qualification and release gates remain pending; no native
Telegram or physical OS shortcut acceptance claimed.

2026-09-20T20:11:26Z: Viewer implementation and 78 targeted browser/gateway regressions pass. Added real
browser-generated native paste coverage using synthetic clipboard content; RFB remains mocked in
this suite. Review follow-up blocks remote pointer/key and Next/Enter interleaving while a paste
is pending. Prepared isolated packaged-stack probe; exact stack and final integrated gate pending.
No physical OS/Telegram acceptance, merge or deployment claimed.

Packaged Dev exposed non-ASCII loss despite correct RFB keysyms. Bounded x11vnc/locale/compose
diagnostics did not qualify Unicode. Root accepted the core paste flow with explicit full-value
rejection and transparent Unicode limitation; global requirements are root-owned. Initial ASCII
probe passed 12 checks. CapsLock corrupted case without `-skip_lockkeys`; the same probe passed
12 checks with it. Added the narrow runner flag and test plus key-release continuity during
pending reads. Final rebuilt installed-image probe and updated targeted tests are in progress.

Final source freeze: 101 targeted tests passed in 43.80 seconds; Ruff and mypy on the two owned
source modules pass. Rebuilt installed viewer/runner Dev image passed 24 synthetic full-stack
checks including unsupported-character no-mutation rejection and CapsLock case safety. Final
probe is `/tmp/booksaver-continuity-release/paste_stage_probe.py`; it derives the exact installed
runner argv and changes only isolated display/port. Full integrated gate and final-image release
qualification remain parent-owned. Full Unicode and native physical Telegram acceptance are not
claimed. No production changes or Git mutations were performed by this worker.

2026-09-22T01:58:55Z: Production defect from user feedback on mobile Telegram: Booking.com's verification-code
page uses six single-character boxes that advance focus asynchronously after each input, and the
viewer sent pasted characters in a synchronous burst, so only one character landed in the first
box. Reproduced in the packaged noVNC/x11vnc/Chromium stack with a synthetic six-box auto-advance
form (shortcut and Insert paths both left one character). Fix: one keystroke per timer tick with a
50 ms gap (`pasteKeyIntervalMs`), unchanged validation, ownership and teardown guards. Regression
test asserts paced delivery and exact order. Release qualification and promotion follow the
existing Operations path; native Telegram acceptance remains user-driven.

2026-09-23T00:03:03Z: Bolt 080 (US-200) modelled, designed and ADR-052 recorded before implementation. Paste now
climbs browser → host → box; bulk arrivals in the box or the keyboard field send immediately and
paced; `one-time-code` hints added. 72 viewer tests pass locally; packaged-stack and full-gate
evidence pending; no commit or deployment yet (awaiting user review per working agreement).

2026-09-23T00:41:10Z: Bugbot review of PR #59 found that a whole-field autofill replacement would relay the
placeholder buffer as backspaces. Fixed (bulk arrivals never delete) with browser and packaged
regressions; see Bolt 080 test report.
