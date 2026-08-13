---
intent: 022-adaptive-booking-browser-resilience
phase: inception
status: complete
created: 2026-08-13T01:51:45.000Z
updated: 2026-08-13T02:25:17.000Z
---

# Requirements: Adaptive Booking Browser Resilience

## Intent Overview

Make BookSaver resilient to Booking.com presentation and DOM drift across every automated browser
journey. A deterministic DOM-sensitive step that cannot prove its postcondition and cannot map the
current evidence to a known exact failure must enter bounded LLM recovery or interpretation. If
Sonnet 5 cannot make verified progress or produce a valid classification, BookSaver escalates to
Opus 5. A browser job must end with a specific, actionable reason instead of a generic navigation or
extraction failure; known deterministic reasons do not spend an LLM call merely to restate them.

The models remain untrusted. They may observe and classify authentication, MFA, captcha, bot-wall,
and unsupported-layout pages, but cannot interact with protected controls. Code remains authoritative
for allowed actions and destinations, authentication state transitions, reservation identity,
inventory completeness, offer equivalence, refundability, currency, reconciliation, and every
booking, cancellation, modification, checkout, purchase, and payment boundary.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Recover safely from Booking.com DOM drift | Every registered DOM-sensitive browser step has either an exact deterministic terminal mapping or a tested LLM recovery/interpretation fallback for ambiguity | Must |
| Eliminate unexplained browser failures | Every terminal browser outcome has a specific reason, evidence source, and caller/admin action; no DOM path falls through to a generic unknown result | Must |
| Replace an ineffective model automatically | Runtime quality signals escalate Sonnet 5 work to Opus 5 within fixed call, time, and dollar limits | Must |
| Surface code-maintenance incidents | Confirmed or repeated DOM drift notifies the owner with a deduplicated incident ID and locally retained diagnostics | Must |
| Preserve trustworthy monitoring | Model output never weakens read-only, identity, completeness, equivalence, privacy, or human-action boundaries | Must |

## Approved Product Direction

- Use Anthropic Sonnet 5 as the default browser-recovery and DOM-interpretation model.
- Escalate to Anthropic Opus 5 only after objective Sonnet quality failures or for the final bounded
  maintenance diagnosis. Fable models are not eligible for this capability.
- Cap estimated provider spend at USD 1 per browser job and USD 10 per deployment UTC day. A call
  whose conservative maximum estimate would exceed either remaining allowance does not start.
- Apply LLM fallback to ambiguous DOM-sensitive validation, navigation, readiness, scope traversal,
  pagination/detail work, page-state classification, reservation interpretation, offer extraction,
  and other registered read-only browser postconditions.
- Return predictable failures such as confirmed authentication/MFA required, captcha/bot wall,
  blocked destination, unavailable observation, provider failure, or exhausted budget immediately
  under their exact code without asking a model to restate them.
- Permit read-only LLM classification when login, MFA, captcha, bot-wall, session-validation, or
  supported-page evidence is ambiguous. Never permit the model to fill, click, submit, or navigate
  protected authentication or account-management controls.
- Attempt an Opus maintenance diagnosis before an ambiguous recoverable DOM failure becomes terminal
  whenever provider access and cost/time budgets remain. If that attempt is impossible, report the
  exact provider, budget, observation, or infrastructure reason instead of claiming a DOM diagnosis.
- Notify the owner immediately when the final diagnostic class is `code_maintenance_required`, or
  after the same safe DOM-failure fingerprint occurs twice within six hours.
- Keep Telegram alerts content-free. Retain one encrypted local diagnostic bundle containing the
  bounded screenshot and sanitized page structure for seven days, then purge it automatically.

## Scope

### In Scope

- A registry and coverage contract for every DOM-sensitive Booking.com browser step.
- Deterministic-first page-state classification with guarded Sonnet/Opus fallback only for ambiguity.
- Safe navigation recovery and typed interpretation for account inventory and customer-search
  price-check journeys.
- Runtime model-quality signals, automatic Sonnet-to-Opus escalation, and replay qualification.
- Deployment-wide dollar accounting and conservative pre-call spend admission.
- Specific terminal reason taxonomy, user guidance, session-state propagation, and local audit.
- DOM-drift fingerprinting, owner notification, encrypted evidence retention, expiry, and purge.
- Configuration, migrations, CLI/operator visibility, and deterministic regression coverage.

### Out of Scope

- Model-driven credential entry, login submission, MFA, captcha bypass, bot-wall bypass, account
  settings, reservation modification, cancellation, checkout, payment, purchase, or final booking
  submission.
- Model authority over inventory completeness or emptiness, absence, reservation identity,
  eligibility, offer equivalence, refundability, currency alignment, or reconciliation.
- Arbitrary model-generated URLs, CSS selectors, JavaScript, coordinate clicks, computer-use tools,
  new browser processes, or a second coordinator.
- Fable models, cross-provider failover, silent cross-user key use, unbounded calls, raw page/account
  content in Telegram or ordinary logs, or autonomous code modification/deployment.

## Functional Requirements

### FR-1: Register every DOM-sensitive browser postcondition

- **Description**: Every automated Booking.com browser step whose success or failure depends on
  page structure, visible copy, controls, or rendered content must use one shared recovery contract.
- **Acceptance Criteria**:
  - A typed registry identifies the journey, named step, deterministic postcondition, permitted
    read-only actions, protected states, interpretation schema, and terminal reason mapping.
  - The registry covers authenticated session validation, account-inventory entry/readiness/scopes/
    pagination/details/extraction, customer-search form/property/context/room-rate work, price/offer
    extraction, and any future DOM-sensitive step added to these journeys.
  - A deterministic structure test fails when a registered browser journey introduces a
    DOM-sensitive step without a recovery/interpretation strategy and terminal reason mapping.
  - Healthy deterministic steps continue without an LLM call.
- **Priority**: Must
- **Related Stories**: US-133

### FR-2: Classify the current page safely despite DOM drift

- **Description**: Authentication, MFA, captcha, bot-wall, reservation, search, property, and
  unsupported pages must be classified from fresh evidence even when selectors or visible copy
  change.
- **Acceptance Criteria**:
  - Deterministic classification uses fresh current-page evidence and treats protected-state
    evidence as stronger than weak signed-in markers.
  - Conclusive deterministic authentication, MFA, captcha, bot-wall, external, or prohibited state
    returns its exact existing reason and guidance with zero LLM calls.
  - An inconclusive deterministic classification invokes a bounded typed LLM classifier before a
    DOM-dependent success or generic failure is accepted.
  - The classifier may return only an allowlisted page-state class, confidence, bounded evidence
    references, and suggested operator action; code validates and applies the state transition.
  - Authentication, MFA, captcha, bot-wall, external, and prohibited states execute zero model-
    proposed browser actions after classification.
  - A classified authentication requirement marks the caller's saved session as requiring reauth
    and renders `/connect` guidance rather than retrying as layout drift.
  - An LLM `authenticated` classification may permit guarded read-only recovery but cannot by itself
    save, extend, or validate a session; only a code-verified authenticated workflow can do so.
- **Priority**: Must
- **Related Stories**: US-134

### FR-3: Recover or interpret every safe DOM-dependent step

- **Description**: A failed deterministic DOM postcondition must offer the model enough current
  visual and structural evidence to navigate safely or return strictly typed positive facts.
- **Acceptance Criteria**:
  - The recovery context includes journey, step, goal, verifier, fresh bounded observation,
    structured prior outcomes, protected stop states, remaining actions/calls/time/cost, and only
    the existing guarded action vocabulary.
  - Safe navigation remains limited to visible fresh element references and allowlisted Booking.com
    destinations; model output cannot introduce a selector, URL, script, or tool.
  - One model-opened popup may be adopted only after code verifies that its current destination is
    allowlisted, read-only, and relevant to the named step; external, protected, ambiguous, or
    additional popups terminate safely without transferring control.
  - DOM-derived reservation and offer candidates use typed schemas and pass independent identity,
    completeness, equivalence, refundability, currency, and price validation before acceptance.
  - A typed semantic step observation may satisfy a DOM-independent verifier only after code compares
    it with trusted booking input and fresh browser evidence; a missing legacy selector alone cannot
    override otherwise verified semantic progress.
  - Invalid, conflicting, incomplete, unsupported, or low-confidence output cannot create a false
    success, empty inventory, price opportunity, or absence transition.
  - All current `/bookings`, post-`/connect`, `/checknow`, scheduled-sync, and scheduled/manual price-
    check triggers use the same fallback-capable path through `CheckCoordinator`.
- **Priority**: Must
- **Related Stories**: US-135

### FR-4: Explain every terminal browser outcome

- **Description**: No browser job may end with an unexplained generic DOM failure.
- **Acceptance Criteria**:
  - Terminal outcomes distinguish at least recovered drift, authentication required, MFA required,
    captcha/bot wall, destination blocked, identity conflict, incomplete evidence, unsupported DOM,
    model no-progress, code maintenance required, provider unavailable, invalid provider response,
    time limit, job cost limit, daily cost limit, observation unavailable, and infrastructure error.
  - When a DOM-sensitive step remains genuinely ambiguous after Sonnet and budget/provider access
    permit, Opus receives one bounded diagnostic turn and returns a typed reason, confidence,
    evidence categories, and operator action without browser-action authority.
  - Known deterministic outcomes—including confirmed reauthentication, MFA, captcha/bot wall,
    destination block, observation failure, provider failure, and cost/time limit—terminate directly
    with zero diagnosis-only calls.
  - A provider, budget, observation, or infrastructure failure that prevents diagnosis is reported
    under its own exact code and never mislabeled as LLM-confirmed DOM drift.
  - User-facing Telegram text gives caller-safe retry, reconnect, or wait guidance; owner-facing
    diagnostics include the named step and incident ID without page content.
  - Existing generic `unknown`, `navigation_failed`, and `extraction_failed` values may remain only
    for truly unclassified legacy/non-DOM exceptions and are regression-tested as unreachable from
    registered DOM-sensitive paths.
- **Priority**: Must
- **Related Stories**: US-136

### FR-5: Escalate Sonnet 5 to Opus 5 on measured quality failure

- **Description**: BookSaver must swap to the stronger approved model when the default model is not
  making valid, verified progress.
- **Acceptance Criteria**:
  - Production routing permits only configured Sonnet 5 primary and Opus 5 escalation profiles for
    this capability; a Fable model is rejected by configuration validation.
  - Opus escalation occurs after repeated semantic no-progress, two invalid typed/schema responses,
    unsafe-action proposals, unresolved low-confidence classification, or exhausted Sonnet recovery
    without satisfying the deterministic verifier.
  - Provider authentication, deployment-wide rate-limit/outage, hard safety rejection, and exhausted
    dollar/time allowance terminate specifically rather than consuming an ineffective escalation.
  - Opus receives the bounded current observation and structured outcome history, not hidden model
    reasoning or unbounded prior prompts.
  - Traces record provider, model role, model identifier, escalation trigger, calls, tokens, latency,
    and result in attempt order without secrets or raw page content.
- **Priority**: Must
- **Related Stories**: US-130

### FR-6: Enforce job and deployment dollar ceilings

- **Description**: Stronger recovery may cost more than immediate failure but must remain inside the
  approved USD 1 per-job and USD 10 per-deployment-day ceilings.
- **Acceptance Criteria**:
  - Before every call, a conservative estimate based on the selected model, bounded input, and
    maximum output reservation must fit within both remaining ceilings.
  - One job is one `CheckCoordinator` browser admission: `/bookings` synchronization; `/checknow`
    synchronization plus its selected price check; or one scheduled slot's synchronization plus the
    checks admitted for that user. Policy reserves enough remaining allowance for one eligible Opus
    diagnostic turn before additional Sonnet calls are admitted.
  - Actual input/output usage and estimated USD cost are recorded exactly once after each call;
    interrupted or unreported usage is charged conservatively.
  - Deployment-day accounting is persisted by UTC day and survives daemon restart; it is separate
    from and additive to existing per-user call/check limits.
  - Caller-scoped personal keys remain caller-scoped; no user borrows another user's key or allowance.
  - A denied call returns `job_cost_limit` or `daily_cost_limit` with retry timing and does not invoke
    the provider.
- **Priority**: Must
- **Related Stories**: US-131

### FR-7: Qualify and monitor model recovery quality

- **Description**: Sonnet and Opus profiles must be evaluated against sanitized production-shaped
  DOM failures before deployment and after prompt/model changes.
- **Acceptance Criteria**:
  - Fixtures cover every registered step plus changed login controls, false signed-in markers,
    account scope drift, pagination/detail drift, customer-search controls, offer/price extraction,
    popup/no-progress behavior, and adversarial prohibited controls.
  - Offline tests remain deterministic with fake brains/browsers; opt-in live replay never opens
    Booking.com and exposes no reservation or session data.
  - Ten-run live qualification requires at least nine correct recoveries or accurate terminal
    diagnoses per solvable/unreachable fixture and zero prohibited action executions.
  - Reports compare completion/diagnosis accuracy, schema validity, safe give-up, escalation rate,
    actions, calls, latency, tokens, and estimated cost by model role.
  - A model or prompt profile that misses its gate cannot become the production primary or escalation
    profile without explicit owner override recorded locally.
- **Priority**: Must
- **Related Stories**: US-132

### FR-8: Detect and correlate likely DOM-drift incidents

- **Description**: DOM failures that require model assistance, whether recovered or not, must be
  grouped into privacy-safe incidents that tell the owner when deterministic code likely needs
  maintenance.
- **Acceptance Criteria**:
  - A fingerprint uses only journey, named step, terminal class, verifier category, sanitized
    structural signature, and model roles tried; it excludes URLs, queries, text, screenshots,
    reservation identifiers, and user identity.
  - Every model-assisted recovery or diagnosis records an occurrence. `code_maintenance_required`
    opens an incident immediately; otherwise the same fingerprint opens an incident after two
    occurrences within six hours, including when the LLM recovered both occurrences.
  - Incident occurrence counts survive restart, remain deduplicated, and do not reveal which invited
    user encountered the page.
  - Later deterministic success at the same step records resolution evidence and suppresses stale
    repeated alerts without deleting the audit; LLM-assisted success alone does not mark code drift
    resolved.
- **Priority**: Must
- **Related Stories**: US-137

### FR-9: Notify the owner with actionable, content-free evidence

- **Description**: The self-hosted owner must learn promptly when DOM drift needs code maintenance.
- **Acceptance Criteria**:
  - The owner receives a Telegram message containing incident ID, journey/step, safe reason,
    occurrence count, models attempted, budget/provider status, and a local diagnostic command.
  - The message contains no screenshot, raw/sanitized page text, URL/query, confirmation number,
    property/stay details, user ID, prompt, response, cookie, session, or API-key material.
  - Delivery failure is persisted and retried with bounded backoff; it never fails the caller's
    browser cleanup or launches another browser job.
  - Repeated occurrences update the incident but do not send more than one alert per fingerprint in
    six hours unless the severity or terminal class changes.
- **Priority**: Must
- **Related Stories**: US-138

### FR-10: Retain encrypted diagnostics for seven days

- **Description**: A code-maintenance incident must retain enough local evidence to reproduce the
  DOM change without moving account content through Telegram or logs.
- **Acceptance Criteria**:
  - One bounded bundle per incident contains the final screenshot, sanitized page structure,
    structured action outcomes, classifier/diagnostic result, model metadata, and safe budget data.
  - The bundle is encrypted with the existing deployment secret, stored under owner-controlled local
    persistence, and accessible only through an owner-scoped diagnostic command.
  - Sanitization removes credentials, cookies, tokens, hidden fields, query strings, free-form model
    reasoning, and known reservation/user identifiers before encryption.
  - Bundles expire after seven days and are purged at startup and on the existing maintenance cadence;
    explicit user purge also removes their source bundles without exposing linkage in the incident.
  - Missing, corrupt, expired, or undecryptable evidence produces an explicit safe diagnostic status.
  - Encryption/storage failure does not suppress the content-free incident or owner notification.
- **Priority**: Must
- **Related Stories**: US-139

## Non-Functional Requirements

### Reliability

- **Coverage**: 100% of registered DOM-sensitive steps have an exact deterministic terminal mapping
  and, where ambiguity can remain, a tested LLM fallback.
- **Explainability**: 0 registered DOM paths terminate with generic `unknown`, `navigation_failed`,
  or `extraction_failed` after a current observation was available.
- **Recovery bounds**: One step may use at most four Sonnet calls plus two Opus calls and 120 seconds;
  existing job action/call/time limits and the stricter dollar ceiling remain outer caps.
- **Cleanup**: Browser pages, contexts, locks, and coordinator admission are released after every
  success, diagnosis, cost stop, provider error, and unexpected exception.
- **No false success**: Protected, incomplete, conflicting, or low-confidence evidence never becomes
  authenticated, complete inventory, an equivalent offer, or a price opportunity.

### Security and Privacy

- **Action safety**: Zero credential, MFA, captcha, account-setting, booking, modification,
  cancellation, checkout, payment, purchase, or final-submit actions in all tests and replays.
- **Caller isolation**: 100% of sessions, keys, usage, traces, and reservation evidence remain scoped
  to the active caller; incident alerts are user-independent and owner-only.
- **Data minimization**: Telegram and ordinary logs contain only allowlisted machine fields.
- **Retention**: Encrypted diagnostic bundles are unavailable after seven days and after applicable
  user purge.

### Performance and Cost

- **Happy path**: Deterministic success adds zero LLM calls and no provider latency.
- **Hard cost admission**: No estimated call starts if it could exceed USD 1 per job or USD 10 per
  deployment UTC day.
- **Bounded evidence**: Page text, structure, screenshots, history, and output tokens have explicit
  size limits before each provider call or persisted bundle.

### Observability and Testability

- **Trace completeness**: Every recovery records named step, observation tier, model role,
  escalation trigger, action outcomes, terminal reason, calls, timing, usage, and estimated cost.
- **Reason provenance**: Each terminal reason records whether it came from deterministic policy,
  Sonnet classification, Opus diagnosis, provider admission, or infrastructure handling.
- **Determinism**: Unit/integration tests inject clocks, price tables, brains, observations,
  notifier outcomes, encryption, and browser outcomes.
- **Compatibility**: Existing configurations migrate to the approved Sonnet 5 primary and Opus 5
  escalation defaults with validated, documented settings.

## Constraints

### Technical Constraints

- Preserve the single-process, synchronous Playwright, hexagonal, stdlib-first architecture.
- Reuse `BrowserAgent`, `AgentBrain`, `InteractiveBrowser`, `CheckCoordinator`, caller-scoped key
  resolution, session vault, ActionGuard, Booking.com allowlists, and current audit boundaries.
- Keep model routing, page-state classification, recovery, diagnostics, notification, and persistence
  behind separate typed ports; do not add an agent framework.
- Preserve deterministic verification as the only authority that can accept success or mutate domain
  state.

### Business Constraints

- The approved production model portfolio is Sonnet 5 and Opus 5 only; Fable is excluded.
- Estimated spend is capped at USD 1 per browser job and USD 10 per deployment UTC day.
- Final reservation and rebooking actions remain entirely outside BookSaver automation.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Anthropic keeps Sonnet 5 and Opus 5 available to the configured API key | Recovery cannot use the approved portfolio | Validate profiles at startup/replay and terminate with an explicit provider/model reason |
| Fresh screenshots and sanitized page structure contain enough evidence for most presentation drift | Both models may diagnose but not recover | Open a maintenance incident with retained local evidence and preserve last safe domain state |
| Conservative token-cost admission can be maintained locally | Published pricing may change | Keep the price table versioned/configurable and expose it in diagnostics; fail closed if the selected model has no price entry |
| The owner Telegram identity and deployment secret remain configured | Alerts or encrypted bundles cannot be delivered/created | Persist an explicit operations failure and expose it through `/status` and CLI diagnostics |

## Open Questions

None. Requirements Checkpoint 1 was approved on 2026-08-13 with Sonnet 5 primary, Opus 5 bounded
escalation, no Fable, USD 1/job and USD 10/deployment-day ceilings, content-free owner alerts, and
seven-day encrypted local diagnostic retention.
