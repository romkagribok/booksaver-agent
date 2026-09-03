---
stage: design
bolt: 064-browser-use-price-executor
created: 2026-09-02T23:56:00Z
---

# Technical Design: Browser Use Price Executor

## Architecture Pattern

Use the existing hexagonal adapter boundary. `PriceBrowserExecutor`, trusted request/result domain
types, owner-bound lease service, validation/equivalence pipeline, coordinator gate, and cost ledger
remain unchanged. A new local Browser Use infrastructure adapter implements the existing port. A
closed configuration value selects Browser Use or Stagehand when an admitted route uses agentic
price execution; it cannot select a second adapter after the job begins.

The implementation reuses the already-qualified Browser Use inventory confinement/runtime patterns
through shared internal components where that reduces duplication. Price-specific prompts, typed
schemas, action policy, trusted-value admission, result mapping, and preflight remain separate from
inventory policy.

## Layer Structure

```text
Telegram /checknow ─┐
                    ├─ CheckCoordinator ─ route admission ─ executor selection
Scheduled slot ─────┘                                      │
                                                           ▼
                                        OwnerBoundAgenticPriceCheck
                                                           │
                                  opaque session lease + trusted query + limits
                                                           │
                                                           ▼
                                          PriceBrowserExecutor port
                                               │               │
                                        browser_use         stagehand
                                         (default)        (explicit rollback)
                                               │
                                 guarded local Browser Use episode
                                               │
                                     typed untrusted observation
                                               │
                                               ▼
                              BookSaver validation → equivalence → savings
```

## Component Design

### Configuration and routing

- Add a closed `price_executor` setting with `browser_use` as the default and `stagehand` as the
  alternate agentic adapter.
- Keep route admission (`legacy`, `owner_canary`, `agentic`) distinct from adapter selection.
  `legacy` continues to select the deterministic monitor; admitted agentic routes resolve exactly
  one configured adapter.
- Use the same factory from the coordinator for `/checknow` and scheduled work. Trigger-specific
  price factories are prohibited.
- Preserve backwards compatibility for existing config files by applying the Browser Use default
  when the setting is absent.

### Browser Use price adapter

- Implement a local adapter with the same constructor boundary as the Stagehand adapter: API key,
  lease broker, job cost budget, and mobile-web settings.
- Restore cookies only through the code-owned transient browser bootstrap. Browser Use receives the
  browser session, never cookie values.
- Enter the stored, verified canonical Booking.com property URL directly with trusted dates,
  occupancy, and currency; use semantic search only when the booking has no canonical URL.
- Remove all stock Browser Use actions and assert exact equality with the BookSaver-owned registry
  before agent execution.
- Register price-specific guarded actions: click, coordinate click, scroll, trusted-value type,
  safe key, wait, back, typed price observation, and typed terminal outcome.
- Reuse generic destination classification, dialog/popup rejection, telemetry confinement,
  one-action-per-step enforcement, physical-call metering, deadline enforcement, and unconditional
  teardown from the inventory adapter where policy is identical.
- Keep price action proof separate: visible element metadata and post-action destination must remain
  read-only; typed values must match a code-owned token derived from the trusted query.

### Typed evidence

- Define one atomic strict Browser Use observation action for query facts and bounded offers using
  the provider's supported schema subset and literal evidence-state values.
- Map decoded output to the existing `PriceExecutionResult`; do not add provider fields to the
  application port.
- Treat a Browser Use final answer without the typed submission action as a provider failure.
- Map signed-out, MFA, captcha, bot wall, unavailable, timeout, budget, unsafe action, and provider
  failure to existing closed price statuses.
- Pass every successful submission to existing BookSaver validation before offer selection.
- Qualify room labels only through a code-owned suffix rule for recognized flexible/refundable rate
  plans after a separator. Preserve bed, accessibility, and other room-variant terms exactly.

### Model-view preflight

- After session restoration and code-owned initial Booking.com navigation, inspect the exact
  Browser Use-owned page/context that will feed the model.
- Verify HTTPS Booking.com destination admission, mobile identity, absence of internal browser
  errors and protected-state redirects, browser attachment, positive viewport dimensions, and at
  least one usable representation.
- Treat a screenshot as unusable when it is absent, has invalid dimensions, or its bounded pixel
  sample has no meaningful variance. An empty semantic tree is allowed only when the visual
  representation is usable.
- Return a closed content-free terminal reason before constructing the paid agent when preflight
  proves failure.
- Log only representation availability, bounded dimensions/variance class, destination class, and
  terminal phase/reason. Never write model-visible bytes or text.

### Cost and qualification

- Continue using the existing exact persisted reservation/reconciliation ledger around every
  physical Anthropic call.
- Introduce `browser-use-price-v1` as the required price qualification identity. Invited-user
  routing treats a qualified row for any other identity as unqualified.
- Associate canary observations with the active policy identity or otherwise filter legacy evidence
  so Stagehand observations cannot count toward Browser Use gates.
- Report owner-canary health at USD 0.25 average while invited-user promotion remains gated at USD
  0.10 average, with existing 30/14-day/10-comparison, 95%, p95, duration, and critical-violation
  requirements.

### Operator replay

- Extend the repository's safe probe pattern with a price replay entrypoint intended for execution
  inside the exact container image.
- Clone the production SQLite database and required encrypted session data into an isolated,
  permission-restricted temporary directory without printing secrets.
- Resolve one owner-owned eligible booking, instantiate the real coordinator/factory configuration,
  force the admitted Browser Use price route without changing production config, and suppress
  notification transports and authoritative production writes.
- Acquire the same browser/coordinator gate, wait for terminal completion, print only redacted
  status/usage/cost/duration counts, and exit zero only for a BookSaver-accepted observation.
- Always remove the isolated state and transient profile.
- Do not perform a second price-stage session refresh after the immediately preceding current-run
  inventory verification; this preserves the accepted price result within the shared deadline.

## Data Model

- Add only the minimum migration required to bind price-canary evidence and qualification state to
  a policy identity. Existing rows remain locally auditable but cannot qualify a different policy.
- Do not persist Browser Use history, screenshots, DOM/accessibility trees, page text, prompts, or
  reasoning.
- No booking, offer, savings, or session schema changes are required.

## Security Design

- Browser Use is an untrusted proposal source; code guards retain action, value, destination, and
  postcondition authority.
- Prompt/page content cannot expand the registered action vocabulary or trusted typed-value set.
- The owner-bound lease and transient profile lifecycle remain unchanged.
- External egress remains Booking.com application/static/WAF dependencies, Anthropic, and loopback;
  the WAF token host remains subresource-only and never agent-navigable.
- Replay operates on isolated state and has no notification or transaction adapter.

## NFR Implementation

- **Reliability**: No Booking.com selectors in the adapter; visual/semantic agent execution plus
  model-view preflight and closed terminal diagnostics.
- **Safety**: Exact registry assertion, one action per step, trusted-value typing, pre/post guards,
  hard limits, and no same-job fallback.
- **Privacy**: Content-free persistence and logs; transient content only to the configured
  Anthropic account after disclosure.
- **Cost**: Existing exact ledgers, USD 1 hard cap, USD 0.50 p95 target, and versioned average gates.
- **Performance**: One 180-second absolute deadline shared with the containing coordinator job.
- **Portability**: Local pinned Browser Use and installed Chromium; no managed service or new secret.
- **Maintainability**: Provider code remains behind the port; shared Browser Use confinement is
  reused only where inventory and price policies are identical.

## Verification Design

- Contract tests for typed evidence mapping, closed terminals, and existing validator behavior.
- Safety tests for every removed/blocked stock action, arbitrary typed value, unsafe destination,
  popup/dialog, and transaction term.
- Preflight fixtures for usable visual state, empty semantic state with usable image, blank image,
  signed-out/challenge/internal-error destinations, and zero paid calls on rejection.
- Routing tests proving manual and scheduled agentic checks construct Browser Use by default and
  Stagehand only when configured.
- Qualification tests proving policy mismatch cannot promote and applying both average-cost gates.
- Exact-container dependency/startup/teardown tests and an isolated operator replay.
- Full repository lint, strict typing, test suite, package, and memory-bank integrity gates before
  review.

## Deployment and Rollback

- Build and verify the exact Docker image locally, then exercise an isolated staging replay on the
  VPS before production replacement.
- Record the current production image ID and database/config backups before deployment.
- Deploy only the BookSaver service; keep Caddy and persistent volumes intact.
- Verify process health, logs, heartbeat, schema/integrity, dependencies, routing configuration, and
  production-equivalent Browser Use price replay.
- Roll back by recreating the prior image and selecting Stagehand or deterministic execution for
  future jobs; never resume a partially failed Browser Use job with another harness.
