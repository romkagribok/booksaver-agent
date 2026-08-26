---
intent: 023-replaceable-agentic-browser-executor
status: accepted
created: 2026-08-16T19:18:41Z
updated: 2026-08-25T13:00:00Z
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

## Formal ADRs

- ADR-036: Trusted control plane and provider-neutral browser-executor port.
- ADR-037: In-process Stagehand v4 with guarded Anthropic computer-use fallback.
- ADR-038: Owner-only qualification, consented promotion, and rollback window.
- ADR-039: Capability-specific agentic inventory with positive-only reconciliation.
