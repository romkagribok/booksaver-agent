---
adr: ADR-052
status: accepted
created: "2026-09-23T00:03:03Z"
bolt: 080-seamless-mobile-paste
---

# ADR-052: Layered explicit paste sources

## Context

ADR-051 allowed one explicit clipboard read with a masked box and Insert as the fallback. Native
mobile use showed the fallback to be two extra steps, and mobile hosts commonly deny the browser
clipboard read. Telegram's Mini App bridge offers its own gesture-bound clipboard read, and phone
keyboards can suggest one-time codes and recently copied text into a focused field.

## Decision

Keep ADR-051's boundary (explicit gesture, transient text, RFB keyboard delivery only) and layer the
sources behind one gesture: browser clipboard, host clipboard, then the box. Treat any bulk arrival
in a local field as the user's paste and deliver it immediately and paced; do not require Insert
for it. Advertise `one-time-code` on local fields so the platform may suggest codes. Do not route
codes through Telegram messages, do not read the clipboard without a gesture, do not synchronise
the remote clipboard, and do not submit.

## Consequences

Fewest taps per platform: one tap where a clipboard read is permitted, two with a keyboard
suggestion or chip, three with a long-press paste; never an Insert tap for pasted text. The host
read is a bounded attempt that most launches will answer null today; it costs 800 ms at most and
becomes useful without code change if the host permits it. Single typed characters in the box keep
Insert to avoid sending partial input. Physical device behaviour remains user-observed.
