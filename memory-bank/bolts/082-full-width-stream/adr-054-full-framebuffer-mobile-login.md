---
adr: ADR-054
status: accepted
created: "2026-09-23T15:43:35Z"
bolt: 082-full-width-stream
---

# ADR-054: Full-framebuffer mobile login window

## Context

Mobile logins streamed Chromium's tab strip and address bar with a page viewport smaller than the
framebuffer, and the viewer letterboxed the 1:2 stream into a nearly square area under a tall
header. The result was small and hard to read.

## Decision

Fullscreen the remote window for every login device and set the mobile page viewport to the
framebuffer size, keeping the server-owned Android profile otherwise unchanged. On phones scale the
stream to full width and scroll vertically; collapse help and compact the chrome. Do not stretch
non-uniformly and do not change the desktop fit-to-screen behaviour.

## Consequences

The phone stream is roughly 1.7× larger and shows no misleading browser chrome. A page taller than
the framebuffer still scrolls inside the remote browser as before. Viewport size is not part of
session identity, so capture and price checks are unaffected. Physical device acceptance remains
user-observed.
