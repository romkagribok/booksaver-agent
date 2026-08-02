---
stage: domain-model
bolt: 038-shared-booking-browser-recovery
created: 2026-08-02T18:16:29Z
status: complete
---

# Domain Model: Shared Booking Browser Recovery

## Bounded Context

**Booking Browser Recovery** begins only after a named deterministic, automated, read-only
Booking.com step is unable to prove its postcondition. It owns the recovery episode: bounded
observation, provider-neutral decision context, semantic action identity, verified progress,
evidence escalation, safe termination, and redacted audit. It does not own reservation truth,
inventory completeness, price equivalence, authentication, or destructive action authority.

## Entities

### RecoveryEpisode

Represents one attempt to recover exactly one named journey step.

**Properties**:

- `journey`: customer search or account inventory.
- `step`: stable named step.
- `goal`: narrow read-only desired state.
- `policy`: immutable step-local limits.
- `started_at`: monotonic start.
- `calls_used`: actual provider calls in this episode.
- `no_progress_count`: consecutive unverified state-preserving actions.
- `semantic_execution_counts`: executions by semantic target since last material progress.
- `visual_reorientation_used`: whether the forced evidence turn occurred.
- `history`: ordered structured outcomes safe for provider rendering.
- `status`: active, verified, gave_up, no_progress, refused, provider_failed, budget_exceeded.

**Invariants**:

- It owns one step and cannot change goals mid-episode.
- Success requires the authoritative step verifier; model assertion is insufficient.
- The outer per-check/daily budgets may terminate it sooner than its local policy.
- It never executes a third semantically equivalent action without material progress.
- It terminates after the first post-reorientation no-progress action.

### RecoveryAudit

Ordered redacted evidence for one recovery episode.

**Properties**: journey, step, provider role/model metadata, prompt version, action outcomes,
screenshot tier, calls/actions, elapsed time, and terminal classification.

**Invariants**: Contains no cookies, keys, raw HTML, full prompt, hidden reasoning, fingerprint source
text, or unnecessary full reservation identity.

## Value Objects

### RecoveryStep

- `journey`
- `name`
- `goal`
- `verification_description`
- `recoverable_failure_categories`
- `non_recoverable_failure_categories`

The step determines the goal and verifier; the provider never supplies either.

### RecoveryPolicy

- `max_llm_calls = 4`
- `timeout_seconds = 60`
- `screenshot_after_no_progress = 2`
- `max_semantic_target_executions = 2`
- `max_post_reorientation_no_progress = 1`

All values are positive validated settings. Policy limits are inner caps and cannot expand
`AgentBudget` or daily caller allowance.

### SemanticTarget

- action type
- normalized accessible role
- normalized visible label
- sanitized Booking.com destination path when present
- stable occurrence/card context when needed to distinguish equivalent labels
- normalized action value when relevant

The volatile observation ref is retained for execution but excluded from semantic equality when
safe semantic metadata exists.

### PageState

- sanitized active URL identity
- normalized title
- bounded visible-text digest
- bounded semantic-element digest
- viewport/scroll marker
- safe top-level page count and newly opened destination classifications

Raw input used to create digests exists only in memory for the active episode.

### ProgressEvidence

- `url_changed`
- `title_changed`
- `content_changed`
- `elements_changed`
- `viewport_changed`
- `popup_opened`
- `popup_controllable`
- `goal_verified`

Material progress is a controllable state change relevant to the step or a passed verifier. An
uncontrollable popup is diagnostic evidence, not progress.

### ActionOutcome

- proposed action and semantic target
- execution classification: executed, failed, refused
- sanitized error category
- before/after progress evidence
- verifier result
- current semantic execution count
- current no-progress count

A normal Playwright return with failed verification and no material state change is `no_progress`.

### AgentTurnContext

- recovery step and goal
- current bounded observation, optionally with screenshot
- structured action outcomes
- remaining local and outer budgets
- explicit safe stop conditions

This is the provider-neutral `AgentBrain` input. Provider adapters render it into their SDK format.

### AgentStopReason

Stable categories:

- `goal_verified`
- `model_gave_up`
- `no_progress`
- `missing_browser_capability`
- `authentication_required`
- `captcha_or_bot_wall`
- `explicit_unavailable`
- `unsafe_action`
- `blocked_destination`
- `provider_error`
- `budget_exhausted`
- `unknown`

Model-selected reason codes are validated; the controller may assign a stronger deterministic code.

## Aggregates

### RecoveryEpisode Aggregate

Root: `RecoveryEpisode`.

Members: policy, step, semantic execution counters, outcomes, current observation evidence, and
audit builder.

**Aggregate invariants**:

1. Only the current fresh observation's refs may execute.
2. The adapter-level action guard is evaluated before execution.
3. Every action is followed by a fresh observation and authoritative verifier, including when the
   adapter raises after a possible state change.
4. All newly observed top-level destinations are checked against host/action boundaries.
5. No-progress state resets only after material controllable progress.
6. Two no-progress outcomes schedule exactly one forced screenshot turn.
7. One no-progress outcome after that turn ends the episode.
8. Provider failure, outer budget breach, unsafe action, auth wall, or captcha produces a terminal
   result and cleanup.

## Domain Services

### ProgressClassifier

Compares bounded before/after state and verifier output to produce `ProgressEvidence` and an outcome
classification. It never delegates success to the LLM.

### SemanticLoopGuard

Counts semantically equivalent action executions since material progress. It refuses a third
execution even when refs change or proposals alternate with another no-progress target.

### RecoveryController

Orchestrates verify → observe → decide → guard → act → observe → verify → classify. It supplies
structured history, enforces policy/outer budgets, forces visual evidence, records audit, and returns
a terminal result.

### RecoveryCapabilityResolver

Resolves a provider-neutral brain/interpreter for an explicit active user and operation role and
connects actual call accounting. It never selects another user's key.

## Domain Events

- `RecoveryStarted`: journey, step, safe trigger category.
- `RecoveryActionEvaluated`: semantic action, execution/progress flags, counters.
- `RecoveryEvidenceEscalated`: screenshot forced after no progress.
- `RecoveryVerified`: authoritative verifier passed.
- `RecoveryTerminated`: normalized stop reason, calls/actions, elapsed time.

## Repository Interfaces

No new business repository is required for Unit 1. Existing check traces persist the safe recovery
audit for price checks. Unit 2 may extend synchronization audit persistence for inventory episodes.

## Ubiquitous Language

- **Action execution**: Playwright attempted an allowed action without necessarily achieving the goal.
- **Verified progress**: A material controllable state change or passed authoritative postcondition.
- **No progress**: Action completed or failed while the verified controllable state remained equivalent.
- **Semantic target**: Stable meaning of the action target independent of volatile DOM ref.
- **Visual reorientation**: One forced current screenshot after two no-progress outcomes.
- **Recovery episode**: Bounded LLM-assisted work for one named step.
- **Missing browser capability**: The desired state may exist outside the controller's observable/actionable surface.
- **Provider-neutral**: Domain/application contracts do not encode Anthropic SDK structures.

## Story Coverage

- US-122: PageState, SemanticTarget, ProgressClassifier, SemanticLoopGuard, RecoveryPolicy.
- US-123: ActionOutcome, AgentTurnContext, visual reorientation, AgentStopReason.
- US-124: RecoveryStep, RecoveryController, RecoveryCapabilityResolver, guard invariants.
- US-125: RecoveryAudit and deterministic episode/event contracts for replay.
