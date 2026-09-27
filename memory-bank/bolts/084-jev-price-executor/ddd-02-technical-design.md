---
stage: technical-design
bolt: 084-jev-price-executor
created: "2026-09-27T17:00:00Z"
status: complete
---

# Jev feasibility — spike design and reuse decision

## Upstream reuse (FR-1)

Reviewed `browser-use/jev-ultrafast` at `1231850a0bf1a0c0341fe408ef1668dbbfdfac46` (MIT,
© 2026 Browser Use). Adopted the *design* only: an indexed control table, an operation question
plus a speculative target question, strict validation that a choice is an offered id with
normalized probabilities and argmax consistency. Not adopted: its package, Browser Harness,
shared Chrome profile, OpenAI-compatible text helper, and coordinate clicks. No upstream code is
copied, so no license notice is needed in-tree.

BookSaver instead reuses its own hardened `BrowserUseSessionHost` (transient profile, mobile
emulation, network/dialog/download guards, code-owned cookie bootstrap, independent account
probe) and its existing guard functions (`node_chain_click_decision`,
`same_tab_click_destination`, `BrowserUseActionGuard`). Only the decision-maker differs.

## Extraction design

A fixed script segments rendered `[data-testid="rate-card"]` elements under their
`[data-testid="room-card"]` (generic fallback: innermost `label/[role=radio]/tr/li/article`
around a price), emitting bounded text lines. Per page: one property question over headings.
Per room: one room-name question over its lines. Per rate: one request with four questions
(whole-stay total among price lines, stated cancellation, the cancellation line, stated tax
inclusion). Code then grounds each answer (see bolt 085).

## Spike evidence (offline, 2026-09-27)

- Unauthenticated mobile (Pixel 7, en-US) property pages for two real hotels, including the
  owner's booked property, rendered 5 room cards / 11 rate cards; each rate card exposes
  `Price $N` whole-stay text, per-night text, cancellation line, and the room card exposes a
  tax line. Booking.com's WAF began challenging the development IP after a handful of loads, so
  later iterations used the saved page.
- Finding that matters for the comparison: those unauthenticated US pages say
  "Not included: 12 % TAX", so the Jev arm will mark such rates `all_in=unknown` and the
  unchanged validator rejects them, while production baseline history shows accepted all-in
  totals for the same property. Whether the authenticated page states tax inclusion is exactly
  what the live comparison will reveal; the Jev arm must not compute taxes.
- No authenticated TypeSafe call was possible without the owner's key. The client was written
  against the published API/OpenAPI and verified with transport fakes; the first live call is part
  of live acceptance.

Conclusion: feasible without any other model, subject to live acceptance.
