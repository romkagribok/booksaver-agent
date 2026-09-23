---
stage: design
bolt: 080-seamless-mobile-paste
created: 2026-09-23T00:03:03Z
---

# Technical design

All changes are inside `src/booksaver/infrastructure/remote_auth/viewer.py` (served viewer document).

1. **Ladder**: `readPaste` awaits `navigator.clipboard.readText()` when present; on throw or absence
   it awaits `readHostClipboard()`, which calls `Telegram.WebApp.readTextFromClipboard` only when the
   host reports version ≥ 6.4 and resolves `null` on a null answer, an exception, or 800 ms of
   silence. A string from either source goes to `insertPaste`; otherwise the box opens. Ownership
   (`ownsPaste`) is re-checked after every await.
2. **Box sends immediately**: the window `paste` listener routes a trusted paste on the box straight
   to `insertFromPanel`. An `input` listener on the box sends when the input type is a paste,
   replacement or drop, or when two or more characters arrive at once; single characters accumulate
   for Insert. `pasteValueLength` tracks the buffer and is reset with it.
3. **Capture field**: `keyInput` computes the inserted slice; if it has two or more characters and
   passes `pasteCharacters`, it begins a paste attempt with `restoreFocus=false` and delivers it
   paced; otherwise the existing immediate keysym loop runs. Backspaces are sent first as before.
4. **Hints**: both fields carry `autocomplete="one-time-code"`; help and status copy explain the
   long-press and suggestion paths per platform (`touchFirst`).

Unchanged: validation, 50 ms pacing, modifier release, blocking of other input while pending,
teardown clearing, ASCII-only delivery, x11vnc flags, gateway and server code.
