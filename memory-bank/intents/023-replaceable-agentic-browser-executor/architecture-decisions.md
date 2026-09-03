---
intent: 023-replaceable-agentic-browser-executor
status: accepted
created: 2026-08-16T19:18:41Z
updated: 2026-09-03T01:41:00Z
---

# Architecture Decisions: Replaceable Agentic Browser Executor

## Decision 1: BookSaver remains the trusted control plane

The executor is a replaceable perception/navigation adapter. It cannot establish authentication,
identity, equivalence, refundability, valid all-in pricing, savings, persistence transitions,
notifications, or transactions. Its output is untrusted typed evidence.

## Decision 2: Local Stagehand first, guarded Anthropic computer use second

The first adapter runs an exactly pinned Stagehand v4 in process against a transient local Chromium.
It uses semantic observation and typed extraction, with one bounded Sonnet 5 computer-use episode
only after semantic failure. This avoids a managed browser trust boundary while using a mature
semantic harness and a visual fallback.

## Decision 3: BookSaver owns browser and session custody

`/connect` stays human-driven and server-verified. Decrypted cookies enter only a fresh transient
browser, never a prompt or provider SDK. Stagehand and computer use share that browser; refreshed
cookies require code-owned re-verification before encrypted persistence; teardown is unconditional.

## Decision 4: Guards wrap every proposal

Stagehand follows `observe -> code guard -> deterministic action replay`. Computer-use actions use a
closed vocabulary, coordinate hit-testing, and pre/post destination checks. No model gets arbitrary
navigation, credentials, filesystem, shell, clipboard, upload/download, MFA/captcha, or transaction
tools.

## Decision 5: Preserve legacy only for qualification and rollback

Routing supports `legacy`, `owner_canary`, and `agentic`; `legacy` is the default until the owner
canary passes. Once promoted, legacy is rollback-only for 30 days without selector maintenance, then
removed by a separate release decision.

## Decision 6: No custom recovery cache or managed browser service

The first release does not implement selector/action caching, selector learning, generated-script
repair, Browserbase caching, Browserbase, Browser Use Cloud, a sidecar, or a local GPU. Future
adapters must implement the same port and repeat qualification.

## Decision 7: Content privacy is explicit and measurable

Only the deployment owner's Anthropic account processes bounded visible page content. Invited users
must acknowledge a versioned disclosure before agentic routing. External Stagehand telemetry/log
export is disabled, persistence is redacted, and egress tests enforce the approved destinations.

## Decision 8: Agentic inventory advances with positive-only reconciliation

Legacy inventory blocks the price canary, so inventory is no longer sequenced after price
promotion. A separate provider-neutral inventory capability uses the same local Stagehand and
guarded computer-use architecture for every disclosed authorized user. BookSaver accepts only
current-run positive observations, never lets agentic evidence mark unseen reservations absent, and
requires a selected reservation to be re-observed before its price check. Price and inventory routes
remain independently reversible, and bare `/checknow` no longer performs a duplicate inventory run.

## Decision 9: Browser Use is first proven through `/bookings`

Reliability is initially evaluated through a trigger-specific adapter rather than a wholesale
executor swap. Telegram `/bookings` uses a pinned local Browser Use OSS agent behind the existing
`InventoryBrowserExecutor` port. Browser Use receives only guarded read-only tools, one action per
step, the existing Anthropic key and hard limits, and no cloud or persistence features. Failure is
terminal for that operation so qualification cannot be masked by a second browser harness.

## Decision 10: Browser Use becomes the default price executor

After live `/bookings` discovery proved that the local Browser Use loop can operate against the
authenticated Booking.com account, both `/checknow` and scheduled price checks select a Browser Use
adapter behind `PriceBrowserExecutor`. Stagehand remains explicitly selectable for future jobs and
the deterministic path remains available during its rollback window, but neither runs after a
failed Browser Use job. A distinct qualification identity prevents Stagehand evidence from
promoting Browser Use, and a production-equivalent replay must prove the deployed price loop before
the release is accepted.

Price execution enters a verified canonical property URL directly when one is stored and falls back
to semantic search only for name-only records. The agent submits query facts and offers atomically.
BookSaver—not the model—may ignore only a recognized flexible/refundable rate-plan suffix after a
separator when comparing room identity; bed, accessibility, and room-variant text remains binding.

## Decision 11: Browser Use serves every agentic inventory trigger

The successful `/bookings` adapter is also the inventory implementation used by post-connect,
`/checknow`, and scheduled work. Price operations retain their required current-run positive
inventory verification, but that verification no longer depends on Stagehand. Positive-only
reconciliation, the shared limits, the provider-neutral port, and fail-closed behavior remain
unchanged; there is still no second harness inside a failed job.

## Formal ADRs

- ADR-036: Trusted control plane and provider-neutral browser-executor port.
- ADR-037: In-process Stagehand v4 with guarded Anthropic computer-use fallback.
- ADR-038: Owner-only qualification, consented promotion, and rollback window.
- ADR-039: Capability-specific agentic inventory with positive-only reconciliation.
- ADR-040: Separate destination observation from interaction authority.
- ADR-041: Trigger-specific local Browser Use execution for `/bookings`.
- ADR-043: Browser Use default price execution with explicit rollback.
- ADR-044: Browser Use for all agentic inventory triggers.
