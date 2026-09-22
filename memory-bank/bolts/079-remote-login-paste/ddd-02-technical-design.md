---
stage: design
bolt: 079-remote-login-paste
created: "2026-09-20T20:07:05Z"
---

# Explicit user paste design

Use the existing authenticated viewer and RFB keyboard channel. A window capture listener owns
trusted Cmd/Ctrl+V before noVNC sees V; it prevents the default paste event and starts one clipboard
read inside the user gesture. A Paste button provides the same operation. Missing/denied clipboard
access reveals a visible masked native input and Insert button. Native paste into that field stays
local until Insert; native paste directed to the remote viewer is captured as text/plain once.

Accept at most 1,024 printable ASCII characters (U+0020 through U+007E), preserving spaces
exactly. Reject the entire value before any key/modifier send when it contains unsupported Unicode,
control characters, newlines or oversize input. Never truncate or normalize it. Send literal keysyms, never Enter/Tab or clipboardPasteFrom. Public RFB blur releases
noVNC-held keys; explicit modifier-up events precede literal text. This changes local canvas focus,
not the remote browser's selected field. Exact-stack verification must demonstrate this behavior.

Each operation owns the exact connected RFB and an input generation. Only one paste can run.
After readText and before each bounded chunk/codepoint, check that ownership and live controls.
Teardown, finalization, cancellation, pagehide and reconnect invalidate it and clear both buffer and
masked input. Pending reads are discarded. No clipboard writes, polling, remote clipboard sync,
HTTP credentials endpoint, persistence or logging. Failures use fixed plain messages only.

Tests exercise real browser event handling with an RFB mock: shortcut interception, Unicode and
spacing, rejection, denial fallback, duplicate attempts, modifiers, async teardown and replacement.
A separate synthetic-input probe must use packaged noVNC/x11vnc/Chromium and a local dummy form,
verifying exact field value, no submission and focus/modifiers. Automated clipboard/event injection
is not a physical OS shortcut or native Telegram acceptance; those remain explicitly distinguished.

Implementation detail: while a read or chunk is pending, capture remote key/pointer events and
ignore Next/Enter, preserving the selected field. Cancel/Close remain usable and invalidate the
attempt; normal keyboard behavior resumes when it finishes.

## Packaged-stack qualification refinement

Initial full-Unicode direct keysyms were correctly encoded by noVNC but lost in Chromium after
x11vnc mapping. Keyboard-flag, locale and compose diagnostics did not qualify an alternative.
Root accepted explicit fail-closed unsupported-character handling for the user's core code/email
paste request and records full Unicode as an unavailable release limitation. No credential HTTP
endpoint, clipboard synchronization or dependency expansion is introduced.

Real CapsLock testing also exposed remote case inversion. The narrow x11vnc `-skip_lockkeys`
flag keeps the freshly started remote lock state unchanged; logical character case still comes
from client keysyms. Exact synthetic ASCII/CapsLock probe passes with that flag. Key releases
remain deliverable during clipboard awaits, even while key presses/pointer/Next/Enter are blocked,
so invalid/denied paste cannot leave Ctrl/Meta held remotely.
