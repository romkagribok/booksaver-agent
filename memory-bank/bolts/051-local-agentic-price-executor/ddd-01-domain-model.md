---
stage: model
bolt: 051-local-agentic-price-executor
created: 2026-08-17T03:24:11Z
status: complete
---

# Static Domain Model: Local Agentic Price Executor

## Bounded Context

The **Local Agentic Price Executor** owns one transient, read-only Booking.com perception/navigation
episode. It implements the provider-neutral price executor port but cannot make BookSaver domain
decisions. It is composed of a semantic Stagehand lane, a generic code guard, and one bounded visual
Anthropic computer-use lane on the same local browser.

## Entities

### LocalBrowserRuntime

- **Identity**: execution ID and transient profile directory.
- **Properties**: Chromium executable, CDP endpoint/session, current page identity, started time,
  session-restored state, cleanup state.
- **Invariants**:
  - One runtime serves one execution and owner-bound lease only.
  - The profile is newly created and always destroyed after the job.
  - Only Booking.com HTTPS and loopback browser destinations are accepted.
  - Session injection occurs through a code-owned bootstrap before provider-facing execution.
  - Stagehand and computer use share the same browser/page.

### SemanticEpisode

- **Identity**: execution ID plus semantic episode ordinal (exactly one in v1).
- **Properties**: goal phase, observed action previews, guarded replays, extraction attempt, usage,
  terminal outcome.
- **Invariants**:
  - Every action originates from `observe`, is translated to a closed proposal, passes the code
    guard, and is replayed exactly once without a second model decision.
  - Typed extraction is the only successful semantic rate-output path.
  - No cross-run cache, selector learning, direct action, generated repair, or self-heal persistence.

### ComputerUseEpisode

- **Identity**: execution ID; at most one per execution.
- **Properties**: screenshot turns, requested actions, guarded executions, typed submission/terminal,
  usage.
- **Invariants**:
  - Entered only after a typed semantic failure eligible for fallback.
  - Sonnet 5 only; Opus is never available as a controlling profile.
  - At most six actions and within the shared 15-action/180-second/USD 1 job budget.
  - Every click is hit-tested and every action receives pre/post destination checks.
  - Success requires a typed `submit_price_observation`; free-form text is never evidence.

## Value Objects

### SemanticActionPreview

- **Properties**: closed action kind, opaque Stagehand replay token, human-visible label, role,
  current URL, candidate destination, bounded arguments.
- **Constraints**: no selector is persisted; unsafe labels/destinations/arguments are rejected;
  replay token is valid only for the current observation/page generation.

### GuardedAction

- **Properties**: action kind (`click`, `scroll`, `type`, `key`, `wait`, `zoom`), target evidence,
  bounded value, pre-action URL, guard verdict.
- **Constraints**: cannot express arbitrary navigation, shell, clipboard, files, credentials, MFA,
  captcha solving, checkout, cancellation, reservation, payment, or purchase.

### CoordinateHitTest

- **Properties**: x/y, in-viewport flag, element role/label, href, owning frame URL, disabled/hidden
  state, destination classification.
- **Constraints**: a click is executable only when one visible enabled element is returned, its label
  is safe, its frame/destination is allowlisted, and it is not a transaction/authentication control.

### DestinationSnapshot

- **Properties**: normalized scheme/host/path, popup count, top-level page identity.
- **Constraints**: HTTPS Booking.com only; no credentials/query/fragment persisted; unexpected popup,
  host, protected path, or transaction path is terminal.

### TypedPriceSubmission

- Contract-shaped observed query facts, observed offers, evidence completeness, and redacted source.
- Cannot contain equivalence, savings, cookies, arbitrary page text, screenshot, tree, prompt,
  reasoning, or provider response objects.

### LocalExecutorSettings

- Exact Stagehand version/model profile, headless flag, telemetry mode, semantic steps, visual action
  ceiling, and approved destination policy version.
- Version one fixes Stagehand 4.0.1, Sonnet 5, loopback/no-export telemetry, and six visual actions.

## Aggregates

### LocalPriceExecution Aggregate

- **Root**: one provider-neutral `PriceExecutionRequest`.
- **Members**: browser runtime, semantic episode, optional computer-use episode, shared execution
  meter, typed result, cleanup record.
- **Invariants**:
  - Session lease is restored before Booking navigation and closed after cleanup.
  - Semantic failure cannot reset shared limits before visual fallback.
  - Exactly one typed terminal result is returned.
  - Cleanup and redaction happen even when provider/runtime code raises.

### ActionGuard Aggregate

- **Root**: immutable destination/action policy version.
- **Members**: unsafe-label lexicon, allowed action types, allowed hosts/paths, protected transaction
  paths, hit-test evidence, pre/post snapshots.
- **Invariants**: models propose; code authorizes and executes. An unknown action/destination is unsafe.

## Domain Services

### StagehandSemanticController

Performs bounded goal phases: open trusted search, locate the trusted property/query, reach complete
rate content, extract contract-shaped evidence. It translates provider actions into previews,
delegates authorization to the guard, and replays only the approved observation token.

### ComputerUseController

Builds a content-minimized screenshot turn, parses the official computer-use tool request into a
closed action, applies generic hit testing and guards, executes through the browser runtime, and
returns only typed observations/tool results. It exposes no arbitrary navigation or system tools.

### BrowserActionGuard

Validates semantic and coordinate actions against label, role, URL, path, popup, value, and action
policy. It produces a content-free rejection code and never attempts to repair an unsafe proposal.

### TypedObservationMapper

Parses Stagehand extraction or computer-use submission into the provider-neutral BookSaver contract.
Schema rejection is a terminal observation failure, not a prompt retry loop beyond admitted limits.

### EgressPolicy

Classifies outbound destinations as Booking.com, Anthropic, loopback, or rejected. Telemetry endpoints
must be absent or loopback. DNS/network enforcement remains a deployment/test responsibility; the
adapter exposes observed destinations for qualification without page content.

## Port Interfaces

- **StagehandRuntimePort**: start/stop local browser, observe, replay observed action, typed extract,
  screenshot, hit test, execute guarded action, destination snapshot.
- **ComputerUseModelPort**: one typed Sonnet turn returning an approved action request, typed
  submission, or closed terminal outcome plus usage.
- **DisclosureConsentRepository**: read/record user acknowledgement of one version; introduced by
  bolt 052 persistence, with an in-memory/no-consent default in bolt 051.

## Domain Events

- **SemanticExecutionFailed**: execution ID and closed reason; may permit visual fallback.
- **ComputerUseEntered**: execution ID and remaining limits.
- **ActionRejected**: execution ID, lane, closed rejection code, action ordinal.
- **TypedPriceObservationSubmitted**: execution ID, offer count, source, evidence count.
- **TransientBrowserDestroyed**: execution ID and closed cleanup status.

Only content-free event fields may be logged or persisted.

## Terminal Outcomes

| Adapter condition | Port status |
|------------------|-------------|
| Complete typed observation | `OBSERVED` |
| No complete rate evidence | `NO_VALID_OBSERVATION` |
| Lease restore/verification failure | `SESSION_UNAVAILABLE` or `SIGNED_OUT` |
| MFA/captcha/bot challenge | `MFA_REQUIRED`, `CAPTCHA`, or `BOT_WALL` |
| Property/stay unavailable | `UNAVAILABLE` |
| Rejected action/destination/popup | `UNSAFE_ACTION` |
| Provider/runtime/schema failure | `PROVIDER_FAILURE` or `NO_VALID_OBSERVATION` |
| Shared cost/action limit | `BUDGET_EXHAUSTED` |
| Deadline | `TIMEOUT` |

## Ubiquitous Language

- **Semantic lane**: Stagehand observation/proposal/replay/extraction path.
- **Visual lane**: One guarded Anthropic computer-use episode after semantic failure.
- **Preview**: Provider proposal translated into facts the guard can authorize before execution.
- **Replay**: Execution of the exact already-observed Stagehand action token without re-prompting.
- **Hit test**: Code-owned inspection of the element under a requested coordinate.
- **Same browser**: Both lanes act on the identical transient Chromium context/page/session.
- **Content-bearing evidence**: Screenshot, page text/tree, prompt, response, or reasoning; ephemeral
  only and never persisted by default.
- **Disclosure version**: Machine identifier for the user-approved Anthropic page-processing notice.

## Story Coverage

- **US-147**: LocalBrowserRuntime and same-browser session lifecycle.
- **US-148**: SemanticEpisode, preview/guard/replay, and typed extraction.
- **US-149**: ComputerUseEpisode, hit testing, closed tools, and terminal mapping.
- **US-150**: EgressPolicy, content-free events, telemetry, and disclosure version.

## Completion Checklist

- [x] Entities, value objects, aggregates, events, services, and ports are defined.
- [x] Semantic and visual lanes share limits/browser but not authority.
- [x] Every forbidden tool/action/data flow is outside the model.
- [x] All terminal outcomes and four stories are covered.
