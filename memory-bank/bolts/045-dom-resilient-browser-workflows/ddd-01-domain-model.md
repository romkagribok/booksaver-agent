---
unit: 002-dom-resilient-browser-workflows
bolt: 045-dom-resilient-browser-workflows
stage: model
status: complete
updated: 2026-08-14T02:07:00Z
---

# Static Model - Remote Authentication DOM Recovery

## Bounded Context

This corrective context decides whether a transient `/connect` browser has reached a fresh,
authenticated, read-only Booking.com inventory page after deterministic selector drift. It prevents
a fixed verification probe from becoming an unbounded navigation loop, admits adaptive
classification only for genuine ambiguity, and creates a code-owned proof before cookies may be
captured. It does not grant models credential, challenge, account-setting, reservation-mutation, or
transaction authority.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `RemoteAuthEpisode` | caller, expiry, current observation fingerprint, probe history, model attempts, result | One browser/context and one shared job budget; a stable page may receive at most one fixed probe and one bounded adaptive resolution sequence |
| `RemoteAuthPageObservation` | fresh observation identity, approved destination class, protected evidence, visible structural references | Must be captured after the latest navigation; raw credentials, form values, cookies, URLs with queries, and reservation content never enter durable diagnostics |
| `AuthenticatedInventoryProof` | observation identity, proof source, approved inventory destination, grounded structure categories | Created only by code after fresh destination, protected-state, grounding, and structural rules pass; model classification alone cannot create it |
| `RemoteAuthTerminalResult` | exact reason, provenance, operator action, optional maintenance flag | Every non-success ends as a typed known stop, provider/budget stop, infrastructure stop, or unresolved DOM diagnosis |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| `ProbeDisposition` | `not_attempted`, `verified`, `ambiguous`, `known_stop`, `unavailable` | One disposition per observation fingerprint; `ambiguous` must advance to the resolver rather than restart the probe |
| `InventoryStructureFact` | allowlisted category, fresh element reference, source observation identity | Positive-only and grounded in the current bounded observation; never proves reservation identity, completeness, or account ownership |
| `AuthProofSource` | `deterministic_selector`, `semantic_structure` | `semantic_structure` requires model interpretation plus independent code checks; neither source permits a protected state |
| `RemoteAuthProgressKey` | observation fingerprint, probe-attempted flag, resolver-attempted flag | Prevents unchanged page polling from repeating physical navigation or provider calls |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| `RemoteAuthEpisode` | page observations, probe dispositions, optional authenticated proof, terminal result | Cookie capture requires exactly one fresh authenticated proof; known protected states use zero model calls; ambiguity cannot loop without either resolver admission or an exact stop |

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `InventoryProbeCompleted` | Fixed read-only probe returns | Content-free disposition and evidence categories only |
| `RemoteAuthSemanticallyVerified` | Code accepts grounded model-assisted inventory structure | Step ID, provenance, structural categories, and observation identity |
| `RemoteAuthDomDriftDiagnosed` | Ambiguity remains after eligible adaptive resolution | Canonical terminal diagnosis suitable for post-cleanup incident recording |
| `RemoteAuthSessionCaptured` | Fresh authenticated proof exists and cookies are serialized | Caller/session revision metadata; never raw cookies in logs or incidents |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| `RemoteAuthProbePolicy` | decide whether the fixed read-only probe may run for the current fingerprint | Fresh page assessment and episode progress key |
| `RemoteAuthSemanticVerifier` | compare typed model facts with the fresh observation and code-owned destination/protected-state rules | Approved Booking.com route classifier and bounded observation reference index |
| `RemoteAuthPageResolver` | classify a stable ambiguous page through Sonnet and eligible Opus | Existing `PageStateResolver`, shared caller key, and shared remote-auth budget |
| `RemoteAuthOutcomeMapper` | convert proof, exact stop, or unresolved ambiguity into the public result | Canonical browser diagnosis and incident draft boundary |

## Repository Interfaces

No new repository is introduced. Model spend uses the existing transactional ledger; eligible DOM
diagnosis uses the existing encrypted incident repository after browser cleanup; successful cookies
use the existing per-user encrypted session vault.

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Fixed probe | One code-owned navigation to the approved Booking.com inventory route used to seek strong deterministic evidence |
| Probe starvation | A control-flow defect where repeating the fixed probe prevents adaptive resolution or terminal diagnosis |
| Grounded semantic structure | Positive model-interpreted inventory-page facts whose element references and freshness are checked against the current observation |
| Code-owned proof | The only receipt that authorizes cookie capture; produced after deterministic safety and grounding checks, never directly by a model |
| Stable ambiguity | The same protected-safe observation fingerprint seen enough times to admit one adaptive classification sequence |

## Invariants

1. Authentication, MFA, captcha, bot wall, prohibited/external destination, and observation failure
   remain exact deterministic outcomes with zero adaptive calls.
2. A fixed probe executes at most once for an unchanged stable page episode and never repeats solely
   because Booking.com redirects between approved inventory aliases.
3. Failed deterministic proof advances to bounded adaptive resolution; it cannot reset progress and
   `continue` indefinitely.
4. Sonnet may identify current semantic inventory structure. Eligible invalid/low-confidence output
   may reach Opus under the same caller, job budget, and attempt ordering.
5. A model-authenticated classification without grounded structural references remains only a
   candidate and cannot save cookies.
6. Code verifies the current approved destination, absence of protected evidence, observation
   freshness, reference grounding, and minimum independent inventory-structure categories before
   creating `AuthenticatedInventoryProof`.
7. Unresolved ambiguity becomes a canonical maintenance diagnosis and incident after browser
   cleanup; provider/budget/infrastructure stops retain their exact non-DOM reason.
