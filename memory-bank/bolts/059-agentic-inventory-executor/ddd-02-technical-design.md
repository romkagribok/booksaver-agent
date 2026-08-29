---
stage: design
bolt: 059-agentic-inventory-executor
created: 2026-08-29T21:01:00Z
---

# Technical Design: Mobile Session Identity and Navigation Failure

## Architecture Pattern

Extend the existing hexagonal agentic adapter without changing its provider-neutral ports. Trusted
configuration is injected from the CLI composition root into both one-shot executors, then into the
shared local Stagehand runtime. Browser transport failures remain infrastructure details converted
to existing typed executor terminals at the adapter boundary.

The design prefers compatibility by construction over additional DOM verification: the same
allowlisted `MobileWebSettings` and Playwright-version device descriptor used by authenticated
monitoring determine the Stagehand Chromium launch identity before cookie restoration.

## Layer Structure

- **Domain**: Existing `MobileWebSettings`, execution statuses, and session leases remain unchanged.
- **Application**: Existing `PriceBrowserExecutor` and `InventoryBrowserExecutor` ports remain
  provider-neutral; no browser error strings cross them.
- **Infrastructure browser runtime**: Resolve the configured Playwright device descriptor, launch
  Stagehand Chromium with its mobile user agent/viewport/scale/touch/locale, observe top-level
  request failures through a temporary loopback CDP client, and raise a closed local navigation
  failure.
- **Inventory adapter**: Map redirect-loop failure at the fixed authenticated inventory entry to
  `SIGNED_OUT`; map all other transport failures to `PROVIDER_FAILURE` before destination guarding,
  extraction, fallback, or cost-bearing model calls.
- **Composition root**: Inject `cfg.mobile_web_settings` into both local agentic executor factories.

## API Design

- `LocalStagehandRuntime(mobile_settings)`: requires a trusted allowlisted mobile profile, defaulting
  to the existing `MobileWebSettings()` only for direct construction and tests.
- `LocalAgenticPriceExecutor(..., mobile_settings)`: forwards browser identity configuration into
  its runtime factory.
- `LocalAgenticInventoryExecutor(..., mobile_settings)`: forwards the same configuration.
- `BrowserNavigationFailure(category)`: infrastructure-local exception containing only a closed
  category; its text contains no URL, redirect value, page content, or session material.

## Data Model

No schema migration. Existing execution metrics persist only the terminal status, action/model
usage, cost, latency, fallback flag, and safety codes.

## Security Design

- Browser identity is trusted config, never provider output and never included in prompts.
- Cookie restoration remains code-owned and occurs only after the transient browser has launched
  with the final identity.
- The navigation observer records only a closed mapping of Chromium transport error names and is
  disconnected without closing the transient browser.
- `chrome-error://` never reaches destination admission, Stagehand extraction, screenshots, or
  computer use.
- Existing Booking.com domain/action guards, positive-only reconciliation, and all limits remain
  unchanged.

## NFR Implementation

- **Reliability**: Session producer and consumer share one version-matched browser identity; tested
  against the production redirect-loop reproduction.
- **Observability**: Logs include execution ID, phase, and closed failure category only.
- **Privacy**: No new persisted fields or content-bearing diagnostics.
- **Cost**: Failed protected navigation terminates before semantic or computer-use calls.
- **Portability**: The profile is resolved from the installed Playwright version and existing
  BookSaver configuration; no hardcoded browser version or external service is added.

## Test Design

- Launch-option tests prove the configured profile supplies user agent, viewport, scale, touch, and
  locale while secrets remain absent.
- Runtime tests reproduce redirect-loop classification from a failed main-document request and
  generic transport classification without retaining raw request data.
- Inventory adapter tests prove redirect loop → signed-out, other transport → provider failure,
  destination guard/model factories are not called, and usage/cost remain zero.
- Composition tests prove both price and inventory factories receive identical mobile settings.
- Existing executor, remote-auth, coordinator, privacy, and full repository gates protect against
  regressions.
