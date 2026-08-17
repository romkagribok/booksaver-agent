---
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: construction
created: 2026-08-14T02:46:26Z
updated: 2026-08-16T19:18:41Z
checkpoint_1_approved: 2026-08-16T19:18:41Z
checkpoint_2_approved: 2026-08-16T19:18:41Z
checkpoint_3_approved: 2026-08-16T19:18:41Z
checkpoint_4_approved: 2026-08-16T19:18:41Z
---

# Requirements: Replaceable Agentic Browser Executor

## Intent Overview

BookSaver becomes the trusted control plane over a replaceable, read-only browser executor. The
accepted first architecture is `local Stagehand semantic execution -> guarded Anthropic computer
use -> BookSaver validation/evaluation`. The executor may perceive and navigate live Booking.com,
but it never becomes authoritative for identity, authentication, equivalence, refundability,
pricing eligibility, savings, persistence, notification, or any transaction.

The first vertical slice replaces both navigation and rate-table perception for owner price checks.
Legacy price checks remain the default and rollback path until qualification succeeds. Account
inventory and other DOM-dependent workflows migrate only after price-check promotion.

## Functional Requirements

### FR-1: Provider-neutral price browser executor
- **Description**: Expose a `PriceBrowserExecutor` port whose request contains trusted property,
  dates, occupancy, currency, an opaque owner-bound session lease, deadline, action limit, and cost
  limit, and whose result contains only typed observations and closed terminal metadata.
- **Acceptance Criteria**:
  - Provider SDK types never cross the application port.
  - Results report terminal status, observed property/date/occupancy/authentication/Genius facts,
    typed offers, redacted provenance, refreshed-session eligibility, usage, cost, latency, and
    fallback usage.
  - Cookie values and decrypted session bytes cannot appear in requests visible to a model or in
    results, logs, traces, or persisted metrics.
- **Priority**: Must

### FR-2: BookSaver-owned validation and evaluation
- **Description**: Treat executor output as untrusted evidence and independently verify property,
  dates, occupancy, authenticated context, currency, all-in total, explicit refundability, room
  equivalence, and savings before an offer can affect state or notifications.
- **Acceptance Criteria**:
  - Every missing, conflicting, or ambiguous required fact fails closed.
  - An observed offer contains a visible room label, total, currency, refundability status/text,
    and evidence completeness, but never declares equivalence or savings.
  - The existing exact/qualified equivalence and savings policies remain BookSaver-owned.
- **Priority**: Must

### FR-3: Owner-bound transient session lease
- **Description**: Decrypt a verified owner session only into a fresh transient local browser,
  retain `/connect` behavior, and destroy the browser profile after each job.
- **Acceptance Criteria**:
  - Stagehand and Anthropic never receive cookie values or credentials.
  - Refreshed cookies are eligible for persistence only after code-owned authentication
    verification and owner/session binding checks.
  - Cleanup runs on success, failure, timeout, cancellation, and provider error.
- **Priority**: Must

### FR-4: Local Stagehand semantic execution
- **Description**: Run an exactly pinned Stagehand v4 release in process through a dedicated async
  runner under the existing global browser lease, using the installed Chromium binary.
- **Acceptance Criteria**:
  - Navigation uses `observe -> code guard -> deterministic action replay` rather than unreviewed
    direct actions.
  - Typed extraction performs rate perception and produces the provider-neutral observation schema.
  - Stagehand external telemetry and external log export are disabled or confined to loopback.
  - No managed browser service, persistent browser profile, selector cache, generated-script repair,
    or cross-run action cache is introduced.
- **Priority**: Must

### FR-5: Guarded Anthropic computer-use fallback
- **Description**: Permit one Sonnet 5 computer-use episode on the same browser after semantic
  failure, with screenshots and a closed guarded action vocabulary.
- **Acceptance Criteria**:
  - Only click, scroll, type, key, wait, and zoom requests are accepted, with at most six actions.
  - Coordinate clicks are hit-tested before execution; labels, links, paths, popups, and
    destinations are checked before and after every action.
  - URL navigation, shell, clipboard, upload/download, credentials, MFA, captcha solving,
    checkout, cancellation, reservation, payment, and purchase are rejected.
  - The episode terminates with typed `submit_price_observation` data or a closed terminal outcome.
  - Opus never controls the browser.
- **Priority**: Must

### FR-6: Exact action, time, and cost accounting
- **Description**: Share the existing per-check and deployment-day hard limits across semantic and
  computer-use work and expose reconciled usage without sensitive content.
- **Acceptance Criteria**:
  - A job cannot exceed 15 total actions, 180 seconds, USD 1.00, or six computer-use actions.
  - Deployment-wide model spend cannot exceed USD 10.00 per UTC day.
  - Reservation and reconciliation are exact for successful, failed, and partially billed calls.
  - Sonnet 5 is the initial semantic and computer-use profile; Haiku 4.5 is unavailable for
    production routing until it passes identical gates; Opus is diagnosis-only.
- **Priority**: Must

### FR-7: Incremental routing and rollback
- **Description**: Add `legacy`, `owner_canary`, and `agentic` routing modes while preserving the
  current deterministic price path.
- **Acceptance Criteria**:
  - `legacy` remains the default before qualification.
  - `owner_canary` can route only the deployment owner; invited users remain legacy.
  - `agentic` requires an explicit qualified state and invitee consent.
  - After promotion, the legacy price path is rollback-only for 30 days and is not maintained for
    selector drift; its later removal is an explicit release action.
- **Priority**: Must

### FR-8: Privacy-safe disclosure and observability
- **Description**: Persist only redacted execution metrics/failure codes and obtain a versioned
  disclosure acknowledgement before an invited user can receive agentic routing.
- **Acceptance Criteria**:
  - Screenshots, accessibility trees, page text, cookies, and model reasoning are not persisted by
    default.
  - `/connect` remains human-driven/server-verified and displays a versioned disclosure that the
    owner-configured Anthropic account may process visible Booking.com page content and escalation
    screenshots.
  - An egress test proves authenticated jobs contact only Booking.com, Anthropic, and loopback.
- **Priority**: Must

### FR-9: Qualification and automatic regression response
- **Description**: Qualify the agentic price path against adversarial fixtures and an owner-only
  live canary before invited-user promotion.
- **Acceptance Criteria**:
  - Fixtures vary classes, test IDs, nesting, overlays, iframe/shadow placement, and accessibility
    quality without changing BookSaver selectors.
  - At least 30 live checks span at least 14 days, with at least 10 successful observations manually
    compared to visible Booking.com offers.
  - Eligible unblocked checks achieve at least 95% valid observations, average cost at most USD 0.10,
    p95 cost at most USD 0.50, p95 duration at most 180 seconds, and ordinary computer-use
    escalation at most 20%.
  - Any prohibited action, non-allowlisted destination, session leak, false accepted offer, or
    cost-cap breach blocks or reverses promotion. During rollback, three consecutive eligible
    invalid observations are a repeated reliability regression and return routing to legacy.
- **Priority**: Must

### FR-10: Post-promotion capability migration
- **Description**: After agentic price checks pass promotion, migrate inventory perception and
  remaining DOM-dependent account checks through separate executor capabilities while retaining the
  `/connect` server-verification boundary.
- **Acceptance Criteria**:
  - Inventory migration cannot begin before price-check qualification is approved.
  - Completeness-gated reconciliation and all existing inventory safety rules remain BookSaver-owned.
  - Playwright remains available for `/connect` until a separately qualified replacement is accepted.
- **Priority**: Should

## Non-Functional Requirements

### NFR-1: Safety
- Zero prohibited browser actions, non-allowlisted destinations, false accepted offers, or
  transaction attempts are permitted in qualification or production.

### NFR-2: Privacy
- Authenticated page content may be sent only to the owner-configured Anthropic account after
  disclosure; session material stays local and ephemeral. Content-bearing evidence is never
  persisted by default.

### NFR-3: Reliability
- Ordinary DOM churn should be absorbed without BookSaver selector changes; qualification measures
  this claim. Unknown, blocked, challenged, signed-out, timed-out, or provider-failed states are
  typed and fail closed.

### NFR-4: Cost
- Promotion requires average model cost no greater than USD 0.10/check, approximating USD 9 per
  booking-month at three checks per day, while preserving the USD 1/check and USD 10/day hard caps.

### NFR-5: Performance
- Promotion requires p95 end-to-end execution within the existing 180-second deadline.

### NFR-6: Portability and self-hosting
- Each owner can reproduce the deployment on their own VPS and pay for invited users with one
  `BOOKSAVER_LLM_API_KEY`; no BookSaver-operated backend, Browserbase, Browser Use Cloud, local GPU,
  or additional provider secret is required.

### NFR-7: Replaceability
- Future OpenAI, Google, Browser Use, or local-model adapters must implement the same executor port
  and repeat qualification without changing BookSaver domain policy.

## Constraints

- Booking.com hotels only; registered and candidate offers remain explicitly refundable.
- BookSaver remains fail-closed and retains all authorization, scheduling, persistence, and
  notification boundaries.
- Final cancellation, reservation, payment, purchase, or booking submission remains human-only on
  the user's own device.
- Stagehand is pinned to the qualified release initially; local v4 has no relied-upon cross-run
  cache.
- Only `BOOKSAVER_LLM_API_KEY` is used for the first executor.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Anthropic processing of visible authenticated page data is acceptable after disclosure | Invitees may reject the privacy boundary | Keep them on legacy routing and make consent revocable |
| Stagehand semantic execution reduces selector maintenance | It may fail under severe visual or accessibility degradation | Require visual fixtures and bounded computer-use fallback |
| Existing Chromium can be shared by executable path, not profile | Packaging mismatch could break VPS startup | Adapter startup test and explicit executable discovery failure |
| The live canary can be run by the owner without automation of manual comparison | Promotion may take longer than 14 days | Keep legacy default and expose auditable qualification records |

## Approved Architecture Decisions

All four inception checkpoints were approved by the product owner in the implementation directive
dated 2026-08-16. Detailed decisions and rejected alternatives are recorded in
`architecture-decisions.md` and ADR-036 through ADR-038.
