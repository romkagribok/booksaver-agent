---
stage: model
bolt: 080-seamless-mobile-paste
created: 2026-09-23T00:03:03Z
---

# Seamless paste model

The aggregate is unchanged from Bolt 079: one authenticated RFB connection with an input
generation, owning at most one paste attempt bound to a trusted gesture. This bolt adds:

- **PasteSource** (value object): an ordered ladder of explicit sources for one gesture: browser
  clipboard read, host (Telegram Mini App) clipboard read, then the local masked box. Each source
  either yields text, answers "not available" or stays silent past a short bound; the ladder never
  reads the clipboard without the originating gesture and never repeats a source.
- **Arrival** (event): text landing in a local field. A *bulk arrival* (native paste, suggested
  one-time code, keyboard clipboard chip, replacement text) carries two or more characters in one
  input and is sent immediately. A *keystroke arrival* is one character and follows the existing
  typing path; in the box it waits for Insert.
- **Delivery** is the existing paced, validated, ownership-checked sender. A delivery that began in
  the keyboard capture field does not move focus, so the keyboard stays open.

Invariants: PasteText bounds (printable ASCII, 1–1,024) apply to every source; text is cleared
after delivery and on teardown; nothing is submitted; no text enters HTTP, Telegram messages,
storage or logs.
