# ADR-030: Shared Progress-Aware Booking Browser Recovery

- **Status**: accepted
- **Date**: 2026-08-02
- **Bolt**: 038-shared-booking-browser-recovery (shared-booking-browser-recovery)

## Context

BookSaver's first browser-agent loop equated a non-throwing Playwright action with successful
execution and used exact transient refs for repetition control. A production Booking.com change
exposed a result without the expected href. The fallback clicked a target-blank property link, but
the controllable page did not change; alternating refs evaded the duplicate guard and the check used
the full six-minute outer budget. Authenticated account inventory has a second problem: its browser
journey is entirely scripted and returns generic navigation/layout failures without any LLM seam.

The LLM cannot adapt reliably when it receives misleading feedback, lacks structured progress
evidence, or has no bounded recovery entrypoint. A stronger model or another provider would still
be unable to control an unobservable popup and could still consume the outer budget.

## Decision

Adopt one provider-neutral, progress-aware recovery contract for every automated, read-only
Booking.com browser journey.

1. Separate action execution from verified progress. Every action is followed by a fresh bounded
   observation and authoritative step verifier.
2. Define semantic target identity from normalized role/label/destination/value rather than volatile
   element refs.
3. Count successful-but-unverified unchanged actions as no progress. After two consecutive
   no-progress outcomes, force one fresh screenshot turn; one further no-progress action ends the
   episode.
4. Bound each recovery episode to four actual LLM calls and 60 seconds, nested inside existing total
   per-check and daily caller limits.
5. Supply provider-neutral typed turn context containing structured outcomes, progress flags,
   popup/capability evidence, verification, and remaining policy. Provider adapters only render and
   parse SDK formats.
6. Observe and validate the controllable page and every top-level destination before verification,
   provider disclosure, and action, then validate again afterward. A safe but uncontrollable popup
   is diagnostic evidence and not progress; unsafe/external destinations fail closed. Provider
   observations sanitize current URLs and link destinations to remove identity-bearing components.
7. Reuse the same controller for customer-search and authenticated account-inventory named steps.
   Human login and credential/MFA pages remain outside LLM control.
8. Permit typed LLM inventory interpretation only as untrusted positive evidence. Deterministic
   traversal alone may prove completeness and authorize absence reconciliation.
9. Preserve structured redacted traces and sanitized replay fixtures; never persist hidden
   reasoning, full prompts, fingerprint inputs, cookies, keys, or unnecessary reservation identity.
10. Attach a bounded content-free recovery audit to assisted inventory synchronization runs. The
    additive schema-v13 fields retain provider profile, call/token/action counts, timing, and safe
    progress classifications under the existing caller-scoped purge lifecycle; they never store
    page evidence or provider content.

## Relationship to Existing Decisions

- **ADR-015 amended**: “failed action” for automatic screenshot escalation includes a normal action
  that produces no verified material progress, not only a thrown adapter exception.
- **ADR-016 amended**: the bounded action vocabulary and adapter guard remain; the provider boundary
  now receives typed turn context and coded give-up reasons. No arbitrary selectors/URLs/JS are added.
- **ADR-017 amended**: existing hard per-check caps remain outer limits; recovery episodes add
  tighter step-local caps.
- **ADR-021 preserved**: one coordinator continues to serialize scheduled, manual, inventory, and
  recovery browser work and own daily accounting.
- **ADRs 027–028 preserved**: Booking.com inventory remains authoritative and only deterministic
  complete traversal may make unseen reservations absent.

## Alternatives Considered

### Change only the prompt

Rejected. The current prompt lacks truthful page-progress and popup evidence. Prompting cannot fix
missing observations or enforce semantic/time bounds.

### Switch to a stronger model or add providers first

Rejected as the immediate fix. Model comparison is valuable, but every provider would inherit the
same incomplete tool/feedback contract. The new replay contract will support later comparison.

### Let the model emit arbitrary selectors, URLs, JavaScript, or coordinates

Rejected. It would weaken the inspectable ActionGuard and allow page prompt injection to expand the
browser blast radius.

### Automatically adopt every popup

Deferred. Popup adoption changes browser control/navigation behavior and requires separate safety
and verification design. This intent detects popups and makes the current limitation explicit.

### Let LLM inventory output establish completeness

Rejected. A model cannot prove that an account has no additional unseen scope/page/reservation.
Positive evidence may be retained, but absence remains completeness-gated.

## Consequences

### Positive

- Ineffective loops stop quickly with actionable reasons.
- Model decisions receive evidence that reflects actual browser state.
- Search and inventory share one guarded, testable recovery abstraction.
- Account discovery can adapt to supported layout drift without sacrificing authoritative truth.
- Future provider selection can be evaluated against stable fixtures and metrics.
- Assisted inventory runs are locally inspectable without overloading price-check traces.

### Negative

- AgentBrain, fakes, prompt tests, traces, config, and browser observations change together.
- The dedicated inventory audit requires an additive schema-v13 migration.
- Some difficult but potentially solvable pages will give up sooner than the old outer budget.
- Inventory interpretation expands bounded account-page evidence sent to the configured provider;
  operator documentation must remain explicit.
- Popup detection without adoption improves diagnosis but does not complete that specific journey.

## Validation

- Semantic changing-ref and alternating-target loop tests.
- Successful-but-unchanged action and forced-screenshot tests.
- Popup detection/all-page safety tests.
- Four-call/60-second and provider-error tests.
- Price-search regression tests.
- Inventory partial/completeness/identity/guard/accounting/Telegram tests.
- Sanitized offline replay plus opt-in live-model evaluation.
