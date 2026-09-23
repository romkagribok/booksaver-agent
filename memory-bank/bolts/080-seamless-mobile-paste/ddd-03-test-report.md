---
stage: test
bolt: 080-seamless-mobile-paste
created: "2026-09-23T00:03:03Z"
status: complete
---

# Seamless paste verification

Browser suite (mocked RFB, real Chromium): host clipboard text / null / silent ladder outcomes,
host skipped on old hosts, native paste into the box sends immediately, typed characters keep
Insert while a chip-like fill sends at once, keyboard-capture suggestions are paced (gaps ≥ 40 ms),
keep the keyboard open and leave single characters immediate, unsupported text keeps the legacy
path, and all Bolt 079 guards (teardown, disconnect mid-sequence and on the final key, blocked
input while pending, rejection before insertion) still pass: **72 viewer tests**.

Packaged-stack evidence and the full gate are appended below when recorded.

## 2026-09-23T00:03:25Z — packaged-stack evidence (working-tree image, pre-review)

A throwaway image built from the working tree on the qualified `paste-7995864` base passed the
extended ASCII probe (**31 checks**: shortcut paste with CapsLock, unsupported-character rejection,
typed text retained across Paste taps until Insert, native paste into the box sent without Insert)
and the six-box auto-advance probe on all four paths: Ctrl/Cmd+V `482913`, masked-box Insert,
keyboard suggestion into the capture field with the keyboard still open, and native paste into the
box, with zero form submissions. Synthetic input only; physical Telegram is not claimed. The
release image will be rebuilt from the reviewed commit and re-probed before promotion.
