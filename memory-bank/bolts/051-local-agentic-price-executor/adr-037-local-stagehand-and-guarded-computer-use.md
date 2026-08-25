---
bolt: 051-local-agentic-price-executor
created: 2026-08-16T19:18:41Z
status: accepted
---

# ADR-037: Local Stagehand with Guarded Anthropic Computer Use

## Context

BookSaver needs DOM-resilient perception without sending session custody to a managed browser or
building another custom self-healing layer. Semantic structure can still degrade enough to require
visual interaction.

## Decision

Pin Stagehand 4.0.1 and run it in process through a dedicated async runner against a fresh local
Chromium. Semantic navigation uses observe, code guard, deterministic replay, and postconditions;
typed extraction performs rate perception. After semantic failure, allow one Sonnet 5 computer-use
episode on the same browser with at most six guarded click/scroll/type/key/wait/zoom actions.

In the supported Docker image, BookSaver passes Stagehand an explicit container-compatible Chromium
sandbox setting rather than relying on Stagehand's generic `CI` inference. This matches the existing
Playwright container launch behavior while the daemon and browser remain unprivileged; it does not
make the container privileged or weaken BookSaver's browser-action and destination guards.

BookSaver executes all actions. Coordinate clicks are browser-hit-tested, destinations are checked
before/after, and unsafe/transaction/authentication/system tools are unavailable. Stagehand external
telemetry/log export is disabled or loopback-only. No managed browser, cache, selector learning,
generated repair, sidecar, local GPU, or additional secret is introduced.

## Alternatives Considered

- **Browserbase or Browser Use Cloud**: rejected for the first release because authenticated page
  and session custody would cross another service boundary.
- **Browser Use as primary harness**: deferred because of its larger fast-moving dependency surface.
- **Raw Anthropic computer use only**: rejected as unnecessarily costly and harder to guard.
- **Stagehand semantic only**: rejected because visual degradation needs a bounded fallback.

## Consequences

The adapter incurs paid Anthropic cost and Stagehand packaging risk, and the Docker runtime relies on
the non-root container boundary plus BookSaver's code-owned controls rather than Chromium's internal
sandbox. It preserves self-hosting and provides two complementary perception modes. Qualification,
not architecture alone, establishes whether maintenance is materially reduced.
