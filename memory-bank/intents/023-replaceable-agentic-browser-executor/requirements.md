---
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: construction
created: 2026-08-14T02:46:26Z
updated: 2026-09-02T23:44:45Z
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
Legacy price checks remain the default and rollback path until qualification succeeds. Agentic
inventory is pulled forward because the legacy inventory prerequisite prevents the price canary
from running. It rolls out to every authorized, disclosed user with positive-only reconciliation;
legacy inventory remains a capability-specific rollback path.

The `/bookings` command proved the first reliability-focused Browser Use slice against live
Booking.com inventory. The next slice makes local Browser Use the default price executor for both
`/checknow` and scheduled checks through the existing price-executor port. Stagehand and the
deterministic path remain explicit rollback choices rather than same-job fallbacks. BookSaver still
owns every acceptance and savings decision.

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
  - Every executor browser uses the same configured, version-matched mobile-web identity family as
    `/connect` and the authenticated monitoring path; cookies are never replayed into an unrelated
    desktop identity.
- **Priority**: Must

### FR-4: Local Stagehand semantic execution
- **Description**: Run an exactly pinned Stagehand v4 release in process through a dedicated async
  runner under the existing global browser lease, using the installed Chromium binary.
- **Acceptance Criteria**:
  - Navigation uses `observe -> code guard -> deterministic action replay` rather than unreviewed
    direct actions.
  - Typed extraction performs rate perception and produces the provider-neutral observation schema.
  - Stagehand external telemetry and external log export are disabled or confined to loopback.
  - Container execution passes an explicit Chromium sandbox setting compatible with the existing
    non-root Playwright image and does not depend on a generic `CI` environment signal.
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

### FR-7: Capability-specific routing and rollback
- **Description**: Route price and inventory capabilities independently while preserving legacy
  price and inventory paths as explicit rollback modes.
- **Acceptance Criteria**:
  - Price routing keeps the existing `legacy`, `owner_canary`, and `agentic` qualification rules.
  - Inventory routing is `agentic` for every authorized user who has accepted the current
    disclosure; it does not wait for price qualification.
  - A capability can regress to `legacy` without changing the other capability's route.
  - An inconclusive agentic inventory run fails closed without a same-job selector fallback.
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
  - An egress test proves authenticated jobs contact only Booking.com application/static-delivery
    hosts (`booking.com` and `bstatic.com`), Booking-required HTTPS subdomains of
    `token.awswaf.com`, Anthropic, and loopback. The WAF token domain is never agent-navigable.
  - Destination rejection logs contain only a closed destination class, sanitized bounded path
    template, sorted query-key names, and code-owned phase/reason; raw URLs, query values,
    fragments, page content, reservation identity, and session material are prohibited.
- **Priority**: Must

### FR-9: Price qualification and automatic regression response
- **Description**: Qualify the agentic price path against adversarial fixtures and an owner-only
  live canary before invited-user price promotion.
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

### FR-10: Provider-neutral agentic inventory execution
- **Description**: Add a separate `InventoryBrowserExecutor` and use local Stagehand plus one
  guarded computer-use episode for every authorized user's account-inventory perception, without
  inserting Stagehand as another recovery tier inside the legacy selector parser.
- **Acceptance Criteria**:
  - The request contains an execution ID, authorized user/account binding, fixed required scopes,
    opaque session lease, absolute deadline, action limit, and cost limit; the result contains only
    typed positive observations, traversal evidence, terminal metadata, refreshed-session
    eligibility, redacted provenance, usage, cost, latency, fallback, and safety outcomes.
  - `/bookings`, post-connect synchronization, `/checknow`, and scheduled synchronization route
    through the inventory executor; `/connect` authentication verification remains unchanged.
  - BookSaver owns the traversal work queue, validates every stable reservation identity and fact,
    derives eligibility, and is the only component allowed to reconcile inventory.
  - Only reservations positively observed in the current run are inserted or refreshed. Agentic
    evidence never removes, archives, cancels, or marks an unseen reservation absent, even when the
    model claims that inventory is empty or complete.
  - An incomplete run may unblock a price check only for a reservation positively re-observed and
    validated in that same run; cached-only reservations cannot proceed.
  - Bare `/checknow` renders its picker from saved caller-owned state, then the selected request runs
    exactly one inventory verification before any price execution. Inventory and price share the
    containing job's cost ledger and absolute deadline.
  - Inventory-specific guards permit only read-only scope, pagination, and detail navigation;
    typing, login, credentials, MFA/captcha, modification, cancellation, reservation, payment, and
    purchase actions are prohibited.
  - Initial inventory redirects use layered `deny`, `observe_only`, and `interact` admission:
    unfamiliar non-mutating HTTPS Booking.com routes may be perceived without requiring an exact
    path/query allowlist, while interaction still requires inspected metadata and task-specific
    code-owned read-only proof.
  - Stagehand extraction and Anthropic computer-use schemas remain within the active providers'
    supported JSON Schema subsets while BookSaver enforces all collection and value bounds after
    decoding; schema incompatibilities fail closed with content-free diagnostics.
  - Browser navigation failures are classified from sanitized transport evidence. An
    authentication redirect loop cannot be mislabeled as an unsafe external destination, and no
    model call begins until a real Booking.com document is available.
  - Session usability is established by successfully reaching the requested protected capability
    in the matching browser identity, rather than by adding page selectors or treating a different
    account endpoint as sufficient proof.
  - The legacy inventory parser remains unchanged and available only as a capability-specific
    rollback path.
- **Priority**: Must

### FR-11: Deferred legacy price-selector retirement
- **Description**: Retire the legacy price path only after price promotion and its complete rollback
  window; inventory rollout does not advance that removal.
- **Acceptance Criteria**:
  - Legacy price selectors remain available throughout the price canary and 30-day rollback window.
  - Removal requires a separate release decision after 30 complete days without rollback.
  - Playwright remains available for `/connect` until a separately qualified replacement is accepted.
- **Priority**: Should

### FR-12: Browser Use execution for `/bookings`
- **Description**: Route only Telegram `/bookings` inventory refreshes through an exactly pinned,
  established Browser Use OSS agent running against a fresh local Chromium browser, without using
  Browser Use Cloud or changing the provider-neutral inventory port.
- **Acceptance Criteria**:
  - `SynchronizationTrigger.BOOKINGS` selects Browser Use, while post-connect, `/checknow`, and
    scheduled inventory continue to select Stagehand and every price route remains unchanged.
  - Browser Use enters inventory through a code-owned canonical HTTPS `mytrips` route. It never
    permits HTTP egress merely to follow Booking.com's legacy `myreservations` redirect, and a
    provider redirect cannot grant navigation authority.
  - A visibly inspected safe Booking.com link that declares `target=_blank` is replayed as guarded
    same-tab navigation. The adapter never permits the popup, and unsafe or missing destinations
    still fail closed.
  - Browser Use receives the existing owner/account-bound session lease and residual action, cost,
    and absolute-deadline limits; each physical model call is admitted and reconciled through the
    BookSaver cost ledger.
  - The agent is limited to one browser action per step and may use only guarded read-only click,
    scroll, safe-key, wait, typed observation submission, and typed terminal submission tools.
    Typing, arbitrary navigation, tabs, popups, files, shell, clipboard, credentials, authentication,
    cancellation, modification, reservation, checkout, purchase, and payment are prohibited.
  - Interaction authorization is deny-oriented and provider-neutral: every action is inspected,
    confined to an observable HTTPS Booking.com destination, and checked again afterward, without
    requiring exact inventory labels, CSS selectors, or read-only route names.
  - The adapter emits the existing typed positive inventory observations and terminal metadata;
    BookSaver remains solely responsible for validation, eligibility, positive-only reconciliation,
    session refresh proof, metrics, and last-safe-state preservation.
  - A saved reservation re-observation is not an inventory-discovery completion condition. The
    agent continues through the visible upcoming inventory and can submit a previously unknown
    reservation using a visibly explicit Booking.com confirmation number.
  - A successful positive-only observation is reported as a refreshed observation rather than a
    failed refresh. It remains distinct from authoritative inventory completeness, and unseen saved
    reservations are still preserved.
  - Unknown positives retain separately submitted visible property, stay, booking, policy, and
    occupancy facts when available. Malformed or absent optional facts degrade to an ineligible
    positive without discarding its validated confirmation identity.
  - A Browser Use failure is terminal for that `/bookings` operation and never cascades to Stagehand
    or the legacy selector parser within the same job.
  - Anonymous telemetry, cloud synchronization, version checks, conversation/history export, GIF,
    video, HAR, trace, and screenshot persistence are disabled before Browser Use is imported.
  - The exact container image proves dependency compatibility, transient-profile teardown, no
    persisted content artifacts, and authenticated egress limited to Booking.com page/application
    hosts, Booking.com's `bstatic.com` static-delivery hosts, Booking-required HTTPS subdomains of
    `token.awswaf.com`, Anthropic, and loopback. The WAF token domain cannot become an observable or
    interactive browser destination.
- **Priority**: Must

### FR-13: Browser Use as the default price executor
- **Description**: Implement local Browser Use behind the existing provider-neutral
  `PriceBrowserExecutor` and select it for both owner `/checknow` and scheduled price checks.
- **Acceptance Criteria**:
  - Manual and scheduled price checks use the same executor, validation, budgeting, and result
    pipeline; trigger type cannot select a different price implementation.
  - Owner-canary price routes use Browser Use immediately after deployment.
  - Invited-user price routing retains the current disclosure and qualification gates.
  - The price operation's required current-run inventory verification uses the already-qualified
    Browser Use inventory adapter, so a Stagehand prerequisite cannot prevent Browser Use price
    execution; `/connect` behavior remains unchanged.
- **Priority**: Must

### FR-14: Guarded Browser Use price operation
- **Description**: Run the pinned Browser Use OSS release locally in a fresh mobile Chromium using
  the owner-bound session lease and only a closed, code-guarded price-check tool vocabulary.
- **Acceptance Criteria**:
  - Browser Use stock actions are unavailable; one model step may request at most one guarded
    click, visual click, scroll, trusted-value type, safe key, wait, back, typed observation, or
    typed terminal action.
  - Typed values must be exact code-owned property, date, occupancy, or currency values from the
    trusted request; arbitrary model-authored values are rejected.
  - Arbitrary URL navigation, tabs/popups, credentials, authentication, MFA/captcha solving,
    files, shell, clipboard, cancellation, modification, reservation, checkout, purchase, and
    payment remain prohibited.
  - The existing 15-action, 180-second, USD 1/check, and USD 10/deployment-day hard limits remain
    binding and exactly reconciled.
  - The adapter contains no Booking.com CSS selector, test ID, or exact DOM-nesting dependency.
- **Priority**: Must

### FR-15: BookSaver-owned price evidence acceptance
- **Description**: Translate Browser Use output into the existing typed price observation and
  preserve BookSaver as the only authority for evidence acceptance and savings evaluation.
- **Acceptance Criteria**:
  - Browser Use returns only observed property/date/occupancy/authentication/Genius facts, visible
    room labels, all-in totals and currencies, refundability evidence, redacted provenance, usage,
    cost, latency, and closed terminal metadata.
  - Browser Use never declares room equivalence, cheapest-valid offer, savings, persistence, or
    notification eligibility.
  - Missing, ambiguous, or conflicting facts fail the existing independent BookSaver validator.
  - Refreshed cookies remain eligible for persistence only after code-owned authentication and
    owner/session binding verification.
- **Priority**: Must

### FR-16: Model-view preflight and redacted diagnostics
- **Description**: Verify the actual page state available to Browser Use before paid inference and
  expose content-free failure evidence suitable for local operations.
- **Acceptance Criteria**:
  - Before the first model call, code verifies the active mobile context, settled allowed HTTPS
    destination, browser attachment, and a usable visual or semantic page representation.
  - Blank screenshots, unusable empty state, authentication redirects, bot walls, transport
    failures, and browser attachment failures terminate before paid inference whenever detectable.
  - Redacted logs contain only execution ID, phase, closed reason, destination class, bounded
    render measurements, action/model counts, token usage, cost, and duration.
  - Screenshots, DOM/accessibility content, page text, cookies, credentials, reservation facts,
    model prompts, and model reasoning are never persisted by default.
- **Priority**: Must

### FR-17: Explicit Stagehand and deterministic rollback
- **Description**: Keep Browser Use, Stagehand, and the deterministic price path replaceable behind
  the same port while preventing hidden same-job cascades.
- **Acceptance Criteria**:
  - A price-executor selection setting defaults to `browser_use` and permits explicit `stagehand`
    selection without changing domain policy or stored bookings.
  - The existing deterministic route remains available for its approved rollback window.
  - A failed Browser Use job fails closed and does not invoke Stagehand or the deterministic path
    in the same operation.
  - Comparative Stagehand cost/reliability optimization and automatic future-job fallback are
    deferred until Browser Use has production evidence.
- **Priority**: Must

### FR-18: Browser Use-specific price qualification
- **Description**: Qualify Browser Use price execution under a distinct policy identity so prior
  Stagehand evidence cannot promote the new adapter.
- **Acceptance Criteria**:
  - The owner canary records at least 30 authentic checks across at least 14 days and at least 10
    manual comparisons with visible Booking.com offers.
  - Eligible unblocked checks achieve at least 95% accepted observations, average cost at most USD
    0.25, p95 cost at most USD 0.50, p95 duration at most 180 seconds, and no hard-limit breach.
  - Invited-user promotion additionally requires average cost at most USD 0.10/check.
  - Any prohibited action, unsafe destination, session leak, false accepted offer, transaction
    attempt, or cost-cap breach blocks promotion and invokes existing regression handling.
- **Priority**: Must

### FR-19: Production-equivalent price replay
- **Description**: Provide an operator-only replay that waits for the real deployed Browser Use
  price path without requiring repeated Telegram commands or mutating production booking truth.
- **Acceptance Criteria**:
  - Replay uses the deployed container, production executor wiring, owner-authorized encrypted
    session, and an isolated database/state copy under the existing coordinator/browser lease.
  - It exits zero only after BookSaver accepts a complete price observation and nonzero for every
    rejected, failed, limited, or timed-out terminal result.
  - It suppresses savings notifications and authoritative production booking mutations.
  - Automated routing tests prove `/checknow` and scheduled jobs select the same Browser Use price
    executor; the VPS replay proves the actual Browser Use loop terminates successfully.
- **Priority**: Must

### FR-20: Browser Use for price-operation inventory prerequisites
- **Description**: Expand the proven local Browser Use inventory adapter from `/bookings` to the
  inventory verification required by `/checknow`, scheduled checks, and post-connect sync so the
  default price flow does not retain a Stagehand availability dependency.
- **Acceptance Criteria**:
  - Every agentic inventory trigger resolves the same Browser Use adapter in production
    composition; `inventory_routing = "legacy"` remains the explicit capability rollback.
  - Current-run positive evidence, authorization, disclosure, session isolation, validation,
    reconciliation, safety, cost, and deadline rules remain unchanged.
  - The operation still performs exactly one inventory verification before price execution and
    shares one outer coordinator/browser admission and budget.
  - No same-job Stagehand or legacy fallback is added.
- **Priority**: Must

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
- Failed or partial inventory preserves last-safe rows, while only current-run positive observations
  may unblock monitoring.
- Qualification includes an authenticated replay whose caller-owned repository contains no saved
  reservation; the visible Booking.com booking must be inserted from current page evidence.

### NFR-4: Cost
- Initial Browser Use owner canary requires average model cost no greater than USD 0.25/check;
  invited-user promotion requires no greater than USD 0.10/check, approximating USD 9 per
  booking-month at three checks per day. The USD 0.50 p95, USD 1/check, and USD 10/day hard caps
  remain binding.
- Inventory and price phases in one operation share admission, reconciliation, and one absolute
  deadline; duplicate `/checknow` inventory execution is prohibited.

### NFR-5: Performance
- Promotion requires p95 end-to-end execution within the existing 180-second deadline.

### NFR-6: Portability and self-hosting
- Each owner can reproduce the deployment on their own VPS and pay for invited users with one
  `BOOKSAVER_LLM_API_KEY`; no BookSaver-operated backend, Browserbase, Browser Use Cloud, local GPU,
  or additional provider secret is required.

### NFR-7: Replaceability
- Future OpenAI, Google, Browser Use, or local-model adapters must implement the same executor port
  and repeat qualification without changing BookSaver domain policy.
- Stagehand remains selectable as an explicit rollback adapter; no automatic or same-job fallback
  policy is introduced in this slice.

## Constraints

- Booking.com hotels only; registered and candidate offers remain explicitly refundable.
- BookSaver remains fail-closed and retains all authorization, scheduling, persistence, and
  notification boundaries.
- Final cancellation, reservation, payment, purchase, or booking submission remains human-only on
  the user's own device.
- Browser Use and Stagehand are pinned to qualified releases; neither executor relies on a
  cross-run action cache.
- Only `BOOKSAVER_LLM_API_KEY` is used for the first executor.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Anthropic processing of visible authenticated page data is acceptable after disclosure | Invitees may reject the privacy boundary | Keep them on legacy routing and make consent revocable |
| Browser Use materially reduces selector maintenance | Harness, browser, provider, or bot-defense changes may still require maintenance | Require model-view preflight, redacted diagnostics, fixtures, and live replay; do not claim zero maintenance |
| Existing Chromium can be shared by executable path, not profile | Packaging mismatch could break VPS startup | Adapter startup test, explicit executable discovery failure, and exact-image Stagehand launch smoke |
| The live canary can be run by the owner without automation of manual comparison | Promotion may take longer than 14 days | Keep legacy default and expose auditable qualification records |
| Positive-only agentic inventory can safely unblock known reservations | A reservation may remain preserved after disappearing from Booking.com | Require same-run positive evidence for checks and defer absence authority |

## Approved Architecture Decisions

All four original inception checkpoints were approved by the product owner in the implementation
directive dated 2026-08-16. On 2026-08-25 the owner approved an inception amendment that advances
agentic inventory for every authorized user, preserves positive-only reconciliation, removes the
duplicate `/checknow` synchronization, and authorizes construction through final merge. Detailed
decisions and rejected alternatives are recorded in `architecture-decisions.md` and ADR-036 through
ADR-039. On 2026-09-02 the owner approved FR-13 through FR-19 and authorized the Browser Use price
extension through construction, review, merge, production deployment, and production-equivalent
verification. On 2026-09-03 the first exact-container replay proved that Stagehand inventory still
blocked the price adapter before construction; the owner's instruction to continue until the full
flow works accepted FR-20 and ADR-044's Browser Use inventory-trigger expansion.
